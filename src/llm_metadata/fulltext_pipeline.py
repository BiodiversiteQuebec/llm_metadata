"""
⚠️ DEPRECATED: This module is deprecated and will be removed in a future version.

This module has been split into three focused pipelines:
1. text_pipeline.py - Direct text classification
2. pdf_pipeline.py - Raw PDF extraction and classification
3. section_pipeline.py - GROBID-based section extraction and classification

For a unified interface, use:
    from llm_metadata.pipelines import classify

Migration examples:

    Old (raw PDF):
        config = FulltextPipelineConfig(
            gpt_config=GPTClassifyConfig(extraction_method="raw_pdf")
        )
        results = fulltext_extraction_pipeline(config=config)
    
    New (PDF pipeline):
        from llm_metadata.pdf_pipeline import PDFClassificationConfig, pdf_classification_flow
        config = PDFClassificationConfig()
        results = pdf_classification_flow(input_records, config)
    
    Old (GROBID sections):
        config = FulltextPipelineConfig(
            gpt_config=GPTClassifyConfig(extraction_method="grobid")
        )
        results = fulltext_extraction_pipeline(config=config)
    
    New (Section pipeline):
        from llm_metadata.section_pipeline import SectionClassificationConfig, section_classification_flow
        config = SectionClassificationConfig()
        results = section_classification_flow(input_records, config)

See docs/pipelines_guide.md for complete documentation.

---

Original docstring:
Prefect pipeline for full-text extraction using GROBID-parsed PDFs.

This module provides batch processing capabilities for extracting structured metadata
from scientific PDFs using full-text content (not just abstracts).

Features:
- GROBID-based PDF parsing with section extraction
- Configurable section selection (by type and/or keywords)
- Full-text prompt building for LLM classification
- Batch processing with parallel execution
- Input/output manifest generation
"""

from __future__ import annotations

import re
import warnings
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

import pandas as pd
from prefect import flow, task
from prefect.task_runners import ThreadPoolTaskRunner
from pydantic import BaseModel, Field

warnings.warn(
    "fulltext_pipeline.py is deprecated. Use text_pipeline.py, pdf_pipeline.py, "
    "or section_pipeline.py instead. See docs/pipelines_guide.md for migration guide.",
    DeprecationWarning,
    stacklevel=2
)

from llm_metadata.chunking import count_tokens
from llm_metadata.gpt_classify import classify_abstract, classify_pdf, extract_text_from_pdf
from llm_metadata.pdf_parsing import ParsedDocument, Section, process_pdf
from llm_metadata.schemas.chunk_metadata import SectionType
from llm_metadata.schemas.fuster_features import DatasetFeatures
from llm_metadata.section_normalize import classify_section


# =============================================================================
# Configuration Dataclasses
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
        """Compile keywords into a case-insensitive regex pattern."""
        if not self.keywords:
            return re.compile(r"^$")  # Match nothing
        pattern = r"\b(" + "|".join(re.escape(k) for k in self.keywords) + r")\b"
        return re.compile(pattern, re.IGNORECASE)


@dataclass
class GPTClassifyConfig:
    """Configuration for GPT classification calls.

    Attributes:
        model: Model name (e.g., "gpt-5-mini")
        reasoning: Reasoning config for GPT-5 series (e.g., {"effort": "low"})
        max_output_tokens: Maximum tokens for output
        temperature: Temperature for non-reasoning models (None for reasoning models)
        extraction_method: Method for text extraction ('grobid' or 'raw_pdf')
        max_pdf_pages: Maximum pages to extract for raw_pdf method (None = all)
    """
    model: str = "gpt-5-mini"
    reasoning: Optional[Dict[str, str]] = field(default_factory=lambda: {"effort": "low"})
    max_output_tokens: int = 4096
    temperature: Optional[float] = None
    extraction_method: str = "grobid"  # 'grobid' or 'raw_pdf'
    max_pdf_pages: Optional[int] = None


