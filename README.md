# llm_metadata

A Python package for extracting structured ecological metadata from scientific dataset abstracts using Large Language Models (LLMs). This tool supports biodiversity monitoring efforts by identifying and characterizing datasets to fill taxonomic, spatial, and temporal gaps in biodiversity data coverage.

## Table of Contents

- [llm\_metadata](#llm_metadata)
  - [Table of Contents](#table-of-contents)
  - [Overview](#overview)
  - [Features](#features)
  - [Installation](#installation)
  - [Setup](#setup)
    - [Required Environment Variables](#required-environment-variables)
  - [Usage](#usage)
    - [Dryad Integration](#dryad-integration)
    - [Zenodo Integration](#zenodo-integration)
    - [GPT-4 Metadata Extraction](#gpt-4-metadata-extraction)
    - [Batch Processing with Prefect](#batch-processing-with-prefect)
  - [Project Context](#project-context)
  - [Development](#development)
    - [Package Structure](#package-structure)
  - [License](#license)

## Overview

Biodiversity observation networks require comprehensive and representative data to track progress toward global biodiversity frameworks (e.g., Kunming-Montreal). However, many valuable datasets remain buried in unstructured text within scientific literature and repository abstracts.

This package leverages GPT-4 to programmatically extract structured metadata from dataset abstracts, including:
- **Species studied** (taxonomic coverage)
- **Spatial extent** (geographic coverage)
- **Temporal period** (time range)
- **Data type** (following Essential Biodiversity Variables framework)

The goal is to identify relevant datasets that can fill data gaps and support more effective biodiversity monitoring.

**Pipeline Architecture:** This package implements a 4-stage workflow: (1) **Data Ingestion** — acquire papers from repositories and parse full-text structure, (2) **Schema & Prompt Engineering** — design Pydantic models as LLM output formats and chunk documents for semantic search, (3) **LLM Inference** — run GPT extraction with Prefect orchestration for batch processing and cost tracking, (4) **Evaluation & Validation** — compare automated extraction against manually annotated ground truth with configurable normalization and fuzzy matching.

This work follows the methodology outlined in Fuster et al. (2024) and their results:

> Fuster-Calvo A, Valentin S, Tamayo WC, Gravel D. 2025. Evaluating the feasibility of automating dataset retrieval for biodiversity monitoring. PeerJ 13:e18853 https://doi.org/10.7717/peerj.18853

## Features

- **Dryad API Integration**: Search and retrieve datasets from Dryad repository
- **Zenodo API Integration**: Query records from Zenodo by DOI
- **GPT-4 Metadata Extraction**: Extract structured ecological metadata from dataset abstracts using OpenAI's GPT-4
- **Structured Schemas**: Pydantic models for dataset metadata and Essential Biodiversity Variables (EBV) features
- **Batch Processing**: Prefect pipeline for processing multiple datasets in parallel
- **Reproducible Extraction**: Deterministic structured output format for consistent metadata extraction

## Installation

```bash
pip install -e .
```

For development dependencies:

```bash
pip install -e .[dev]
```

## Setup

### Required Environment Variables

Create a `.env` file in the project root:

```bash
# For GPT-4 classification
OPENAI_API_KEY=your_openai_api_key

# For Zenodo API access (optional, required only for Zenodo features)
ZENODO_ACCESS_TOKEN=your_zenodo_token
```

## Usage

The package implements a 4-stage LLM data engineering pipeline for ecological metadata extraction. Below are usage examples organized by workflow stage.

### Stage 1: Data Ingestion & Preparation

**Retrieve Dataset Abstracts**

```python
from llm_metadata.dryad import search_datasets, get_dataset
from llm_metadata.zenodo import get_record_by_doi, get_record_by_doi_list

# Search for datasets on Dryad
results = search_datasets("biodiversity Quebec Canada", per_page=10)

# Get specific dataset by DOI
dataset = get_dataset("doi:10.5061/dryad.n726pq6")

# Get Zenodo records (single or batch)
record = get_record_by_doi("10.5061/dryad.2n5h6")
records = get_record_by_doi_list(["10.5061/dryad.2n5h6", "10.5061/dryad.3nh72"])
```

**Download Scientific Article PDFs**

Multi-strategy fallback for robust PDF acquisition:

```python
from llm_metadata.pdf_download import download_pdf_with_fallback
from llm_metadata.ezproxy import extract_cookies_from_browser

# Try OpenAlex → Unpaywall → EZproxy → Sci-Hub
pdf_path = download_pdf_with_fallback(
    doi="10.1371/journal.pone.0128238",
    year=2025
)

# With institutional access (EZproxy)
cookies = extract_cookies_from_browser()
pdf_path = download_pdf_with_fallback(
    doi="10.1111/paywalled-article",
    ezproxy_cookies=cookies
)
```

**Extract Full-Text Structure**

Parse PDF into hierarchical sections using GROBID:

```python
from llm_metadata.pdf_parsing import process_pdf

tei_path, doc = process_pdf(
    pdf_path="data/pdfs/article.pdf",
    work_id="doi_10.1111_article",
    grobid_url="http://localhost:8070"
)

print(f"Title: {doc.title}")
print(f"Abstract: {doc.abstract}")
print(f"Sections: {len(doc.sections)}")
```

**Note on `article_retrieval.py`:** This module matches scientific article DOIs to data repository DOIs (e.g., Dryad dataset → corresponding paper). Used during ground truth preparation to link annotations with full-text sources.

### Stage 2: Schema Design & Prompt Engineering

**Define Extraction Schema**

```python
from llm_metadata.schemas.fuster_features import DatasetFeatureExtraction, EBVDataType
from llm_metadata.schemas.abstract_metadata import DatasetAbstractMetadata

# Detailed EBV features (following Fuster et al. methodology)
features_schema = DatasetFeatureExtraction

# High-level metadata for quick categorization
metadata_schema = DatasetAbstractMetadata
```

**Chunk Full-Text for Semantic Search**

```python
from llm_metadata.chunking import chunk_sections, ChunkingConfig

# Configure chunking strategy
config = ChunkingConfig(
    target_tokens=450,  # Soft limit
    max_tokens=650,     # Hard limit
    overlap_tokens=80   # Sliding window overlap
)

# Chunk parsed document sections
chunks = chunk_sections(
    sections=doc.sections,
    work_id=doc.work_id,
    config=config
)

print(f"Generated {len(chunks)} chunks")
```

**Generate Embeddings & Store in Vector DB**

```python
from llm_metadata.embedding import generate_embeddings_batch
from llm_metadata.vector_store import VectorStore

# Generate embeddings with caching
embeddings = generate_embeddings_batch(chunks)

# Store in Qdrant for semantic search
store = VectorStore(collection_name="papers_chunks")
store.upsert_chunks(chunks, embeddings)
```

### Stage 3: LLM Inference & Batch Processing

**Extract Metadata from Abstract**

```python
from llm_metadata.gpt_classify import classify_abstract
from llm_metadata.schemas.fuster_features import DatasetFeatureExtraction

abstract = """
We monitored caribou populations in northern Quebec from 1999 to 2015
using GPS telemetry. The dataset includes movement trajectories and
habitat use data for 45 individuals across three herds.
"""

# Extract detailed EBV features
result = classify_abstract(
    abstract,
    response_format=DatasetFeatureExtraction
)

features = result['output']
print(f"Taxons: {features.taxons}")
print(f"Temporal range: {features.temp_range_i} - {features.temp_range_f}")
print(f"Data type: {features.data_type}")
print(f"Cost: ${result['usage_cost']['total_cost']}")
```

**Batch Processing with Prefect**

Process multiple datasets in parallel with monitoring:

```python
from llm_metadata.prefect_pipeline import doi_classification_pipeline

dois = [
    "10.5061/dryad.2n5h6",
    "10.5061/dryad.3nh72",
    "10.5061/dryad.4k275"
]

# Prefect manages parallelization, retries, and monitoring
results = doi_classification_pipeline(dois=dois)

for result in results:
    print(f"DOI: {result['abstract'][:30]}...")
    print(f"  Species: {result['output'].taxons}")
    print(f"  Cost: ${result['usage_cost']['total_cost']}")
```

### Stage 4: Evaluation & Validation

**Validate Ground Truth Data**

```python
from llm_metadata.schemas.validation import DataFrameValidator
from llm_metadata.schemas.fuster_features import DatasetFeatureExtraction
import pandas as pd

# Load manual annotations
df = pd.read_excel("data/dataset_092624.xlsx")

# Validate against Pydantic schema
validator = DataFrameValidator(DatasetFeatureExtraction)
validation_result = validator.validate_dataframe(df)

if validation_result.is_valid:
    print(f"✓ All {len(df)} rows valid")
    validated_df = validation_result.valid_data
else:
    print(f"✗ {len(validation_result.errors)} validation errors")
    errors_df = validation_result.to_dataframe()
```

**Compare Automated vs Manual Extraction**

```python
from llm_metadata.groundtruth_eval import (
    evaluate_indexed, 
    EvaluationConfig, 
    FuzzyMatchConfig,
    micro_average,
    macro_f1
)

# Configure evaluation with fuzzy matching
config = EvaluationConfig(
    treat_lists_as_sets=True,
    fuzzy_match_fields={
        "species": FuzzyMatchConfig(threshold=70)
    }
)

# Compare extractions
report = evaluate_indexed(
    true_by_id=manual_annotations,
    pred_by_id=automated_extractions,
    config=config
)

# Compute metrics
micro_metrics = micro_average(report.field_metrics.values())
print(f"Precision: {micro_metrics['precision']:.3f}")
print(f"Recall: {micro_metrics['recall']:.3f}")
print(f"F1: {micro_metrics['f1']:.3f}")
```

## Project Context

This work is part of ongoing research to support biodiversity observation networks like **Biodiversité Québec** in implementing the **Kunming-Montreal Global Biodiversity Framework**. The project aims to:

1. **Identify data gaps**: Detect taxonomic, spatial, and temporal gaps in biodiversity data coverage for Quebec
2. **Discover hidden datasets**: Find relevant datasets buried in scientific literature and data repositories
3. **Evaluate LLM precision**: Compare automated extraction against manually annotated reference datasets
4. **Enable reproducible workflows**: Provide deterministic, repeatable metadata extraction for large-scale analysis

The extracted metadata helps prioritize data collection efforts and supports evidence-based decision-making for conservation policies and territorial planning.

## Development

Install development dependencies:

```bash
pip install -e .[dev]
```

Development tools included:
- pandas: Data analysis
- python-dotenv: Environment variable management
- ipykernel: Jupyter notebook support

### Notebooks

All experimentation, model evaluation, and proof-of-concept work happens in **Jupyter notebooks**. Notebooks serve as a research lab journal for testing the 4-stage pipeline: data ingestion strategies, schema variations, prompt engineering, and evaluation metric computation. Results are documented in `notebooks/README.md` with timestamped experiment reports.

**Key notebooks:**
- `fuster_test_extraction_evaluation.ipynb` - Abstract extraction evaluation (precision/recall/F1)
- `fulltext_extraction_evaluation.ipynb` - Full-text extraction with GROBID-parsed sections
- `download_dryad_pdfs_fuster.ipynb` - PDF acquisition with multi-strategy fallback
- `fuster_annotations_validation.ipynb` - Ground truth cleaning with Pydantic validation

See `notebooks/README.md` for complete experiment history and detailed results.

### Package Structure

```
llm_metadata/
├── dryad.py                    # Dryad API integration
├── zenodo.py                   # Zenodo API integration
├── openalex.py                 # OpenAlex API for article metadata
├── pdf_download.py             # Multi-strategy PDF acquisition
├── unpaywall.py                # Open access PDF discovery
├── ezproxy.py                  # Institutional authentication
├── scihub.py                   # Sci-Hub fallback
├── article_retrieval.py        # DOI matching (data papers ↔ articles)
├── pdf_parsing.py              # GROBID integration, TEI XML parsing
├── chunking.py                 # Section-aware text chunking
├── section_normalize.py        # Section classification
├── embedding.py                # OpenAI embeddings with caching
├── vector_store.py             # Qdrant vector database client
├── gpt_classify.py             # LLM classification engine
├── prefect_pipeline.py         # Batch processing orchestration
├── registry.py                 # Document tracking database
└── schemas/
    ├── abstract_metadata.py    # High-level metadata schema
    ├── fuster_features.py      # Detailed EBV feature schema
    ├── chunk_metadata.py       # Section-aware chunk metadata
    ├── evaluation.py           # Evaluation metrics framework
    └── validation.py           # Ground truth validation
```

## License

MIT License. See LICENSE for details.

---

**Keywords**: biodiversity, metadata extraction, LLM, GPT-4, Essential Biodiversity Variables (EBV), data gaps, Dryad, Zenodo, Kunming-Montreal Framework, Biodiversité Québec