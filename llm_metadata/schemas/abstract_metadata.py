"""
Schema for dataset metadata extracted from abstracts using LLM classification.

This module defines the Pydantic model for high-level ecological dataset metadata
that can be automatically extracted from dataset abstracts using large language models.
"""

from pydantic import BaseModel, Field
from typing import Optional, List


class DatasetAbstractMetadata(BaseModel):
    """
    High-level dataset metadata extracted from abstracts using LLM classification.

    This schema captures essential information about ecological datasets including
    data categories, taxonomic groups, temporal extent, and geographic regions.
    Designed for use with OpenAI's structured output API for automated extraction.
    """

    categories: Optional[List[str]] = Field(
        default=None,
        description=(
            "List each applicable category. "
            "Accepted keys: population time-series, trait data, abundances, "
            "presence/absence, plots, specimens, museum collection, trajectory."
        )
    )
    taxonomic_groups: Optional[List[str]] = Field(
        default=None,
        description="List all species, taxonomic entities or groups mentioned in the abstract."
    )
    additional_keywords: Optional[List[str]] = Field(
        default=None,
        description="List additional keywords relevant to the dataset."
    )
    additional_data: Optional[List[str]] = Field(
        default=None,
        description="Describe any additional data types used in relation to the ecological dataset."
    )
    dataset_year_start: Optional[int] = Field(
        default=None,
        description="Provide the start year of the dataset, if mentioned."
    )
    dataset_year_end: Optional[int] = Field(
        default=None,
        description="Provide the end year of the dataset, if mentioned."
    )
    regions_of_interest: Optional[List[str]] = Field(
        default=None,
        description="List geographical regions relevant to the dataset."
    )


# Default category list for validation and reference
DEFAULT_DATASET_CATEGORIES = [
    "population time-series",
    "trait data",
    "abundances",
    "presence/absence",
    "plots",
    "specimens",
    "museum collection",
    "trajectory"
]
