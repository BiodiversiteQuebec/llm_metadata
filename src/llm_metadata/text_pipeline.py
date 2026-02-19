"""
Pipeline for classifying text directly (abstracts, pre-extracted text, etc.)

This is the simplest pipeline - takes text input and classifies it using GPT.
No PDF parsing, no section extraction, just direct text-to-classification.
"""

from __future__ import annotations

import pandas as pd
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

from prefect import flow, task
from prefect.task_runners import ThreadPoolTaskRunner
from pydantic import BaseModel, Field

from llm_metadata.chunking import count_tokens
from llm_metadata.gpt_classify import classify_abstract
from llm_metadata.prompts.abstract import SYSTEM_MESSAGE
from llm_metadata.schemas import DatasetAbstractMetadata


# =============================================================================
# Configuration
# =============================================================================

@dataclass
class TextClassificationConfig:
    """Configuration for direct text classification pipeline.
    
    Attributes:
        model: Model name (e.g., "gpt-5-mini")
        reasoning: Reasoning config for GPT-5 series
        max_output_tokens: Maximum tokens for output
        temperature: Temperature for non-reasoning models
        text_format: Pydantic model for structured output
        output_dir: Directory for output manifests
        max_workers: Maximum parallel workers
    """
    model: str = "gpt-5-mini"
    reasoning: Optional[Dict[str, str]] = field(default_factory=lambda: {"effort": "low"})
    max_output_tokens: int = 4096
    temperature: Optional[float] = None
    text_format: Type[BaseModel] = DatasetAbstractMetadata
    system_message: str = field(default_factory=lambda: SYSTEM_MESSAGE)
    output_dir: Path = field(default_factory=lambda: Path("artifacts/text_results"))
    max_workers: int = 5


# =============================================================================
# Manifest Schemas
# =============================================================================

class TextInputRecord(BaseModel):
    """Input record for text classification."""
    id: str = Field(..., description="Unique identifier (e.g., DOI, UUID)")
    text: str = Field(..., description="Text content to classify")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Optional metadata")

    class Config:
        populate_by_name = True


class TextOutputRecord(BaseModel):
    """Output record with classification results."""
    id: str = Field(..., description="Unique identifier")
    status: str = Field(..., description="Processing status (success, error)")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    
    # Token stats
    input_tokens: Optional[int] = Field(None, description="GPT input tokens")
    output_tokens: Optional[int] = Field(None, description="GPT output tokens")
    cost_usd: Optional[float] = Field(None, description="Estimated cost in USD")
    text_length: Optional[int] = Field(None, description="Input text length (characters)")
    
    # Extraction result
    extraction: Optional[Dict[str, Any]] = Field(None, description="Extracted features")
    
    # Metadata
    metadata: Optional[Dict[str, Any]] = Field(None, description="Original metadata")
    processed_at: Optional[datetime] = Field(None, description="Processing timestamp")

    class Config:
        populate_by_name = True


# =============================================================================
# Tasks
# =============================================================================

@task(retries=2, retry_delay_seconds=10)
def classify_text_task(
    text: str,
    config: TextClassificationConfig
) -> Dict[str, Any]:
    """Classify text using GPT.
    
    Args:
        text: Text content to classify
        config: Configuration
        
    Returns:
        Classification result dict
    """
    result = classify_abstract(
        abstract=text,
        system_message=config.system_message,
        text_format=config.text_format,
        model=config.model,
        reasoning=config.reasoning,
        max_output_tokens=config.max_output_tokens,
        temperature=config.temperature
    )
    return result


@task
def process_text_record(
    input_record: TextInputRecord,
    config: TextClassificationConfig
) -> TextOutputRecord:
    """Process a single text record through classification.
    
    Args:
        input_record: Input record
        config: Configuration
        
    Returns:
        Output record with results
    """
    output = TextOutputRecord(
        id=input_record.id,
        status="pending",
        metadata=input_record.metadata,
        processed_at=datetime.utcnow(),
        text_length=len(input_record.text)
    )
    
    try:
        result = classify_text_task.fn(input_record.text, config)
        
        # Extract usage stats
        if result.get("usage_cost"):
            output.input_tokens = result["usage_cost"].get("input_tokens")
            output.output_tokens = result["usage_cost"].get("output_tokens")
            output.cost_usd = result["usage_cost"].get("total_cost")
        
        # Extract features
        if result.get("output"):
            output.extraction = result["output"].model_dump(mode="python")
        
        output.status = "success"
        
    except Exception as e:
        output.status = "error"
        output.error_message = str(e)
    
    return output


