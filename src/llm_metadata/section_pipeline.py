"""
Pipeline for classifying documents using GROBID-parsed sections.

This pipeline uses GROBID to parse PDF documents into structured sections,
selects relevant sections based on configuration, and builds prompts from
selected content for GPT classification.

Best for:
- When document structure matters
- Selective extraction (e.g., only Methods and Data sections)
- High-quality structured output from scientific papers
"""

from __future__ import annotations

import re
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
from llm_metadata.pdf_parsing import ParsedDocument, Section, process_pdf
from llm_metadata.schemas.chunk_metadata import SectionType
from llm_metadata.schemas import DatasetAbstractMetadata
from llm_metadata.section_normalize import classify_section


# =============================================================================
# Configuration
# =============================================================================

@dataclass
class SectionSelectionConfig:
    """Configuration for selecting relevant sections from parsed documents.

    Attributes:
        section_types: List of SectionType values to include (e.g., [ABSTRACT, METHODS])
        keywords: List of keywords to match in section titles (case-insensitive)
        include_abstract: Whether to always include abstract even if not in section_types
        include_all: If True, include all sections regardless of type/keyword matching
    """
    section_types: List[SectionType] = field(default_factory=lambda: [
        SectionType.ABSTRACT,
        SectionType.METHODS,
    ])
    keywords: List[str] = field(default_factory=lambda: [
        "data", "dataset", "survey", "site", "area", "species",
        "sampling", "collection", "study", "material", "method", "sample"
    ])
    include_abstract: bool = True
    include_all: bool = False

    def to_pattern(self) -> re.Pattern:
        """Convert keywords to regex pattern for matching."""
        if not self.keywords:
            return re.compile(r"(?!)")  # Never match
        pattern = "|".join(re.escape(kw) for kw in self.keywords)
        return re.compile(pattern, re.IGNORECASE)


@dataclass
class SectionClassificationConfig:
    """Configuration for section-based classification pipeline.
    
    Attributes:
        model: Model name (e.g., "gpt-5-mini")
        reasoning: Reasoning config for GPT-5 series
        max_output_tokens: Maximum tokens for output
        temperature: Temperature for non-reasoning models
        text_format: Pydantic model for structured output
        section_config: Section selection configuration
        grobid_url: GROBID service URL
        pdf_dir: Directory containing PDFs
        output_dir: Directory for output manifests
        max_workers: Maximum parallel workers
    """
    model: str = "gpt-5-mini"
    reasoning: Optional[Dict[str, str]] = field(default_factory=lambda: {"effort": "low"})
    max_output_tokens: int = 4096
    temperature: Optional[float] = None
    text_format: Type[BaseModel] = DatasetAbstractMetadata
    section_config: SectionSelectionConfig = field(default_factory=SectionSelectionConfig)
    grobid_url: str = "http://localhost:8070"
    pdf_dir: Path = field(default_factory=lambda: Path("data/pdfs"))
    output_dir: Path = field(default_factory=lambda: Path("artifacts/section_results"))
    max_workers: int = 5


# =============================================================================
# Manifest Schemas
# =============================================================================

class SectionInputRecord(BaseModel):
    """Input record for section-based classification."""
    id: str = Field(..., description="Unique identifier (e.g., DOI)")
    pdf_path: str = Field(..., description="Path to PDF file")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Optional metadata")

    class Config:
        populate_by_name = True


class SectionOutputRecord(BaseModel):
    """Output record with classification results."""
    id: str = Field(..., description="Unique identifier")
    pdf_path: str = Field(..., description="Path to PDF file")
    status: str = Field(..., description="Processing status (success, error)")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    
    # Token stats
    input_tokens: Optional[int] = Field(None, description="GPT input tokens")
    output_tokens: Optional[int] = Field(None, description="GPT output tokens")
    cost_usd: Optional[float] = Field(None, description="Estimated cost in USD")
    abstract_tokens: Optional[int] = Field(None, description="Abstract token count")
    fulltext_tokens: Optional[int] = Field(None, description="Full-text prompt token count")
    sections_used: Optional[int] = Field(None, description="Number of sections used")
    
    # Extraction result
    extraction: Optional[Dict[str, Any]] = Field(None, description="Extracted features")
    
    # Metadata
    metadata: Optional[Dict[str, Any]] = Field(None, description="Original metadata")
    processed_at: Optional[datetime] = Field(None, description="Processing timestamp")

    class Config:
        populate_by_name = True


# =============================================================================
# Section Selection Functions
# =============================================================================

