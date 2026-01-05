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

### Dryad Integration

Search for datasets on Dryad by keywords:

```python
from llm_metadata.dryad import search_datasets, get_dataset

# Search for datasets related to Quebec biodiversity
results = search_datasets("biodiversity Quebec Canada", per_page=10)

# Get a specific dataset by DOI
doi = "doi:10.5061/dryad.n726pq6"
dataset = get_dataset(doi)
print(dataset)
```

### Zenodo Integration

Retrieve Zenodo records by DOI:

```python
from llm_metadata.zenodo import get_record_by_doi, get_record_by_doi_list

# Get a single record
record = get_record_by_doi("10.5061/dryad.2n5h6")
abstract = record['metadata']['description']

# Get multiple records
dois = ["10.5061/dryad.2n5h6", "10.5061/dryad.3nh72"]
records = get_record_by_doi_list(dois)
```

### GPT-4 Metadata Extraction

Extract structured metadata from dataset abstracts to identify data gaps:

```python
from llm_metadata.gpt_classify import classify_abstract
from llm_metadata.schemas import DatasetAbstractMetadata

abstract = """
We monitored caribou populations in northern Quebec from 1999 to 2015
using GPS telemetry. The dataset includes movement trajectories and
habitat use data for 45 individuals across three herds.
"""

# Extract high-level metadata
result = classify_abstract(
    abstract, 
    response_format=DatasetAbstractMetadata
)

metadata = result['output']
print(metadata.taxonomic_groups)        # ['caribou']
print(metadata.regions_of_interest)     # ['Quebec']
print(metadata.dataset_year_start)      # 1999
print(metadata.dataset_year_end)        # 2015
print(metadata.categories)              # ['trajectory', 'population time-series']
```

For detailed feature extraction following the EBV framework:

```python
from llm_metadata.schemas import DatasetFeatureExtraction

result = classify_abstract(
    abstract,
    response_format=DatasetFeatureExtraction
)

features = result['output']
print(features.data_type)          # ['trajectory', 'time_series']
print(features.taxons)             # 'caribou'
print(features.temp_range_i)       # 1999
print(features.temp_range_f)       # 2015
print(features.geospatial_info_dataset)  # 'sample'
```

### Batch Processing with Prefect

Process multiple datasets in parallel for large-scale data gap analysis:

```python
from llm_metadata.prefect_pipeline import doi_classification_pipeline

# Process multiple DOIs from Quebec-related datasets
dois = [
    "10.5061/dryad.2n5h6",
    "10.5061/dryad.3nh72",
    "10.5061/dryad.4k275"
]

results = doi_classification_pipeline(dois=dois)

# Analyze results to identify data gaps
for result in results:
    print(f"Taxons: {result['output'].taxons}")
    print(f"Temporal range: {result['output'].temp_range_i} - {result['output'].temp_range_f}")
    print(f"Data type: {result['output'].data_type}")
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

### Package Structure

```
llm_metadata/
├── dryad.py                    # Dryad API integration
├── zenodo.py                   # Zenodo API integration
├── gpt_classify.py             # GPT-4 classification engine
├── prefect_pipeline.py         # Batch processing pipeline
└── schemas/
    ├── abstract_metadata.py    # High-level metadata schema
    └── fuster_features.py      # EBV feature extraction schema
```

## License

MIT License. See LICENSE for details.

---

**Keywords**: biodiversity, metadata extraction, LLM, GPT-4, Essential Biodiversity Variables (EBV), data gaps, Dryad, Zenodo, Kunming-Montreal Framework, Biodiversité Québec