# =============================================================================
# Flows
# =============================================================================

@flow(task_runner=ThreadPoolTaskRunner(max_workers=5))
def text_classification_flow(
    input_records: List[TextInputRecord],
    config: Optional[TextClassificationConfig] = None,
    output_manifest: Optional[Path] = None
) -> List[TextOutputRecord]:
    """Batch text classification pipeline.
    
    Args:
        input_records: List of text records to classify
        config: Configuration (uses defaults if None)
        output_manifest: Path to save output manifest (optional)
        
    Returns:
        List of output records
    """
    if config is None:
        config = TextClassificationConfig()
    
    print(f"Processing {len(input_records)} text records...")
    
    # Process in parallel
    futures = process_text_record.map(
        input_records,
        [config] * len(input_records)
    )
    results = [f.result() for f in futures]
    
    # Summary
    success = sum(1 for r in results if r.status == "success")
    failed = sum(1 for r in results if r.status == "error")
    total_cost = sum(r.cost_usd for r in results if r.cost_usd)
    
    print(f"Completed: {success} success, {failed} failed")
    print(f"Total cost: ${total_cost:.4f}")
    
    # Save manifest if requested
    if output_manifest:
        save_text_manifest(results, output_manifest)
    
    return results


@flow
def single_text_classification(
    text: str,
    record_id: str,
    config: Optional[TextClassificationConfig] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> TextOutputRecord:
    """Classify a single text string.
    
    Args:
        text: Text to classify
        record_id: Unique identifier
        config: Configuration (uses defaults if None)
        metadata: Optional metadata to include
        
    Returns:
        Output record with results
    """
    if config is None:
        config = TextClassificationConfig()
    
    input_record = TextInputRecord(
        id=record_id,
        text=text,
        metadata=metadata
    )
    
    return process_text_record.fn(input_record, config)


# =============================================================================
# Manifest I/O
# =============================================================================

def load_text_manifest(manifest_path: Path) -> List[TextInputRecord]:
    """Load text input manifest from CSV.
    
    Expected columns: id, text, [optional metadata columns]
    
    Args:
        manifest_path: Path to manifest CSV
        
    Returns:
        List of input records
    """
    df = pd.read_csv(manifest_path)
    records = []
    
    required_cols = {"id", "text"}
    if not required_cols.issubset(df.columns):
        raise ValueError(f"Manifest must have columns: {required_cols}")
    
    for _, row in df.iterrows():
        # Extract metadata columns (everything except id and text)
        metadata_cols = [col for col in df.columns if col not in required_cols]
        metadata = {col: row[col] for col in metadata_cols if pd.notna(row[col])} if metadata_cols else None
        
        record = TextInputRecord(
            id=row["id"],
            text=row["text"],
            metadata=metadata
        )
        records.append(record)
    
    return records


def save_text_manifest(
    records: List[TextOutputRecord],
    output_path: Path
) -> None:
    """Save output manifest to CSV.
    
    Args:
        records: List of output records
        output_path: Path to output CSV
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Convert to dicts, flattening extraction
    rows = []
    for rec in records:
        row = rec.model_dump(exclude={"extraction", "metadata"})
        
        # Add extraction fields with prefix
        if rec.extraction:
            for key, val in rec.extraction.items():
                row[f"extraction_{key}"] = val
        
        # Add metadata fields with prefix
        if rec.metadata:
            for key, val in rec.metadata.items():
                row[f"metadata_{key}"] = val
        
        rows.append(row)
    
    df = pd.DataFrame(rows)
    df.to_csv(output_path, index=False)
    print(f"Saved output manifest to {output_path} ({len(records)} records)")


# =============================================================================
# Main entry point
# =============================================================================

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    
    # Example: Classify some abstracts
    texts = [
        {
            "id": "example_1",
            "text": "We collected genetic samples from 150 individuals across 5 populations...",
            "metadata": {"source": "test", "year": 2024}
        },
        {
            "id": "example_2",
            "text": "Field surveys were conducted in Quebec from 2020-2022...",
            "metadata": {"source": "test", "year": 2024}
        }
    ]
    
    input_records = [TextInputRecord(**t) for t in texts]
    
    config = TextClassificationConfig(
        model="gpt-5-mini",
        reasoning={"effort": "low"}
    )
    
    results = text_classification_flow(
        input_records=input_records,
        config=config,
        output_manifest=Path("artifacts/text_results/example_output.csv")
    )
    
    print(f"\nProcessed {len(results)} texts")
