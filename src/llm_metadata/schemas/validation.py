"""
Validation utilities for ecological dataset metadata.

This module provides a robust validation system using Pydantic for 
row-level semantic validation with structured error reporting.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

import pandas as pd
from pydantic import ValidationError as PydanticValidationError

from llm_metadata.logging_utils import logger

from llm_metadata.schemas.fuster_features import (
    DatasetFeatures,
    EBVDataType,
    GeospatialInfoType,
)


class ErrorType(str, Enum):
    """Classification of validation errors."""
    SCHEMA_ERROR = "schema_error"  # Field type/missing field issues
    DATA_ERROR = "data_error"  # Invalid values (NaN, wrong enum, etc.)


@dataclass
class ValidationError:
    """
    Structured validation error with provenance and suggested fix.
    
    Attributes:
        row_index: Index of the row in the DataFrame (None for column-level errors)
        field: Name of the field that failed validation
        raw_value: Original value that caused the error
        error_type: Classification as SCHEMA_ERROR or DATA_ERROR
        message: Human-readable error description
        suggested_fix: Optional suggestion for correcting the error
    """
    row_index: Any  # DataFrame index can be any hashable type
    field: str
    raw_value: Any
    error_type: ErrorType
    message: str
    suggested_fix: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for DataFrame construction."""
        return {
            "row_index": self.row_index,
            "field": self.field,
            "raw_value": repr(self.raw_value),
            "error_type": self.error_type.value,
            "message": self.message,
            "suggested_fix": self.suggested_fix or "",
        }


@dataclass
class ValidationReport:
    """
    Comprehensive validation report with valid/invalid rows and error details.
    
    Attributes:
        valid_rows: List of successfully validated DatasetFeatureExtraction objects
        valid_indices: Original DataFrame indices of valid rows
        invalid_rows: List of dictionaries containing invalid row data
        invalid_indices: Original DataFrame indices of invalid rows
        errors: List of ValidationError objects with detailed error info
        warnings: List of warning messages (e.g., coerced enum values)
    """
    valid_rows: list[DatasetFeatures] = field(default_factory=list)
    valid_indices: list[Any] = field(default_factory=list)
    invalid_rows: list[dict] = field(default_factory=list)
    invalid_indices: list[Any] = field(default_factory=list)
    errors: list[ValidationError] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def summary(self) -> str:
        """Generate a human-readable summary of validation results."""
        total = len(self.valid_rows) + len(self.invalid_rows)
        valid_pct = (len(self.valid_rows) / total * 100) if total > 0 else 0
        
        # Count errors by type
        schema_errors = sum(1 for e in self.errors if e.error_type == ErrorType.SCHEMA_ERROR)
        data_errors = sum(1 for e in self.errors if e.error_type == ErrorType.DATA_ERROR)
        
        # Count errors by field
        field_counts = {}
        for e in self.errors:
            field_counts[e.field] = field_counts.get(e.field, 0) + 1
        
        lines = [
            "=" * 50,
            "VALIDATION REPORT",
            "=" * 50,
            f"Total rows:     {total}",
            f"Valid rows:     {len(self.valid_rows)} ({valid_pct:.1f}%)",
            f"Invalid rows:   {len(self.invalid_rows)}",
            "",
            "Error Breakdown:",
            f"  Type/Schema errors: {schema_errors}",
            f"  Data/Value errors:  {data_errors}",
            "",
            "Errors by Field:",
        ]
        
        for fld, count in sorted(field_counts.items(), key=lambda x: -x[1]):
            lines.append(f"  {fld}: {count}")
        
        if self.warnings:
            lines.extend(["", f"Warnings: {len(self.warnings)}"])
        
        lines.append("=" * 50)
        return "\n".join(lines)

    def errors_to_dataframe(self) -> pd.DataFrame:
        """Convert errors to a DataFrame."""
        if not self.errors:
            return pd.DataFrame(columns=[
                "row_index", "field", "raw_value", "error_type", "message", "suggested_fix"
            ])
        return pd.DataFrame([e.to_dict() for e in self.errors])

    def invalid_rows_to_dataframe(self) -> pd.DataFrame:
        """Convert invalid rows to a DataFrame."""
        if not self.invalid_rows:
            return pd.DataFrame()
        df = pd.DataFrame(self.invalid_rows)
        df.index = self.invalid_indices
        return df

    def valid_rows_to_dataframe(self) -> pd.DataFrame:
        """Convert valid rows to a DataFrame."""
        if not self.valid_rows:
            return pd.DataFrame()
        df = pd.DataFrame([row.model_dump() for row in self.valid_rows])
        df.index = self.valid_indices
        return df


