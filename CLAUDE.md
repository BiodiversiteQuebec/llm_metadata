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
Create a `.env` file in the project root (see `.env.example` for all vars):
```bash
OPENAI_API_KEY=your_openai_api_key
ZENODO_ACCESS_TOKEN=your_zenodo_token            # Optional, for Zenodo features only
SEMANTIC_SCHOLAR_API_KEY=your_ss_api_key         # Optional, enables dedicated rate limit
```

Base URL overrides (set automatically in devcontainer, not needed locally):
```bash
OPENAI_API_BASE=http://proxy:8080/openai/v1      # Defaults to https://api.openai.com/v1
SEMANTIC_SCHOLAR_API_BASE=http://proxy:8080/semantic-scholar  # Defaults to https://api.semanticscholar.org/graph/v1
```

### Runtime Requirements

**IMPORTANT:** Always run Python through `uv` so the project `.venv` is used and `.env` is loaded.

```bash
uv run python your_script.py
```

Set `UV_ENV_FILE=.env` in your shell profile (`.bashrc`/`.zshrc`) once. `uv run` will auto-load `.env` locally; in cloud/Docker the var is simply absent and no file is loaded.


### Jupyter MCP Server

Before using the Jupyter MCP server, ensure a Jupyter Lab server is running. Use this command to check if it's running and start it if not:

```bash
export $(grep -v '^#' .env | xargs) && netstat -an | grep -q ":${JUPYTER_PORT}.*LISTEN" || jupyter lab --port=${JUPYTER_PORT} --IdentityProvider.token=${JUPYTER_TOKEN} --no-browser &
```

With uv run
```bash
uv run powershell.exe -NoProfile -Command '$p=$env:JUPYTER_PORT; $running=Test-NetConnection -ComputerName 127.0.0.1 -Port $p -InformationLevel Quiet; if ($running) { Write-Host ("Jupyter already listening on port " + $p) } else { Start-Process -WindowStyle Hidden -FilePath jupyter -ArgumentList @("lab","--port",$env:JUPYTER_PORT,"--IdentityProvider.token",$env:JUPYTER_TOKEN,"--no-browser"); Write-Host ("Started Jupyter on port " + $p) }'
```

Then start the MCP server.

## Architecture

This project implements a **4-stage LLM data engineering pipeline** for ecological metadata extraction:

```
Data Ingestion → Schema & Prompt Engineering → LLM Inference → Evaluation & Validation
```

### Stage 1: Data Ingestion & Preparation

**Purpose:** Acquire scientific papers and ground truth data for metadata extraction and model evaluation.

**Modules:**
- **[Stage 1]** `dryad.py`, `zenodo.py` — Repository API clients for dataset abstracts (Dryad, Zenodo)
- **[Stage 1]** `openalex.py` — OpenAlex API integration for article metadata and PDF URLs
- **[Stage 1]** `pdf_download.py` — Multi-strategy PDF acquisition with fallback chain:
  1. OpenAlex PDF URL (open access)
  2. Unpaywall API (green/gold OA repositories)
  3. EZproxy (institutional access via `ezproxy.py`)
  4. Sci-Hub (last resort via `scihub.py`)
- **[Stage 1]** `pdf_parsing.py` — GROBID-based full-text extraction, TEI XML parsing, hierarchical section structure
- **[Stage 1]** `article_retrieval.py` — DOI matching between data papers (Dryad) and scientific articles (for ground truth preparation)
- **[Stage 1]** `unpaywall.py` — Open access PDF discovery API
- **[Stage 1]** `semantic_scholar.py` — Semantic Scholar Graph API client for paper search, citations, and references
- **[Stage 1]** `registry.py` — SQLite-based document tracking database for processing status and chunk management

**Key Pattern:** All batch operations (search, download, parsing) use **Prefect** for parallelization, monitoring, and retry logic.

### Stage 2: Schema Design & Prompt Engineering

**Purpose:** Define structured output formats (Pydantic models) and engineer prompts for reliable extraction.

**Modules:**
- **[Stage 2]** `schemas/fuster_features.py` — Detailed EBV feature extraction following Fuster et al. methodology
  - Controlled vocabularies: `EBVDataType`, `GeospatialInfoType`, `ValidationStatus`, `FeatureLocation`
  - Main model: `DatasetFeatureExtraction` with field validators for data cleaning (European decimals, placeholder suppression, list splitting)
  - Vocabulary normalization mappings: `DATA_TYPE_MAPPING`, `GEO_TYPE_MAPPING`
