"""Anthropic IO helpers with environment-driven base URL routing.

Same convention as ``openai_io.py``: run directly against Anthropic (default),
or through a reverse proxy set with ``ANTHROPIC_API_BASE`` (the proxy injects the key).
"""

import os
from typing import Optional

from anthropic import Anthropic


DEFAULT_ANTHROPIC_API_BASE = "https://api.anthropic.com"


def get_anthropic_api_base() -> str:
    """Return Anthropic base URL from env with a safe default fallback."""
    base_url = (
        os.getenv("ANTHROPIC_API_BASE")
        or os.getenv("ANTHROPIC_BASE_URL")
        or DEFAULT_ANTHROPIC_API_BASE
    )
    return base_url.rstrip("/")


def get_anthropic_client(
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
) -> Anthropic:
    """Build an Anthropic client honoring env-overridable base URL."""
    kwargs = {"base_url": (base_url or get_anthropic_api_base()).rstrip("/")}
    if api_key is not None:
        kwargs["api_key"] = api_key
    return Anthropic(**kwargs)