# Valid enum values for suggestion generation
VALID_EBV_VALUES = [e.value for e in EBVDataType]
VALID_GEOSPATIAL_VALUES = [e.value for e in GeospatialInfoType]


def _suggest_enum_fix(value: str, valid_values: list[str]) -> Optional[str]:
    """Suggest the closest valid enum value."""
    if not isinstance(value, str):
        return None
    
    value_lower = value.lower().strip().replace("-", "_").replace(" ", "_")
    
    for valid in valid_values:
        if value_lower == valid.lower().replace("-", "_"):
            return f"Use '{valid}'"
    
    for valid in valid_values:
        if value_lower in valid.lower() or valid.lower() in value_lower:
            return f"Consider '{valid}'"
    
    return f"Valid values: {', '.join(valid_values[:5])}..."


class DataFrameValidator:
    """
    Efficient validator for ecological dataset DataFrames using Pydantic.
    """
    
    def __init__(
        self,
        model: type = DatasetFeatures,
        strict: bool = False,
    ):
        """
        Initialize the validator.
        """
        self.model = model
        self.strict = strict

    def validate(self, df: pd.DataFrame) -> ValidationReport:
        """
        Validate a DataFrame against the Pydantic model.
        """
        report = ValidationReport()
        
        for idx, row in df.iterrows():
            # Convert row to dict. NaN values are kept; Pydantic model handles them.
            row_dict = row.to_dict()
            
            try:
                # Pydantic's internal validators now handle all pre-cleaning.
                validated_model = self.model(**row_dict)
                report.valid_rows.append(validated_model)
                report.valid_indices.append(idx)
                
            except PydanticValidationError as e:
                report.invalid_rows.append(row_dict)
                report.invalid_indices.append(idx)
                
                # Extract detailed errors from Pydantic
                for error in e.errors():
                    field_name = ".".join(str(loc) for loc in error["loc"])
                    raw_loc = error["loc"][0] if error["loc"] else None
                    raw_value = row_dict.get(raw_loc) if raw_loc in row_dict else None
                    
                    error_type = ErrorType.DATA_ERROR
                    suggested_fix = None
                    
                    if "enum" in error["type"].lower() or "literal" in error["type"].lower():
                        if "geospatial_info_dataset" in field_name:
                            suggested_fix = _suggest_enum_fix(str(raw_value), VALID_GEOSPATIAL_VALUES)
                        elif "data_type" in field_name:
                            suggested_fix = _suggest_enum_fix(str(raw_value), VALID_EBV_VALUES)
                    elif "type" in error["type"].lower():
                        error_type = ErrorType.SCHEMA_ERROR
                        suggested_fix = f"Expected type for field '{field_name}'"
                    
                    report.errors.append(ValidationError(
                        row_index=idx,
                        field=field_name,
                        raw_value=raw_value,
                        error_type=error_type,
                        message=error["msg"],
                        suggested_fix=suggested_fix,
                    ))
                
                if self.strict:
                    return report
        
        logger.info(
            f"Validation complete: {len(report.valid_rows)} valid, "
            f"{len(report.invalid_rows)} invalid, {len(report.errors)} errors"
        )
        return report

    def validate_and_coerce(self, df: pd.DataFrame) -> tuple[pd.DataFrame, ValidationReport]:
        """
        Validate DataFrame and return coerced valid rows as DataFrame.
        """
        report = self.validate(df)
        clean_df = report.valid_rows_to_dataframe()
        return clean_df, report
