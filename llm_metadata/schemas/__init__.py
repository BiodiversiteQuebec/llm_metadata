"""
Pydantic schemas for ecological dataset metadata extraction.

This package contains schema definitions for different metadata extraction approaches:
- abstract_metadata: High-level metadata extracted from dataset abstracts using LLMs
- fuster_features: Detailed feature extraction following EBV classification framework
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

__all__ = [
    "DatasetAbstractMetadata",
    "DEFAULT_DATASET_CATEGORIES",
    "DatasetFeatureExtraction",
    "EBVDataType",
    "GeospatialInfoType",
    "FeatureLocation",
]
