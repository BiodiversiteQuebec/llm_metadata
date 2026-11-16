"""Output contracts for relevance scoring by the LLM.

Naming used in the logs and the article outline:

* **R1** rules on extracted features: no schema here (``DatasetFeaturesExtraction``,
  then ``relevance_rules`` in code);
* **R2** combined: features and the category in one call
  (:class:`DatasetFeaturesWithRelevance`);
* **R3** scoring only: the category and a short reason, no features
  (:class:`RelevanceScore`), small enough for native structured output.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from llm_metadata.schemas.fuster_features import DatasetFeaturesExtraction

RelevanceLabel = Literal["H", "M", "L", "X"]


class RelevanceScore(BaseModel):
    """R3: the relevance category, decided by the model from the rules it is given."""

    model_config = ConfigDict(extra="forbid")

    reasoning: str = Field(
        description="Two to four short sentences: the data type, temporal and spatial classes you "
        "assigned, the modulators that apply, and how they give the category."
    )
    has_dataset: bool = Field(description="True if the text describes data produced or curated by the authors.")
    relevance: RelevanceLabel = Field(description="H high, M moderate, L low, X not relevant or no dataset.")


class DatasetFeaturesWithRelevance(DatasetFeaturesExtraction):
    """R2: every extraction feature plus the category, in one call."""

    has_dataset: Optional[bool] = Field(
        None, description="True if the text describes data produced or curated by the authors."
    )
    relevance: Optional[RelevanceLabel] = Field(
        None, description="H high, M moderate, L low, X not relevant or no dataset, from the scoring rules."
    )
    relevance_reasoning: Optional[str] = Field(
        None, description="One to three sentences explaining the category from the extracted features."
    )


class RelevanceTarget(BaseModel):
    """Ground truth for relevance runs: the rule label (primary) and the human label."""

    relevance: Optional[RelevanceLabel] = None
    human_relevance: Optional[RelevanceLabel] = None


__all__ = ["DatasetFeaturesWithRelevance", "RelevanceLabel", "RelevanceScore", "RelevanceTarget"]
