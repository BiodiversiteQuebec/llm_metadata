"""
Unified interface for all classification pipelines.

This module provides a simple, consistent API for running any of the three
classification pipelines:
1. Text pipeline: Direct text classification
2. PDF pipeline: Raw PDF extraction and classification
3. Section pipeline: GROBID-based section extraction and classification
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# Import all three pipelines
from llm_metadata.text_pipeline import (
    TextClassificationConfig,
    TextInputRecord,
    TextOutputRecord,
    text_classification_flow,
    single_text_classification,
)

from llm_metadata.pdf_pipeline import (
    PDFClassificationConfig,
    PDFInputRecord,
    PDFOutputRecord,
    pdf_classification_flow,
    single_pdf_classification,
    pdf_classification_from_directory,
)

from llm_metadata.section_pipeline import (
    SectionClassificationConfig,
    SectionInputRecord,
    SectionOutputRecord,
    SectionSelectionConfig,
    section_classification_flow,
    single_section_classification,
)


# =============================================================================
# Unified Configuration Types
# =============================================================================

PipelineConfig = Union[
    TextClassificationConfig,
    PDFClassificationConfig,
    SectionClassificationConfig
]

InputRecord = Union[
    TextInputRecord,
    PDFInputRecord,
    SectionInputRecord
]

OutputRecord = Union[
    TextOutputRecord,
    PDFOutputRecord,
    SectionOutputRecord
]


# =============================================================================
# Unified Interface
# =============================================================================

def classify(
    source: Union[str, Path, List[str], List[Path], List[InputRecord]],
    pipeline: str = "auto",
    config: Optional[PipelineConfig] = None,
    output_manifest: Optional[Path] = None,
    **kwargs
) -> List[OutputRecord]:
    """
    Unified classification interface - automatically chooses the right pipeline.
    
    Args:
        source: Input to classify. Can be:
            - str: Direct text or path to PDF/manifest file
            - Path: Path to PDF/manifest file
            - List[str]: Multiple texts or PDF paths
            - List[Path]: Multiple PDF paths
            - List[InputRecord]: Pre-structured input records
        pipeline: Pipeline to use ('text', 'pdf', 'section', or 'auto')
        config: Pipeline-specific configuration
        output_manifest: Path to save output manifest
        **kwargs: Additional arguments passed to pipeline
        
    Returns:
        List of output records from the selected pipeline
        
    Examples:
        >>> # Classify text directly
        >>> results = classify("We collected samples from 50 sites...", pipeline="text")
        
        >>> # Classify a PDF file
        >>> results = classify(Path("paper.pdf"), pipeline="pdf")
        
        >>> # Classify with section extraction
        >>> results = classify(Path("paper.pdf"), pipeline="section")
        
        >>> # Auto-detect from file extension
        >>> results = classify(Path("paper.pdf"))  # Uses PDF pipeline
        
        >>> # Batch processing
        >>> results = classify([Path("p1.pdf"), Path("p2.pdf")], pipeline="pdf")
    """
    # Auto-detect pipeline if requested
    if pipeline == "auto":
        pipeline = _detect_pipeline(source)
    
    # Route to appropriate pipeline
    if pipeline == "text":
        return _run_text_pipeline(source, config, output_manifest, **kwargs)
    elif pipeline == "pdf":
        return _run_pdf_pipeline(source, config, output_manifest, **kwargs)
    elif pipeline == "section":
        return _run_section_pipeline(source, config, output_manifest, **kwargs)
    else:
        raise ValueError(f"Unknown pipeline: {pipeline}. Must be 'text', 'pdf', 'section', or 'auto'")


def _detect_pipeline(source: Any) -> str:
    """Auto-detect which pipeline to use based on input."""
    # Single string that's not a file path
    if isinstance(source, str) and not Path(source).exists():
        return "text"
    
    # Path to PDF file
    if isinstance(source, (str, Path)):
        path = Path(source)
        if path.suffix.lower() == ".pdf":
            return "pdf"  # Default to faster PDF pipeline
        elif path.suffix.lower() == ".csv":
            return "section"  # Assume manifest wants section extraction
    
    # List of paths
    if isinstance(source, list) and len(source) > 0:
        if isinstance(source[0], (str, Path)):
            first_path = Path(source[0])
            if first_path.suffix.lower() == ".pdf":
                return "pdf"
        elif isinstance(source[0], str):
            return "text"
        elif isinstance(source[0], (TextInputRecord, PDFInputRecord, SectionInputRecord)):
            # Detect from record type
            if isinstance(source[0], TextInputRecord):
                return "text"
            elif isinstance(source[0], PDFInputRecord):
                return "pdf"
            else:
                return "section"
    
    # Default to section pipeline (most comprehensive)
    return "section"


def _run_text_pipeline(
    source: Any,
    config: Optional[TextClassificationConfig],
    output_manifest: Optional[Path],
    **kwargs
) -> List[TextOutputRecord]:
    """Run text classification pipeline."""
    if config is None:
        config = TextClassificationConfig()
    
    # Convert source to input records
    if isinstance(source, str):
        # Single text string
        record_id = kwargs.get("id", "text_1")
        metadata = kwargs.get("metadata")
        return [single_text_classification(source, record_id, config, metadata)]
    
    elif isinstance(source, list):
        if isinstance(source[0], TextInputRecord):
            # Already structured
            input_records = source
        elif isinstance(source[0], str):
            # List of text strings
            input_records = [
                TextInputRecord(id=f"text_{i+1}", text=text)
                for i, text in enumerate(source)
            ]
        else:
            raise ValueError(f"Unsupported source type for text pipeline: {type(source[0])}")
        
        return text_classification_flow(input_records, config, output_manifest)
    
    else:
        raise ValueError(f"Unsupported source type for text pipeline: {type(source)}")


def _run_pdf_pipeline(
    source: Any,
    config: Optional[PDFClassificationConfig],
    output_manifest: Optional[Path],
    **kwargs
) -> List[PDFOutputRecord]:
    """Run PDF classification pipeline."""
    if config is None:
        config = PDFClassificationConfig()
    
    # Convert source to input records
    if isinstance(source, (str, Path)):
        path = Path(source)
        
        if path.is_dir():
            # Directory of PDFs
            return pdf_classification_from_directory(
                path, config, output_manifest
            )
        elif path.suffix.lower() == ".pdf":
            # Single PDF
            record_id = kwargs.get("id", path.stem)
            metadata = kwargs.get("metadata")
            return [single_pdf_classification(path, record_id, config, metadata)]
        else:
            raise ValueError(f"Expected PDF file or directory, got: {path}")
    
    elif isinstance(source, list):
        if isinstance(source[0], PDFInputRecord):
            # Already structured
            input_records = source
        elif isinstance(source[0], (str, Path)):
            # List of PDF paths
            input_records = [
                PDFInputRecord(id=Path(p).stem, pdf_path=str(p))
                for p in source
            ]
        else:
            raise ValueError(f"Unsupported source type for PDF pipeline: {type(source[0])}")
        
        return pdf_classification_flow(input_records, config, output_manifest)
    
    else:
        raise ValueError(f"Unsupported source type for PDF pipeline: {type(source)}")


def _run_section_pipeline(
    source: Any,
    config: Optional[SectionClassificationConfig],
    output_manifest: Optional[Path],
    **kwargs
) -> List[SectionOutputRecord]:
    """Run section-based classification pipeline."""
    if config is None:
        config = SectionClassificationConfig()
    
    # Convert source to input records
    if isinstance(source, (str, Path)):
        path = Path(source)
        
        if path.suffix.lower() == ".pdf":
            # Single PDF
            record_id = kwargs.get("id", path.stem)
            metadata = kwargs.get("metadata")
            return [single_section_classification(path, record_id, config, metadata)]
        else:
            raise ValueError(f"Expected PDF file, got: {path}")
    
    elif isinstance(source, list):
        if isinstance(source[0], SectionInputRecord):
            # Already structured
            input_records = source
        elif isinstance(source[0], (str, Path)):
            # List of PDF paths
            input_records = [
                SectionInputRecord(id=Path(p).stem, pdf_path=str(p))
                for p in source
            ]
        else:
            raise ValueError(f"Unsupported source type for section pipeline: {type(source[0])}")
        
        return section_classification_flow(input_records, config, output_manifest)
    
    else:
        raise ValueError(f"Unsupported source type for section pipeline: {type(source)}")


# =============================================================================
# Pipeline Comparison Helper
# =============================================================================

def compare_pipelines() -> str:
    """Return a comparison table of the three pipelines."""
    return """
