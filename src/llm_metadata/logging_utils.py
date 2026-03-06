"""Shared loguru configuration for llm_metadata."""

from __future__ import annotations

import os
import sys

from loguru import logger as _logger


_LOG_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
    "<level>{level:<8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
    "<level>{message}</level>"
)


def _resolve_level(level: str | None, *, default: str) -> str:
    return (level or os.getenv("LLM_METADATA_LOG_LEVEL") or default).upper()


def configure_logging(level: str | None = None, *, default_level: str = "INFO") -> None:
    """Reset sinks and apply the project log format."""

    resolved_level = _resolve_level(level, default=default_level)
    colorize = bool(getattr(sys.stderr, "isatty", lambda: False)())
    _logger.remove()
    _logger.add(
        sys.stderr,
        level=resolved_level,
        colorize=colorize,
        format=_LOG_FORMAT,
        backtrace=False,
        diagnose=False,
    )


def configure_extraction_logging(level: str | None = None) -> None:
    """Use a more verbose default for extraction/evaluation flows."""

    configure_logging(level=level, default_level="DEBUG")


logger = _logger


configure_logging()


__all__ = ["logger", "configure_logging", "configure_extraction_logging"]
