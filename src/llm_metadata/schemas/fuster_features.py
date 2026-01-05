"""
Schema for detailed dataset feature extraction following Fuster et al. EBV framework.

This module defines Pydantic models for comprehensive ecological dataset feature extraction
based on Essential Biodiversity Variables (EBV) classification methodology. It includes
controlled vocabularies for data types, geospatial information, and feature provenance.

Reference: Fuster et al. methodology for biodiversity dataset characterization.
"""

from enum import Enum
from typing import Any, Optional
import math

from pydantic import BaseModel, Field, field_validator, model_validator


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

    # --- Field Validators ---
    
    @model_validator(mode='before')
    @classmethod
    def convert_nan_to_none(cls, data: Any) -> Any:
        """Convert NaN, NA, and placeholder values to None across all fields."""
        if not isinstance(data, dict):
            return data
        
        null_placeholders = {
            "not given", "Not given", "NOT GIVEN",
            "NA", "N/A", "n/a", "na",
            "nan", "NaN", "NAN",
            "none", "None", "NONE",
            "", " ",
        }
        
        def is_nan(value: Any) -> bool:
            if value is None:
                return False
            if isinstance(value, float) and math.isnan(value):
                return True
            return False
        
        cleaned = {}
        for key, value in data.items():
            if is_nan(value):
                cleaned[key] = None
            elif isinstance(value, str) and value.strip() in null_placeholders:
                cleaned[key] = None
            else:
                cleaned[key] = value
        return cleaned

    @field_validator('data_type', mode='before')
    @classmethod
    def parse_data_type_list(cls, v: Any) -> Optional[list[str]]:
        """
        Convert comma-separated string to list of EBV data type values.
        
        Handles: 'abundance,density' -> ['abundance', 'density']
        Also normalizes common variations (e.g., 'genetic analysis' -> 'genetic_analysis')
        """
        if v is None:
            return None
        
        if isinstance(v, list):
            # Already a list, normalize each value
            return [cls._normalize_ebv_value(item) for item in v if item]
        
        if isinstance(v, str):
            # Split comma-separated values and normalize
            values = [cls._normalize_ebv_value(item.strip()) for item in v.split(',')]
            return [val for val in values if val]  # Filter out empty strings
        
        return v

    @staticmethod
    def _normalize_ebv_value(value: str) -> str:
        """Normalize EBV data type value to match enum format."""
        if not isinstance(value, str):
            return value
        
        normalized = value.lower().strip()
        # Remove 'ebv' prefix if present
        normalized = normalized.replace('ebv', '').strip()
        # Take only part before parentheses
        normalized = normalized.split('(')[0].strip()
        # Replace spaces and hyphens with underscores for enum matching
        normalized = normalized.replace(' ', '_').replace('-', '_')
        # Common normalizations
        replacements = {
            'analyses': 'analysis',
            'presence_only': 'presence_absence',
            'presence': 'presence_absence',
            'genetic_analysis': 'genetic_analysis',
        }
        for old, new in replacements.items():
            if normalized == old:
                normalized = new
                break
        
        # Convert back to enum format (with hyphens where appropriate)
        if normalized == 'presence_absence':
            return 'presence-absence'
        
        return normalized

    @field_validator('geospatial_info_dataset', mode='before')
    @classmethod
    def normalize_geospatial_enum(cls, v: Any) -> Optional[str]:
        """Normalize geospatial info value to match enum format."""
        if v is None:
            return None
        
        if not isinstance(v, str):
            return v
        
        normalized = v.lower().strip().replace(' ', '_').replace('-', '_')
        
        # Map common variations to valid enum values
        mapping = {
            'sample_coordinates': 'sample',
            'site_coordinates': 'site',
            'range_coordinates': 'range',
            'geographic_feature': 'geographic_features',
            'administrative_unit': 'administrative_units',
            'map': 'maps',
            'site_id': 'site_ids',
        }
        
        return mapping.get(normalized, normalized)

    @field_validator('spatial_range_km2', mode='before')
    @classmethod
    def coerce_spatial_range(cls, v: Any) -> Optional[float]:
        """Coerce spatial range to float, handling string inputs."""
        if v is None:
            return None
        
        if isinstance(v, (int, float)):
            return float(v)
        
        if isinstance(v, str):
            # Try to extract numeric value
            cleaned = v.strip().replace(',', '').replace(' ', '')
            try:
                return float(cleaned)
            except ValueError:
                return None
        
        return v

    @field_validator('temp_range_i', 'temp_range_f', mode='before')
    @classmethod
    def coerce_year_to_int(cls, v: Any) -> Optional[int]:
        """Coerce temporal range years to int, handling float inputs from pandas."""
        if v is None:
            return None
        
        if isinstance(v, float):
            return int(v)
        
        if isinstance(v, int):
            return v
        
        if isinstance(v, str):
            try:
                return int(float(v.strip()))
            except ValueError:
                return None
        
        return v

    class Config:
        """Pydantic model configuration."""
        use_enum_values = True  # Serialize enums as their values
        populate_by_name = True  # Allow field population by alias or name
