"""Anthropic (Claude) extraction helper for text inputs.

Mirror of ``gpt_extract.extract_from_text`` so ``extraction.py`` can route a
``claude-*`` model to Claude without changing anything else in the pipeline.
The returned dict has the same keys (``output``, ``usage_cost``, ...).
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional, Type

from joblib import Memory
from pydantic import BaseModel

from llm_metadata.anthropic_io import get_anthropic_client
from llm_metadata.logging_utils import logger
from llm_metadata.prompts.abstract import SYSTEM_MESSAGE as ABSTRACT_SYSTEM_MESSAGE
from llm_metadata.schemas import DatasetAbstractMetadata


memory = Memory("./cache", verbose=0)

# USD per 1M tokens. Haiku 5.5 prices apply to prompts up to 100K tokens.
# "cache" = price of a prompt-cache read (assumed 10% of input; update if it differs).
MODEL_COST_PER_1M_TOKENS = {
    "claude-haiku-5-5": {"input": 0.10, "output": 0.50, "cache": 0.01},
    "claude-sonnet-5-5": {"input": 2.00, "output": 10.00, "cache": 0.20},
    "claude-opus-5-5": {"input": 4.00, "output": 20.00, "cache": 0.20},
}

MODEL = "claude-haiku-5-5"
MAX_OUTPUT_TOKENS = 4096
REASONING = {"effort": "low"}


def is_claude_model(model: str) -> bool:
    return model.startswith("claude-")


def _usage_cost(usage: dict[str, Any], model: str, *, joblib_cache_hit: bool) -> dict[str, Any]:
    costs = MODEL_COST_PER_1M_TOKENS[model]
    input_tokens = usage.get("input_tokens", 0) or 0
    cached_tokens = usage.get("cache_read_input_tokens", 0) or 0
    output_tokens = usage.get("output_tokens", 0) or 0
    base = {
        "input_tokens": input_tokens + cached_tokens,
        "cached_tokens": cached_tokens,
        # Thinking tokens are already counted inside output_tokens by the API.
        "reasoning_tokens": 0,
        "output_tokens": output_tokens,
        "joblib_cache_hit": joblib_cache_hit,
    }
    if joblib_cache_hit:
        return {**base, "input_cost": 0.0, "cache_cost": 0.0, "reasoning_cost": 0.0,
                "output_cost": 0.0, "total_cost": 0.0}
    input_cost = round(input_tokens * costs["input"] / 1_000_000, 4)
    cache_cost = round(cached_tokens * costs["cache"] / 1_000_000, 4)
    output_cost = round(output_tokens * costs["output"] / 1_000_000, 4)
    return {**base, "input_cost": input_cost, "cache_cost": cache_cost, "reasoning_cost": 0.0,
            "output_cost": output_cost, "total_cost": round(input_cost + cache_cost + output_cost, 4)}


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
) -> dict[str, Any]:
    """Extract and structure text into a Pydantic model with Claude.

    ``temperature`` is ignored: recent Claude models reject non-default sampling
    values. ``reasoning["effort"]`` maps to Claude's ``output_config.effort``.
    """
    if model not in MODEL_COST_PER_1M_TOKENS:
        raise ValueError(f"Unknown Claude model {model!r}; add it to MODEL_COST_PER_1M_TOKENS.")

    effort = (reasoning or {}).get("effort")
    parameters = json.dumps(
        {
            "text": text,
            "system_message": system_message,
            "model": model,
            "max_output_tokens": max_output_tokens,
            "text_format": json.dumps(text_format.model_json_schema(), sort_keys=True),
            "effort": effort,
        },
        sort_keys=True,
    )

    @memory.cache
    def _response_parse(parameters_json_dump: str) -> dict[str, Any]:
        del parameters_json_dump
        client = get_anthropic_client()
        logger.debug("Calling Anthropic Messages API model={} schema={}", model, text_format.__name__)
        kwargs: dict[str, Any] = {}
        if effort:
            kwargs["output_config"] = {"effort": effort}
        # The API's constrained-output mode rejects our schemas ("Schema is too
        # complex"), so the schema goes in the prompt and Pydantic validates the reply.
        system = (
            system_message
            + "\n\nReturn ONLY one JSON object matching this JSON schema. No prose, no code fence.\n"
            + json.dumps(text_format.model_json_schema())
        )
        response = client.messages.create(
            model=model,
            max_tokens=max_output_tokens,
            system=system,
            messages=[{"role": "user", "content": text}],
            **kwargs,
        )
        if response.stop_reason in ("max_tokens", "refusal"):
            raise RuntimeError(f"Claude stopped with stop_reason={response.stop_reason}")
        reply = "".join(b.text for b in response.content if b.type == "text").strip()
        if reply.startswith("```"):
            reply = reply.strip("`").removeprefix("json").strip()
        output = text_format.model_validate_json(reply)
        return {
            "output_json": output.model_dump_json(),
            "usage": response.usage.model_dump(),
        }

    check = getattr(_response_parse, "check_call_in_cache", None)
    try:
        cache_state = "bypass" if skip_cache else ("hit" if check and check(parameters) else "miss")
    except Exception:
        cache_state = "unknown"
    logger.info(
        "Starting text extraction model={} schema={} chars={} cache={}",
        model, text_format.__name__, len(text), cache_state,
    )
    raw = _response_parse.func(parameters) if skip_cache else _response_parse(parameters)  # type: ignore[attr-defined]
    usage_cost = _usage_cost(raw["usage"], model, joblib_cache_hit=cache_state == "hit")
    logger.info(
        "Completed text extraction model={} cache={} cost=${:.4f} output_tokens={}",
        model, cache_state, usage_cost["total_cost"], usage_cost["output_tokens"],
    )
    return {
        "prompt": system_message,
        "text": text,
        "model": model,
        "response": raw,
        "output": text_format.model_validate_json(raw["output_json"]),
        "usage_cost": usage_cost,
        "temperature": None,
        "reasoning": reasoning,
    }
