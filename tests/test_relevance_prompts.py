"""The relevance prompts state the same thresholds as the code-side rules."""

from llm_metadata.prompts.relevance import COMBINED_SYSTEM_MESSAGE, RULES_BLOCK, RULES_CORE, SCORING_SYSTEM_MESSAGE
from llm_metadata.relevance_rules import TEMPORAL_HIGH_FROM_YEARS, TEMPORAL_MODERATE_FROM_YEARS
from llm_metadata.schemas.relevance import RelevanceScore


def test_thresholds_come_from_the_rules_module():
    assert f"H = {TEMPORAL_HIGH_FROM_YEARS} years or more" in RULES_CORE
    assert f"M = {TEMPORAL_MODERATE_FROM_YEARS} to {TEMPORAL_HIGH_FROM_YEARS - 1} years" in RULES_CORE
    assert "more than 15 000 km²" in RULES_CORE and "less than 5 000 km²" in RULES_CORE


def test_spatial_guidance_appears_once_in_each_prompt():
    marker = "spatial_range_km2 (area covered by the dataset)"
    assert SCORING_SYSTEM_MESSAGE.count(marker) == 1
    assert COMBINED_SYSTEM_MESSAGE.count(marker) == 1
    assert marker in RULES_BLOCK and marker not in RULES_CORE


def test_scoring_schema_is_small_and_strict():
    schema = RelevanceScore.model_json_schema()
    assert set(schema["properties"]) == {"reasoning", "has_dataset", "relevance"}
    assert schema.get("additionalProperties") is False
