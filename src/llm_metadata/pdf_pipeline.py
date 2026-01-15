"""
Pipeline for classifying raw PDF files without GROBID parsing.

This pipeline extracts text directly from PDF files using pypdf and
classifies the content. Faster and simpler than section-based extraction
but doesn't preserve document structure.
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
from llm_metadata.gpt_classify import (
    classify_abstract,
    classify_pdf_file,
    PDF_SYSTEM_MESSAGE,
)
from llm_metadata.schemas import DatasetAbstractMetadata


# =============================================================================
# Configuration
# =============================================================================

@dataclass
class PDFClassificationConfig:
    """Configuration for raw PDF classification pipeline.

    Attributes:
        model: Model name (e.g., "gpt-5-mini")
        reasoning: Reasoning config for GPT-5 series
        max_output_tokens: Maximum tokens for output
        temperature: Temperature for non-reasoning models
        text_format: Pydantic model for structured output
        max_pdf_pages: Maximum pages to extract (None = all pages, only used in text extraction mode)
        pdf_dir: Directory containing PDFs
        output_dir: Directory for output manifests
        max_workers: Maximum parallel workers
        use_native_pdf: If True, use OpenAI File API for native PDF understanding (text + visual).
                        If False, extract text with pypdf and classify text only.
        system_message: System prompt for classification (defaults vary by mode)
        cleanup_files: Whether to delete uploaded files from OpenAI after classification
    """
    model: str = "gpt-5-mini"
    reasoning: Optional[Dict[str, str]] = field(default_factory=lambda: {"effort": "low"})
    max_output_tokens: int = 4096
    temperature: Optional[float] = None
    text_format: Type[BaseModel] = DatasetAbstractMetadata
    max_pdf_pages: Optional[int] = None
    pdf_dir: Path = field(default_factory=lambda: Path("data/pdfs"))
    output_dir: Path = field(default_factory=lambda: Path("artifacts/pdf_results"))
    max_workers: int = 5
    use_native_pdf: bool = False
    system_message: Optional[str] = None  # Uses default for mode if None
    cleanup_files: bool = False


# =============================================================================
# Manifest Schemas
# =============================================================================

class PDFInputRecord(BaseModel):
    """Input record for PDF classification."""
    id: str = Field(..., description="Unique identifier (e.g., DOI)")
    pdf_path: str = Field(..., description="Path to PDF file")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Optional metadata")

    class Config:
        populate_by_name = True


class PDFOutputRecord(BaseModel):
    """Output record with classification results."""
    id: str = Field(..., description="Unique identifier")
    pdf_path: str = Field(..., description="Path to PDF file")
    status: str = Field(..., description="Processing status (success, error)")
    error_message: Optional[str] = Field(None, description="Error message if failed")

    # Token stats
    input_tokens: Optional[int] = Field(None, description="GPT input tokens")
    output_tokens: Optional[int] = Field(None, description="GPT output tokens")
    cost_usd: Optional[float] = Field(None, description="Estimated cost in USD")
    pdf_text_tokens: Optional[int] = Field(None, description="Extracted text token count (text mode only)")
    pages_extracted: Optional[int] = Field(None, description="Number of pages extracted (text mode only)")

    # Extraction result
    extraction: Optional[Dict[str, Any]] = Field(None, description="Extracted features")
    extraction_method: Optional[str] = Field(None, description="Method used: 'text_extraction' or 'openai_file_api'")
    file_id: Optional[str] = Field(None, description="OpenAI file ID (native PDF mode only)")

    # Metadata
    metadata: Optional[Dict[str, Any]] = Field(None, description="Original metadata")
    processed_at: Optional[datetime] = Field(None, description="Processing timestamp")

    class Config:
        populate_by_name = True


# =============================================================================
# Tasks
# =============================================================================

@task(retries=2, retry_delay_seconds=5)
def extract_pdf_text_task(
    pdf_path: Path,
    max_pages: Optional[int] = None
) -> Optional[str]:
    """Extract text from PDF file.
    
    Args:
        pdf_path: Path to PDF file
        max_pages: Optional limit on pages to extract
        
    Returns:
        Extracted text or None if extraction fails
    """
    try:
        return extract_text_from_pdf(pdf_path, max_pages=max_pages)
    except Exception as e:
        print(f"PDF extraction failed for {pdf_path}: {e}")
        return None


@task(retries=2, retry_delay_seconds=10)
def classify_pdf_text_task(
    text: str,
    config: PDFClassificationConfig
) -> Dict[str, Any]:
    """Classify extracted PDF text using GPT.

    Args:
        text: Extracted text
        config: Configuration

    Returns:
        Classification result dict
    """
    from llm_metadata.gpt_classify import SYSTEM_MESSAGE

    system_message = config.system_message or SYSTEM_MESSAGE
    result = classify_abstract(
        abstract=text,
        system_message=system_message,
        text_format=config.text_format,
        model=config.model,
        reasoning=config.reasoning,
        max_output_tokens=config.max_output_tokens,
        temperature=config.temperature
    )
    return result


@task(retries=2, retry_delay_seconds=10)
def classify_pdf_native_task(
    pdf_path: Path,
    config: PDFClassificationConfig
) -> Dict[str, Any]:
    """Classify PDF using OpenAI File API with native PDF understanding.

    Args:
        pdf_path: Path to PDF file
        config: Configuration

    Returns:
        Classification result dict with file_id and extraction_method
    """
    system_message = config.system_message or PDF_SYSTEM_MESSAGE
    result = classify_pdf_file(
        pdf_path=pdf_path,
        system_message=system_message,
        text_format=config.text_format,
        model=config.model,
        reasoning=config.reasoning,
        max_output_tokens=config.max_output_tokens,
        temperature=config.temperature,
        cleanup_file=config.cleanup_files,
    )
    return result


@task
def process_pdf_record(
    input_record: PDFInputRecord,
    config: PDFClassificationConfig
) -> PDFOutputRecord:
    """Process a single PDF through extraction and classification.

    Supports two modes:
    - Text extraction mode (use_native_pdf=False): Extract text with pypdf, classify text
    - Native PDF mode (use_native_pdf=True): Upload to OpenAI File API, use native PDF understanding

    Args:
        input_record: Input record
        config: Configuration

    Returns:
        Output record with results
    """
    pdf_path = Path(input_record.pdf_path)

    output = PDFOutputRecord(
        id=input_record.id,
        pdf_path=str(pdf_path),
        status="pending",
        metadata=input_record.metadata,
        processed_at=datetime.utcnow()
    )

    try:
        if config.use_native_pdf:
            # Native PDF mode: Upload to OpenAI and use native PDF understanding
            result = classify_pdf_native_task.fn(pdf_path, config)

            # Extract usage stats
            if result.get("usage_cost"):
                output.input_tokens = result["usage_cost"].get("input_tokens")
                output.output_tokens = result["usage_cost"].get("output_tokens")
                output.cost_usd = result["usage_cost"].get("total_cost")

            # Extract features
            if result.get("output"):
                output.extraction = result["output"].model_dump(mode="python")

            output.extraction_method = result.get("extraction_method", "openai_file_api")
            output.file_id = result.get("file_id")
            output.status = "success"

        else:
            # Text extraction mode: Extract text from PDF, then classify
            text = extract_pdf_text_task.fn(pdf_path, max_pages=config.max_pdf_pages)

            if not text or not text.strip():
                output.status = "error"
                output.error_message = "No text extracted from PDF"
                return output

            # Count tokens
            output.pdf_text_tokens = count_tokens(text)

            # Estimate pages extracted (rough estimate from token count)
            # Assuming ~2000 tokens per page on average
            output.pages_extracted = min(
                config.max_pdf_pages or 999,
                max(1, output.pdf_text_tokens // 2000)
            )

            # Classify
            result = classify_pdf_text_task.fn(text, config)

            # Extract usage stats
            if result.get("usage_cost"):
                output.input_tokens = result["usage_cost"].get("input_tokens")
                output.output_tokens = result["usage_cost"].get("output_tokens")
                output.cost_usd = result["usage_cost"].get("total_cost")

            # Extract features
            if result.get("output"):
                output.extraction = result["output"].model_dump(mode="python")

            output.extraction_method = "text_extraction"
            output.status = "success"

    except Exception as e:
        output.status = "error"
        output.error_message = str(e)

    return output


# =============================================================================
# Flows
# =============================================================================

@flow(task_runner=ThreadPoolTaskRunner(max_workers=5))
def pdf_classification_flow(
    input_records: List[PDFInputRecord],
    config: Optional[PDFClassificationConfig] = None,
    output_manifest: Optional[Path] = None
) -> List[PDFOutputRecord]:
    """Batch PDF classification pipeline.

    Args:
        input_records: List of PDF records to process
        config: Configuration (uses defaults if None)
        output_manifest: Path to save output manifest (optional)

    Returns:
        List of output records
    """
    if config is None:
        config = PDFClassificationConfig()

    mode_str = "native PDF (OpenAI File API)" if config.use_native_pdf else "text extraction"
    print(f"Processing {len(input_records)} PDFs using {mode_str} mode...")
    print(f"  Model: {config.model}")
    if not config.use_native_pdf and config.max_pdf_pages:
        print(f"  Limiting extraction to {config.max_pdf_pages} pages per PDF")

    # Process in parallel
    futures = process_pdf_record.map(
        input_records,
        [config] * len(input_records)
    )
    results = [f.result() for f in futures]

    # Summary
    success = sum(1 for r in results if r.status == "success")
    failed = sum(1 for r in results if r.status == "error")
    total_cost = sum(r.cost_usd for r in results if r.cost_usd)

    print(f"\nCompleted: {success} success, {failed} failed")
    print(f"Total cost: ${total_cost:.4f}")

    if not config.use_native_pdf:
        avg_pages = sum(r.pages_extracted for r in results if r.pages_extracted) / max(success, 1)
        print(f"Average pages extracted: {avg_pages:.1f}")

    # Save manifest if requested
    if output_manifest:
        save_pdf_manifest(results, output_manifest)

    return results


@flow
def single_pdf_classification(
    pdf_path: Path,
    record_id: str,
    config: Optional[PDFClassificationConfig] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> PDFOutputRecord:
    """Classify a single PDF file.
    
    Args:
        pdf_path: Path to PDF file
        record_id: Unique identifier
        config: Configuration (uses defaults if None)
        metadata: Optional metadata to include
        
    Returns:
        Output record with results
    """
    if config is None:
        config = PDFClassificationConfig()
    
    input_record = PDFInputRecord(
        id=record_id,
        pdf_path=str(pdf_path),
        metadata=metadata
    )
    
    return process_pdf_record.fn(input_record, config)


# =============================================================================
# Manifest I/O
# =============================================================================

def load_pdf_manifest(manifest_path: Path) -> List[PDFInputRecord]:
    """Load PDF input manifest from CSV.
    
    Expected columns: id, pdf_path, [optional metadata columns]
    
    Args:
        manifest_path: Path to manifest CSV
        
    Returns:
        List of input records
    """
    df = pd.read_csv(manifest_path)
    records = []
    
    required_cols = {"id", "pdf_path"}
    if not required_cols.issubset(df.columns):
        raise ValueError(f"Manifest must have columns: {required_cols}")
    
    for _, row in df.iterrows():
        pdf_path = Path(row["pdf_path"])
        
        # Skip if PDF doesn't exist
        if not pdf_path.exists():
            print(f"Warning: PDF not found: {pdf_path}")
            continue
        
        # Extract metadata columns
        metadata_cols = [col for col in df.columns if col not in required_cols]
        metadata = {col: row[col] for col in metadata_cols if pd.notna(row[col])} if metadata_cols else None
        
        record = PDFInputRecord(
            id=row["id"],
            pdf_path=str(pdf_path),
            metadata=metadata
        )
        records.append(record)
    
    return records


def save_pdf_manifest(
    records: List[PDFOutputRecord],
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
# Convenience functions
# =============================================================================

def pdf_classification_from_directory(
    pdf_dir: Path,
    config: Optional[PDFClassificationConfig] = None,
    output_manifest: Optional[Path] = None,
    pattern: str = "*.pdf"
) -> List[PDFOutputRecord]:
    """Process all PDFs in a directory.
    
    Args:
        pdf_dir: Directory containing PDF files
        config: Configuration (uses defaults if None)
        output_manifest: Path to save output manifest (optional)
        pattern: File pattern for matching PDFs
        
    Returns:
        List of output records
    """
    if config is None:
        config = PDFClassificationConfig(pdf_dir=pdf_dir)
    
    # Find all PDFs
    pdf_files = list(pdf_dir.glob(pattern))
    print(f"Found {len(pdf_files)} PDF files in {pdf_dir}")
    
    # Create input records
    input_records = [
        PDFInputRecord(
            id=pdf.stem,  # Use filename without extension as ID
            pdf_path=str(pdf)
        )
        for pdf in pdf_files
    ]
    
    return pdf_classification_flow(
        input_records=input_records,
        config=config,
        output_manifest=output_manifest
    )


# =============================================================================
# Main entry point
# =============================================================================

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    
    # Example 1: Process from manifest
    config = PDFClassificationConfig(
        model="gpt-5-mini",
        reasoning={"effort": "low"},
        max_pdf_pages=10,  # Limit to first 10 pages
        pdf_dir=Path("data/pdfs/fuster"),
        output_dir=Path("artifacts/pdf_results")
    )
    
    manifest_path = Path("data/pdfs/fuster/manifest.csv")
    output_path = Path("artifacts/pdf_results/output_manifest.csv")
    
    if manifest_path.exists():
        input_records = load_pdf_manifest(manifest_path)
        results = pdf_classification_flow(
            input_records=input_records,
            config=config,
            output_manifest=output_path
        )
        print(f"\nProcessed {len(results)} PDFs from manifest")
    
    # Example 2: Process all PDFs in directory
    # results = pdf_classification_from_directory(
    #     pdf_dir=Path("data/pdfs/fuster"),
    #     config=config,
    #     output_manifest=Path("artifacts/pdf_results/directory_output.csv")
    # )
