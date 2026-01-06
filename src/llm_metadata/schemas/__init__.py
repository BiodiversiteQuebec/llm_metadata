"""
Pydantic schemas for ecological dataset metadata extraction.

This package contains schema definitions for different metadata extraction approaches:
- abstract_metadata: High-level metadata extracted from dataset abstracts using LLMs
- fuster_features: Detailed feature extraction following EBV classification framework
- validation: Two-layer validation system (pandera + Pydantic) for data wrangling
"""

from llm_metadata.schemas.abstract_metadata import (
    DatasetAbstractMetadata,
    DEFAULT_DATASET_CATEGORIES,
)
from llm_metadata.schemas.fuster_features import (
    DatasetFeatureExtraction,
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


__all__ = [
    # Abstract metadata
    "DatasetAbstractMetadata",
    "DEFAULT_DATASET_CATEGORIES",
    # Fuster features
    "DatasetFeatureExtraction",
    "EBVDataType",
    "GeospatialInfoType",
    "FeatureLocation",
    # Validation
    "DataFrameValidator",
    "ValidationReport",
    "ValidationError",
    "ErrorType",
    "AnnotationsDataFrameSchema",
]