- **[Stage 2]** `schemas/abstract_metadata.py` — High-level dataset metadata for quick categorization
- **[Stage 2]** `schemas/chunk_metadata.py` — Section-aware chunk metadata for full-text processing (section types, token counts, content flags)
- **[Stage 2]** `chunking.py` — Token-based text chunking with section boundary preservation (tiktoken-based, optimized for OpenAI embeddings)
- **[Stage 2]** `section_normalize.py` — Section classification into standard types (ABSTRACT, METHODS, RESULTS, etc.) using keyword matching
- **[Stage 2]** `openai_io.py` — Shared OpenAI client factory with env-driven base URL routing (see External Service IO pattern)
- **[Stage 2]** `embedding.py` — OpenAI embedding generation with local caching (text-embedding-3-large)
- **[Stage 2]** `vector_store.py` — Qdrant vector store client for chunk indexing and semantic search

**Key Pattern:** Pydantic models serve dual purpose: (1) structured output format for LLM via `responses.parse()`, (2) validation layer for ground truth data.

### Stage 3: LLM Inference & Batch Processing

**Purpose:** Execute metadata extraction at scale with cost tracking and caching.

**Modules:**
- **[Stage 3]** `gpt_classify.py` — Core classification engine using OpenAI's structured output API
  - Currently using `gpt-5-mini` with `reasoning={"effort": "low"}` (GPT-5 series parameter)
  - System prompt: "EcodataGPT" — conservative extraction philosophy (only explicit information)
  - Uses `client.responses.parse()` with Pydantic `text_format` for deterministic schema compliance
  - Built-in cost tracking per inference (`_response_usage_cost()`)
  - Joblib caching for reproducibility (`Memory("./cache")`)
- **[Stage 3]** `prefect_pipeline.py` — Orchestration layer for all batch operations
  - ThreadPoolTaskRunner (max_workers=10) for parallel DOI processing
  - Workflows: `doi_classification_pipeline()`, `quebec_papers_pipeline()`
  - Task decomposition: `fetch_abstracts()` → `classify_abstract_task()` (mapped)
  - Handles batch retrieval from Zenodo (20 DOIs per API call)

**Key Pattern:** Prefect manages ALL batch workflows (paper search, PDF download, inference) with monitoring dashboards.

### Stage 4: Evaluation & Validation

**Purpose:** Compare automated extraction against ground truth, compute metrics, normalize for fair comparison.

**Modules:**
- **[Stage 4]** `schemas/validation.py` — Pydantic-based validation for cleaning ground truth annotations
  - Row-level validation with structured error reporting (`ValidationError`, `ErrorType`)
  - `DataFrameValidator` for batch validation of annotated datasets
- **[Stage 4]** `groundtruth_eval.py` — Evaluation framework for precision/recall/F1 computation
  - Configurable normalization: case-folding, whitespace collapse, set-based list comparison
  - Fuzzy matching support: `FuzzyMatchConfig` with threshold-based string matching
  - Classes: `EvaluationConfig`, `FieldResult`, `FieldMetrics`, `EvaluationReport`
  - Key functions: `evaluate_indexed()`, `micro_average()`, `macro_f1()`

**Key Pattern:** Vocabulary normalization happens in Pydantic validators (single source of truth), fuzzy matching in evaluation config (experiment-friendly).

### Key Design Patterns

**Pydantic-Only Validation**: The project migrated from dual-layer Pandera+Pydantic to Pydantic-only architecture for data validation, reducing complexity by 50% while maintaining strict type enforcement.

**Conservative Extraction Philosophy**: The LLM prompt explicitly instructs to "only use information explicitly supported by text" and "prefer conservative outputs over over-extraction" to minimize false positives.

**Evaluation Normalization**: The evaluation module uses configurable normalization strategies (case-folding, whitespace collapse, set-based list comparison) to handle semantic equivalence between manual and automated extractions.

**Enrichment Pattern**: For fields that benefit from external resolution (e.g., species strings → GBIF taxon keys, locations → GADM codes), add a derived field to the model (like `gbif_keys: Optional[list[int]]`) alongside the original, then evaluate both independently in a single `evaluate_indexed()` call. This avoids complex matcher abstractions — strategy comparison is just `report.metrics_for("species")` vs `report.metrics_for("gbif_keys")`. Precedent: source-tracking fields (`source`, `is_oa`, etc.) in `fuster_features.py`.

**Validator Boundary**: Pydantic validators handle pure, fast normalization only — delimiter splitting, whitespace stripping, vocabulary mapping. Never put network I/O or external API calls in validators. Enrichment from external services (GBIF, GADM, etc.) is a separate preprocessing step that runs *after* model construction.

**Structured Preprocessing Models**: When a raw field (e.g., `species: list[str]`) needs structured parsing for downstream consumers, use a Pydantic model with `model_validator(mode='before')` that accepts the raw type (e.g., `ParsedTaxon("41 fish mock species")` → structured fields). This keeps the storage format unchanged while providing structured access when needed.

