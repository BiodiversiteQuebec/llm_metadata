"""Prompts for relevance scoring by the LLM (R2 combined, R3 scoring only).

The rules block is written from the constants of ``relevance_rules.py`` so the
instructions and the code-side rules cannot drift apart. It states the rules of
Fuster-Calvo et al. (2025) as reproduced on the released labels; no Biodiversité
Québec priorities are added (none have been specified yet).
"""

from __future__ import annotations

from llm_metadata.prompts import abstract as abstract_prompt
from llm_metadata.prompts.common import PERSONA, SCOPING, SPATIAL_EXTENT, build_prompt
from llm_metadata.relevance_rules import (
    SPATIAL_HIGH_ABOVE_KM2,
    SPATIAL_MODERATE_FROM_KM2,
    TEMPORAL_HIGH_FROM_YEARS,
    TEMPORAL_MODERATE_FROM_YEARS,
)


def _n(x: int) -> str:
    return f"{x:,}".replace(",", " ")


RULES_CORE = f"""## Relevance scoring rules

Score how useful the dataset is for biodiversity monitoring in Quebec, with these rules.

**Three main classifiers**, each H (high), M (moderate), L (low) or X (not stated or unusable):
- Data type: H = abundance, density, or genetic data describing variation within species (population genetic diversity, structure, relatedness, effective size); M = distribution, presence-absence; L = presence-only, relative abundance, species richness, other genetic data (barcoding, eDNA detection, phylogenies); X = no species or biodiversity data, or unknown. With several data types, take the best.
- Temporal extent, counted in calendar years from first to last year inclusive: H = {TEMPORAL_HIGH_FROM_YEARS} years or more, M = {TEMPORAL_MODERATE_FROM_YEARS} to {TEMPORAL_HIGH_FROM_YEARS - 1} years, L = 1 or 2 years, X = years not stated.
- Spatial extent: H = more than {_n(SPATIAL_HIGH_ABOVE_KM2)} km², M = {_n(SPATIAL_MODERATE_FROM_KM2)} to {_n(SPATIAL_HIGH_ABOVE_KM2)} km², L = less than {_n(SPATIAL_MODERATE_FROM_KM2)} km², X = no place information. Estimate the area as described below when it is not stated.

**Combine** by majority: if two or three classifiers agree, that class wins. If all three differ: when data type is H and temporal or spatial is X, the result is L; otherwise take the lower of the data type class and the better of the temporal and spatial classes.

**Modulators:** raise the result by one level (X to L, L to M, M to H; H stays H) if at least one applies: the dataset covers more than one species; it includes threatened, endangered or at-risk species; it describes species new to science; it reports species new to a region; it lies north of the 49th parallel in Quebec or northern Canada, or explicitly addresses a north–south sampling gap. Raise by one level at most.

If the text describes no dataset produced or curated by the authors, set has_dataset to false and the category to X."""

#: Rules plus the spatial-extent guidance (for scoring only, which has no extraction prompt).
RULES_BLOCK = RULES_CORE + "\n\n" + SPATIAL_EXTENT

SCORING_TASK = """## Task

Read the text and assign the relevance category with the rules below. Do not list the features; reason briefly and return the category. Use only what the text supports, except for the spatial extent, which you estimate from named places when the area is not stated."""

#: R3: scoring only.
SCORING_SYSTEM_MESSAGE: str = build_prompt(PERSONA, SCORING_TASK, SCOPING, RULES_BLOCK)

COMBINED_TASK = """## Relevance category

After extracting all features, also assign the relevance category (field `relevance`), applying the scoring rules below to the features you extracted, and explain it in `relevance_reasoning`."""

#: R2: the feature extraction prompt plus the rules and the category.
COMBINED_SYSTEM_MESSAGE: str = build_prompt(abstract_prompt.SYSTEM_MESSAGE, COMBINED_TASK, RULES_CORE)

__all__ = ["COMBINED_SYSTEM_MESSAGE", "RULES_BLOCK", "RULES_CORE", "SCORING_SYSTEM_MESSAGE"]
