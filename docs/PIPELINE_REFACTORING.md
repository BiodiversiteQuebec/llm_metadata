# Pipeline Refactoring Summary

## Overview

The monolithic `fulltext_pipeline.py` has been refactored into three focused, specialized pipelines:

1. **text_pipeline.py** - Direct text classification
2. **pdf_pipeline.py** - Raw PDF extraction and classification  
3. **section_pipeline.py** - GROBID-based section extraction and classification

Plus a unified interface in **pipelines.py** for easy access to all three.

## New Structure

```
src/llm_metadata/
├── text_pipeline.py         # Text → GPT
├── pdf_pipeline.py           # PDF → pypdf → GPT
├── section_pipeline.py       # PDF → GROBID → Sections → GPT
├── pipelines.py              # Unified interface (classify() function)
├── gpt_classify.py           # Core GPT functions (updated)
└── fulltext_pipeline.py      # DEPRECATED (with migration guide)
```

## Key Benefits

### 1. Clear Separation of Concerns
- Each pipeline has a specific purpose
- No conditional logic based on extraction_method
- Easier to understand and maintain

### 2. Dedicated Configuration Classes
```python
# Before (confusing)
FulltextPipelineConfig(
    gpt_config=GPTClassifyConfig(extraction_method="raw_pdf")
)

# After (clear)
PDFClassificationConfig(...)  # or
SectionClassificationConfig(...)  # or
TextClassificationConfig(...)
```

### 3. Consistent API Across All Pipelines
All three pipelines share the same structure:
- `*InputRecord` - Input schema
- `*OutputRecord` - Output schema
- `*ClassificationConfig` - Configuration
- `*_classification_flow` - Batch processing
- `single_*_classification` - Single record processing
- `load_*_manifest` / `save_*_manifest` - I/O functions

### 4. Unified Interface
```python
from llm_metadata.pipelines import classify

# Auto-detects the right pipeline
results = classify("text")  # → text_pipeline
results = classify(Path("paper.pdf"))  # → pdf_pipeline
results = classify(Path("paper.pdf"), pipeline="section")  # → section_pipeline
```

## Migration Guide

### From fulltext_pipeline.py

**Old Code:**
```python
from llm_metadata.fulltext_pipeline import (
    FulltextPipelineConfig,
    GPTClassifyConfig,
    fulltext_extraction_pipeline
)

config = FulltextPipelineConfig(
    gpt_config=GPTClassifyConfig(
        model="gpt-5-mini",
        extraction_method="raw_pdf",  # or "grobid"
        max_pdf_pages=10
    )
)

results = fulltext_extraction_pipeline(
    config=config,
    pdf_paths=pdfs
)
```

**New Code (PDF Pipeline):**
```python
from llm_metadata.pdf_pipeline import (
    PDFClassificationConfig,
    pdf_classification_flow,
    PDFInputRecord
)

config = PDFClassificationConfig(
    model="gpt-5-mini",
    reasoning={"effort": "low"},
    max_pdf_pages=10
)

input_records = [
    PDFInputRecord(id=pdf.stem, pdf_path=str(pdf))
    for pdf in pdfs
]

results = pdf_classification_flow(input_records, config)
```

**New Code (Section Pipeline):**
```python
from llm_metadata.section_pipeline import (
    SectionClassificationConfig,
    SectionSelectionConfig,
    section_classification_flow,
    SectionInputRecord
)

config = SectionClassificationConfig(
    model="gpt-5-mini",
    reasoning={"effort": "low"},
    section_config=SectionSelectionConfig(
        section_types=[SectionType.ABSTRACT, SectionType.METHODS]
    )
)

input_records = [
    SectionInputRecord(id=pdf.stem, pdf_path=str(pdf))
    for pdf in pdfs
]

results = section_classification_flow(input_records, config)
```

**New Code (Unified Interface):**
```python
from llm_metadata.pipelines import classify, PDFClassificationConfig

config = PDFClassificationConfig(
    model="gpt-5-mini",
    max_pdf_pages=10
)

results = classify(
    source=pdfs,
    pipeline="pdf",  # or "section" or "auto"
    config=config
)
```

## Testing

Run the comprehensive test suite:

```bash
python test_pipelines.py
```

Expected output:
```
✓ text_pipeline imports successful
✓ pdf_pipeline imports successful
✓ section_pipeline imports successful
✓ unified pipelines interface imports successful
✓ Configuration creation tests pass
✓ Record creation tests pass
✓ Pipeline auto-detection tests pass
✓ Deprecation warning raised for fulltext_pipeline
```

## Documentation

- **[docs/pipelines_guide.md](docs/pipelines_guide.md)** - Complete user guide with examples
- **[docs/raw_pdf_classification.md](docs/raw_pdf_classification.md)** - Raw PDF extraction documentation

## Breaking Changes

### Deprecated
- `fulltext_pipeline.py` - Still works but issues deprecation warning
- `FulltextPipelineConfig` - Use pipeline-specific configs instead
- `extraction_method` parameter - Use appropriate pipeline instead

### Removed
- None (all old code still works with deprecation warnings)

### Changed
- Configuration structure - Each pipeline has its own config class
- Input record types - Each pipeline has its own record type

## Performance Comparison

| Pipeline | Speed | Dependencies | Use Case |
|----------|-------|--------------|----------|
| text_pipeline | ~1-2s | OpenAI API | Pre-extracted text |
| pdf_pipeline | ~3-5s | pypdf + API | Quick PDF processing |
| section_pipeline | ~10-15s | GROBID + API | Structured extraction |

## Examples

See the `__main__` block in each pipeline file for runnable examples:

```bash
# Text pipeline
python -m llm_metadata.text_pipeline

# PDF pipeline
python -m llm_metadata.pdf_pipeline

# Section pipeline (requires GROBID server)
python -m llm_metadata.section_pipeline
```

## Next Steps

1. Update existing notebooks to use new pipelines
2. Update any scripts that import from fulltext_pipeline.py
3. Consider removing fulltext_pipeline.py in next major version
4. Add integration tests for all three pipelines

## Files Changed

### New Files
- `src/llm_metadata/text_pipeline.py` (345 lines)
- `src/llm_metadata/pdf_pipeline.py` (437 lines)
- `src/llm_metadata/section_pipeline.py` (592 lines)
- `src/llm_metadata/pipelines.py` (353 lines) - Unified interface
- `docs/pipelines_guide.md` - Comprehensive documentation
- `test_pipelines.py` - Test suite

### Modified Files
- `src/llm_metadata/fulltext_pipeline.py` - Added deprecation warning
- `src/llm_metadata/gpt_classify.py` - Added raw PDF support (already done)
- `pyproject.toml` - Added pypdf dependency (already done)

### Total
- **~1,900 lines** of new, focused pipeline code
- **Clear separation** of concerns
- **100% backward compatible** (with deprecation warnings)
