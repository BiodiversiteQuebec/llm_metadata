"""
Schema for detailed dataset feature extraction following Fuster et al. EBV framework.

This module defines Pydantic models for comprehensive ecological dataset feature extraction
based on Essential Biodiversity Variables (EBV) classification methodology. It includes
controlled vocabularies for data types, geospatial information, and feature provenance.

Reference: Fuster et al. methodology for biodiversity dataset characterization.
"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class EBVDataType(str, Enum):
    """
    Essential Biodiversity Variable (EBV) data type categories.

    Based on EBV classification framework (Table S1 in Fuster et al.).
    """
    ABUNDANCE = "abundance"
    PRESENCE_ABSENCE = "presence-absence"
    DENSITY = "density"
    DISTRIBUTION = "distribution"
    TRAITS = "traits"
    ECOSYSTEM_FUNCTION = "ecosystem_function"
    ECOSYSTEM_STRUCTURE = "ecosystem_structure"
    GENETIC_ANALYSIS = "genetic_analysis"
    TIME_SERIES = "time_series"
    UNKNOWN = "unknown"


class GeospatialInfoType(str, Enum):
    """
    Geospatial information categories for dataset characterization.

    Classifies geospatial data into distinct categories: sample, site, or range
    coordinates, distribution, geographic features, administrative units, maps, site IDs.
    """
    SAMPLE = "sample"  # sample coordinates
    SITE = "site"  # site coordinates
    RANGE = "range"  # range coordinates
    DISTRIBUTION = "distribution"  # species distribution models
    GEOGRAPHIC_FEATURES = "geographic_features"
    ADMINISTRATIVE_UNITS = "administrative_units"
    MAPS = "maps"
    SITE_IDS = "site_ids"
    UNKNOWN = "unknown"


class FeatureLocation(str, Enum):
    """
    Location where dataset features were found during extraction.

    Tracks provenance of extracted information across different sources:
    abstract, repository page text, article (source publication), or dataset files.
    """
    ABSTRACT = "abstract"
    REPOSITORY_TEXT = "repository text"
    ARTICLE_TEXT = "article text"
    DATASET = "dataset"
    REPOSITORY = "repository"
    UNKNOWN = "unknown"


class DatasetFeatureExtraction(BaseModel):
    """
    Detailed dataset features following Essential Biodiversity Variables (EBV) framework.

    This schema captures comprehensive dataset characteristics including:
    - EBV data type categories with time-series indicators
    - Spatiotemporal extent (geospatial and temporal information)
    - Taxonomic information
    - Dataset source references
    - Feature provenance (where information was found)

    Based on Fuster et al. methodology for evaluating biodiversity dataset quality
    and completeness. Some enum values are inferred as the full classification
    framework was not completely specified in the reference.
    """

    # EBV data type (categorical)
    data_type: Optional[list[EBVDataType]] = Field(
        None,
        description="List of EBV data type categories (e.g. ['abundance', 'density'])."
    )

    # Geospatial information
    geospatial_info_dataset: Optional[GeospatialInfoType] = Field(
        None,
        description="Geospatial info in the dataset (sample, site, range, etc.)."
    )

    # Spatial range with explicit units (km²)
    spatial_range_km2: Optional[float] = Field(
        None,
        description="Spatial range in square kilometers (km²) (e.g. 100000).",
        ge=0  # Must be non-negative
    )

    # Temporal range
    temporal_range: Optional[str] = Field(
        None,
        description="Raw temporal range as text (e.g. 'from 1999 to 2008')."
    )
    temp_range_i: Optional[int] = Field(
        None,
        description="Start year of temporal range.",
        alias="temp_range_i"
    )
    temp_range_f: Optional[int] = Field(
        None,
        description="End year of temporal range.",
        alias="temp_range_f"
    )

    # Taxonomic information
    taxons: Optional[str] = Field(
        None,
        description="Taxonomic groups or species (e.g. 'black-legged tick')."
    )

    # Dataset references
    referred_dataset: Optional[str] = Field(
        None,
        description="Referred dataset source (e.g. 'Ministère des Ressources naturelles...')."
    )

    class Config:
        """Pydantic model configuration."""
        use_enum_values = True  # Serialize enums as their values
        populate_by_name = True  # Allow field population by alias or name
