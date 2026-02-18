"""OpenAI IO helpers with environment-driven base URL routing.

This module centralizes OpenAI client creation so services can run either:
- directly against OpenAI (default), or
- through a reverse proxy/base URL configured via environment variables.
"""

import os
from typing import Optional

from openai import OpenAI


DEFAULT_OPENAI_API_BASE = "https://api.openai.com/v1"


def get_openai_api_base() -> str:
    """Return OpenAI base URL from env with a safe default fallback."""
    base_url = (
        os.getenv("OPENAI_API_BASE")
        or os.getenv("OPENAI_BASE_URL")
        or DEFAULT_OPENAI_API_BASE
    )
    return base_url.rstrip("/")


def get_openai_client(
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
) -> OpenAI:
    """Build an OpenAI client honoring env-overridable base URL.

    Args:
        api_key: Optional OpenAI API key override.
        base_url: Optional base URL override.

    Returns:
        Configured OpenAI client.
    """
    resolved_base_url = (base_url or get_openai_api_base()).rstrip("/")

    kwargs = {"base_url": resolved_base_url}
    if api_key is not None:
        kwargs["api_key"] = api_key

    return OpenAI(**kwargs)
