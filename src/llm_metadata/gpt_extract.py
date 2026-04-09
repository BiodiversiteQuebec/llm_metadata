"""OpenAI extraction helpers for text and PDF inputs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional, Type, Union

import pypdf
from joblib import Memory
from openai.types.responses.parsed_response import ParsedResponse
from pydantic import BaseModel

from llm_metadata.logging_utils import logger
from llm_metadata.openai_io import get_openai_client
from llm_metadata.prompts.abstract import SYSTEM_MESSAGE as ABSTRACT_SYSTEM_MESSAGE
from llm_metadata.prompts.pdf_file import SYSTEM_MESSAGE as PDF_SYSTEM_MESSAGE
from llm_metadata.prompts.section import SYSTEM_MESSAGE as SECTION_SYSTEM_MESSAGE
from llm_metadata.schemas import DatasetAbstractMetadata


memory = Memory("./cache", verbose=0)

MODEL_COST_PER_1M_TOKENS = {
    "gpt-5-nano": {"input": 0.05, "output": 0.40, "cache": 0.005},
    "gpt-5-mini": {"input": 0.25, "output": 2.00, "cache": 0.025},
    "gpt-5": {"input": 1.25, "output": 10.00, "cache": 0.125},
    "gpt-5.1": {"input": 1.25, "output": 10.00, "cache": 0.125},
    "gpt-5.2": {"input": 1.75, "output": 14.00, "cache": 0.175},
    "gpt-5.4": {"input": 2.50, "output": 15.00, "cache": 0.25},
    "gpt-5.4-mini": {"input": 0.75, "output": 4.50, "cache": 0.075},
    "gpt-5.4-nano": {"input": 0.20, "output": 1.25, "cache": 0.02},
    "gpt-4.1": {"input": 2.00, "output": 8.00, "cache": 0.50},
    "gpt-4o": {"input": 2.50, "output": 10.00, "cache": 1.25},
}

MODEL = "gpt-5-mini"
MAX_OUTPUT_TOKENS = 4096
TEMPERATURE = None
REASONING = {"effort": "low"}


def _cache_state(cached_callable: Any, *args: Any, **kwargs: Any) -> str:
    check_call_in_cache = getattr(cached_callable, "check_call_in_cache", None)
    if check_call_in_cache is None:
        return "unknown"
    try:
        return "hit" if check_call_in_cache(*args, **kwargs) else "miss"
    except Exception:
        return "unknown"


def _cost_summary(usage_cost: Optional[dict[str, Any]]) -> str:
    if not usage_cost:
        return "n/a"
    total_cost = usage_cost.get("total_cost")
    return "n/a" if total_cost is None else f"${total_cost:.4f}"


def _response_usage_cost(usage: dict[str, Any], model: str = MODEL) -> dict[str, Any]:
    costs = MODEL_COST_PER_1M_TOKENS[model]
    input_tokens = usage.get("input_tokens", 0)
    cached_tokens = usage.get("input_tokens_details", {}).get("cached_tokens", 0)
    reasoning_tokens = usage.get("output_tokens_details", {}).get("reasoning_tokens", 0)
    output_tokens = usage.get("output_tokens", 0)

    input_cost = round((input_tokens - cached_tokens) * costs["input"] / 1_000_000, 4)
    cache_cost = round(cached_tokens * costs["cache"] / 1_000_000, 4)
    reasoning_cost = round(reasoning_tokens * costs["output"] / 1_000_000, 4)
    output_cost = round(output_tokens * costs["output"] / 1_000_000, 4)
    total_cost = round(input_cost + cache_cost + reasoning_cost + output_cost, 4)

    return {
        "input_tokens": input_tokens,
        "cached_tokens": cached_tokens,
        "reasoning_tokens": reasoning_tokens,
        "output_tokens": output_tokens,
        "input_cost": input_cost,
        "cache_cost": cache_cost,
        "reasoning_cost": reasoning_cost,
        "output_cost": output_cost,
        "total_cost": total_cost,
    }


def _build_parse_response(
    *,
    response_dict: dict[str, Any],
    text_format: Type[BaseModel],
) -> ParsedResponse:
    return ParsedResponse[text_format].model_construct(**response_dict)


def extract_from_text(
    text: str,
    *,
    system_message: str = ABSTRACT_SYSTEM_MESSAGE,
    temperature: Optional[float] = TEMPERATURE,
    model: str = MODEL,
    max_output_tokens: int = MAX_OUTPUT_TOKENS,
    text_format: Type[BaseModel] = DatasetAbstractMetadata,
    reasoning: Optional[Dict[str, Any]] = REASONING,
    skip_cache: bool = False,
) -> dict[str, Any]:
    """Extract and structure text into a Pydantic model."""

    parameters = json.dumps(
        {
            "text": text,
            "system_message": system_message,
            "temperature": temperature,
            "model": model,
            "max_output_tokens": max_output_tokens,
            "text_format": json.dumps(text_format.model_json_schema(), sort_keys=True),
            "reasoning": reasoning,
        },
        sort_keys=True,
    )

    @memory.cache
    def _response_parse(parameters_json_dump: str) -> dict[str, Any]:
        del parameters_json_dump
        client = get_openai_client()
        logger.debug(
            "Calling OpenAI Responses API for text extraction model={} schema={}",
            model,
            text_format.__name__,
        )
        response = client.responses.parse(
            model=model,
            input=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": text},
            ],
            text_format=text_format,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )
        return response.model_dump()

    cache_state = "bypass" if skip_cache else _cache_state(_response_parse, parameters)
    logger.info(
        "Starting text extraction model={} schema={} chars={} cache={}",
        model,
        text_format.__name__,
        len(text),
        cache_state,
    )
    response_dict = _response_parse.func(parameters) if skip_cache else _response_parse(parameters)  # type: ignore[attr-defined]
    response = _build_parse_response(response_dict=response_dict, text_format=text_format)
    result = {
        "prompt": system_message,
        "text": text,
        "model": model,
        "response": response,
        "output": response.output_parsed,
        "usage_cost": _response_usage_cost(response_dict["usage"], model=model) if response_dict.get("usage") else None,
        "temperature": temperature,
        "reasoning": reasoning,
    }
    logger.info(
        "Completed text extraction model={} schema={} cache={} cost={} output_tokens={}",
        model,
        text_format.__name__,
        cache_state,
        _cost_summary(result["usage_cost"]),
        result["usage_cost"].get("output_tokens") if result["usage_cost"] else "n/a",
    )
    return result


@memory.cache
def extract_pdf_text(pdf_path: Union[str, Path], max_pages: Optional[int] = None) -> str:
    """Extract text from a local PDF using pypdf."""
    path = Path(pdf_path)
    logger.debug("Reading PDF text from {} max_pages={}", path, max_pages)
    reader = pypdf.PdfReader(str(path))
    page_limit = max_pages if max_pages is not None else len(reader.pages)
    text_pages: list[str] = []
    for page in reader.pages[:page_limit]:
        text_pages.append(page.extract_text() or "")
    text = "\n".join(text_pages)
    logger.info("Extracted PDF text from {} pages={} chars={}", path, page_limit, len(text))
    return text


def extract_from_pdf_text(
    pdf_path: Union[str, Path],
    *,
    system_message: str = ABSTRACT_SYSTEM_MESSAGE,
    temperature: Optional[float] = TEMPERATURE,
    model: str = MODEL,
    max_output_tokens: int = MAX_OUTPUT_TOKENS,
    text_format: Type[BaseModel] = DatasetAbstractMetadata,
    reasoning: Optional[Dict[str, Any]] = REASONING,
    max_pages: Optional[int] = None,
    skip_cache: bool = False,
) -> dict[str, Any]:
    """Extract text from a PDF and extract structured information from the extracted text."""
    cache_state = _cache_state(extract_pdf_text, pdf_path, max_pages=max_pages)
    logger.info(
        "Starting pdf_text extraction pdf_path={} max_pages={} text_cache={}",
        pdf_path,
        max_pages,
        cache_state,
    )
    pdf_text = extract_pdf_text(pdf_path, max_pages=max_pages)
    result = extract_from_text(
        pdf_text,
        system_message=system_message,
        temperature=temperature,
        model=model,
        max_output_tokens=max_output_tokens,
        text_format=text_format,
        reasoning=reasoning,
        skip_cache=skip_cache,
    )
    result["pdf_path"] = str(pdf_path)
    result["extraction_method"] = "pdf_text"
    logger.info(
        "Completed pdf_text extraction pdf_path={} cost={}",
        pdf_path,
        _cost_summary(result.get("usage_cost")),
    )
    return result

@memory.cache
def upload_pdf_to_openai(pdf_path: Union[str, Path], purpose: str = "user_data") -> str:
    client = get_openai_client()
    logger.info("Uploading PDF to OpenAI path={} purpose={}", pdf_path, purpose)
    with Path(pdf_path).open("rb") as handle:
        uploaded = client.files.create(file=handle, purpose=purpose)
    logger.debug("Uploaded PDF to OpenAI file_id={}", uploaded.id)
    return uploaded.id


def delete_openai_file(file_id: str) -> bool:
    client = get_openai_client()
    try:
        client.files.delete(file_id)
        logger.debug("Deleted OpenAI file file_id={}", file_id)
        return True
    except Exception:
        logger.warning("Failed to delete OpenAI file file_id={}", file_id)
        return False


def list_openai_files() -> list[dict[str, Any]]:
    client = get_openai_client()
    files = client.files.list()
    return [file.model_dump() for file in files.data]


def extract_from_pdf_file(
    pdf_path: Union[str, Path],
    *,
    system_message: str = PDF_SYSTEM_MESSAGE,
    temperature: Optional[float] = TEMPERATURE,
    model: str = MODEL,
    max_output_tokens: int = MAX_OUTPUT_TOKENS,
    text_format: Type[BaseModel] = DatasetAbstractMetadata,
    reasoning: Optional[Dict[str, Any]] = REASONING,
    file_id: Optional[str] = None,
    cleanup_file: bool = False,
    skip_cache: bool = False,
) -> dict[str, Any]:
    """Extract structured information from a local PDF using OpenAI's native PDF support."""

    pdf_path = Path(pdf_path)
    file_id = file_id or upload_pdf_to_openai(pdf_path)
    parameters = json.dumps(
        {
            "file_id": file_id,
            "pdf_path": str(pdf_path),
            "system_message": system_message,
            "temperature": temperature,
            "model": model,
            "max_output_tokens": max_output_tokens,
            "text_format": json.dumps(text_format.model_json_schema(), sort_keys=True),
            "reasoning": reasoning,
        },
        sort_keys=True,
    )

    @memory.cache
    def _response_parse_pdf(parameters_json_dump: str, uploaded_file_id: str) -> dict[str, Any]:
        del parameters_json_dump
        client = get_openai_client()
        logger.debug(
            "Calling OpenAI Responses API for native PDF extraction model={} schema={} file_id={}",
            model,
            text_format.__name__,
            uploaded_file_id,
        )
        response = client.responses.parse(
            model=model,
            input=[
                {"role": "system", "content": system_message},
                {
                    "role": "user",
                    "content": [
                        {"type": "input_file", "file_id": uploaded_file_id},
                        {
                            "type": "input_text",
                            "text": "Extract the biodiversity dataset features from this scientific paper PDF according to the schema.",
                        },
                    ],
                },
            ],
            text_format=text_format,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )
        return response.model_dump()

    cache_state = "bypass" if skip_cache else _cache_state(_response_parse_pdf, parameters, file_id)
    logger.info(
        "Starting pdf_native extraction pdf_path={} file_id={} model={} schema={} cache={}",
        pdf_path,
        file_id,
        model,
        text_format.__name__,
        cache_state,
    )
    response_dict = (
        _response_parse_pdf.func(parameters, file_id)  # type: ignore[attr-defined]
        if skip_cache
        else _response_parse_pdf(parameters, file_id)
    )
    response = _build_parse_response(response_dict=response_dict, text_format=text_format)
    result = {
        "prompt": system_message,
        "pdf_path": str(pdf_path),
        "file_id": file_id,
        "model": model,
        "response": response,
        "output": response.output_parsed,
        "usage_cost": _response_usage_cost(response_dict["usage"], model=model) if response_dict.get("usage") else None,
        "extraction_method": "pdf_native",
        "temperature": temperature,
        "reasoning": reasoning,
    }
    if cleanup_file:
        delete_openai_file(file_id)
    logger.info(
        "Completed pdf_native extraction pdf_path={} file_id={} cache={} cost={}",
        pdf_path,
        file_id,
        cache_state,
        _cost_summary(result.get("usage_cost")),
    )
    return result