**External Service IO**: Modules that call external APIs (OpenAI, Semantic Scholar, etc.) must support base URL swapping via environment variable so they can run either directly against the provider or through a reverse proxy that injects secrets.

- **Env var convention**: `{SERVICE}_API_BASE` for the base URL the app code uses, `{SERVICE}_API_KEY` for the auth credential. Examples: `OPENAI_API_BASE`, `SEMANTIC_SCHOLAR_API_BASE`.
- **Secrets are optional**: IO modules must treat API keys as `Optional`. Behind a proxy, the proxy injects auth headers — the app never sees the key. Only require a key when the base URL points to the official provider (i.e., no proxy).
- **Always provide a safe default**: `os.getenv("SEMANTIC_SCHOLAR_API_BASE", "https://api.semanticscholar.org/graph/v1")`. When no env var is set, code hits the official endpoint directly — zero config for local development.
- **Centralize client creation**: Use a factory module (e.g., `openai_io.py` → `get_openai_client()`) so every call site inherits the base URL routing. Avoid scattering `os.getenv` across individual functions.
- **Devcontainer proxy pattern**: In the devcontainer, an nginx reverse proxy holds the API keys and injects auth headers. The app container only sees `{SERVICE}_API_BASE` pointing to the proxy. This keeps secrets out of the app environment. Details in `.devcontainer/README.md`.
- **Adding a new service**: (1) create or update an IO module with env-driven base URL + default, (2) add the key to the proxy nginx config, (3) add `{SERVICE}_API_BASE` to docker-compose for the app container, (4) document in `.env.example`.

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

All testing, prototyping, and proof-of-concept work is **notebook-based**. Notebooks serve as the primary medium for experimenting with the 4-stage pipeline:

**Stage 1 (Data Ingestion):** PDF download notebooks, article retrieval exploration
**Stage 2 (Schema/Prompt):** Schema validation, chunking parameter tuning
**Stage 3 (Inference):** Model comparison, prompt variations, cost analysis
**Stage 4 (Evaluation):** Metric computation, error analysis, comparative reports

**Key Notebooks:**
- `fuster_test_extraction_evaluation.ipynb` - Abstract-based extraction evaluation against ground truth
- `fulltext_extraction_evaluation.ipynb` - Full-text extraction using GROBID-parsed sections
- `single_doi_extraction_with_evidence.ipynb` - Evidence tracking cost-benefit analysis
- `download_dryad_pdfs_fuster.ipynb` - PDF acquisition with multi-strategy fallback
- `pdf_chunking_exploration.ipynb` - Chunking parameter optimization
- `fuster_annotations_validation.ipynb` - Ground truth cleaning and Pydantic validation

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

## Task Management & Session Coordination

### Session Start
- Read `TODO.md` for current project state and task assignments
- Check Active Sessions table for conflicts before starting work
- Read referenced plan file in `plans/` for task details

### Plans
- Plan files live in `plans/`, one file per initiative
- `TODO.md` references plans; plans hold the detail
- Keep plans concise — prefer actionable work units over prose
- Do not create multiple files for a single initiative (no separate "agent plan", "visual overview", "execution guide")

### Task Parallelization & Flow
- Plan files should declare **dependencies** between work units so independent tasks can run in parallel
- Use a simple notation: `deps: [2.1, 2.3]` means "blocked until 2.1 and 2.3 are done"
- Group tasks into **execution rounds** — each round contains tasks whose dependencies are satisfied
- Within a round, independent tasks can be dispatched to parallel sessions or subagents

Example:
```
Round 1: Task 2.1 || Task 2.2          (no deps, run in parallel)
Round 2: Task 2.3                       (deps: 2.1)
Round 3: Task 3.1 || Task 3.2          (deps: 2.3 and 2.2 respectively)
```

### Model Recommendations
Each work unit in a plan should include a **model recommendation** to guide session dispatch:

| Model | Use for |
|-------|---------|
| `opus` | Architecture decisions, complex multi-file refactors, research requiring deep reasoning |
| `sonnet` | Standard implementation, API clients, schema changes, notebook work, most coding tasks |
| `haiku` | Documentation updates, simple edits, file moves, mechanical refactors |

Notation in plan files: `model: sonnet` on each work unit. Default to `sonnet` if unspecified.

When launching subagents via the Task tool, pass the `model` parameter matching the work unit's recommendation (e.g., `model="haiku"` for a docs task tagged `model: haiku`).

### Session End
- Update `TODO.md`: mark tasks complete, clear Active Sessions entry
- If notebook work was done, update `notebooks/README.md` per Lab Logging Protocol
- Commit and push
