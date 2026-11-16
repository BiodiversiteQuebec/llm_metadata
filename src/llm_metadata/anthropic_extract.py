"""Anthropic (Claude) extraction helpers: text, PDF text and native PDF input.

Mirror of the ``gpt_extract`` helpers (``extract_from_text``,
``extract_from_pdf_text``, ``extract_from_pdf_file``) so ``extraction.py`` can
route a ``claude-*`` model to Claude without changing anything else in the
pipeline. The returned dicts have the same keys (``output``, ``usage_cost``, ...).

Design notes
------------
- The system prompt (instructions + schema text) is sent as one block with
  ``cache_control: ephemeral``. The API only caches a prefix of at least 512
  tokens on the 5.5 models; shorter prefixes are processed normally, no error.
- The default output path puts the JSON schema in the prompt and validates the
  reply with Pydantic. ``structured_output=True`` switches to the API's native
  ``output_config.format`` json_schema mode (may reject complex schemas with a
  400, which costs nothing).
- One repair retry: when the reply fails validation, the validation error is
  sent back once. ``validation_retries`` / ``validation_failed`` are recorded in
  ``usage_cost`` so a run can report its failure rate.
- Thinking is adaptive by default on the 5.5 models. Thinking tokens are billed
  as output tokens and are already inside ``usage.output_tokens``.
"""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Optional, Type, Union

from joblib import Memory
from pydantic import BaseModel, ValidationError

from llm_metadata.anthropic_io import get_anthropic_client
from llm_metadata.logging_utils import logger
from llm_metadata.prompts.abstract import SYSTEM_MESSAGE as ABSTRACT_SYSTEM_MESSAGE
from llm_metadata.prompts.pdf_file import SYSTEM_MESSAGE as PDF_SYSTEM_MESSAGE
from llm_metadata.schemas import DatasetAbstractMetadata


memory = Memory("./cache", verbose=0)

# USD per 1M tokens (base input / output). Cache writes cost 1.25x the input
# price, cache reads 0.1x (5-minute ephemeral cache).
MODEL_COST_PER_1M_TOKENS = {
    "claude-haiku-5-5": {"input": 0.10, "output": 0.50},
    "claude-sonnet-5-5": {"input": 2.00, "output": 10.00},
    "claude-opus-5-5": {"input": 4.00, "output": 20.00},
}
CACHE_WRITE_MULTIPLIER = 1.25
CACHE_READ_MULTIPLIER = 0.10

MODEL = "claude-haiku-5-5"
# Thinking tokens count as output tokens: leave room so high effort does not truncate.
MAX_OUTPUT_TOKENS = 16000
REASONING = {"effort": "low"}
PDF_USER_INSTRUCTION = (
    "Extract the biodiversity dataset features from this scientific paper PDF according to the schema."
)
SCHEMA_INSTRUCTION = "Return ONLY one JSON object matching this JSON schema. No prose, no code fence.\n"
MAX_ERROR_CHARS = 2000


class ClaudeValidationError(RuntimeError):
    """The reply still failed validation after the repair retry.

    Carries ``usage_cost`` (with ``validation_failed=True``) so callers can bill and report it.
    """

    def __init__(self, message: str, usage_cost: dict[str, Any]):
        super().__init__(message)
        self.usage_cost = usage_cost


def is_claude_model(model: str) -> bool:
    return model.startswith("claude-")


def _check_model(model: str) -> None:
    if model not in MODEL_COST_PER_1M_TOKENS:
        raise ValueError(f"Unknown Claude model {model!r}; add it to MODEL_COST_PER_1M_TOKENS.")


# --------------------------------------------------------------------------- cost


def _sum_usage(usages: list[dict[str, Any]]) -> dict[str, int]:
    keys = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens")
    return {key: sum((u.get(key) or 0) for u in usages) for key in keys}