@dataclass
class FulltextPipelineConfig:
    """Complete configuration for fulltext extraction pipeline.

    Attributes:
        section_config: Section selection configuration
        gpt_config: GPT classification configuration
        grobid_url: GROBID service URL
        pdf_dir: Directory containing PDFs
        output_dir: Directory for output manifests
        text_format: Pydantic model for structured output
        max_workers: Maximum parallel workers
    """
    section_config: SectionSelectionConfig = field(default_factory=SectionSelectionConfig)
    gpt_config: GPTClassifyConfig = field(default_factory=GPTClassifyConfig)
    grobid_url: str = "http://localhost:8070"
    pdf_dir: Path = field(default_factory=lambda: Path("data/pdfs/fuster"))
    output_dir: Path = field(default_factory=lambda: Path("artifacts/fulltext_results"))
    text_format: Type[BaseModel] = DatasetFeatures
    max_workers: int = 5


# =============================================================================
# Manifest Schemas
# =============================================================================

class FulltextInputRecord(BaseModel):
    """Input manifest record for a PDF to be processed."""
    article_doi: str = Field(..., description="Article DOI (used as work_id)")
    dataset_doi: Optional[str] = Field(None, description="Associated dataset DOI")
    pdf_path: str = Field(..., description="Path to PDF file")
    title: Optional[str] = Field(None, description="Article title")

    class Config:
        populate_by_name = True


class ParsedDocumentRecord(BaseModel):
    """Intermediate record after GROBID parsing (for staged pipeline)."""
    article_doi: str = Field(..., description="Article DOI")
    dataset_doi: Optional[str] = Field(None, description="Associated dataset DOI")
    pdf_path: str = Field(..., description="Path to PDF file")
    status: str = Field(..., description="Parsing status (success, error)")
    error_message: Optional[str] = Field(None, description="Error message if failed")

    # Parsed document data (serialized)
    document: Optional[ParsedDocument] = Field(None, description="Parsed document")

    # Token stats
    abstract_tokens: Optional[int] = Field(None, description="Abstract token count")
    total_section_tokens: Optional[int] = Field(None, description="Total tokens in all sections")
    section_count: Optional[int] = Field(None, description="Number of sections parsed")

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True


class PromptRecord(BaseModel):
    """Intermediate record with built prompt (for staged pipeline)."""
    article_doi: str = Field(..., description="Article DOI")
    dataset_doi: Optional[str] = Field(None, description="Associated dataset DOI")
    pdf_path: str = Field(..., description="Path to PDF file")
    status: str = Field(..., description="Status (success, error, skipped)")
    error_message: Optional[str] = Field(None, description="Error message if failed")

    # Prompt data
    prompt: Optional[str] = Field(None, description="Full-text prompt for classification")
    abstract_tokens: Optional[int] = Field(None, description="Abstract token count")
    fulltext_tokens: Optional[int] = Field(None, description="Full-text prompt token count")
    sections_used: Optional[int] = Field(None, description="Number of sections used")

    class Config:
        populate_by_name = True


class FulltextOutputRecord(BaseModel):
    """Output manifest record with extraction results."""
    article_doi: str = Field(..., description="Article DOI")
    dataset_doi: Optional[str] = Field(None, description="Associated dataset DOI")
    pdf_path: str = Field(..., description="Path to PDF file")
    status: str = Field(..., description="Processing status (success, error, skipped)")
    error_message: Optional[str] = Field(None, description="Error message if failed")

    # Token stats
    abstract_tokens: Optional[int] = Field(None, description="Abstract token count")
    fulltext_tokens: Optional[int] = Field(None, description="Full-text prompt token count")
    sections_used: Optional[int] = Field(None, description="Number of sections used")

    # GPT usage
    input_tokens: Optional[int] = Field(None, description="GPT input tokens")
    output_tokens: Optional[int] = Field(None, description="GPT output tokens")
    cost_usd: Optional[float] = Field(None, description="Estimated cost in USD")

    # Extraction result (flattened from DatasetFeatures or similar)
    extraction: Optional[Dict[str, Any]] = Field(None, description="Extracted features as dict")

    # Timestamps
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
# Prefect Tasks
# =============================================================================

