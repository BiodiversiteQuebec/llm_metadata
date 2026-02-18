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
import re
import pandas as pd

from pydantic import BaseModel, Field, field_validator, model_validator


# Vocabulary normalization mappings for manual annotations
# Maps free-text values to controlled vocabulary enums
DATA_TYPE_MAPPING = {
    # Direct matches
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
    """
    Essential Biodiversity Variable (EBV) data type categories.

    Based on EBV classification framework (Table S1 in Fuster et al.).
    """
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
    """Dataset validation status."""
    YES = "yes"
    NO = "no"


class InvalidReason(str, Enum):
    """
    Reasons for invalid dataset classification.
    
    Includes categories observed in validation data.
    """
    LOCATION = "location"
    NON_RELEVANT = "non-relevant information"
    NON_FIELD_EXPERIMENT = "non-field experiment"
    NOT_IN_THE_FIELD = "not in the field"
    BIODIVERSITY_UNRELATED = "biodiversity-unrelated"
    MICROBIAL_COMMUNITY = "microbial community"
    OTHER = "other"


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


class DataSource(str, Enum):
    """
    Source repository from which a dataset record was obtained.

    Used for ground truth tracking and multi-source evaluation segmentation.
    """
    DRYAD = "dryad"
    ZENODO = "zenodo"
    SEMANTIC_SCHOLAR = "semantic_scholar"
    REFERENCED = "referenced"


class DatasetFeatures(BaseModel):
    """
    Schema for LLM-based feature extraction to describe biodiversity dataset (Fuster et al. EBV framework).

    This is the base extraction schema sent to ChatGPT for feature extraction tasks.
    It defines the structure and controlled vocabularies without validation/normalization logic.

    For validating manual annotations from Excel/CSV files, use DatasetFeaturesNormalized.

    **Key features:**
    - EBV data type categories with time-series indicators
    - Spatiotemporal extent (geospatial and temporal information)
    - Taxonomic information
    - Dataset source references
    - Optional evidence tracking (confidence, quotes, reasoning)

    Reference: Fuster et al. methodology for biodiversity dataset characterization.
    """

    # EBV data type (categorical)
    data_type: Optional[list[EBVDataType]] = Field(
        None,
        description="List of EBV data type categories (e.g. ['abundance', 'density'])."
    )

    # Geospatial information
    geospatial_info_dataset: Optional[list[GeospatialInfoType]] = Field(
        None,
        description="List of geospatial info categories in the dataset (sample, site, range, etc.)."
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
    species: Optional[list[str]] = Field(
        None,
        description="Extracted text as-is (copy pasted), not interpreted. Taxonomic groups, scientific names, common names, mixtures, or counts (e.g. 'Tamias striatus', 'raccoons', '41 fish mock species', '12 mammal, 199 ground-dwelling beetles')."
    )

    # Dataset references
    referred_dataset: Optional[str] = Field(
        None,
        description="Referred dataset source (e.g. 'Ministère des Ressources naturelles...')."
    )

    # Modulator features (boolean indicators for dataset characteristics)
    time_series: Optional[bool] = Field(
        None,
        description="Whether the dataset contains time-series data (repeated measurements over time)."
    )
    multispecies: Optional[bool] = Field(
        None,
        description="Whether the dataset covers multiple species."
    )
    threatened_species: Optional[bool] = Field(
        None,
        description="Whether the dataset includes threatened, endangered, or at-risk species."
    )
    new_species_science: Optional[bool] = Field(
        None,
        description="Whether the dataset describes species new to science (newly described taxa)."
    )
    new_species_region: Optional[bool] = Field(
        None,
        description="Whether the dataset reports species new to a particular region (range extensions or first records)."
    )
    bias_north_south: Optional[bool] = Field(
        None,
        description="Whether the dataset exhibits a geographic bias toward the Global North over the Global South."
    )

    # Validation fields
    valid_yn: Optional[ValidationStatus] = Field(
        None,
        description="Validation status (yes/no)."
    )
    reason_not_valid: Optional[str] = Field(
        None,
        description="Reason for invalid classification. See InvalidReason enum for common values."
    )

    # Data source tracking (for ground truth, not LLM extraction)
    source: Optional[DataSource] = Field(
        None,
        description="Source repository (dryad, zenodo, semantic_scholar, referenced). Used for ground truth tracking, not extracted by LLM."
    )

    class Config:
        """Pydantic model configuration."""
        use_enum_values = True  # Serialize enums as their values
        populate_by_name = True  # Allow field population by alias or name

class DatasetFeaturesNormalized(DatasetFeatures):
    """
    Extended schema with validation/normalization for manual annotations from Excel/CSV.

    Inherits all fields from DatasetFeatures and adds field validators to:
    - Clean NaN/NA values and placeholder strings
    - Normalize vocabulary (e.g., 'presence only' → 'presence-only')
    - Parse comma-separated lists
    - Coerce numeric types from pandas DataFrames
    - Handle European-style decimals (0,5 → 0.5)

    Use this for validating manually annotated datasets.
    Use base DatasetFeatureExtraction for LLM extraction prompts.
    """
    
    # --- Field Validators (for manual annotation normalization) ---
    
    @model_validator(mode='before')
    @classmethod
    def convert_nan_to_none(cls, data: Any) -> Any:
        """
        Clean raw data across all fields.
        - Converts NaN/NA and placeholder strings to None
        - Normalizes European-style decimals (0,5 -> 0.5)
        - Handles whitespace
        """
        if not isinstance(data, dict):
            return data
        
        null_placeholders = {
            "not given", "not_given", "no",
            "na", "n/a", "nan", "none",
            "", " ",
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
                s = value.strip()
                # 1. Placeholder check
                if s.lower() in null_placeholders:
                    cleaned[key] = None
                # 2. European decimal check (e.g., '0,5')
                elif ',' in s and s.replace(',', '').replace('.', '').replace('-', '').isdigit():
                    cleaned[key] = s.replace(',', '.')
                else:
                    cleaned[key] = s
            else:
                cleaned[key] = value
        return cleaned

    @field_validator('reason_not_valid', mode='before')
    @classmethod
    def normalize_reason_not_valid(cls, v: Any) -> Optional[str]:
        """
        Normalize validation reason values.
        Maps observed variations to standard categories.
        """
        if isinstance(v, str):
             v = v.strip()
             v_lower = v.lower()
             
             # Map aliases to standard values
             if v_lower == 'non biological':
                 return "biodiversity-unrelated"
             
             if v_lower == 'experiment':
                 return "non-field experiment"
                 
             if v_lower in ['micorbial community', 'microbial communities']:
                 return "microbial community"

             if v_lower.startswith('gut microbiota'):
                 return "microbial community"

             return v

        return v

    @field_validator('species', mode='before')
    @classmethod
    def parse_species_list(cls, v: Any) -> Optional[list[str]]:
        """
        Convert string input to list of species strings.
        Splits by comma if input is a string.
        """
        if v is None:
            return None
        
        raw_items = []
        if isinstance(v, list):
            raw_items = v
        elif isinstance(v, str):
            raw_items = [v]
        else:
            return [str(v)]
            
        final_values = []
        for item in raw_items:
            if isinstance(item, str):
                # Split comma-separated or semicolon-separated values and strip whitespace
                # Use regex to split by , or ;
                for part in re.split(r'[;,]', item):
                    cleaned = part.strip()
                    if cleaned:
                        final_values.append(cleaned)
            elif item:
                final_values.append(str(item))
        
        return final_values if final_values else None

    @field_validator('data_type', mode='before')
    @classmethod
    def parse_data_type_list(cls, v: Any) -> Optional[list[str]]:
        """
        Convert comma-separated strings to list of EBV data type values.
        
        Handles: 
        - 'abundance,density' -> ['abundance', 'density']
        - ['abundance', 'density, other'] -> ['abundance', 'density', 'other']
        """
        if v is None:
            return None
        
        raw_items = []
        if isinstance(v, list):
            raw_items = v
        elif isinstance(v, str):
            raw_items = [v]
        else:
            return v
            
        final_values = []
        for item in raw_items:
            if not item or not isinstance(item, str):
                if item: final_values.append(item)
                continue
            
            # Split comma-separated values and normalize each
            for part in item.split(','):
                norm = cls._normalize_ebv_value(part.strip())
                if norm:
                    final_values.append(norm)
        
        return final_values if final_values else None

    @staticmethod
    def _normalize_ebv_value(value: str) -> str:
        """Normalize EBV data type value to match enum format using vocabulary mapping."""
        if not isinstance(value, str):
            return value
        
        normalized = value.lower().strip()
        # Remove 'ebv' prefix if present
        normalized = normalized.replace('ebv', '').strip()
        # Take only part before parentheses
        normalized = normalized.split('(')[0].strip()
        
        # Handle common pluralizations and variations
        normalized = normalized.replace('analyses', 'analysis')
        normalized = normalized.replace('records', '').strip()  # 'presence records' -> 'presence'
        
        # Check vocabulary mapping first
        if normalized in DATA_TYPE_MAPPING:
            return DATA_TYPE_MAPPING[normalized]
        
        # Replace spaces and hyphens with underscores for enum matching
        normalized = normalized.replace(' ', '_').replace('-', '_')
        normalized = normalized.strip('_')
        
        # Mapping for full matches
        replacements = {
            'presence': 'presence_only',  # bare 'presence' maps to presence-only
            'presence_only': 'presence_only',
            'presence_absence': 'presence_absence',
            'genetic_analysis': 'genetic_analysis',
        }
        
        if normalized in replacements:
            normalized = replacements[normalized]
        
        # Convert back to enum format (with hyphens where appropriate for known values)
        if normalized == 'presence_absence':
            return 'presence-absence'
        if normalized == 'presence_only':
            return 'presence-only'
        
        return normalized

    @field_validator('geospatial_info_dataset', mode='before')
    @classmethod
    def parse_geospatial_list(cls, v: Any) -> Optional[list[str]]:
        """
        Convert comma or complex strings to list of GeospatialInfoType values.
        
        Handles:
        - 'site IDs, site coordinates' -> ['site_ids', 'site']
        - 'site coordinates geographic feature' -> ['site', 'geographic_features']
        """
        if v is None:
            return None
        
        raw_items = []
        if isinstance(v, list):
            raw_items = v
        elif isinstance(v, str):
            # First split by comma
            raw_items = [v]
        else:
            return v
            
        final_values = []
        for item in raw_items:
            if not item or not isinstance(item, str):
                if item: final_values.append(item)
                continue
            
            # Sub-split by comma
            for part in item.split(','):
                p = part.strip()
                if not p: continue
                
                # Check if it's a composite space-separated string that needs further splitting
                # e.g. 'site coordinates geographic feature'
                # Strategy: try to normalize the whole part first
                norm = cls._normalize_geospatial_value(p)
                
                # If normalization didn't map to a known value, try splitting by space
                # but only if it's not a known multi-word phrase
                known_phrases = {'site coordinates', 'sample coordinates', 'range coordinates', 
                                'geographic feature', 'geographic features',
                                'administrative unit', 'administrative units', 'site ids',
                                'distribution model'}
                
                if norm not in [e.value for e in GeospatialInfoType] and ' ' in p:
                    # Very simple heuristic: if it contains a known phrase, we might want to split around it
                    # But simpler: just try to normalize each word if it doesn't match a known phrase
                    words = p.split()
                    i = 0
                    while i < len(words):
                        # Try 2-word phrase
                        if i + 1 < len(words):
                            phrase = f"{words[i]} {words[i+1]}"
                            if phrase.lower() in known_phrases:
                                final_values.append(cls._normalize_geospatial_value(phrase))
                                i += 2
                                continue
                        
                        # Fallback to single word
                        word_norm = cls._normalize_geospatial_value(words[i])
                        if word_norm:
                            final_values.append(word_norm)
                        i += 1
                else:
                    if norm:
                        final_values.append(norm)
        
        # Deduplicate while preserving order
        seen = set()
        unique_values = []
        for val in final_values:
            if val not in seen:
                unique_values.append(val)
                seen.add(val)
                
        return unique_values if unique_values else None

    @staticmethod
    def _normalize_geospatial_value(v: str) -> str:
        """Normalize geospatial info value to match enum format using vocabulary mapping."""
        if not isinstance(v, str):
            return v
        
        # Check vocabulary mapping first (handles multi-word phrases)
        key = v.lower().strip()
        if key in GEO_TYPE_MAPPING:
            return GEO_TYPE_MAPPING[key]
        
        normalized = key.replace('-', '_').replace(' ', '_')
        normalized = normalized.strip('_')
        
        # Map common variations to valid enum values
        mapping = {
            'sample_coordinates': 'sample',
            'site_coordinates': 'site',
            'sites_ids': 'site_ids',
            'site_id': 'site_ids',
            'ids': 'site_ids',
            'id': 'site_ids',
            'range_coordinates': 'range',
            'geographic_feature': 'geographic_features',
            'administrative_unit': 'administrative_units',
            'distribution_model': 'distribution',
            'map': 'maps',
        }
        
        return mapping.get(normalized, normalized)

    @field_validator(
        'time_series', 'multispecies', 'threatened_species',
        'new_species_science', 'new_species_region', 'bias_north_south',
        mode='before',
    )
    @classmethod
    def coerce_bool(cls, v: Any) -> Optional[bool]:
        """
        Coerce various boolean representations to Optional[bool].

        Handles: True/False, "yes"/"no", "true"/"false", "1"/"0", 1/0, NaN → None.
        """
        if v is None:
            return None
        if isinstance(v, bool):
            return v
        if isinstance(v, (int, float)):
            if isinstance(v, float) and (math.isnan(v) or pd.isna(v)):
                return None
            return bool(v)
        if isinstance(v, str):
            s = v.strip().lower()
            if s in ('yes', 'true', '1'):
                return True
            if s in ('no', 'false', '0'):
                return False
            if s in ('', 'na', 'n/a', 'nan', 'none'):
                return None
        return None

    @field_validator('source', mode='before')
    @classmethod
    def coerce_source(cls, v: Any) -> Optional[str]:
        """Coerce source strings to DataSource enum values."""
        if v is None:
            return None
        if isinstance(v, (float, int)) and pd.isna(v):
            return None
        if isinstance(v, str):
            s = v.strip().lower()
            if s in ('', 'na', 'n/a', 'nan', 'none'):
                return None
            return s
        return v

    @field_validator('spatial_range_km2', mode='before')
    @classmethod
    def coerce_spatial_range(cls, v: Any) -> Optional[float]:
        """Coerce spatial range to float, handling string inputs and comma-decimal separators."""
        if v is None:
            return None
        
        if isinstance(v, (int, float)):
            if isinstance(v, float) and math.isnan(v):
                return None
            return float(v)
        
        if isinstance(v, str):
            # Try to extract numeric value, handle '0,5' -> 0.5
            cleaned = v.strip().replace(',', '.').replace(' ', '')
            try:
                return float(cleaned)
            except ValueError:
                return None
        
        return v

    @field_validator('temporal_range', mode='before')
    @classmethod
    def coerce_temporal_range(cls, v: Any) -> Optional[str]:
        """Coerce temporal range to string, handling numeric inputs from Excel/Pandas."""
        if v is None:
            return None
            
        if isinstance(v, (int, float)):
            if isinstance(v, float) and math.isnan(v):
                return None
            return str(int(v))
        
        return str(v).strip()

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
