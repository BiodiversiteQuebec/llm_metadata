# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`llm_metadata` is a Python package for extracting structured ecological metadata from scientific dataset abstracts using Large Language Models (LLMs). The project supports biodiversity monitoring efforts by identifying datasets to fill taxonomic, spatial, and temporal gaps in biodiversity data coverage, following the methodology of Fuster et al. (2025).

**Core goal:** Automate metadata extraction from unstructured abstract text to support the Kunming-Montreal Global Biodiversity Framework and Biodiversité Québec initiatives.

## Commands

### Setup
```bash
# Install package
pip install -e .

# Install with development dependencies
pip install -e .[dev]
```

### Testing
```bash
# Run all tests
python -m pytest tests/

# Run specific test file
python -m pytest tests/test_evaluation.py

# Run specific test
python -m pytest tests/test_evaluation.py::TestEvaluation::test_evaluate_pairs_scalar_and_list_fields
```

### Running Scripts
```bash
# Test GPT classification with example abstract
python src/llm_metadata/gpt_classify.py

# Test Prefect pipeline for batch processing
python src/llm_metadata/prefect_pipeline.py
```

### Environment Setup
Create a `.env` file in the project root with:
```bash
OPENAI_API_KEY=your_openai_api_key
ZENODO_ACCESS_TOKEN=your_zenodo_token  # Optional, for Zenodo features only
```

## Architecture

### Core Components

**1. Data Acquisition Layer** (`dryad.py`, `zenodo.py`)
- Retrieves dataset abstracts from scientific repositories (Dryad, Zenodo)
- Handles API pagination and batch requests

**2. LLM Extraction Engine** (`gpt_classify.py`)
- Extracts structured metadata using OpenAI's structured output API
- Currently using `gpt-5-mini` model with reasoning parameter `{"effort": "low"}`
- System prompt defines "EcodataGPT" as a conservative extraction engine that only extracts information explicitly supported by text
- Uses `client.responses.parse()` with Pydantic `text_format` parameter for deterministic schema compliance

**3. Schema Layer** (`schemas/`)
- **`fuster_features.py`**: Detailed Essential Biodiversity Variables (EBV) feature extraction following Fuster et al. methodology
  - Includes controlled vocabularies: `EBVDataType`, `GeospatialInfoType`, `ValidationStatus`, `InvalidReason`, `FeatureLocation`
  - Main model: `DatasetFeatureExtraction` with validators for data cleaning (e.g., European decimals, placeholder suppression, comma-separated list splitting)
- **`abstract_metadata.py`**: High-level dataset metadata for quick categorization
- **`evaluation.py`**: Evaluation framework for comparing manual vs automated extraction
  - Implements precision/recall/F1 metrics with configurable normalization (casefold, whitespace collapse, set-based list comparison)
  - Classes: `EvaluationConfig`, `FieldResult`, `FieldMetrics`, `EvaluationReport`
  - Key functions: `evaluate_pairs()`, `micro_average()`, `macro_f1()`
- **`validation.py`**: Pydantic-based validation utilities for cleaning annotated data

**4. Batch Processing Pipeline** (`prefect_pipeline.py`)
- Prefect flow with ThreadPoolTaskRunner (max_workers=10) for parallel DOI processing
- Task decomposition: `fetch_abstracts()` → `classify_abstract_task()` (mapped)
- Handles batch retrieval from Zenodo (20 DOIs per API call)

### Key Design Patterns

**Pydantic-Only Validation**: The project migrated from dual-layer Pandera+Pydantic to Pydantic-only architecture for data validation, reducing complexity by 50% while maintaining strict type enforcement.

**Conservative Extraction Philosophy**: The LLM prompt explicitly instructs to "only use information explicitly supported by text" and "prefer conservative outputs over over-extraction" to minimize false positives.

**Evaluation Normalization**: The evaluation module uses configurable normalization strategies (case-folding, whitespace collapse, set-based list comparison) to handle semantic equivalence between manual and automated extractions.

## Data Files

- **`data/dataset_092624.xlsx`**: Raw manual annotations from Fuster et al. (418 records)
- **`data/dataset_092624_validated.xlsx`**: Cleaned annotations (100% schema compliance)
- **`notebooks/results/`**: Evaluation reports (HTML) with side-by-side comparisons

## Research Context

This project implements and evaluates the automated dataset retrieval methodology from:

> Fuster-Calvo A, Valentin S, Tamayo WC, Gravel D. 2025. Evaluating the feasibility of automating dataset retrieval for biodiversity monitoring. PeerJ 13:e18853 https://doi.org/10.7717/peerj.18853

Key research questions:
1. Can LLMs extract EBV features from abstracts with sufficient precision for data gap analysis?
2. What is the tradeoff between recall (comprehensive coverage) and precision (false positive rate)?
3. Which feature types (taxonomic, spatial, temporal, data type) are most reliably extracted?

## Development Workflow

### Notebook-Based Experimentation

All testing, prototyping, and proof-of-concept work is **notebook-based**. Notebooks serve as the primary medium for:
- Model experimentation (comparing GPT versions, prompt variations, parameter tuning)
- Evaluation pipeline development
- Data exploration and validation
- Performance analysis and metric computation

**Notebook Organization:**
- Store all notebooks in `notebooks/`
- Create timestamped subdirectories in `notebooks/results/` for experiment outputs (e.g., `fuster_test_extraction_evaluation_20260107_01/`)
- Archive old or superseded notebooks in `notebooks/archives/`

**Lab Logging Protocol:**
When completing notebook-based work, **ALWAYS** update `notebooks/README.md` with:
1. **Date header** (e.g., `### 2026-01-08: [Task Title]`)
2. **Task description**: What you set out to accomplish
3. **Work performed**: Notebook name, architectural changes, methods used
4. **Results**: Quantitative metrics, key findings, tables
5. **Key issues identified**: Problems, limitations, unexpected behavior
6. **Next steps**: Follow-up work or open questions (optional)
7. **Report link**: Path to HTML report if generated

This creates a research journal that documents the evolution of the project's methodology and performance.

### Model Configuration Notes

- **Model Selection**: Currently using `gpt-5-mini` (cost-effective, faster than GPT-4)
- **Reasoning Parameter**: GPT-5 series models use `reasoning={"effort": "low"}` instead of `temperature` for inference control
- **Structured Output**: All extraction uses OpenAI's `responses.parse()` API with Pydantic `text_format` for guaranteed schema compliance