def is_relevant_section(
    section: Section,
    config: SectionSelectionConfig
) -> bool:
    """Check if a section is relevant based on configuration.

    Args:
        section: Section to check
        config: Selection configuration

    Returns:
        True if section should be included
    """
    if config.include_all:
        return True

    section_type = classify_section(section.title)

    # Check by section type
    if section_type in config.section_types:
        return True

    # Check by keyword in title
    pattern = config.to_pattern()
    if pattern.search(section.title):
        return True

    return False


def collect_relevant_sections(
    sections: List[Section],
    config: SectionSelectionConfig,
    parent_relevant: bool = False
) -> List[Section]:
    """Recursively collect relevant sections from document tree.

    Args:
        sections: List of sections to filter
        config: Selection configuration
        parent_relevant: Whether parent section was relevant (inherit relevance)

    Returns:
        List of relevant sections (flattened)
    """
    relevant = []
    for sec in sections:
        is_rel = is_relevant_section(sec, config) or parent_relevant
        if is_rel and sec.text and sec.text.strip():
            relevant.append(sec)
        # Recurse into subsections (inherit parent relevance)
        relevant.extend(collect_relevant_sections(sec.subsections, config, is_rel))
    return relevant


def build_fulltext_prompt(
    doc: ParsedDocument,
    sections: List[Section],
    include_abstract: bool = True
) -> str:
    """Build full-text prompt from document and selected sections.

    Args:
        doc: Parsed document
        sections: List of relevant sections
        include_abstract: Whether to prepend abstract

    Returns:
        Formatted prompt string
    """
    parts = []

    # Abstract first
    if include_abstract and doc.abstract:
        parts.append("## Abstract\n")
        parts.append(doc.abstract)
        parts.append("\n\n")

    # Relevant sections with headers
    seen_titles = set()
    for sec in sections:
        # Skip duplicate abstract if already included
        if classify_section(sec.title) == SectionType.ABSTRACT and include_abstract:
            continue
        # Skip duplicate section titles
        if sec.title in seen_titles:
            continue
        seen_titles.add(sec.title)

        parts.append(f"## {sec.title}\n")
        parts.append(sec.text)
        parts.append("\n\n")

    return "".join(parts)


# =============================================================================
# Tasks
# =============================================================================

@task(retries=2, retry_delay_seconds=5)
def parse_pdf_task(
    pdf_path: Path,
    work_id: str,
    grobid_url: str = "http://localhost:8070"
) -> Optional[ParsedDocument]:
    """Parse a PDF using GROBID and return structured document.

    Args:
        pdf_path: Path to PDF file
        work_id: Work ID for the document
        grobid_url: GROBID service URL

    Returns:
        ParsedDocument or None if parsing fails
    """
    try:
        _, doc = process_pdf(
            pdf_path=pdf_path,
            work_id=work_id,
            grobid_url=grobid_url
        )
        return doc
    except Exception as e:
        print(f"GROBID parsing failed for {pdf_path}: {e}")
        return None


@task
def select_sections_task(
    doc: ParsedDocument,
    config: SectionSelectionConfig
) -> List[Section]:
    """Select relevant sections from parsed document.

    Args:
        doc: Parsed document
        config: Section selection configuration

    Returns:
        List of relevant sections
    """
    sections = collect_relevant_sections(doc.sections, config)

    # Ensure abstract is included if configured
    if config.include_abstract and doc.abstract:
        # Check if we already have abstract as a section
        has_abstract = any(
            classify_section(sec.title) == SectionType.ABSTRACT
            for sec in sections
        )
        if not has_abstract:
            # Create abstract section
            abstract_section = Section(
                title="Abstract",
                text=doc.abstract,
                subsections=[]
            )
            sections.insert(0, abstract_section)

    return sections


@task
def build_prompt_task(
    doc: ParsedDocument,
    sections: List[Section],
    include_abstract: bool = True
) -> str:
    """Build full-text prompt from document and sections.

    Args:
        doc: Parsed document
        sections: Selected sections
        include_abstract: Whether to include abstract

    Returns:
        Formatted prompt string
    """
    return build_fulltext_prompt(doc, sections, include_abstract)


@task(retries=2, retry_delay_seconds=10)
def classify_sections_task(
    prompt: str,
    config: SectionClassificationConfig
) -> Dict[str, Any]:
    """Classify section-based prompt using GPT.

    Args:
        prompt: Full-text prompt
        config: Configuration

    Returns:
        Classification result dict
    """
    result = classify_abstract(
        abstract=prompt,
        text_format=config.text_format,
        model=config.model,
        reasoning=config.reasoning,
        max_output_tokens=config.max_output_tokens,
        temperature=config.temperature
    )
    return result


