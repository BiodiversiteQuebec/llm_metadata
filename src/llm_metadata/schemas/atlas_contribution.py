"""Extraction contract for the Atlas contribution track.

The Fuster schema asks "is this dataset relevant in general?". This schema asks
"what would this dataset add to the Biodiversité Québec Atlas?": which taxa,
where, when, what kind of records, and whether the records themselves are
available. Its answers are matched against the Atlas holdings
(``atlas_match.py``) to compute contribution scores.

Kept deliberately small and flat (enums, optional scalars, two short lists of
objects) so that it fits the API's native structured output, unlike the Fuster
schema, which the API rejected as too complex.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class TaxonRank(str, Enum):
    species = "species"
    genus = "genus"
    family = "family"
    order = "order"
    taxon_class = "class"
    broad_group = "broad_group"
    other = "other"


class PlaceType(str, Enum):
    province_or_state = "province_or_state"
    administrative_region = "administrative_region"
    municipality = "municipality"
    protected_area = "protected_area"
    water_body = "water_body"
    natural_region = "natural_region"
    site = "site"
    country = "country"
    other = "other"


class RecordKind(str, Enum):
    occurrence = "occurrence"
    presence_absence = "presence_absence"
    abundance = "abundance"
    traits_or_genetics = "traits_or_genetics"
    environmental_or_other = "environmental_or_other"


class FocalTaxon(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verbatim_name: str = Field(description="The taxon as written in the text, e.g. 'wood turtle' or 'ground beetles'.")
    scientific_name: Optional[str] = Field(
        None,
        description="Scientific name when stated or unambiguous (a common name with one obvious species), else null.",
    )
    rank: TaxonRank = Field(description="Rank of the name: species, genus, family, order, class, or broad_group for labels like 'birds'.")


class Place(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(description="Place name as written, e.g. 'Shawinigan River', 'Nunavik', 'Quebec'.")
    place_type: PlaceType
    in_quebec: Optional[bool] = Field(None, description="True if the place is in the province of Quebec, False if outside, null if unclear.")
    north_of_49: Optional[bool] = Field(
        None,
        description="True if the place lies north of the 49th parallel, False if south, null if unclear or spanning both.",
    )


class AtlasContributionExtraction(BaseModel):
    """What a dataset holds, described for matching against the Atlas."""

    model_config = ConfigDict(extra="forbid")

    focal_taxa: list[FocalTaxon] = Field(
        default_factory=list,
        description="Taxa the dataset records data on. Not taxa only mentioned as context, prey, hosts or comparison.",
    )
    taxon_count: Optional[int] = Field(
        None, description="Number of taxa recorded when stated as a number rather than listed (e.g. '73 weevil species' -> 73)."
    )
    places: list[Place] = Field(default_factory=list, description="Places where the data were collected.")
    year_start: Optional[int] = Field(None, description="First year of data collection.")
    year_end: Optional[int] = Field(None, description="Last year of data collection.")
    record_kind: RecordKind = Field(description="Main kind of record in the dataset.")
    occurrence_records_available: Optional[bool] = Field(
        None,
        description=(
            "True if the dataset (or its repository deposit) contains taxon records with place and date "
            "that could be loaded into an occurrence database; False if it holds only derived values "
            "(model outputs, summary statistics, sequences without locations); null if unclear."
        ),
    )
    n_sites: Optional[int] = Field(None, description="Number of sampling sites or stations, when stated.")
    n_records: Optional[int] = Field(None, description="Number of records, specimens or individuals, when stated.")


__all__ = [
    "AtlasContributionExtraction",
    "FocalTaxon",
    "Place",
    "PlaceType",
    "RecordKind",
    "TaxonRank",
]
