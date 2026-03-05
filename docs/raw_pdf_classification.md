# Raw PDF Classification Feature

## Summary

Added functionality to perform classification from raw PDF files without requiring GROBID parsing. This provides a simpler, faster alternative when structured section parsing is not needed.

## Changes Made

### 1. `gpt_extract.py`

**New Functions:**
- `extract_text_from_pdf(pdf_path, max_pages=None)`: Extracts text from PDF files using pypdf
- `extract_from_pdf_file(pdf_path, ...)`: Complete classification pipeline for raw PDF files

**Key Features:**
- Page limit support (`max_pages` parameter)
- Error handling for invalid PDFs
- Caching support via joblib
- Returns same structure as `extract_from_text()`

### 2. `fulltext_pipeline.py`

**Configuration Updates:**
- Added `extraction_method` field to `GPTClassifyConfig` ('grobid' or 'raw_pdf')
- Added `max_pdf_pages` field to limit pages extracted in raw mode

**New Task:**
- `extract_raw_pdf_text_task()`: Prefect task for raw PDF text extraction

**Modified Tasks:**
- `process_single_pdf()`: Now supports both GROBID and raw PDF extraction modes

### 3. `pyproject.toml`

**Dependencies:**
- Added `pypdf` to project dependencies

## Usage Examples

### Basic Usage (gpt_extract.py)

```python
from llm_metadata.gpt_extract import extract_from_pdf_file
from pathlib import Path

# Classify entire PDF
result = extract_from_pdf_file(
    pdf_path=Path("data/pdfs/paper.pdf"),
    model="gpt-5-mini"
)

# Classify first 10 pages only
result = extract_from_pdf_file(
    pdf_path=Path("data/pdfs/paper.pdf"),
    max_pages=10,
    model="gpt-5-mini"
)

print(result["output"])  # Structured extraction
print(result["usage_cost"]["total_cost"])  # Cost in USD
```

### Pipeline Usage (fulltext_pipeline.py)

```python
from llm_metadata.fulltext_pipeline import (
    FulltextPipelineConfig,
    GPTClassifyConfig,
    fulltext_extraction_pipeline
)
from pathlib import Path

# Configure for raw PDF extraction
config = FulltextPipelineConfig(
    gpt_config=GPTClassifyConfig(
        model="gpt-5-mini",
        reasoning={"effort": "low"},
        extraction_method="raw_pdf",  # Use raw PDF mode
        max_pdf_pages=20  # Limit to first 20 pages
    ),
    pdf_dir=Path("data/pdfs/fuster"),
    output_dir=Path("artifacts/fulltext_results")
)

# Run pipeline
results = fulltext_extraction_pipeline(
    config=config,
    input_manifest=Path("data/pdfs/fuster/manifest.csv"),
    output_manifest=Path("artifacts/fulltext_results/output_raw.csv")
)
```

### GROBID vs Raw PDF Comparison

| Feature | GROBID Mode | Raw PDF Mode |
|---------|-------------|--------------|
| **Setup** | Requires GROBID server | No external dependencies |
| **Speed** | Slower (2-step process) | Faster (1-step) |
| **Structure** | Preserves sections, metadata | Plain text only |
| **Section Selection** | Yes (configurable) | No (full text) |
| **Quality** | Better for structured papers | Good for simple extraction |
| **Use Case** | When section context matters | Quick extraction, all text |

## When to Use Each Mode

**Use GROBID mode when:**
- You need section-level granularity (Methods, Results, etc.)
- You want to exclude certain sections
- Paper structure is important for extraction
- You have a GROBID server available

**Use raw PDF mode when:**
- You need quick, simple text extraction
- GROBID server is unavailable
- You want to process the entire document
- Section structure is not critical
- You need a lightweight solution

## Testing

Run the test script to verify functionality:

```bash
python test_raw_pdf_extraction.py
```

Expected output:
- ✓ Text extraction successful
- ✓ Pipeline configuration successful
- ✓ All Tests Passed

## Installation

Install the new dependency:

```bash
pip install pypdf
# or
pip install -e .
```

## Notes

- Raw PDF extraction uses pypdf library
- Text quality depends on PDF quality (OCR, formatting, etc.)
- Some PDFs may fail extraction if corrupted or HTML-based
- Token counting and cost tracking work the same in both modes
- Caching is preserved across both extraction methods
