from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field

#
# 1) EBV Data Type (categorical)
#    - Lines 189–193 mention following the EBV classification (Table S1).
#    - We have only the example "abundance" in the table.
#    - Full set of EBV categories is unknown; placeholders are provided.
#

# 'non-EBV genetic analysis' 'presence-only' 'EBV genetic analysis' 'other'
#  'density' 'presence-absence' 'abundance' 'distribution' nan

class EBVDataType(str, Enum):
    ABUNDANCE = "abundance"
    PRESENCE_ABSENCE = "presence-absence"
    DENSITY = "density"
    DISTRIBUTION = "distribution"
    TRAITS = "traits"
    ECOSYSTEM_FUNCTION = "ecosystem_function"
    ECOSYSTEM_STRUCTURE = "ecosystem_structure"
    GENETIC_ANALYSIS = "genetic_analysis"
    TIME_SERIES = "time_series"
    UNKNOWN = "unknown"  # Insufficient info for complete list

#
# 2) Geospatial Information (lines 195–198)
#    - The text says “We classified geospatial data into distinct categories:
#      sample, site, or range coordinates, distribution, geographic features,
#      administrative units, maps, site IDs.”
#    - The table’s example is “sample coordinates” but labeled as continuous.
#    - We’ll treat it as categorical here (as per text) and flag possible values.
#
class GeospatialInfoType(str, Enum):
    SAMPLE = "sample"                       # sample coordinates
    SITE = "site"                           # site coordinates
    RANGE = "range"                         # range coordinates
    DISTRIBUTION = "distribution"           # species distribution models
    GEOGRAPHIC_FEATURES = "geographic_features"
    ADMINISTRATIVE_UNITS = "administrative_units"
    MAPS = "maps"
    SITE_IDS = "site_ids"
    UNKNOWN = "unknown"  # Fallback if category not matched

#
# 3) Feature Location (categorical)
#    - Lines 186–187 mention locations:
#      abstract, repository page text, article (source publication), or dataset.
#    - The table’s examples: “abstract,” “article text,” “repository.”
#    - We unify them into a single enum with a few typical values.
#
class FeatureLocation(str, Enum):
    ABSTRACT = "abstract"
    REPOSITORY_TEXT = "repository text"
    ARTICLE_TEXT = "article text"
    DATASET = "dataset"
    REPOSITORY = "repository"  # The table example uses "repository"
    UNKNOWN = "unknown"

class DatasetFeatures(BaseModel):
    """
    Pydantic model for dataset features essential to evaluating:
    - EBV data type categories (with time-series flag),
    - Spatiotemporal extent (geospatial and temporal information),
    - Taxon information,
    - Referred dataset sources,
    - Where each feature was found (dataset, repository page text, article text).

    Some Enums include placeholder or inferred values because
    the full classification was not provided.
    """

    # EBV data type (categorical)
    data_type: Optional[list[EBVDataType]] = Field(
        None,
        description="List of EBV data type categories (e.g. ['abundance', 'density'])."
    )

    # Geospatial info: we treat them as categorical (per text lines 195–198),
    # even though the table says 'continuous'. Values come from GeospatialInfoType.
    geospatial_info_dataset: Optional[GeospatialInfoType] = Field(
        None,
        description="Geospatial info in the dataset (sample, site, range, etc.)."
    )
    # Spatial range (continuous in the table), refactored to include unit
    spatial_range_km2: Optional[float] = Field(
        None,
        description="Spatial range in square kilometers (km^2) (e.g. 100000)."
    )
    # Temporal range (string in the table)
    temporal_range: Optional[str] = Field(
        None,
        description="Raw temporal range (e.g. 'from 1999 to 2008')."
    )
    temp_range_i: Optional[int] = Field(
        None,
        description="Start year of temporal range."
    )
    temp_range_f: Optional[int] = Field(
        None,
        description="End year of temporal range."
    )
    # Taxons (string)
    taxons: Optional[str] = Field(
        None,
        description="Taxons (e.g. 'black-legged tick')."
    )
    # Referred dataset source (string)
    referred_dataset: Optional[str] = Field(
        None,
        description="Referred dataset source (e.g. 'Ministère des Ressources naturelles...')."
    )


if __name__ == "__main__":
    # Example usage
    dataset_features = DatasetFeatures(
        data_type=["abundance", "density"],
        geospatial_info_dataset="sample",
        spatial_range_km2=100000,
        temporal_range="from 1999 to 2008",
        temp_range_i=1999,
        temp_range_f=2008,
        taxons="black-legged tick",
        referred_dataset="Ministère des Ressources naturelles..."
    )