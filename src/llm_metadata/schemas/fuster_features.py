"""Feature-model hierarchy for ecological metadata extraction and evaluation."""

from __future__ import annotations

from enum import Enum
import math
import re
from typing import TYPE_CHECKING, Any, Optional, Sequence

import pandas as pd
from pydantic import BaseModel, Field, field_validator, model_validator

from llm_metadata.species_parsing import (
    ParsedTaxon,
    TaxonRichnessMention,
    extract_parsed_taxa,
    extract_species_richness_mentions,
    project_species_richness_counts,
    project_species_richness_group_keys,
)

if TYPE_CHECKING:
    from llm_metadata.gbif import ResolvedTaxon


DATA_TYPE_MAPPING = {
    "abundance": "abundance",
    "presence-absence": "presence-absence",
    "presence only": "presence-only",
    "presence-only": "presence-only",
    "density": "density",
    "distribution": "distribution",
    "traits": "traits",
    "ecosystem function": "ecosystem_function",
    "ecosystem_function": "ecosystem_function",
    "ecosystem structure": "ecosystem_structure",
    "ecosystem_structure": "ecosystem_structure",
    "genetic analysis": "genetic_analysis",
    "genetic_analysis": "genetic_analysis",
    "ebv genetic analysis": "genetic_analysis",
    "time series": "time_series",
    "time_series": "time_series",
    "species richness": "species_richness",
    "species_richness": "species_richness",
    "other": "other",
    "unknown": "unknown",
}

GEO_TYPE_MAPPING = {
    "sample": "sample",
    "sample coordinates": "sample",
    "site": "site",
    "site coordinates": "site",
    "range": "range",
    "range coordinates": "range",
    "distribution": "distribution",
    "species distribution": "distribution",
    "geographic features": "geographic_features",
    "geographic_features": "geographic_features",
    "administrative units": "administrative_units",
    "administrative_units": "administrative_units",
    "maps": "maps",
    "site ids": "site_ids",
    "site_ids": "site_ids",
    "unknown": "unknown",
}


class EBVDataType(str, Enum):
    ABUNDANCE = "abundance"
    PRESENCE_ABSENCE = "presence-absence"
    PRESENCE_ONLY = "presence-only"
    DENSITY = "density"
    DISTRIBUTION = "distribution"
    TRAITS = "traits"
    ECOSYSTEM_FUNCTION = "ecosystem_function"
    ECOSYSTEM_STRUCTURE = "ecosystem_structure"
    GENETIC_ANALYSIS = "genetic_analysis"
    TIME_SERIES = "time_series"
    SPECIES_RICHNESS = "species_richness"
    OTHER = "other"
    UNKNOWN = "unknown"


class ValidationStatus(str, Enum):
    YES = "yes"
    NO = "no"


class InvalidReason(str, Enum):
    LOCATION = "location"
    NON_RELEVANT = "non-relevant information"
    NON_FIELD_EXPERIMENT = "non-field experiment"
    NOT_IN_THE_FIELD = "not in the field"
    BIODIVERSITY_UNRELATED = "biodiversity-unrelated"
    MICROBIAL_COMMUNITY = "microbial community"
    OTHER = "other"


class GeospatialInfoType(str, Enum):
    SAMPLE = "sample"
    SITE = "site"
    RANGE = "range"
    DISTRIBUTION = "distribution"
    GEOGRAPHIC_FEATURES = "geographic_features"
    ADMINISTRATIVE_UNITS = "administrative_units"
    MAPS = "maps"
    SITE_IDS = "site_ids"
    UNKNOWN = "unknown"


class FeatureLocation(str, Enum):
    ABSTRACT = "abstract"
    REPOSITORY_TEXT = "repository text"
    ARTICLE_TEXT = "article text"
    DATASET = "dataset"
    REPOSITORY = "repository"
    UNKNOWN = "unknown"


class DataSource(str, Enum):
    DRYAD = "dryad"
    ZENODO = "zenodo"
    SEMANTIC_SCHOLAR = "semantic_scholar"
    REFERENCED = "referenced"


