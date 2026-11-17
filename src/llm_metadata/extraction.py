"""Unified extraction engine with explicit modes."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Type

from pydantic import BaseModel

from llm_metadata.gpt_extract import (
    ABSTRACT_SYSTEM_MESSAGE,
    PDF_SYSTEM_MESSAGE,
    SECTION_SYSTEM_MESSAGE,
    extract_from_pdf_file,
    extract_from_pdf_text,
    extract_from_text,
)
from llm_metadata import anthropic_extract
from llm_metadata.logging_utils import configure_extraction_logging, logger
from llm_metadata.pdf_parsing import ParsedDocument, Section, process_pdf
from llm_metadata.schemas import DatasetAbstractMetadata
from llm_metadata.schemas.chunk_metadata import SectionType
from llm_metadata.schemas.data_paper import (
    DataPaperManifest,
    DataPaperRecord,
    ExtractionMode,
    RunArtifact,
    RunRecord,
)
from llm_metadata.section_normalize import classify_in_reading_order, extract_from_section


DEFAULT_PROMPT_MODULES = {
    ExtractionMode.ABSTRACT: "prompts.abstract",
    ExtractionMode.PDF_TEXT: "prompts.abstract",
    ExtractionMode.PDF_NATIVE: "prompts.pdf_file",
    ExtractionMode.SECTIONS: "prompts.section",
}


def _extract_text(text: str, *, model: str, **kwargs: Any) -> dict[str, Any]:
    """Route text extraction to Claude for ``claude-*`` models, OpenAI otherwise."""
    if anthropic_extract.is_claude_model(model):
        return anthropic_extract.extract_from_text(text, model=model, **kwargs)
    kwargs.pop("structured_output", None)
    return extract_from_text(text, model=model, **kwargs)


def _provider_kwargs(config: "ExtractionConfig") -> dict[str, Any]:
    """Keyword arguments shared by every extraction helper, adapted to the provider."""
    claude = anthropic_extract.is_claude_model(config.model)
    max_tokens = config.max_output_tokens
    if max_tokens is None:
        max_tokens = anthropic_extract.MAX_OUTPUT_TOKENS if claude else 4096
    kwargs: dict[str, Any] = {
        "temperature": config.temperature,
        "model": config.model,
        "max_output_tokens": max_tokens,
        "text_format": config.text_format,
        "reasoning": config.reasoning,
    }
    if claude:
        kwargs["structured_output"] = config.structured_output
    return kwargs


def _usage_cost_total(record: RunRecord) -> str:
    if not record.usage_cost:
        return "n/a"
    total_cost = record.usage_cost.get("total_cost")
    return "n/a" if total_cost is None else f"${total_cost:.4f}"


def _reasoning_effort(reasoning: Optional[Dict[str, Any]]) -> Optional[str]:
    if not reasoning:
        return None
    effort = reasoning.get("effort")
    return str(effort).strip() if effort is not None and str(effort).strip() else None

@dataclass
class SectionSelectionConfig:
    section_types: list[SectionType] = field(
        default_factory=lambda: [SectionType.ABSTRACT, SectionType.METHODS]
    )
    keywords: list[str] = field(
        default_factory=lambda: [
            "data",
            "dataset",
            "survey",
            "site",
            "area",
            "species",
            "sampling",
            "collection",
            "study",
            "material",
            "method",
            "sample",
        ]
    )
    include_abstract: bool = True
    include_all: bool = False

    def to_pattern(self) -> re.Pattern[str]:
        if not self.keywords:
            return re.compile(r"(?!)")
        return re.compile("|".join(re.escape(keyword) for keyword in self.keywords), re.IGNORECASE)


@dataclass
class ExtractionConfig:
    model: str = "gpt-5-mini"
    reasoning: Optional[Dict[str, Any]] = field(default_factory=lambda: {"effort": "low"})
    # None = provider default: 4096 for OpenAI, 16000 for Claude (thinking tokens count as output).
    max_output_tokens: Optional[int] = None
    # Claude only: use the API's native json_schema output instead of schema-in-prompt + Pydantic.
    structured_output: bool = False
    temperature: Optional[float] = None
    text_format: Type[BaseModel] = DatasetAbstractMetadata
    max_pdf_pages: Optional[int] = None
    section_config: SectionSelectionConfig = field(default_factory=SectionSelectionConfig)
    grobid_url: str = "http://localhost:8070"


def _load_system_message(prompt_module: str) -> str:
    import importlib

    try:
        mod = importlib.import_module(f"llm_metadata.{prompt_module}")
    except ModuleNotFoundError:
        mod = importlib.import_module(prompt_module)
    return mod.SYSTEM_MESSAGE


def _default_system_message(mode: ExtractionMode) -> str:
    if mode == ExtractionMode.PDF_NATIVE:
        return PDF_SYSTEM_MESSAGE
    if mode == ExtractionMode.SECTIONS:
        return SECTION_SYSTEM_MESSAGE
    return ABSTRACT_SYSTEM_MESSAGE


def is_relevant_section(section: Section, config: SectionSelectionConfig) -> bool:
    if config.include_all:
        return True
    section_type = extract_from_section(section.title)
    if section_type in config.section_types:
        return True
    return bool(config.to_pattern().search(section.title))


def collect_relevant_sections(
    sections: list[Section],
    config: SectionSelectionConfig,
    parent_relevant: bool = False,
) -> list[Section]:
    relevant: list[Section] = []
    # Subsections returned flat (GROBID 0.7.3) take the type of the block they sit in.
    in_order = classify_in_reading_order([s.title for s in sections])
    for section, block_type in zip(sections, in_order):
        is_relevant = (
            is_relevant_section(section, config)
            or parent_relevant
            or (not config.include_all and block_type in config.section_types)
        )
        if is_relevant and section.text and section.text.strip():
            relevant.append(section)
        relevant.extend(collect_relevant_sections(section.subsections, config, is_relevant))
    return relevant


def build_section_prompt(
    document: ParsedDocument,
    sections: list[Section],
    *,
    include_abstract: bool = True,
) -> str:
    parts: list[str] = []
    if include_abstract and document.abstract:
        parts.extend(["## Abstract\n", document.abstract, "\n\n"])

    seen_titles: set[str] = set()
    for section in sections:
        if include_abstract and extract_from_section(section.title) == SectionType.ABSTRACT:
            continue
        if section.title in seen_titles:
            continue
        seen_titles.add(section.title)
        parts.extend([f"## {section.title}\n", section.text, "\n\n"])
    return "".join(parts)


def _record_result_base(record: DataPaperRecord, mode: ExtractionMode) -> dict[str, Any]:
    return {
        "gt_record_id": record.gt_record_id,
        "record_id": record.canonical_id(),
        "mode": mode,
        "title": record.title,
        "abstract": record.abstract,
        "pdf_path": record.pdf_local_path,
    }


def _run_record_safe(
    record: DataPaperRecord,
    *,
    mode: ExtractionMode,
    runner: Callable[..., RunRecord],
    config: ExtractionConfig,
    system_message: str,
    skip_cache: bool,
) -> RunRecord:
    try:
        return runner(record, config=config, system_message=system_message, skip_cache=skip_cache)
    except Exception as exc:
        usage_cost = getattr(exc, "usage_cost", None)  # set by ClaudeValidationError
        logger.exception(
            "Extraction failed gt_record_id={} mode={} title={}",
            record.gt_record_id,
            mode.value,
            record.title or "<untitled>",
        )
        return RunRecord(
            **_record_result_base(record, mode),
            status="error",
            error_message=str(exc),
            usage_cost=usage_cost,
        )


def _run_abstract_mode(
    record: DataPaperRecord,
    *,
    config: ExtractionConfig,
    system_message: str,
    skip_cache: bool,
) -> RunRecord:
    if not record.abstract:
        return RunRecord(**_record_result_base(record, ExtractionMode.ABSTRACT), status="skipped", error_message="Missing abstract.")

    result = _extract_text(
        record.abstract,
        system_message=system_message,
        **_provider_kwargs(config),
        skip_cache=skip_cache,
    )
    return RunRecord(
        **_record_result_base(record, ExtractionMode.ABSTRACT),
        status="success",
        input_text=record.abstract,
        extraction_method="abstract_text",
        usage_cost=result.get("usage_cost"),
        output=result["output"].model_dump(mode="python"),
    )


def _run_pdf_text_mode(
    record: DataPaperRecord,
    *,
    config: ExtractionConfig,
    system_message: str,
    skip_cache: bool,
) -> RunRecord:
    if not record.pdf_local_path:
        return RunRecord(**_record_result_base(record, ExtractionMode.PDF_TEXT), status="skipped", error_message="Missing pdf_local_path.")

    pdf_text_fn = (
        anthropic_extract.extract_from_pdf_text
        if anthropic_extract.is_claude_model(config.model)
        else extract_from_pdf_text
    )
    result = pdf_text_fn(
        record.pdf_local_path,
        system_message=system_message,
        **_provider_kwargs(config),
        max_pages=config.max_pdf_pages,
        skip_cache=skip_cache,
    )
    return RunRecord(
        **_record_result_base(record, ExtractionMode.PDF_TEXT),
        status="success",
        input_text=result.get("text"),
        extraction_method=result.get("extraction_method"),
        usage_cost=result.get("usage_cost"),
        output=result["output"].model_dump(mode="python"),
    )


def _run_pdf_native_mode(
    record: DataPaperRecord,
    *,
    config: ExtractionConfig,
    system_message: str,
    skip_cache: bool,
) -> RunRecord:
    if not record.pdf_local_path:
        return RunRecord(**_record_result_base(record, ExtractionMode.PDF_NATIVE), status="skipped", error_message="Missing pdf_local_path.")

    pdf_file_fn = (
        anthropic_extract.extract_from_pdf_file
        if anthropic_extract.is_claude_model(config.model)
        else extract_from_pdf_file
    )
    result = pdf_file_fn(
        record.pdf_local_path,
        system_message=system_message,
        **_provider_kwargs(config),
        skip_cache=skip_cache,
    )
    return RunRecord(
        **_record_result_base(record, ExtractionMode.PDF_NATIVE),
        status="success",
        extraction_method=result.get("extraction_method"),
        usage_cost=result.get("usage_cost"),
        output=result["output"].model_dump(mode="python"),
    )


def _run_sections_mode(
    record: DataPaperRecord,
    *,
    config: ExtractionConfig,
    system_message: str,
    skip_cache: bool,
) -> RunRecord:
    if not record.pdf_local_path:
        return RunRecord(**_record_result_base(record, ExtractionMode.SECTIONS), status="skipped", error_message="Missing pdf_local_path.")

    _, document = process_pdf(
        pdf_path=Path(record.pdf_local_path),
        work_id=record.doi_filename_stem() or str(record.gt_record_id),
        grobid_url=config.grobid_url,
    )
    sections = collect_relevant_sections(document.sections, config.section_config)
    logger.debug(
        "Collected sections gt_record_id={} relevant_sections={} include_abstract={}",
        record.gt_record_id,
        len(sections),
        config.section_config.include_abstract,
    )
    if config.section_config.include_abstract and document.abstract:
        has_abstract = any(extract_from_section(section.title) == SectionType.ABSTRACT for section in sections)
        if not has_abstract:
            sections.insert(
                0,
                Section(section_id="abstract_0", title="Abstract", level=1, text=document.abstract, subsections=[]),
            )
    prompt_text = build_section_prompt(
        document,
        sections,
        include_abstract=config.section_config.include_abstract,
    )
    result = _extract_text(
        prompt_text,
        system_message=system_message,
        **_provider_kwargs(config),
        skip_cache=skip_cache,
    )
    return RunRecord(
        **_record_result_base(record, ExtractionMode.SECTIONS),
        status="success",
        input_text=prompt_text,
        extraction_method="sections",
        usage_cost=result.get("usage_cost"),
        output=result["output"].model_dump(mode="python"),
    )


def run_manifest_extraction(
    manifest: DataPaperManifest,
    *,
    mode: ExtractionMode | str,
    parallelism: int = 1,
    prompt: Optional[str] = None,
    config: Optional[ExtractionConfig] = None,
    output_path: Optional[str | Path] = None,
    manifest_path: Optional[str] = None,
    name: Optional[str] = None,
    description: Optional[str] = None,
    skip_cache: bool = False,
) -> RunArtifact:
    """Run one explicit extraction mode across a manifest."""

    configure_extraction_logging()
    config = config or ExtractionConfig()
    mode = ExtractionMode(mode)
    if parallelism < 1:
        raise ValueError("parallelism must be at least 1.")
    if prompt:
        system_message = prompt
        prompt_module_label = "custom"
    else:
        prompt_module_label = DEFAULT_PROMPT_MODULES[mode]
        system_message = _load_system_message(prompt_module_label)
    logger.info(
        "Starting manifest extraction mode={} records={} parallelism={} model={} reasoning_effort={} prompt_module={} description={} skip_cache={}",
        mode.value,
        len(manifest.records),
        parallelism,
        config.model,
        _reasoning_effort(config.reasoning) or "default",
        prompt_module_label,
        description or "",
        skip_cache,
    )
    artifact = RunArtifact(
        name=name or f"{mode.value}_run",
        description=description,
        mode=mode,
        manifest_path=manifest_path,
        prompt_module=prompt_module_label,
        system_message=system_message,
        model=config.model,
        reasoning=config.reasoning,
        reasoning_effort=_reasoning_effort(config.reasoning),
        schema=config.text_format.model_json_schema(),
        records=[],
    )

    runners = {
        ExtractionMode.ABSTRACT: _run_abstract_mode,
        ExtractionMode.PDF_TEXT: _run_pdf_text_mode,
        ExtractionMode.PDF_NATIVE: _run_pdf_native_mode,
        ExtractionMode.SECTIONS: _run_sections_mode,
    }
    runner = runners[mode]

    if parallelism == 1 or len(manifest.records) < 2:
        artifact.records = []
        total_records = len(manifest.records)
        for index, record in enumerate(manifest.records, start=1):
            logger.info(
                "[{}/{}] Extracting gt_record_id={} record_id={} title={}",
                index,
                total_records,
                record.gt_record_id,
                record.canonical_id(),
                record.title or "<untitled>",
            )
            run_record = _run_record_safe(
                record,
                mode=mode,
                runner=runner,
                config=config,
                system_message=system_message,
                skip_cache=skip_cache,
            )
            artifact.records.append(run_record)
            logger.info(
                "[{}/{}] Finished gt_record_id={} status={} method={} cost={}",
                index,
                total_records,
                record.gt_record_id,
                run_record.status,
                run_record.extraction_method or "n/a",
                _usage_cost_total(run_record),
            )
    else:
        ordered_results: list[Optional[RunRecord]] = [None] * len(manifest.records)
        with ThreadPoolExecutor(max_workers=parallelism) as executor:
            future_to_index = {}
            for index, record in enumerate(manifest.records):
                logger.info(
                    "[{}/{}] Queueing gt_record_id={} record_id={} title={}",
                    index + 1,
                    len(manifest.records),
                    record.gt_record_id,
                    record.canonical_id(),
                    record.title or "<untitled>",
                )
                future = executor.submit(
                    _run_record_safe,
                    record,
                    mode=mode,
                    runner=runner,
                    config=config,
                    system_message=system_message,
                    skip_cache=skip_cache,
                )
                future_to_index[future] = index
            for future in as_completed(future_to_index):
                index = future_to_index[future]
                record = manifest.records[index]
                run_record = future.result()
                ordered_results[index] = run_record
                logger.info(
                    "[{}/{}] Finished gt_record_id={} status={} method={} cost={}",
                    index + 1,
                    len(manifest.records),
                    record.gt_record_id,
                    run_record.status,
                    run_record.extraction_method or "n/a",
                    _usage_cost_total(run_record),
                )
        artifact.records = [record for record in ordered_results if record is not None]

    if output_path is not None:
        artifact.save_json(output_path)
        artifact.save_extraction_csv(Path(output_path).with_suffix(".csv"))
        logger.info("Saved extraction artifact to {}", output_path)
    stats = validation_stats(artifact.records)
    if stats["records_with_usage"]:
        logger.info(
            "Validation: failed={}/{} ({:.1%}) repaired_by_retry={} retries_used={}",
            stats["failed"],
            stats["records_with_usage"],
            stats["failure_rate"],
            stats["repaired"],
            stats["retries"],
        )
    logger.info(
        "Completed manifest extraction mode={} records={} total_cost=${:.4f}",
        mode.value,
        len(artifact.records),
        artifact.total_cost_usd,
    )
    return artifact


def validation_stats(records: list[RunRecord]) -> dict[str, Any]:
    """Run-level validation failure rate from per-record ``validation_*`` fields (Claude runs)."""
    usage = [r.usage_cost for r in records if r.usage_cost and "validation_failed" in r.usage_cost]
    failed = sum(1 for u in usage if u["validation_failed"])
    retries = sum(int(u.get("validation_retries") or 0) for u in usage)
    return {
        "records_with_usage": len(usage),
        "failed": failed,
        "retries": retries,
        "repaired": retries - failed,
        "failure_rate": (failed / len(usage)) if usage else 0.0,
    }


def estimate_run_cost(
    manifest: DataPaperManifest,
    *,
    mode: ExtractionMode | str,
    config: ExtractionConfig,
    prompt: Optional[str] = None,
    assumed_output_tokens: int = 1500,
    skip_cache: bool = False,
    client: Any = None,
) -> dict[str, Any]:
    """Estimate the cost of a Claude run before spending anything.

    Counts the real input tokens of each record (system + user, PDF included) with
    the free ``count_tokens`` endpoint, skips records already in the joblib cache,
    and assumes ``assumed_output_tokens`` output tokens per record. Inputs are priced
    as uncached (an upper bound: prompt caching only lowers the bill).
    """
    mode = ExtractionMode(mode)
    if not anthropic_extract.is_claude_model(config.model):
        raise ValueError(f"Cost estimation needs a claude-* model, got {config.model!r}.")
    if mode == ExtractionMode.SECTIONS:
        raise ValueError("Cost estimation is not supported for sections mode (it needs GROBID output).")
    system_message = prompt or _load_system_message(DEFAULT_PROMPT_MODULES[mode])
    prices = anthropic_extract.MODEL_COST_PER_1M_TOKENS[config.model]
    max_pages = config.max_pdf_pages if mode == ExtractionMode.PDF_TEXT else None
    common = dict(
        model=config.model,
        system_message=system_message,
        text_format=config.text_format,
        reasoning=config.reasoning,
        structured_output=config.structured_output,
    )
    max_tokens = config.max_output_tokens or anthropic_extract.MAX_OUTPUT_TOKENS
    counted = cached = skipped = input_tokens = 0
    for record in manifest.records:
        kind: str
        inputs: dict[str, Any]
        if mode == ExtractionMode.ABSTRACT:
            kind, inputs = "text", {"text": record.abstract}
            usable = bool(record.abstract)
        elif mode == ExtractionMode.PDF_TEXT:
            usable = bool(record.pdf_local_path)
            kind = "text"
            inputs = {"text": anthropic_extract.extract_pdf_text_pymupdf(record.pdf_local_path, max_pages) if usable else None}
        else:
            kind, inputs = "pdf_native", {"pdf_path": record.pdf_local_path}
            usable = bool(record.pdf_local_path)
        if not usable:
            skipped += 1
            continue
        if not skip_cache and anthropic_extract.is_call_cached(
            kind=kind, max_output_tokens=max_tokens, **common, **inputs
        ):
            cached += 1
            continue
        input_tokens += anthropic_extract.count_input_tokens(kind=kind, client=client, **common, **inputs)
        counted += 1
    output_tokens = counted * assumed_output_tokens
    cost = (input_tokens * prices["input"] + output_tokens * prices["output"]) / 1_000_000
    return {
        "records": len(manifest.records),
        "to_call": counted,
        "already_cached": cached,
        "skipped_no_input": skipped,
        "input_tokens": input_tokens,
        "assumed_output_tokens": output_tokens,
        "estimated_cost_usd": round(cost, 6),
    }


__all__ = [
    "ExtractionMode",
    "ExtractionConfig",
    "SectionSelectionConfig",
    "run_manifest_extraction",
    "estimate_run_cost",
    "validation_stats",
    "collect_relevant_sections",
    "build_section_prompt",
]