def extract_from_pdf_url(
    pdf_url: str,
    *,
    system_message: str = PDF_SYSTEM_MESSAGE,
    temperature: Optional[float] = TEMPERATURE,
    model: str = MODEL,
    max_output_tokens: int = MAX_OUTPUT_TOKENS,
    text_format: Type[BaseModel] = DatasetAbstractMetadata,
    reasoning: Optional[Dict[str, Any]] = REASONING,
) -> dict[str, Any]:
    """Extract structured information from a public PDF URL using OpenAI's native PDF support."""

    parameters = json.dumps(
        {
            "pdf_url": pdf_url,
            "system_message": system_message,
            "temperature": temperature,
            "model": model,
            "max_output_tokens": max_output_tokens,
            "text_format": json.dumps(text_format.model_json_schema(), sort_keys=True),
            "reasoning": reasoning,
        },
        sort_keys=True,
    )

    @memory.cache
    def _response_parse_pdf_url(parameters_json_dump: str) -> dict[str, Any]:
        del parameters_json_dump
        client = get_openai_client()
        logger.debug(
            "Calling OpenAI Responses API for PDF URL extraction model={} schema={}",
            model,
            text_format.__name__,
        )
        response = client.responses.parse(
            model=model,
            input=[
                {"role": "system", "content": system_message},
                {
                    "role": "user",
                    "content": [
                        {"type": "input_file", "file_url": pdf_url},
                        {
                            "type": "input_text",
                            "text": "Extract the biodiversity dataset features from this scientific paper PDF according to the schema.",
                        },
                    ],
                },
            ],
            text_format=text_format,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )
        return response.model_dump()

    cache_state = _cache_state(_response_parse_pdf_url, parameters)
    logger.info(
        "Starting pdf_url extraction pdf_url={} model={} schema={} cache={}",
        pdf_url,
        model,
        text_format.__name__,
        cache_state,
    )
    response_dict = _response_parse_pdf_url(parameters)
    response = _build_parse_response(response_dict=response_dict, text_format=text_format)
    result = {
        "prompt": system_message,
        "pdf_url": pdf_url,
        "model": model,
        "response": response,
        "output": response.output_parsed,
        "usage_cost": _response_usage_cost(response_dict["usage"], model=model) if response_dict.get("usage") else None,
        "extraction_method": "pdf_url",
        "temperature": temperature,
        "reasoning": reasoning,
    }
    logger.info(
        "Completed pdf_url extraction pdf_url={} cache={} cost={}",
        pdf_url,
        cache_state,
        _cost_summary(result.get("usage_cost")),
    )
    return result


__all__ = [
    "ABSTRACT_SYSTEM_MESSAGE",
    "SECTION_SYSTEM_MESSAGE",
    "PDF_SYSTEM_MESSAGE",
    "extract_from_text",
    "extract_pdf_text",
    "extract_from_pdf_text",
    "extract_from_pdf_file",
    "extract_from_pdf_url",
    "upload_pdf_to_openai",
    "delete_openai_file",
    "list_openai_files",
]