def _usage_cost(
    usage: dict[str, Any],
    model: str,
    *,
    joblib_cache_hit: bool,
    validation_retries: int = 0,
    validation_failed: bool = False,
) -> dict[str, Any]:
    """Cost of one record.

    The API's ``input_tokens`` EXCLUDES cached tokens: total prompt size is
    ``input_tokens + cache_creation_input_tokens + cache_read_input_tokens``.
    """
    costs = MODEL_COST_PER_1M_TOKENS[model]
    fresh = usage.get("input_tokens", 0) or 0
    written = usage.get("cache_creation_input_tokens", 0) or 0
    read = usage.get("cache_read_input_tokens", 0) or 0
    output_tokens = usage.get("output_tokens", 0) or 0
    base = {
        "input_tokens": fresh + written + read,
        "uncached_input_tokens": fresh,
        "cache_write_tokens": written,
        "cache_read_tokens": read,
        "cached_tokens": read,
        # Thinking tokens are already counted inside output_tokens by the API.
        "reasoning_tokens": 0,
        "output_tokens": output_tokens,
        "joblib_cache_hit": joblib_cache_hit,
        "validation_retries": validation_retries,
        "validation_failed": validation_failed,
    }
    if joblib_cache_hit:
        return {**base, "input_cost": 0.0, "cache_write_cost": 0.0, "cache_cost": 0.0,
                "reasoning_cost": 0.0, "output_cost": 0.0, "total_cost": 0.0}
    per = 1_000_000
    input_cost = fresh * costs["input"] / per
    write_cost = written * costs["input"] * CACHE_WRITE_MULTIPLIER / per
    read_cost = read * costs["input"] * CACHE_READ_MULTIPLIER / per
    output_cost = output_tokens * costs["output"] / per
    return {
        **base,
        "input_cost": round(input_cost, 6),
        "cache_write_cost": round(write_cost, 6),
        "cache_cost": round(read_cost, 6),
        "reasoning_cost": 0.0,
        "output_cost": round(output_cost, 6),
        "total_cost": round(input_cost + write_cost + read_cost + output_cost, 6),
    }


# ------------------------------------------------------------------ request build


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _system_text(system_message: str, text_format: Type[BaseModel], structured_output: bool) -> str:
    if structured_output:
        return system_message
    return system_message + "\n\n" + SCHEMA_INSTRUCTION + json.dumps(text_format.model_json_schema())


def _output_config(effort: Optional[str], text_format: Type[BaseModel], structured_output: bool) -> dict[str, Any]:
    config: dict[str, Any] = {}
    if effort:
        config["effort"] = effort
    if structured_output:
        from anthropic import transform_schema

        config["format"] = {"type": "json_schema", "schema": transform_schema(text_format)}
    return config