class CoreFeatureModel(BaseModel):
    """Shared semantic feature fields only."""

    data_type: Optional[list[EBVDataType]] = Field(
        None,
        description="List of EBV data type categories (e.g. ['abundance', 'density']).",
    )
    geospatial_info_dataset: Optional[list[GeospatialInfoType]] = Field(
        None,
        description="List of geospatial info categories in the dataset (sample, site, range, etc.).",
    )
    spatial_range_km2: Optional[float] = Field(
        None,
        description="Spatial range in square kilometers (km^2) (e.g. 100000).",
        ge=0,
    )
    temporal_range: Optional[str] = Field(
        None,
        description="Raw temporal range as text (e.g. 'from 1999 to 2008').",
    )
    temp_range_i: Optional[int] = Field(None, description="Start year of temporal range.", alias="temp_range_i")
    temp_range_f: Optional[int] = Field(None, description="End year of temporal range.", alias="temp_range_f")
    species: Optional[list[str]] = Field(
        None,
        description=(
            "Extracted text as-is, not interpreted. Taxonomic groups, scientific names, "
            "common names, mixtures, or counts."
        ),
    )
    referred_dataset: Optional[str] = Field(
        None,
        description="Referred dataset source (e.g. 'Ministere des Ressources naturelles...').",
    )
    time_series: Optional[bool] = Field(
        None,
        description="Whether the dataset contains time-series data (repeated measurements over time).",
    )
    multispecies: Optional[bool] = Field(
        None,
        description="Whether the dataset covers multiple species.",
    )
    threatened_species: Optional[bool] = Field(
        None,
        description="Whether the dataset includes threatened, endangered, or at-risk species.",
    )
    new_species_science: Optional[bool] = Field(
        None,
        description="Whether the dataset describes species new to science.",
    )
    new_species_region: Optional[bool] = Field(
        None,
        description="Whether the dataset reports species new to a particular region.",
    )
    bias_north_south: Optional[bool] = Field(
        None,
        description="Whether the dataset exhibits a Global North / Global South geographic bias.",
    )
    valid_yn: Optional[ValidationStatus] = Field(None, description="Validation status (yes/no).")
    reason_not_valid: Optional[str] = Field(
        None,
        description="Reason for invalid classification. See InvalidReason enum for common values.",
    )

    class Config:
        use_enum_values = True
        populate_by_name = True


class DatasetFeaturesExtraction(CoreFeatureModel):
    """LLM extraction contract sent to `responses.parse()`."""


