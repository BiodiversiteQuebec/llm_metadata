"""Prompt for PDF document-based biodiversity dataset feature extraction."""

from llm_metadata.prompts.common import (
    PERSONA, PHILOSOPHY, SCOPING, VOCABULARY, MODULATOR_FIELDS, OUTPUT_FORMAT, build_prompt
)

TASK_INSTRUCTIONS = """## Task

Extract biodiversity dataset features from the provided PDF document into the schema.

## PDF Document Analysis

This PDF has been processed to provide both:
1. **Extracted text** from each page for detailed content analysis
2. **Visual rendering** of each page for tables, figures, and layout understanding

Use BOTH the text and visual information to extract accurate metadata. Pay special attention to:
- **Tables**: Often contain structured data about sampling sites, species lists, temporal coverage
- **Figures/Maps**: May show study area extent, spatial distribution, geographic coordinates
- **Supplementary materials**: Sometimes contain detailed methods or data descriptions

Scientific papers typically follow this structure — prioritize sections accordingly:

| Section | Primary Information |
|---------|-------------------|
| Abstract | Overview summary (use for context, prefer details from body) |
| Introduction | Study objectives, geographic scope |
| Methods/Materials | **PRIMARY SOURCE**: Sampling protocols, study sites, dates, species |
| Study Area | Geographic coordinates, spatial extent, region names |
| Data/Data Availability | Dataset descriptions, data types, access information |
| Results | Actual measurements, confirmed values |
| Supplementary | Detailed species lists, coordinate tables, extended methods |

When text and figures contradict, prefer quantitative data from tables/figures."""

SYSTEM_MESSAGE: str = build_prompt(
    PERSONA, TASK_INSTRUCTIONS, PHILOSOPHY, SCOPING, VOCABULARY, MODULATOR_FIELDS, OUTPUT_FORMAT
)


def build_prompt_override(**overrides) -> str:
    """Build PDF prompt with overridden blocks.

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
