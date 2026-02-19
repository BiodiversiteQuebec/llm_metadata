"""Prompt for abstract-based biodiversity dataset feature extraction."""

from llm_metadata.prompts.common import (
    PERSONA, PHILOSOPHY, SCOPING, VOCABULARY, MODULATOR_FIELDS, OUTPUT_FORMAT, build_prompt
)

TASK_INSTRUCTIONS = """## Task

Extract biodiversity dataset features from the provided abstract text into the schema."""

SYSTEM_MESSAGE: str = build_prompt(
    PERSONA, TASK_INSTRUCTIONS, PHILOSOPHY, SCOPING, VOCABULARY, MODULATOR_FIELDS, OUTPUT_FORMAT
)


def build_prompt_override(**overrides) -> str:
    """Build abstract prompt with overridden blocks.

    Args:
        **overrides: Block name to replacement string. Valid keys:
            persona, task_instructions, philosophy, scoping, vocabulary,
            modulator_fields, output_format

    Returns:
        Assembled prompt string.
    """
    blocks = {
        "persona": PERSONA,
        "task_instructions": TASK_INSTRUCTIONS,
        "philosophy": PHILOSOPHY,
        "scoping": SCOPING,
        "vocabulary": VOCABULARY,
        "modulator_fields": MODULATOR_FIELDS,
        "output_format": OUTPUT_FORMAT,
    }
    blocks.update(overrides)
    return build_prompt(
        blocks["persona"], blocks["task_instructions"], blocks["philosophy"],
        blocks["scoping"], blocks["vocabulary"], blocks["modulator_fields"],
        blocks["output_format"],
    )