class DatasetFeaturesNormalized(DatasetFeaturesExtraction):
    """Ground-truth validation contract with spreadsheet normalization."""

    @model_validator(mode="before")
    @classmethod
    def convert_nan_to_none(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        null_placeholders = {
            "not given",
            "not_given",
            "na",
            "n/a",
            "nan",
            "none",
            "",
            " ",
        }

        def is_nan(value: Any) -> bool:
            if value is None:
                return False
            if isinstance(value, (float, int)) and pd.isna(value):
                return True
            return False

        cleaned = {}
        for key, value in data.items():
            if is_nan(value):
                cleaned[key] = None
            elif isinstance(value, str):
                stripped = value.strip()
                if stripped.lower() in null_placeholders:
                    cleaned[key] = None
                elif "," in stripped and stripped.replace(",", "").replace(".", "").replace("-", "").isdigit():
                    cleaned[key] = stripped.replace(",", ".")
                else:
                    cleaned[key] = stripped
            else:
                cleaned[key] = value
        return cleaned

    @field_validator("reason_not_valid", mode="before")
    @classmethod
    def normalize_reason_not_valid(cls, value: Any) -> Optional[str]:
        if isinstance(value, str):
            normalized = value.strip()
            lowered = normalized.lower()
            if lowered == "non biological":
                return "biodiversity-unrelated"
            if lowered == "experiment":
                return "non-field experiment"
            if lowered in ["micorbial community", "microbial communities"]:
                return "microbial community"
            if lowered.startswith("gut microbiota"):
                return "microbial community"
            return normalized
        return value

    @field_validator("species", mode="before")
    @classmethod
    def parse_species_list(cls, value: Any) -> Optional[list[str]]:
        if value is None:
            return None
        if isinstance(value, list):
            raw_items = value
        elif isinstance(value, str):
            raw_items = [value]
        else:
            return [str(value)]

        parsed: list[str] = []
        for item in raw_items:
            if isinstance(item, str):
                for part in re.split(r"[;,]", item):
                    cleaned = part.strip()
                    if cleaned:
                        parsed.append(cleaned)
            elif item:
                parsed.append(str(item))
        return parsed or None

    @field_validator("data_type", mode="before")
    @classmethod
    def parse_data_type_list(cls, value: Any) -> Optional[list[str]]:
        if value is None:
            return None
        if isinstance(value, list):
            raw_items = value
        elif isinstance(value, str):
            raw_items = [value]
        else:
            return value

        parsed: list[str] = []
        for item in raw_items:
            if not item or not isinstance(item, str):
                if item:
                    parsed.append(item)
                continue
            for part in item.split(","):
                normalized = cls._normalize_ebv_value(part.strip())
                if normalized:
                    parsed.append(normalized)
        return parsed or None

    @staticmethod
    def _normalize_ebv_value(value: str) -> str:
        if not isinstance(value, str):
            return value

        normalized = value.lower().strip().replace("ebv", "").strip()
        normalized = normalized.split("(")[0].strip()
        normalized = normalized.replace("analyses", "analysis")
        normalized = normalized.replace("records", "").strip()

        if normalized in DATA_TYPE_MAPPING:
            return DATA_TYPE_MAPPING[normalized]

        normalized = normalized.replace(" ", "_").replace("-", "_").strip("_")
        replacements = {
            "presence": "presence_only",
            "presence_only": "presence_only",
            "presence_absence": "presence_absence",
            "genetic_analysis": "genetic_analysis",
        }
        if normalized in replacements:
            normalized = replacements[normalized]
        if normalized == "presence_absence":
            return "presence-absence"
        if normalized == "presence_only":
            return "presence-only"
        return normalized

    @field_validator("geospatial_info_dataset", mode="before")
    @classmethod
    def parse_geospatial_list(cls, value: Any) -> Optional[list[str]]:
        if value is None:
            return None
        if isinstance(value, list):
            raw_items = value
        elif isinstance(value, str):
            raw_items = [value]
        else:
            return value

        parsed: list[str] = []
        known_phrases = {
            "site coordinates",
            "sample coordinates",
            "range coordinates",
            "geographic feature",
            "geographic features",
            "administrative unit",
            "administrative units",
            "site ids",
            "distribution model",
        }

        for item in raw_items:
            if not item or not isinstance(item, str):
                if item:
                    parsed.append(item)
                continue

            for part in item.split(","):
                cleaned = part.strip()
                if not cleaned:
                    continue

                normalized = cls._normalize_geospatial_value(cleaned)
                if normalized not in [member.value for member in GeospatialInfoType] and " " in cleaned:
                    words = cleaned.split()
                    index = 0
                    while index < len(words):
                        if index + 1 < len(words):
                            phrase = f"{words[index]} {words[index + 1]}"
                            if phrase.lower() in known_phrases:
                                parsed.append(cls._normalize_geospatial_value(phrase))
                                index += 2
                                continue
                        word_norm = cls._normalize_geospatial_value(words[index])
                        if word_norm:
                            parsed.append(word_norm)
                        index += 1
                elif normalized:
                    parsed.append(normalized)

        unique: list[str] = []
        seen: set[str] = set()
        for item in parsed:
            if item not in seen:
                unique.append(item)
                seen.add(item)
        return unique or None

    @staticmethod
    def _normalize_geospatial_value(value: str) -> str:
        if not isinstance(value, str):
            return value

        key = value.lower().strip()
        if key in GEO_TYPE_MAPPING:
            return GEO_TYPE_MAPPING[key]

        normalized = key.replace("-", "_").replace(" ", "_").strip("_")
        mapping = {
            "sample_coordinates": "sample",
            "site_coordinates": "site",
            "sites_ids": "site_ids",
            "site_id": "site_ids",
            "ids": "site_ids",
            "id": "site_ids",
            "range_coordinates": "range",
            "geographic_feature": "geographic_features",
            "administrative_unit": "administrative_units",
            "distribution_model": "distribution",
            "map": "maps",
        }
        return mapping.get(normalized, normalized)

    @field_validator(
        "time_series",
        "multispecies",
        "threatened_species",
        "new_species_science",
        "new_species_region",
        "bias_north_south",
        mode="before",
    )
    @classmethod
    def coerce_bool(cls, value: Any) -> Optional[bool]:
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            if isinstance(value, float) and (math.isnan(value) or pd.isna(value)):
                return None
            return bool(value)
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in ("yes", "true", "1"):
                return True
            if normalized in ("no", "false", "0"):
                return False
            if normalized in ("", "na", "n/a", "nan", "none"):
                return None
        return None

    @field_validator("spatial_range_km2", mode="before")
    @classmethod
    def coerce_spatial_range(cls, value: Any) -> Optional[float]:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            if isinstance(value, float) and math.isnan(value):
                return None
            return float(value)
        if isinstance(value, str):
            cleaned = value.strip().replace(",", ".").replace(" ", "")
            try:
                return float(cleaned)
            except ValueError:
                return None
        return value

    @field_validator("temporal_range", mode="before")
    @classmethod
    def coerce_temporal_range(cls, value: Any) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            if isinstance(value, float) and math.isnan(value):
                return None
            return str(int(value))
        return str(value).strip()

    @field_validator("temp_range_i", "temp_range_f", mode="before")
    @classmethod
    def coerce_year_to_int(cls, value: Any) -> Optional[int]:
        if value is None:
            return None
        if isinstance(value, float):
            return int(value)
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            try:
                return int(float(value.strip()))
            except ValueError:
                return None
        return value


class DatasetFeaturesEvaluation(CoreFeatureModel):
    """Evaluation-time feature model with enrichment-only derived fields."""

    parsed_species: Optional[list[ParsedTaxon]] = Field(
        None,
        description="Structured parse of the raw species field. Populated during evaluation preprocessing.",
    )
    species_richness_mentions: Optional[list[TaxonRichnessMention]] = Field(
        None,
        description="Structured count-bearing taxonomic mentions parsed from species.",
    )
    species_richness_counts: Optional[list[int]] = Field(
        None,
        description="Comparison-oriented projection of taxonomic richness counts.",
    )
    species_richness_group_keys: Optional[list[str]] = Field(
        None,
        description="Comparison-oriented projection formatted as '<count>|<normalized_group>'.",
    )
    taxon_broad_group_labels: Optional[list[str]] = Field(
        None,
        description="Broad taxonomic group labels derived during preprocessing.",
    )
    gbif_keys: Optional[list[int]] = Field(
        None,
        description="GBIF backbone taxon keys resolved from the species field.",
    )

    @staticmethod
    def _core_payload(model: CoreFeatureModel) -> dict[str, Any]:
        return {
            field_name: getattr(model, field_name, None)
            for field_name in CoreFeatureModel.model_fields
        }

    @staticmethod
    def _gbif_keys_from_payload(gbif: Optional[Sequence["ResolvedTaxon"]]) -> Optional[list[int]]:
        if not gbif:
            return None
        keys = sorted({item.gbif_match.gbif_key for item in gbif if item.gbif_match is not None})
        return keys or None

    @classmethod
    def from_extraction(
        cls,
        model: CoreFeatureModel,
        *,
        gbif: Optional[Sequence["ResolvedTaxon"]] = None,
        parsed_species: Optional[list[ParsedTaxon]] = None,
        species_richness_mentions: Optional[list[TaxonRichnessMention]] = None,
        species_richness_counts: Optional[list[int]] = None,
        species_richness_group_keys: Optional[list[str]] = None,
        taxon_broad_group_labels: Optional[list[str]] = None,
        gbif_keys: Optional[list[int]] = None,
    ) -> "DatasetFeaturesEvaluation":
        species = getattr(model, "species", None)
        mentions = (
            species_richness_mentions
            if species_richness_mentions is not None
            else extract_species_richness_mentions(species)
        )
        return cls.model_validate(
            {
                **cls._core_payload(model),
                "parsed_species": parsed_species if parsed_species is not None else extract_parsed_taxa(species),
                "species_richness_mentions": mentions,
                "species_richness_counts": (
                    species_richness_counts
                    if species_richness_counts is not None
                    else project_species_richness_counts(species, mentions)
                ),
                "species_richness_group_keys": (
                    species_richness_group_keys
                    if species_richness_group_keys is not None
                    else project_species_richness_group_keys(mentions)
                ),
                "taxon_broad_group_labels": taxon_broad_group_labels,
                "gbif_keys": gbif_keys if gbif_keys is not None else cls._gbif_keys_from_payload(gbif),
            }
        )


DatasetFeatures = DatasetFeaturesExtraction
SEMANTIC_FEATURE_FIELD_NAMES = tuple(DatasetFeaturesExtraction.model_fields.keys())
EVALUATION_FEATURE_FIELD_NAMES = tuple(DatasetFeaturesEvaluation.model_fields.keys())
