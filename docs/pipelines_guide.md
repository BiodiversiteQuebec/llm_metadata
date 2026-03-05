# Classification extraction Guide

## Overview

The LLM Metadata package provides three specialized classification extraction for extracting structured metadata from scientific documents:

1. **Text Pipeline** - Direct text classification
2. **PDF Pipeline** - Raw PDF extraction and classification  
3. **Section Pipeline** - GROBID-based section extraction and classification

## Quick Start

### Unified Interface

The simplest way to use any pipeline is through the unified `extract()` function:

```python
from llm_metadata.extraction import extract

# Auto-detect and extract
results = extract("path/to/paper.pdf")

# Or specify pipeline explicitly
results = extract("path/to/paper.pdf", pipeline="pdf")
```

### Pipeline Selection

Use this decision tree to choose the right pipeline:

```
Do you already have extracted text?
├─ YES → Use text_pipeline
└─ NO → Do you have PDF files?
    └─ YES → Do you need section-level granularity?
        ├─ YES → Use section_pipeline (GROBID)
        └─ NO → Use pdf_pipeline (raw extraction)
```

## Pipeline Details

### 1. Text Pipeline

**Module**: `text_pipeline.py`  
**Input**: Raw text strings (abstracts, pre-extracted content, etc.)  
**Processing**: Text → GPT Classification  

**Use Cases:**
- Classifying abstracts from a database
- Processing pre-extracted text
- Testing prompts without PDF processing
- Batch processing text from APIs

**Example:**

```python
from llm_metadata.text_pipeline import (
    text_classification_flow,
    TextClassificationConfig,
    TextInputRecord
)

# Configure
config = TextClassificationConfig(
    model="gpt-5-mini",
    reasoning={"effort": "low"}
)

# Prepare input
records = [
    TextInputRecord(
        id="paper_1",
        text="We collected genetic samples from 150 individuals...",
        metadata={"source": "openalex", "year": 2024}
    )
]

# Run
results = text_classification_flow(records, config)
```

**Performance**: Fastest (~1-2s per record, GPT only)

---

### 2. PDF Pipeline

**Module**: `pdf_pipeline.py`  
**Input**: PDF files  
**Processing**: PDF → Text Extraction (pypdf) → GPT Classification  

**Use Cases:**
- Quick batch processing of PDFs
- When document structure is not important
- No GROBID server available
- Processing papers where all content matters

**Example:**

```python
from llm_metadata.pdf_pipeline import (
    pdf_classification_flow,
    PDFClassificationConfig,
    PDFInputRecord
)

# Configure
config = PDFClassificationConfig(
    model="gpt-5-mini",
    reasoning={"effort": "low"},
    max_pdf_pages=10  # Optional: limit to first 10 pages
)

# Prepare input
records = [
    PDFInputRecord(
        id="10.1234/example",
        pdf_path="data/pdfs/paper.pdf",
        metadata={"doi": "10.1234/example"}
    )
]

# Run
results = pdf_classification_flow(records, config)

# Or process entire directory
from llm_metadata.pdf_pipeline import pdf_classification_from_directory
results = pdf_classification_from_directory(
    pdf_dir=Path("data/pdfs"),
    config=config
)
```

**Performance**: Fast (~3-5s per record, pypdf + GPT)

---

### 3. Section Pipeline

**Module**: `section_pipeline.py`  
**Input**: PDF files  
**Processing**: PDF → GROBID Parsing → Section Selection → GPT Classification  

**Use Cases:**
- Need structured section extraction
- Want to focus on specific sections (Methods, Data, etc.)
- High-quality scientific papers
- When section context improves extraction

**Example:**

```python
from llm_metadata.section_pipeline import (
    section_classification_flow,
    SectionClassificationConfig,
    SectionSelectionConfig,
    SectionInputRecord
)
from llm_metadata.schemas.chunk_metadata import SectionType

# Configure section selection
section_config = SectionSelectionConfig(
    section_types=[SectionType.ABSTRACT, SectionType.METHODS],
    keywords=["data", "dataset", "sample"],
    include_abstract=True,
    include_all=False  # Only selected sections
)

# Configure pipeline
config = SectionClassificationConfig(
    model="gpt-5-mini",
    reasoning={"effort": "low"},
    section_config=section_config,
    grobid_url="http://localhost:8070"
)

# Prepare input
records = [
    SectionInputRecord(
        id="10.1234/example",
        pdf_path="data/pdfs/paper.pdf"
    )
]

# Run
results = section_classification_flow(records, config)
```

**Performance**: Slower (~10-15s per record, GROBID + GPT)  
**Requires**: GROBID server running

---

## Configuration Comparison

| Feature | Text Pipeline | PDF Pipeline | Section Pipeline |
|---------|--------------|--------------|------------------|
| **Model** | ✓ | ✓ | ✓ |
| **Reasoning** | ✓ | ✓ | ✓ |
| **Temperature** | ✓ | ✓ | ✓ |
| **Text Format** | ✓ | ✓ | ✓ |
| **Max PDF Pages** | ✗ | ✓ | ✗ |
| **Section Selection** | ✗ | ✗ | ✓ |
| **GROBID URL** | ✗ | ✗ | ✓ |

## Unified Interface Examples

### Auto-Detection

```python
from llm_metadata.extraction import extract

# Automatically detects pipeline based on input type
results = extract("Direct text to extract")  # → text_pipeline
results = extract(Path("paper.pdf"))  # → pdf_pipeline (default for PDFs)
results = extract([Path("p1.pdf"), Path("p2.pdf")])  # → pdf_pipeline
```