Pipeline Comparison
===================

1. TEXT PIPELINE (text_pipeline.py)
   - Input: Raw text strings
   - Processing: Direct GPT classification
   - Speed: Fastest
   - Use when: Text already extracted, no PDF processing needed
   - Example: Classifying abstracts from a database

2. PDF PIPELINE (pdf_pipeline.py)
   - Input: PDF files
   - Processing: pypdf text extraction → GPT classification
   - Speed: Fast
   - Dependencies: pypdf only
   - Use when: Quick extraction, don't need section structure
   - Example: Batch processing papers where structure doesn't matter

3. SECTION PIPELINE (section_pipeline.py)
   - Input: PDF files
   - Processing: GROBID parsing → section selection → GPT classification
   - Speed: Slower (GROBID parsing overhead)
   - Dependencies: GROBID server required
   - Use when: Need structured extraction, selective section processing
   - Example: Extracting only Methods and Data sections

Quick Selection Guide:
- Have text? → text_pipeline
- Have PDFs, need speed? → pdf_pipeline
- Have PDFs, need structure? → section_pipeline
- Not sure? → Use classify() with pipeline="auto"
"""


# =============================================================================
# Re-export for convenience
# =============================================================================

__all__ = [
    # Main interface
    "classify",
    "compare_pipelines",
    
    # Pipeline flows
    "text_classification_flow",
    "pdf_classification_flow",
    "section_classification_flow",
    
    # Single record functions
    "single_text_classification",
    "single_pdf_classification",
    "single_section_classification",
    
    # Config classes
    "TextClassificationConfig",
    "PDFClassificationConfig",
    "SectionClassificationConfig",
    "SectionSelectionConfig",
    
    # Record types
    "TextInputRecord",
    "TextOutputRecord",
    "PDFInputRecord",
    "PDFOutputRecord",
    "SectionInputRecord",
    "SectionOutputRecord",
    
    # Type aliases
    "PipelineConfig",
    "InputRecord",
    "OutputRecord",
]


if __name__ == "__main__":
    # Print comparison guide
    print(compare_pipelines())