@task(retries=2, retry_delay_seconds=5)
def extract_raw_pdf_text_task(
    pdf_path: Path,
    max_pages: Optional[int] = None
) -> Optional[str]:
    """Extract text from raw PDF without GROBID parsing.

    Args:
        pdf_path: Path to PDF file
        max_pages: Optional limit on pages to extract

    Returns:
        Extracted text or None if extraction fails
    """
    try:
        return extract_text_from_pdf(pdf_path, max_pages=max_pages)
    except Exception as e:
        print(f"Raw PDF extraction failed for {pdf_path}: {e}")
        return None


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
        print(f"Failed to parse {pdf_path}: {e}")
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
        has_abstract = any(
            classify_section(sec.title) == SectionType.ABSTRACT
            for sec in sections
        )
        if not has_abstract:
            abstract_section = Section(
                section_id=f"{doc.work_id}_abstract",
                title="ABSTRACT",
                level=1,
                text=doc.abstract,
                subsections=[],
                page_start=None,
                page_end=None
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
def classify_fulltext_task(
    prompt: str,
    gpt_config: GPTClassifyConfig,
    text_format: Type[BaseModel]
) -> Dict[str, Any]:
    """Classify full-text prompt using GPT.

    Args:
        prompt: Full-text prompt
        gpt_config: GPT configuration
        text_format: Pydantic model for output

    Returns:
        Classification result dict
    """
    result = classify_abstract(
        abstract=prompt,
        text_format=text_format,
        model=gpt_config.model,
        reasoning=gpt_config.reasoning,
        max_output_tokens=gpt_config.max_output_tokens,
        temperature=gpt_config.temperature
    )
    return result


@task
def process_single_pdf(
    input_record: FulltextInputRecord,
    config: FulltextPipelineConfig
) -> FulltextOutputRecord:
    """Process a single PDF through the full pipeline.

    Args:
        input_record: Input manifest record
        config: Pipeline configuration

    Returns:
        Output manifest record with results
    """
    pdf_path = Path(input_record.pdf_path)
    work_id = input_record.article_doi.replace("/", "_")

    # Initialize output record
    output = FulltextOutputRecord(
        article_doi=input_record.article_doi,
        dataset_doi=input_record.dataset_doi,
        pdf_path=str(pdf_path),
        status="pending",
        processed_at=datetime.utcnow()
    )

    try:
        if config.gpt_config.extraction_method == "raw_pdf":
            # Raw PDF extraction mode
            print(f"Extracting text from raw PDF: {pdf_path.name}")
            raw_text = extract_raw_pdf_text_task.fn(pdf_path, max_pages=config.gpt_config.max_pdf_pages)
            
            if not raw_text or not raw_text.strip():
                output.status = "error"
                output.error_message = "No text extracted from PDF"
                return output
            
            # Count tokens
            output.fulltext_tokens = count_tokens(raw_text)
            output.sections_used = 1  # Treating entire PDF as one section
            
            # Classify using raw text
            result = classify_fulltext_task.fn(raw_text, config.gpt_config, config.text_format)
            
            # Extract results
            if result.get("output"):
                output.extraction = result["output"].model_dump(mode="python")
            
            if result.get("usage_cost"):
                usage = result["usage_cost"]
                output.input_tokens = usage.get("input_tokens")
                output.output_tokens = usage.get("output_tokens")
                output.cost_usd = usage.get("total_cost")
            
            output.status = "success"
            
        else:
            # GROBID parsing mode (original behavior)
            # Step 1: Parse PDF
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
            result = classify_fulltext_task.fn(prompt, config.gpt_config, config.text_format)

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
# Manifest I/O
# =============================================================================

def load_input_manifest(manifest_path: Path) -> List[FulltextInputRecord]:
    """Load input manifest from CSV file.

    Args:
        manifest_path: Path to manifest CSV

    Returns:
        List of input records
    """
    df = pd.read_csv(manifest_path)
    records = []

    for _, row in df.iterrows():
        # Skip rows without PDF path
        if pd.isna(row.get("downloaded_pdf_path")) or row.get("status") != "downloaded":
            continue

        # Construct full PDF path
        pdf_path = Path(manifest_path).parent / row["downloaded_pdf_path"]
        if not pdf_path.exists():
            continue

        record = FulltextInputRecord(
            article_doi=row["article_doi"],
            dataset_doi=row.get("dataset_doi"),
            pdf_path=str(pdf_path),
            title=row.get("title")
        )
        records.append(record)

    return records


def save_output_manifest(
    records: List[FulltextOutputRecord],
    output_path: Path
) -> None:
    """Save output manifest to CSV file.

    Args:
        records: List of output records
        output_path: Path to output CSV
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Convert to dicts, flattening extraction
    rows = []
    for rec in records:
        row = rec.model_dump(exclude={"extraction"})
        # Add extraction fields with prefix
        if rec.extraction:
            for k, v in rec.extraction.items():
                # Convert lists to semicolon-separated strings
                if isinstance(v, list):
                    v = "; ".join(str(x) for x in v)
                row[f"ext_{k}"] = v
        rows.append(row)

    df = pd.DataFrame(rows)
    df.to_csv(output_path, index=False)
    print(f"Saved output manifest to {output_path} ({len(records)} records)")


# =============================================================================
# Prefect Flows
# =============================================================================

@flow(task_runner=ThreadPoolTaskRunner(max_workers=5))
def fulltext_extraction_pipeline(
    config: Optional[FulltextPipelineConfig] = None,
    input_manifest: Optional[Path] = None,
    input_records: Optional[List[FulltextInputRecord]] = None,
    pdf_paths: Optional[List[Path]] = None,
    output_manifest: Optional[Path] = None
) -> List[FulltextOutputRecord]:
    """Batch full-text extraction pipeline.

    Processes multiple PDFs through GROBID parsing and GPT classification.

    Args:
        config: Pipeline configuration (uses defaults if None)
        input_manifest: Path to input manifest CSV (optional)
        input_records: List of FulltextInputRecord objects (preferred for preserving DOI mappings)
        pdf_paths: List of PDF paths to process (alternative to manifest)
        output_manifest: Path to save output manifest (optional)

    Returns:
        List of output records
    """
    if config is None:
        config = FulltextPipelineConfig()

    # Build input records from various sources (priority: input_records > input_manifest > pdf_paths > pdf_dir)
    records: List[FulltextInputRecord] = []

    if input_records:
        records = input_records
        print(f"Using {len(records)} provided input records")
    elif input_manifest and input_manifest.exists():
        records = load_input_manifest(input_manifest)
        print(f"Loaded {len(records)} records from manifest")
    elif pdf_paths:
        for pdf_path in pdf_paths:
            # Extract DOI from filename (assumes format: doi_with_underscores.pdf)
            doi = pdf_path.stem.replace("_", "/")
            records.append(FulltextInputRecord(
                article_doi=doi,
                pdf_path=str(pdf_path)
            ))
        print(f"Created {len(records)} records from PDF paths")
    else:
        # Default: scan pdf_dir for all PDFs
        pdf_dir = config.pdf_dir
        if pdf_dir.exists():
            for pdf_path in pdf_dir.glob("*.pdf"):
                doi = pdf_path.stem.replace("_", "/")
                records.append(FulltextInputRecord(
                    article_doi=doi,
                    pdf_path=str(pdf_path)
                ))
            print(f"Found {len(records)} PDFs in {pdf_dir}")

    if not records:
        print("No input records to process")
        return []

    # Process PDFs in parallel
    print(f"Processing {len(records)} PDFs in parallel (max_workers=5)...")
    futures = process_single_pdf.map(
        records,
        [config] * len(records)
    )
    results = [f.result() for f in futures]

    # Summary
    success = sum(1 for r in results if r.status == "success")
    errors = sum(1 for r in results if r.status == "error")
    print(f"\nPipeline complete: {success} success, {errors} errors")

    # Save output manifest if specified
    if output_manifest:
        save_output_manifest(results, output_manifest)

    return results


@flow
def fulltext_extraction_single(
    pdf_path: Path,
    article_doi: str,
    dataset_doi: Optional[str] = None,
    config: Optional[FulltextPipelineConfig] = None
) -> FulltextOutputRecord:
    """Process a single PDF through the full-text extraction pipeline.

    Args:
        pdf_path: Path to PDF file
        article_doi: Article DOI
        dataset_doi: Optional dataset DOI
        config: Pipeline configuration

    Returns:
        Output record with extraction results
    """
    if config is None:
        config = FulltextPipelineConfig()

    input_record = FulltextInputRecord(
        article_doi=article_doi,
        dataset_doi=dataset_doi,
        pdf_path=str(pdf_path)
    )

    return process_single_pdf.fn(input_record, config)


# =============================================================================
# Separate Flows for Staged Pipeline
# =============================================================================

@task(retries=2, retry_delay_seconds=5)
def parse_pdf_to_record(
    input_record: FulltextInputRecord,
    grobid_url: str = "http://localhost:8070"
) -> ParsedDocumentRecord:
    """Parse a single PDF and return a ParsedDocumentRecord.

    Args:
        input_record: Input record with PDF path
        grobid_url: GROBID service URL

    Returns:
        ParsedDocumentRecord with parsed document or error
    """
    pdf_path = Path(input_record.pdf_path)
    work_id = input_record.article_doi.replace("/", "_")

    try:
        _, doc = process_pdf(
            pdf_path=pdf_path,
            work_id=work_id,
            grobid_url=grobid_url
        )

        # Calculate token stats
        abstract_tokens = count_tokens(doc.abstract) if doc.abstract else 0
        total_section_tokens = sum(
            count_tokens(sec.text) for sec in doc.sections if sec.text
        )

        return ParsedDocumentRecord(
            article_doi=input_record.article_doi,
            dataset_doi=input_record.dataset_doi,
            pdf_path=str(pdf_path),
            status="success",
            document=doc,
            abstract_tokens=abstract_tokens,
            total_section_tokens=total_section_tokens,
            section_count=len(doc.sections),
        )

    except Exception as e:
        return ParsedDocumentRecord(
            article_doi=input_record.article_doi,
            dataset_doi=input_record.dataset_doi,
            pdf_path=str(pdf_path),
            status="error",
            error_message=str(e),
        )


@task
def build_prompt_from_record(
    parsed_record: ParsedDocumentRecord,
    section_config: SectionSelectionConfig
) -> PromptRecord:
    """Build a prompt from a parsed document record.

    Args:
        parsed_record: Parsed document record
        section_config: Section selection configuration

    Returns:
        PromptRecord with built prompt
    """
    if parsed_record.status != "success" or not parsed_record.document:
        return PromptRecord(
            article_doi=parsed_record.article_doi,
            dataset_doi=parsed_record.dataset_doi,
            pdf_path=parsed_record.pdf_path,
            status="skipped",
            error_message=parsed_record.error_message or "No parsed document",
        )

    doc = parsed_record.document

    # Select sections
    sections = collect_relevant_sections(doc.sections, section_config)

    # Ensure abstract is included if configured
    if section_config.include_abstract and doc.abstract:
        has_abstract = any(
            classify_section(sec.title) == SectionType.ABSTRACT
            for sec in sections
        )
        if not has_abstract:
            abstract_section = Section(
                section_id=f"{doc.work_id}_abstract",
                title="ABSTRACT",
                level=1,
                text=doc.abstract,
                subsections=[],
                page_start=None,
                page_end=None
            )
            sections.insert(0, abstract_section)

    # Build prompt
    prompt = build_fulltext_prompt(doc, sections, section_config.include_abstract)

    return PromptRecord(
        article_doi=parsed_record.article_doi,
        dataset_doi=parsed_record.dataset_doi,
        pdf_path=parsed_record.pdf_path,
        status="success",
        prompt=prompt,
        abstract_tokens=parsed_record.abstract_tokens,
        fulltext_tokens=count_tokens(prompt),
        sections_used=len(sections),
    )


@task(retries=2, retry_delay_seconds=10)
def classify_prompt_record(
    prompt_record: PromptRecord,
    gpt_config: GPTClassifyConfig,
    text_format: Type[BaseModel]
) -> FulltextOutputRecord:
    """Classify a prompt and return extraction results.

    Args:
        prompt_record: Prompt record with text to classify
        gpt_config: GPT configuration
        text_format: Pydantic model for structured output

    Returns:
        FulltextOutputRecord with extraction results
    """
    if prompt_record.status != "success" or not prompt_record.prompt:
        return FulltextOutputRecord(
            article_doi=prompt_record.article_doi,
            dataset_doi=prompt_record.dataset_doi,
            pdf_path=prompt_record.pdf_path,
            status="skipped",
            error_message=prompt_record.error_message or "No prompt available",
            abstract_tokens=prompt_record.abstract_tokens,
            fulltext_tokens=prompt_record.fulltext_tokens,
            sections_used=prompt_record.sections_used,
            processed_at=datetime.utcnow(),
        )

    try:
        result = classify_abstract(
            abstract=prompt_record.prompt,
            text_format=text_format,
            model=gpt_config.model,
            reasoning=gpt_config.reasoning,
            max_output_tokens=gpt_config.max_output_tokens,
            temperature=gpt_config.temperature
        )

        output = FulltextOutputRecord(
            article_doi=prompt_record.article_doi,
            dataset_doi=prompt_record.dataset_doi,
            pdf_path=prompt_record.pdf_path,
            status="success",
            abstract_tokens=prompt_record.abstract_tokens,
            fulltext_tokens=prompt_record.fulltext_tokens,
            sections_used=prompt_record.sections_used,
            processed_at=datetime.utcnow(),
        )

        # Extract usage stats
        if result.get("usage_cost"):
            output.input_tokens = result["usage_cost"].get("input_tokens")
            output.output_tokens = result["usage_cost"].get("output_tokens")
            output.cost_usd = result["usage_cost"].get("total_cost")

        # Extract features
        if result.get("output"):
            output.extraction = result["output"].model_dump(mode="python")

        return output

    except Exception as e:
        return FulltextOutputRecord(
            article_doi=prompt_record.article_doi,
            dataset_doi=prompt_record.dataset_doi,
            pdf_path=prompt_record.pdf_path,
            status="error",
            error_message=str(e),
            abstract_tokens=prompt_record.abstract_tokens,
            fulltext_tokens=prompt_record.fulltext_tokens,
            sections_used=prompt_record.sections_used,
            processed_at=datetime.utcnow(),
        )


@flow(task_runner=ThreadPoolTaskRunner(max_workers=10))
def grobid_parsing_flow(
    input_records: List[FulltextInputRecord],
    grobid_url: str = "http://localhost:8070",
    max_workers: int = 10,
) -> List[ParsedDocumentRecord]:
    """Batch GROBID parsing flow - parse multiple PDFs in parallel.

    This flow focuses only on PDF parsing with GROBID, allowing higher
    parallelization since GROBID can handle concurrent requests well.

    Args:
        input_records: List of input records with PDF paths
        grobid_url: GROBID service URL
        max_workers: Maximum parallel workers (default: 10)

    Returns:
        List of ParsedDocumentRecord with parsing results
    """
    print(f"Parsing {len(input_records)} PDFs with GROBID (max_workers={max_workers})...")

    # Parse all PDFs in parallel
    futures = parse_pdf_to_record.map(
        input_records,
        [grobid_url] * len(input_records)
    )
    results = [f.result() for f in futures]

    # Summary
    success = sum(1 for r in results if r.status == "success")
    errors = sum(1 for r in results if r.status == "error")
    print(f"GROBID parsing complete: {success} success, {errors} errors")

    return results


@flow(task_runner=ThreadPoolTaskRunner(max_workers=5))
def prompt_building_flow(
    parsed_records: List[ParsedDocumentRecord],
    section_config: Optional[SectionSelectionConfig] = None,
) -> List[PromptRecord]:
    """Batch prompt building flow - build prompts from parsed documents.

    Args:
        parsed_records: List of parsed document records
        section_config: Section selection configuration

    Returns:
        List of PromptRecord with built prompts
    """
    if section_config is None:
        section_config = SectionSelectionConfig()

    print(f"Building prompts for {len(parsed_records)} documents...")

    # Build prompts in parallel
    futures = build_prompt_from_record.map(
        parsed_records,
        [section_config] * len(parsed_records)
    )
    results = [f.result() for f in futures]

    # Summary
    success = sum(1 for r in results if r.status == "success")
    skipped = sum(1 for r in results if r.status == "skipped")
    print(f"Prompt building complete: {success} success, {skipped} skipped")

    return results


@flow(task_runner=ThreadPoolTaskRunner(max_workers=5))
def gpt_classification_flow(
    prompt_records: List[PromptRecord],
    gpt_config: Optional[GPTClassifyConfig] = None,
    text_format: Type[BaseModel] = DatasetFeatures,
    output_manifest: Optional[Path] = None,
) -> List[FulltextOutputRecord]:
    """Batch GPT classification flow - classify prompts in parallel.

    This flow focuses only on GPT classification, allowing control over
    parallelization to manage API rate limits and costs.

    Args:
        prompt_records: List of prompt records to classify
        gpt_config: GPT configuration
        text_format: Pydantic model for structured output
        output_manifest: Optional path to save output manifest

    Returns:
        List of FulltextOutputRecord with classification results
    """
    if gpt_config is None:
        gpt_config = GPTClassifyConfig()

    # Filter to only success prompts
    valid_prompts = [r for r in prompt_records if r.status == "success"]
    print(f"Classifying {len(valid_prompts)} prompts with GPT (max_workers=5)...")
    print(f"  Model: {gpt_config.model}")
    print(f"  Reasoning: {gpt_config.reasoning}")

    # Classify prompts in parallel
    futures = classify_prompt_record.map(
        prompt_records,  # Include all for proper tracking
        [gpt_config] * len(prompt_records),
        [text_format] * len(prompt_records)
    )
    results = [f.result() for f in futures]

    # Summary
    success = sum(1 for r in results if r.status == "success")
    errors = sum(1 for r in results if r.status == "error")
    skipped = sum(1 for r in results if r.status == "skipped")
    total_cost = sum(r.cost_usd or 0 for r in results)
    print(f"GPT classification complete: {success} success, {errors} errors, {skipped} skipped")
    print(f"Total cost: ${total_cost:.4f}")

    # Save output manifest if specified
    if output_manifest:
        save_output_manifest(results, output_manifest)

    return results


@flow
def staged_fulltext_pipeline(
    input_records: List[FulltextInputRecord],
    config: Optional[FulltextPipelineConfig] = None,
    output_manifest: Optional[Path] = None,
    grobid_workers: int = 10,
    gpt_workers: int = 5,
) -> List[FulltextOutputRecord]:
    """Staged full-text extraction pipeline with separate parallelization.

    This pipeline runs in three stages:
    1. GROBID parsing (high parallelization - GROBID handles concurrency well)
    2. Prompt building (medium parallelization - CPU-bound)
    3. GPT classification (controlled parallelization - API rate limits)

    Args:
        input_records: List of input records with PDF paths
        config: Pipeline configuration
        output_manifest: Optional path to save output manifest
        grobid_workers: Max workers for GROBID parsing (default: 10)
        gpt_workers: Max workers for GPT classification (default: 5)

    Returns:
        List of FulltextOutputRecord with extraction results
    """
    if config is None:
        config = FulltextPipelineConfig()

    print(f"Starting staged pipeline for {len(input_records)} PDFs")
    print(f"  Stage 1: GROBID parsing (max_workers={grobid_workers})")
    print(f"  Stage 2: Prompt building")
    print(f"  Stage 3: GPT classification (max_workers={gpt_workers})")
    print()

    # Stage 1: GROBID parsing
    parsed_records = grobid_parsing_flow(
        input_records=input_records,
        grobid_url=config.grobid_url,
        max_workers=grobid_workers,
    )

    # Stage 2: Prompt building
    prompt_records = prompt_building_flow(
        parsed_records=parsed_records,
        section_config=config.section_config,
    )

    # Stage 3: GPT classification
    results = gpt_classification_flow(
        prompt_records=prompt_records,
        gpt_config=config.gpt_config,
        text_format=config.text_format,
        output_manifest=output_manifest,
    )

    return results


# =============================================================================
# Main entry point
# =============================================================================

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    # Example 1: Process with GROBID parsing (default)
    config_grobid = FulltextPipelineConfig(
        section_config=SectionSelectionConfig(
            include_all=True  # Use all sections for testing
        ),
        gpt_config=GPTClassifyConfig(
            model="gpt-5-mini",
            reasoning={"effort": "low"},
            extraction_method="grobid"  # Use GROBID parsing
        ),
        pdf_dir=Path("data/pdfs/fuster"),
        output_dir=Path("artifacts/fulltext_results")
    )

    # Example 2: Process with raw PDF text extraction (no GROBID)
    config_raw = FulltextPipelineConfig(
        gpt_config=GPTClassifyConfig(
            model="gpt-5-mini",
            reasoning={"effort": "low"},
            extraction_method="raw_pdf",  # Use raw PDF extraction
            max_pdf_pages=20  # Limit to first 20 pages
        ),
        pdf_dir=Path("data/pdfs/fuster"),
        output_dir=Path("artifacts/fulltext_results")
    )

    # Run with manifest (choose one config)
    manifest_path = Path("data/pdfs/fuster/manifest.csv")
    output_path = Path("artifacts/fulltext_results/output_manifest.csv")

    # Use GROBID mode
    results = fulltext_extraction_pipeline(
        config=config_grobid,
        input_manifest=manifest_path,
        output_manifest=output_path
    )

    # Or use raw PDF mode (uncomment to use)
    # results = fulltext_extraction_pipeline(
    #     config=config_raw,
    #     input_manifest=manifest_path,
    #     output_manifest=output_path
    # )

    print(f"\nProcessed {len(results)} PDFs")
