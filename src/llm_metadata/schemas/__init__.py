"""
Pydantic schemas for ecological dataset metadata extraction.

This package contains schema definitions for different metadata extraction approaches:
- abstract_metadata: High-level metadata extracted from dataset abstracts using LLMs
- fuster_features: Detailed feature extraction following EBV classification framework
- validation: Two-layer validation system (pandera + Pydantic) for data wrangling
- openalex_work: Scientific paper metadata from OpenAlex for Quebec researcher tracking
"""

from llm_metadata.species_parsing import ParsedTaxon
from llm_metadata.schemas.abstract_metadata import (
    DatasetAbstractMetadata,
    DEFAULT_DATASET_CATEGORIES,
)
from llm_metadata.schemas.fuster_features import (
    DatasetFeatures,
    DatasetFeaturesNormalized,
    DataSource,
    EBVDataType,
    GeospatialInfoType,
    FeatureLocation,
)
from llm_metadata.schemas.validation import (
    DataFrameValidator,
    ValidationReport,
    ValidationError,
    ErrorType,
)
from llm_metadata.schemas.openalex_work import (
    OpenAlexWork,
    OpenAlexAuthor,
    work_dict_to_model,
    works_to_dict_list,
)
from llm_metadata.schemas.data_paper import (
    DataPaperRecord,
    DataPaperManifest,
)


__all__ = [
    # Species parsing
    "ParsedTaxon",
    # Abstract metadata
    "DatasetAbstractMetadata",
    "DEFAULT_DATASET_CATEGORIES",
    # Fuster features
    "DatasetFeatures",
    "DatasetFeaturesNormalized",
    "DataSource",
    "EBVDataType",
    "GeospatialInfoType",
    "FeatureLocation",
    # Validation
    "DataFrameValidator",
    "ValidationReport",
    "ValidationError",
    "ErrorType",
    "AnnotationsDataFrameSchema",
    # OpenAlex work metadata
    "OpenAlexWork",
    "OpenAlexAuthor",
    "work_dict_to_model",
    "works_to_dict_list",
    # Data paper manifest
    "DataPaperRecord",
    "DataPaperManifest",
]
