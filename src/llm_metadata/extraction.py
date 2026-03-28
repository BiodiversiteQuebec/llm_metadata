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
from llm_metadata.section_normalize import extract_from_section


DEFAULT_PROMPT_MODULES = {
    ExtractionMode.ABSTRACT: "prompts.abstract",
    ExtractionMode.PDF_TEXT: "prompts.abstract",
    ExtractionMode.PDF_NATIVE: "prompts.pdf_file",
    ExtractionMode.SECTIONS: "prompts.section",
}


def _usage_cost_total(record: RunRecord) -> str:
    if not record.usage_cost:
        return "n/a"
    total_cost = record.usage_cost.get("total_cost")
    return "n/a" if total_cost is None else f"${total_cost:.4f}"

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
    max_output_tokens: int = 4096
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
    for section in sections:
        is_relevant = is_relevant_section(section, config) or parent_relevant
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

    result = extract_from_text(
        record.abstract,
        system_message=system_message,
        temperature=config.temperature,
        model=config.model,
        max_output_tokens=config.max_output_tokens,
        text_format=config.text_format,
        reasoning=config.reasoning,
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

    result = extract_from_pdf_text(
        record.pdf_local_path,
        system_message=system_message,
        temperature=config.temperature,
        model=config.model,
        max_output_tokens=config.max_output_tokens,
        text_format=config.text_format,
        reasoning=config.reasoning,
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

    result = extract_from_pdf_file(
        record.pdf_local_path,
        system_message=system_message,
        temperature=config.temperature,
        model=config.model,
        max_output_tokens=config.max_output_tokens,
        text_format=config.text_format,
        reasoning=config.reasoning,
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
    result = extract_from_text(
        prompt_text,
        system_message=system_message,
        temperature=config.temperature,
        model=config.model,
        max_output_tokens=config.max_output_tokens,
        text_format=config.text_format,
        reasoning=config.reasoning,
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
    prompt_module: Optional[str] = None,
    config: Optional[ExtractionConfig] = None,
    output_path: Optional[str | Path] = None,
    manifest_path: Optional[str] = None,
    name: Optional[str] = None,
    skip_cache: bool = False,
) -> RunArtifact:
    """Run one explicit extraction mode across a manifest."""

    configure_extraction_logging()
    config = config or ExtractionConfig()
    mode = ExtractionMode(mode)
    if parallelism < 1:
        raise ValueError("parallelism must be at least 1.")
    prompt_module = prompt_module or DEFAULT_PROMPT_MODULES[mode]
    system_message = _load_system_message(prompt_module) if prompt_module else _default_system_message(mode)
    logger.info(
        "Starting manifest extraction mode={} records={} parallelism={} model={} prompt_module={} skip_cache={}",
        mode.value,
        len(manifest.records),
        parallelism,
        config.model,
        prompt_module,
        skip_cache,
    )
    artifact = RunArtifact(
        name=name or f"{mode.value}_run",
        mode=mode,
        manifest_path=manifest_path,
        prompt_module=prompt_module,
        system_message=system_message,
        model=config.model,
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
    logger.info(
        "Completed manifest extraction mode={} records={} total_cost=${:.4f}",
        mode.value,
        len(artifact.records),
        artifact.total_cost_usd,
    )
    return artifact


__all__ = [
    "ExtractionMode",
    "ExtractionConfig",
    "SectionSelectionConfig",
    "run_manifest_extraction",
    "collect_relevant_sections",
    "build_section_prompt",
]