### Explicit Pipeline Selection

```python
from llm_metadata.extraction import extract, TextClassificationConfig

# Force specific pipeline
config = TextClassificationConfig(model="gpt-5-mini")
results = extract(
    source="Some text to extract",
    pipeline="text",
    config=config,
    output_manifest=Path("results.csv")
)
```

### Batch Processing

```python
from llm_metadata.extraction import extract
from pathlib import Path

# Process directory of PDFs
pdf_files = list(Path("data/pdfs").glob("*.pdf"))
results = extract(
    source=pdf_files,
    pipeline="pdf",
    output_manifest=Path("artifacts/results.csv")
)

print(f"Processed {len(results)} PDFs")
print(f"Success: {sum(r.status == 'success' for r in results)}")
```

## Input/Output Formats

### Input Records

All extraction use structured input records:

```python
# Text Pipeline
TextInputRecord(id="...", text="...", metadata={...})

# PDF Pipeline
PDFInputRecord(id="...", pdf_path="...", metadata={...})

# Section Pipeline
SectionInputRecord(id="...", pdf_path="...", metadata={...})
```

### Output Records

All extraction return structured output records:

```python
OutputRecord(
    id="...",
    status="success",  # or "error"
    error_message=None,
    input_tokens=1234,
    output_tokens=567,
    cost_usd=0.0123,
    extraction={...},  # Structured metadata
    metadata={...},  # Original metadata
    processed_at=datetime.utcnow()
)
```

### Manifest Files

Save/load results as CSV:

```python
# Save results
results = text_classification_flow(
    records,
    config,
    output_manifest=Path("results.csv")
)

# Load existing manifest
from llm_metadata.text_pipeline import load_text_manifest
records = load_text_manifest(Path("input.csv"))
```

Expected CSV format:

**Input CSV** (text_pipeline):
```csv
id,text,source,year
paper_1,"We collected samples...",openalex,2024
paper_2,"Field surveys were...",crossref,2023
```

**Output CSV** (all extraction):
```csv
id,status,input_tokens,output_tokens,cost_usd,extraction_field1,extraction_field2,...
paper_1,success,1234,567,0.0123,value1,value2,...
```

## Advanced Configuration

### Custom Schema

```python
from pydantic import BaseModel, Field

class CustomMetadata(BaseModel):
    species: str = Field(None, description="Species name")
    location: str = Field(None, description="Study location")
    sample_size: int = Field(None, description="Number of samples")

config = TextClassificationConfig(
    text_format=CustomMetadata
)
```

### Section Selection Strategies

```python
from llm_metadata.section_pipeline import SectionSelectionConfig
from llm_metadata.schemas.chunk_metadata import SectionType

# Strategy 1: Specific section types
config = SectionSelectionConfig(
    section_types=[SectionType.METHODS, SectionType.RESULTS],
    include_abstract=True
)

# Strategy 2: Keyword matching
config = SectionSelectionConfig(
    keywords=["data", "dataset", "sampling", "survey"],
    include_all=False
)

# Strategy 3: Everything
config = SectionSelectionConfig(
    include_all=True
)
```

### Cost Control

```python
# Limit PDF pages to control costs
config = PDFClassificationConfig(
    max_pdf_pages=10,  # Only first 10 pages
    max_output_tokens=2048  # Limit response size
)

# Use cheaper model
config = TextClassificationConfig(
    model="gpt-5-nano",  # Cheaper alternative
    reasoning=None
)
```

## Performance Tips

1. **Use the right pipeline**: Don't use section_pipeline if you don't need sections
2. **Batch processing**: Process multiple records in one flow call for parallelization
3. **Page limits**: Set `max_pdf_pages` for PDF pipeline to reduce costs
4. **Caching**: Results are cached by joblib - identical inputs return cached results
5. **GROBID optimization**: For section pipeline, ensure GROBID server is local

## Migration from fulltext_pipeline.py

Old code:
```python
from llm_metadata.fulltext_pipeline import (
    FulltextPipelineConfig,
    fulltext_extraction_pipeline
)

config = FulltextPipelineConfig(
    gpt_config=GPTClassifyConfig(extraction_method="raw_pdf")
)
results = fulltext_extraction_pipeline(config=config, pdf_paths=pdfs)
```

New code:
```python
from llm_metadata.extraction import extract, PDFClassificationConfig

config = PDFClassificationConfig()
results = extract(source=pdfs, pipeline="pdf", config=config)
```

## Troubleshooting

### GROBID Connection Error
**Problem**: Section pipeline fails with "Connection refused"  
**Solution**: Start GROBID server: `docker-compose up -d grobid`

### PDF Extraction Fails
**Problem**: PDF pipeline returns "No text extracted"  
**Solution**: PDF may be corrupted, scanned, or HTML. Try section pipeline with GROBID

### High Costs
**Problem**: Processing costs higher than expected  
**Solution**: 
- Use `max_pdf_pages` to limit extraction
- Choose appropriate model (gpt-5-nano vs gpt-5-mini)
- Use text pipeline if text already available

### Slow Processing
**Problem**: Batch processing takes too long  
**Solution**:
- Increase `max_workers` in config
- Use faster pipeline (text > pdf > section)
- Process in smaller batches

## API Reference

See individual module documentation:
- [`text_pipeline.py`](../src/llm_metadata/text_pipeline.py)
- [`pdf_pipeline.py`](../src/llm_metadata/pdf_pipeline.py)
- [`section_pipeline.py`](../src/llm_metadata/section_pipeline.py)
- [`extraction.py`](../src/llm_metadata/extraction.py) - Unified interface