@task
def process_section_record(
    input_record: SectionInputRecord,
    config: SectionClassificationConfig
) -> SectionOutputRecord:
    """Process a single PDF through section-based pipeline.

    Args:
        input_record: Input record
        config: Configuration

    Returns:
        Output record with results
    """
    pdf_path = Path(input_record.pdf_path)
    work_id = input_record.id.replace("/", "_")

    output = SectionOutputRecord(
        id=input_record.id,
        pdf_path=str(pdf_path),
        status="pending",
        metadata=input_record.metadata,
        processed_at=datetime.utcnow()
    )

    try:
        # Step 1: Parse PDF with GROBID
        doc = parse_pdf_task.fn(pdf_path, work_id, config.grobid_url)
        if doc is None:
            output.status = "error"
            output.error_message = "GROBID parsing failed"
            return output

        # Step 2: Select sections
        sections = select_sections_task.fn(doc, config.section_config)
        output.sections_used = len(sections)

        # Step 3: Build prompt
        prompt = build_prompt_task.fn(doc, sections, config.section_config.include_abstract)
        output.fulltext_tokens = count_tokens(prompt)
        output.abstract_tokens = count_tokens(doc.abstract) if doc.abstract else 0

        # Step 4: Classify
        result = classify_sections_task.fn(prompt, config)

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
def section_classification_flow(
    input_records: List[SectionInputRecord],
    config: Optional[SectionClassificationConfig] = None,
    output_manifest: Optional[Path] = None
) -> List[SectionOutputRecord]:
    """Batch section-based classification pipeline.

    Args:
        input_records: List of PDF records to process
        config: Configuration (uses defaults if None)
        output_manifest: Path to save output manifest (optional)

    Returns:
        List of output records
    """
    if config is None:
        config = SectionClassificationConfig()

    print(f"Processing {len(input_records)} PDFs with GROBID + section selection...")
    print(f"  GROBID URL: {config.grobid_url}")
    print(f"  Section types: {[st.value for st in config.section_config.section_types]}")

    # Process in parallel
    futures = process_section_record.map(
        input_records,
        [config] * len(input_records)
    )
    results = [f.result() for f in futures]

    # Summary
    success = sum(1 for r in results if r.status == "success")
    failed = sum(1 for r in results if r.status == "error")
    total_cost = sum(r.cost_usd for r in results if r.cost_usd)
    avg_sections = sum(r.sections_used for r in results if r.sections_used) / max(success, 1)

    print(f"Completed: {success} success, {failed} failed")
    print(f"Average sections used: {avg_sections:.1f}")
    print(f"Total cost: ${total_cost:.4f}")

    # Save manifest if requested
    if output_manifest:
        save_section_manifest(results, output_manifest)

    return results


@flow
def single_section_classification(
    pdf_path: Path,
    record_id: str,
    config: Optional[SectionClassificationConfig] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> SectionOutputRecord:
    """Classify a single PDF using section extraction.

    Args:
        pdf_path: Path to PDF file
        record_id: Unique identifier
        config: Configuration (uses defaults if None)
        metadata: Optional metadata to include

    Returns:
        Output record with results
    """
    if config is None:
        config = SectionClassificationConfig()

    input_record = SectionInputRecord(
        id=record_id,
        pdf_path=str(pdf_path),
        metadata=metadata
    )

    return process_section_record.fn(input_record, config)


# =============================================================================
# Manifest I/O
# =============================================================================

def load_section_manifest(manifest_path: Path) -> List[SectionInputRecord]:
    """Load section input manifest from CSV.

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

        record = SectionInputRecord(
            id=row["id"],
            pdf_path=str(pdf_path),
            metadata=metadata
        )
        records.append(record)

    return records


def save_section_manifest(
    records: List[SectionOutputRecord],
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

    # Example: Process PDFs with selective section extraction
    config = SectionClassificationConfig(
        model="gpt-5-mini",
        reasoning={"effort": "low"},
        section_config=SectionSelectionConfig(
            section_types=[SectionType.ABSTRACT, SectionType.METHODS],
            keywords=["data", "dataset", "sample", "collection"],
            include_abstract=True,
            include_all=False  # Only selected sections
        ),
        grobid_url="http://localhost:8070",
        pdf_dir=Path("data/pdfs/fuster"),
        output_dir=Path("artifacts/section_results")
    )

    manifest_path = Path("data/pdfs/fuster/manifest.csv")
    output_path = Path("artifacts/section_results/output_manifest.csv")

    if manifest_path.exists():
        input_records = load_section_manifest(manifest_path)
        results = section_classification_flow(
            input_records=input_records,
            config=config,
            output_manifest=output_path
        )
        print(f"\nProcessed {len(results)} PDFs with section extraction")