def _user_content(kind: str, params: dict[str, Any]) -> Any:
    """User turn: plain text, or a PDF document block placed before a short instruction."""
    if kind == "pdf_native":
        data = base64.standard_b64encode(Path(params["pdf_path"]).read_bytes()).decode("ascii")
        return [
            {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": data}},
            {"type": "text", "text": PDF_USER_INSTRUCTION},
        ]
    return params["text"]


def _build_request(kind: str, params: dict[str, Any], text_format: Type[BaseModel]) -> dict[str, Any]:
    """Keyword arguments shared by ``messages.create`` and ``messages.count_tokens``."""
    structured = bool(params["structured_output"])
    request: dict[str, Any] = {
        "model": params["model"],
        "system": [
            {
                "type": "text",
                "text": _system_text(params["system_message"], text_format, structured),
                "cache_control": {"type": "ephemeral"},
            }
        ],
        "messages": [{"role": "user", "content": _user_content(kind, params)}],
    }
    output_config = _output_config(params.get("effort"), text_format, structured)
    if output_config:
        request["output_config"] = output_config
    return request


def _parameters(
    kind: str,
    *,
    model: str,
    system_message: str,
    text_format: Type[BaseModel],
    effort: Optional[str],
    max_output_tokens: int,
    structured_output: bool,
    text: Optional[str] = None,
    pdf_path: Optional[Union[str, Path]] = None,
) -> tuple[str, dict[str, Any]]:
    """Return (joblib cache key, params dict). The key hashes the PDF content, not just its path."""
    params: dict[str, Any] = {
        "kind": kind,
        "model": model,
        "system_message": system_message,
        "max_output_tokens": max_output_tokens,
        "text_format": json.dumps(text_format.model_json_schema(), sort_keys=True),
        "effort": effort,
        "structured_output": structured_output,
    }
    if text is not None:
        params["text"] = text
    if pdf_path is not None:
        params["pdf_path"] = str(pdf_path)
        params["pdf_sha256"] = _sha256_file(Path(pdf_path))
    return json.dumps(params, sort_keys=True), params


# ------------------------------------------------------------------ the API call


def _reply_text(response: Any) -> str:
    reply = "".join(b.text for b in response.content if b.type == "text").strip()
    if reply.startswith("```"):
        reply = reply.strip("`").removeprefix("json").strip()
    return reply


def _check_stop(response: Any) -> None:
    if response.stop_reason in ("max_tokens", "refusal"):
        raise RuntimeError(f"Claude stopped with stop_reason={response.stop_reason}")


def _make_cached_call(text_format: Type[BaseModel]):
    """Joblib-cached API call (with one validation repair retry) for one schema."""

    @memory.cache
    def _call(parameters_json_dump: str) -> dict[str, Any]:
        params = json.loads(parameters_json_dump)
        kind = params["kind"]
        model = params["model"]
        client = get_anthropic_client()
        request = _build_request(kind, params, text_format)
        logger.debug("Calling Anthropic Messages API model={} kind={} schema={}", model, kind, text_format.__name__)
        usages: list[dict[str, Any]] = []
        messages = list(request["messages"])
        retries = 0
        output: Optional[BaseModel] = None
        error_text = ""
        for attempt in range(2):
            response = client.messages.create(
                **{**request, "messages": messages}, max_tokens=params["max_output_tokens"]
            )
            usages.append(response.usage.model_dump())
            _check_stop(response)
            reply = _reply_text(response)
            try:
                output = text_format.model_validate_json(reply)
                break
            except (ValidationError, ValueError) as exc:
                error_text = str(exc)[:MAX_ERROR_CHARS]
                if attempt == 0:
                    retries = 1
                    messages = messages + [
                        {"role": "assistant", "content": reply or "{}"},
                        {
                            "role": "user",
                            "content": (
                                "Your reply failed schema validation:\n"
                                f"{error_text}\n\n"
                                "Return the corrected JSON object only. No prose, no code fence."
                            ),
                        },
                    ]
        usage = _sum_usage(usages)
        if output is None:
            failed_cost = _usage_cost(usage, model, joblib_cache_hit=False, validation_retries=retries, validation_failed=True)
            raise ClaudeValidationError(
                f"Claude reply failed validation after {retries} repair retry: {error_text}", failed_cost
            )
        return {
            "output_json": output.model_dump_json(),
            "usage": usage,
            "validation_retries": retries,
            "validation_failed": False,
        }

    return _call


def _cache_state(fn: Any, parameters: str, skip_cache: bool) -> str:
    check = getattr(fn, "check_call_in_cache", None)
    try:
        return "bypass" if skip_cache else ("hit" if check and check(parameters) else "miss")
    except Exception:
        return "unknown"


def _run(
    kind: str,
    *,
    model: str,
    system_message: str,
    text_format: Type[BaseModel],
    reasoning: Optional[Dict[str, Any]],
    max_output_tokens: int,
    structured_output: bool,
    skip_cache: bool,
    text: Optional[str] = None,
    pdf_path: Optional[Union[str, Path]] = None,
) -> dict[str, Any]:
    _check_model(model)
    effort = (reasoning or {}).get("effort")
    parameters, _ = _parameters(
        kind, model=model, system_message=system_message, text_format=text_format, effort=effort,
        max_output_tokens=max_output_tokens, structured_output=structured_output, text=text, pdf_path=pdf_path,
    )
    call = _make_cached_call(text_format)
    state = _cache_state(call, parameters, skip_cache)
    logger.info("Starting claude {} extraction model={} schema={} cache={}", kind, model, text_format.__name__, state)
    raw = call.func(parameters) if skip_cache else call(parameters)  # type: ignore[attr-defined]
    usage_cost = _usage_cost(
        raw["usage"], model, joblib_cache_hit=state == "hit",
        validation_retries=raw.get("validation_retries", 0), validation_failed=raw.get("validation_failed", False),
    )
    logger.info(
        "Completed claude {} extraction model={} cache={} cost=${:.6f} output_tokens={} cache_read={} cache_write={} retries={}",
        kind, model, state, usage_cost["total_cost"], usage_cost["output_tokens"],
        usage_cost["cache_read_tokens"], usage_cost["cache_write_tokens"], usage_cost["validation_retries"],
    )
    return {
        "prompt": system_message,
        "model": model,
        "response": raw,
        "output": text_format.model_validate_json(raw["output_json"]),
        "usage_cost": usage_cost,
        "temperature": None,
        "reasoning": reasoning,
    }


# ------------------------------------------------------------------ public helpers


def extract_from_text(
    text: str,
    *,
    system_message: str = ABSTRACT_SYSTEM_MESSAGE,
    temperature: Optional[float] = None,
    model: str = MODEL,
    max_output_tokens: int = MAX_OUTPUT_TOKENS,
    text_format: Type[BaseModel] = DatasetAbstractMetadata,
    reasoning: Optional[Dict[str, Any]] = REASONING,
    skip_cache: bool = False,
    structured_output: bool = False,
) -> dict[str, Any]:
    """Extract and structure text into a Pydantic model with Claude.

    ``temperature`` is ignored: recent Claude models reject non-default sampling
    values. ``reasoning["effort"]`` maps to Claude's ``output_config.effort``.
    """
    result = _run(
        "text", model=model, system_message=system_message, text_format=text_format, reasoning=reasoning,
        max_output_tokens=max_output_tokens, structured_output=structured_output, skip_cache=skip_cache, text=text,
    )
    result["text"] = text
    return result


def extract_pdf_text_pymupdf(pdf_path: Union[str, Path], max_pages: Optional[int] = None) -> str:
    """Extract the text of a local PDF with PyMuPDF (pages joined by newlines)."""
    import pymupdf

    with pymupdf.open(str(pdf_path)) as doc:
        pages = list(doc)[:max_pages] if max_pages is not None else list(doc)
        return "\n".join(page.get_text() for page in pages)


def extract_from_pdf_text(
    pdf_path: Union[str, Path],
    *,
    system_message: str = ABSTRACT_SYSTEM_MESSAGE,
    temperature: Optional[float] = None,
    model: str = MODEL,
    max_output_tokens: int = MAX_OUTPUT_TOKENS,
    text_format: Type[BaseModel] = DatasetAbstractMetadata,
    reasoning: Optional[Dict[str, Any]] = REASONING,
    max_pages: Optional[int] = None,
    skip_cache: bool = False,
    structured_output: bool = False,
) -> dict[str, Any]:
    """Extract PDF text with PyMuPDF, then call the Claude text path."""
    pdf_text = extract_pdf_text_pymupdf(pdf_path, max_pages=max_pages)
    result = extract_from_text(
        pdf_text, system_message=system_message, model=model, max_output_tokens=max_output_tokens,
        text_format=text_format, reasoning=reasoning, skip_cache=skip_cache, structured_output=structured_output,
    )
    result["pdf_path"] = str(pdf_path)
    result["extraction_method"] = "pdf_text"
    return result


def extract_from_pdf_file(
    pdf_path: Union[str, Path],
    *,
    system_message: str = PDF_SYSTEM_MESSAGE,
    temperature: Optional[float] = None,
    model: str = MODEL,
    max_output_tokens: int = MAX_OUTPUT_TOKENS,
    text_format: Type[BaseModel] = DatasetAbstractMetadata,
    reasoning: Optional[Dict[str, Any]] = REASONING,
    skip_cache: bool = False,
    structured_output: bool = False,
) -> dict[str, Any]:
    """Extract structured information from a local PDF sent as a native ``document`` block."""
    result = _run(
        "pdf_native", model=model, system_message=system_message, text_format=text_format, reasoning=reasoning,
        max_output_tokens=max_output_tokens, structured_output=structured_output, skip_cache=skip_cache,
        pdf_path=pdf_path,
    )
    result["pdf_path"] = str(pdf_path)
    result["extraction_method"] = "pdf_native"
    return result


# ------------------------------------------------------- token counting (free) / estimate


def count_input_tokens(
    *,
    kind: str,
    model: str,
    system_message: str,
    text_format: Type[BaseModel],
    reasoning: Optional[Dict[str, Any]] = REASONING,
    structured_output: bool = False,
    text: Optional[str] = None,
    pdf_path: Optional[Union[str, Path]] = None,
    client: Any = None,
) -> int:
    """Exact input token count (system + user, PDF included) with ``messages.count_tokens`` (free)."""
    _check_model(model)
    _, params = _parameters(
        kind, model=model, system_message=system_message, text_format=text_format,
        effort=(reasoning or {}).get("effort"), max_output_tokens=0, structured_output=structured_output,
        text=text, pdf_path=pdf_path,
    )
    request = _build_request(kind, params, text_format)
    client = client or get_anthropic_client()
    return int(client.messages.count_tokens(**request).input_tokens)


def count_system_prefix_tokens(
    *,
    model: str,
    system_message: str,
    text_format: Type[BaseModel],
    structured_output: bool = False,
    client: Any = None,
) -> int:
    """Token count of the cacheable system block (minimum cacheable prefix is 512 tokens on 5.5 models).

    Counted with a one-word user turn, which is subtracted by counting that turn alone.
    """
    client = client or get_anthropic_client()
    system = [{"type": "text", "text": _system_text(system_message, text_format, structured_output)}]
    user = [{"role": "user", "content": "x"}]
    with_system = client.messages.count_tokens(model=model, system=system, messages=user).input_tokens
    without = client.messages.count_tokens(model=model, messages=user).input_tokens
    return int(with_system - without)


def is_call_cached(
    *,
    kind: str,
    model: str,
    system_message: str,
    text_format: Type[BaseModel],
    reasoning: Optional[Dict[str, Any]] = REASONING,
    max_output_tokens: int = MAX_OUTPUT_TOKENS,
    structured_output: bool = False,
    text: Optional[str] = None,
    pdf_path: Optional[Union[str, Path]] = None,
) -> bool:
    """True when this exact call is already in the joblib cache (a rerun is free)."""
    parameters, _ = _parameters(
        kind, model=model, system_message=system_message, text_format=text_format,
        effort=(reasoning or {}).get("effort"), max_output_tokens=max_output_tokens,
        structured_output=structured_output, text=text, pdf_path=pdf_path,
    )
    return _cache_state(_make_cached_call(text_format), parameters, False) == "hit"
