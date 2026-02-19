"""llm_metadata.prompts — versioned prompt modules for structured extraction.

Each module exposes:
- SYSTEM_MESSAGE: str — the assembled prompt (for direct use)
- build_prompt_override(**overrides) -> str — parameterized constructor for experiments
"""

from llm_metadata.prompts.abstract import SYSTEM_MESSAGE as ABSTRACT_SYSTEM_MESSAGE
from llm_metadata.prompts.section import SYSTEM_MESSAGE as SECTION_SYSTEM_MESSAGE
from llm_metadata.prompts.pdf_file import SYSTEM_MESSAGE as PDF_SYSTEM_MESSAGE

__all__ = ["ABSTRACT_SYSTEM_MESSAGE", "SECTION_SYSTEM_MESSAGE", "PDF_SYSTEM_MESSAGE"]
