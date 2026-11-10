# llm_metadata

Extract structured ecological metadata from scientific datasets and articles with large language models (LLMs), then use it to judge which datasets are relevant for biodiversity monitoring.

✨ Results exploration app: [coleo.biodiversite-quebec.ca/llm_extraction_results](https://coleo.biodiversite-quebec.ca/llm_extraction_results/)

## Contents

- [Overview](#overview)
- [Notebooks: how the project was used](#notebooks-how-the-project-was-used)
- [Quick start](#quick-start)
- [Project structure](#project-structure)
- [Key concepts](#key-concepts)
- [Running evaluations](#running-evaluations)
- [Results app](#results-app)
- [Using the modules directly](#using-the-modules-directly)
- [Tests](#tests)
- [Where to find things](#where-to-find-things)
- [Reference](#reference)

## Overview

**Why.** Biodiversity observation networks such as Biodiversité Québec need data that covers taxa, regions and periods well enough to track progress toward the Kunming-Montreal Global Biodiversity Framework. Many useful datasets are known only through unstructured text: repository descriptions, abstracts and articles. This project reads that text with an LLM and turns it into structured features. The features can then show which datasets fill taxonomic, spatial and temporal gaps, and which ones can feed Biodiversité Québec's indicators and analyses.

**What is extracted.** The features follow the Essential Biodiversity Variables (EBV) framing of Fuster-Calvo et al. (2025):
- data type;
- species;
- temporal range;
- spatial range and type of geospatial information;
- time series;
- "modulator" flags: multispecies, threatened species, new species to science or to the region, north–south bias.

**How it is evaluated.** Fuster-Calvo et al. annotated about 400 datasets by hand (Dryad, Zenodo, Semantic Scholar). Those annotations are the ground truth. The project measures precision, recall and F1 per field, for several kinds of input:
- the abstract or repository description (short text);
- the article PDF sent to the model;
- the article's sections parsed with GROBID.

**Relevance scoring: two approaches compared.**
1. **Rules on extracted features:** the LLM extracts the features, then the relevance rules of Fuster-Calvo et al. are applied in code.
2. **Direct scoring:** the rules and priorities are written into the prompt, and the LLM returns the relevance category itself.

The article in preparation compares the two, on short text and on full text. Its plan is in [`docs/article_outline.md`](docs/article_outline.md).

## Notebooks: how the project was used

All experiments are run in Jupyter notebooks in [`notebooks/`](notebooks/). [`notebooks/README.md`](notebooks/README.md) is the **lab journal**: one dated entry per session, with the task, the work performed, the results and the issues found. Read it to see how a result was obtained.

The research went through these steps, in order:

| Step | What it does | Notebooks |
|---|---|---|
| 1. Clean the ground truth | Validate the manual annotations against the Pydantic schemas, keep the valid records, add article and PDF links | `fuster_annotations_validation.ipynb`, `data_semantic_scholar.ipynb` |
| 2. Get the full text | Download the PDFs (open-access sources first), parse them with GROBID | `download_all_fuster_pdfs.ipynb`, `pdf_chunking_exploration.ipynb` |
| 3. Baseline extraction | Extract features from each kind of input and evaluate them against the ground truth | `batch_abstract_evaluation.ipynb`, `batch_pdf_file_evaluation.ipynb`, `batch_fulltext_evaluation.ipynb` |
| 4. Harden the evaluation | Choose a matching strategy per field; improve species matching | `field_strategies_eval_demo.ipynb`, `species_recall_improvement.ipynb`, `taxonomic_relevance_evaluation.ipynb` |
| 5. Prompt iteration | Change one prompt block at a time and compare each run with the baseline, on the fixed 30-record evaluation subset | `prompt_eval` command (see [Running evaluations](#running-evaluations)), results app, `prompt_eval_results.ipynb` |
| 6. Relevance scoring, rules on extracted features | Apply the relevance rules to the human-annotated features (a ceiling check), then to the features extracted from short text and from PDFs | `relevance_mechanistic.ipynb`, `relevance_mechanistic_pdf.ipynb` |
| 7. Relevance scoring, direct | Ask the LLM for the relevance category, from short text and from PDFs | `relevance_llm_direct.ipynb`, `relevance_llm_direct_pdf.ipynb` |
| Exploratory | Tracing each extracted value back to the sentence that supports it | `claim_grounding_pilot.ipynb`, `single_doi_extraction_with_evidence.ipynb` |

- **Results:** figures and tables are saved in `notebooks/results/`.
- **Older notebooks** are in `notebooks/archives/`.
- **Results and synthesis for relevance scoring:** [`plans/automated_relevance_classification.md`](plans/automated_relevance_classification.md).

## Quick start

1. **Install** with [uv](https://docs.astral.sh/uv/):

   ```bash
   uv sync
   ```

2. **Configure.** Create a `.env` file at the project root:

   ```bash
   OPENAI_API_KEY=your_openai_api_key           # required for extraction
   SEMANTIC_SCHOLAR_API_KEY=your_key            # optional, higher rate limit
   ZENODO_ACCESS_TOKEN=your_token               # optional, Zenodo features only

   # Optional: where runs are written and where the app looks for them
   PROMPT_EVAL_OUTPUT_DIR=artifacts/runs
   EVAL_VIEWER_RESULTS_DIR=artifacts/runs

   # Optional: route API calls through a proxy (set in the devcontainer)
   # OPENAI_API_BASE=http://proxy:8080/openai/v1
   # SEMANTIC_SCHOLAR_API_BASE=http://proxy:8080/semantic-scholar
   ```

   Always run Python through `uv run` so the project environment is used. Set `UV_ENV_FILE=.env` once in your shell profile, and `uv run` will load `.env` automatically.

3. **Run one evaluation** on the 30-record evaluation subset (cached calls are reused):

   ```bash
   uv run python -m llm_metadata.prompt_eval --mode abstract --manifest data/manifests/dev_subset_data_paper.csv --gt-manifest data/gt/fuster_gt.json --name my_first_run
   ```

4. **Look at the results:**

   ```bash
   uv run app
   ```

**Full-text work needs two services.** PDF parsing needs GROBID, and semantic search needs Qdrant. Both are in `docker-compose.yml`:

```bash
docker compose up -d
```

## Project structure

```
llm_metadata/
├── src/llm_metadata/   # the package: the four-stage pipeline (below)
├── notebooks/          # experiments + README.md lab journal
├── data/               # durable inputs: annotations, ground truth, manifests
├── artifacts/          # generated outputs: parsed PDFs, runs, logs (mostly gitignored)
├── configs/            # evaluation strategies (default, fuzzy species, strict)
├── app/                # Docker files for deploying the results app
├── docs/               # guides and article material
├── plans/              # one plan per initiative; TODO.md tracks their status
├── scripts/            # one-off scripts (bulk PDF download, Jupyter start-up)
└── tests/              # pytest suite
```

**Rule of thumb:** `data/` holds what you would not want to regenerate. `artifacts/` holds anything a run can produce again.

### The package, by pipeline stage

**1. Data ingestion:** get the datasets, the articles and their full text.

| Module | Role |
|---|---|
| `dryad.py`, `zenodo.py`, `semantic_scholar.py` | API clients for the dataset and paper sources |
| `openalex.py`, `unpaywall.py` | Article metadata and open-access PDF links |
| `pdf_download.py` (+ `ezproxy.py`, `scihub.py`) | PDF download with a fallback chain |
| `pdf_parsing.py`, `section_normalize.py` | GROBID parsing into sections, section types (methods, results…) |
| `doi_utils.py` | DOI cleaning and matching |

**2. Schemas and prompts:** what the LLM must return and how it is asked.

| Module | Role |
|---|---|
| `schemas/fuster_features.py` | The feature schemas and controlled vocabularies (see [Key concepts](#key-concepts)) |
| `schemas/data_paper.py` | The input manifest and run artifact contracts |
| `schemas/validation.py` | Validation of the manual annotations |
| `schemas/abstract_metadata.py`, `schemas/chunk_metadata.py`, `schemas/openalex_work.py`, `schemas/evidence.py` | Other contracts: quick categorization, text chunks, article metadata, evidence |
| `prompts/common.py` | Shared prompt blocks: persona, extraction philosophy, vocabulary, modulator fields, output format |
| `prompts/abstract.py`, `prompts/section.py`, `prompts/pdf_file.py` | The prompt for each input mode |
| `chunking.py`, `embedding.py`, `vector_store.py`, `registry.py` | Chunking, embeddings and Qdrant storage for full-text search |

**3. LLM inference:** run the extraction.

| Module | Role |
|---|---|
| `openai_io.py` | The single OpenAI client factory (handles the proxy base URL) |
| `gpt_extract.py` | One structured-output call, with cost tracking and caching |
| `extraction.py` | Runs a whole manifest in one explicit mode |

**4. Evaluation:** compare with the ground truth.

| Module | Role |
|---|---|
| `groundtruth_eval.py` | Per-field matching, precision / recall / F1, evaluation report |
| `species_parsing.py`, `taxonomy_eval.py`, `gbif.py` | Species string parsing, taxonomic matching, GBIF taxon lookup |
| `prompt_eval.py` | Extraction + evaluation in one command or function call; saves a run artifact |
| `app/app_eval_viewer.py` | The Streamlit results app |

## Key concepts

- **Three feature schemas, three roles** (`schemas/fuster_features.py`):
  - `DatasetFeaturesExtraction` is what the LLM must return;
  - `DatasetFeaturesNormalized` cleans the manual annotations (synonym mapping, list splitting, placeholder removal);
  - `DatasetFeaturesEvaluation` adds derived fields such as GBIF keys.

  The LLM output and the ground truth go through the same normalization, so they are compared fairly.
- **Explicit extraction mode:** every run states its mode:
  - `abstract`: abstract or repository description;
  - `pdf_text`: text extracted from the PDF;
  - `pdf_native`: PDF file sent to the model;
  - `sections`: GROBID sections.

  Prompts do not imply a mode.
- **Manifest as input:** a run takes a `DataPaperManifest` (a CSV of records with DOIs, text and PDF paths) and writes one JSON run artifact. Build and load manifests only through their own methods (`DataPaperManifest.load_csv`, `.build`, `.save_csv`).
- **Per-field evaluation strategies:** `DEFAULT_FIELD_STRATEGIES` in `groundtruth_eval.py` (mirrored in `configs/eval_default.json`) sets which 12 fields are evaluated and how. Matching is exact for categories, years and booleans, and name-aware fuzzy matching is used for species.
- **Conservative extraction:** the prompts ask the model to report only what the text states explicitly, and to prefer leaving a field empty over guessing.
- **Validators stay pure:** schema validators only normalize text. Calls to outside services (GBIF and others) are a separate enrichment step.

## Running evaluations

From the command line:

```bash
uv run python -m llm_metadata.prompt_eval \
  --mode abstract \
  --manifest data/manifests/dev_subset_data_paper.csv \
  --gt-manifest data/gt/fuster_gt.json \
  --config configs/eval_default.json \
  --name abstract_20260219_01
```

- `--mode`: `abstract`, `pdf_text`, `pdf_native` or `sections`.
- `--fields species,data_type`: evaluate only some fields.
- `--skip-cache`: force fresh API calls (by default, identical calls are read from the cache).

Where the output goes:
- `--name run_id` → `artifacts/runs/{timestamp}_run_id.json` plus a matching `.log`.
- `--output run.json` (bare file name) → `artifacts/runs/{timestamp}_run.json`.
- `--output path/to/run.json` → exactly that path.
- With neither option → `{timestamp}_prompt_eval.json`.

From Python or a notebook:

```python
import json
from llm_metadata.prompt_eval import run_eval
from llm_metadata.schemas.data_paper import DataPaperManifest

manifest = DataPaperManifest.load_csv("data/manifests/dev_subset_data_paper.csv").records
gt = json.loads(open("data/gt/fuster_gt.json").read())

report = run_eval(
    mode="abstract",
    manifest=manifest,
    gt=gt,
    config_path="configs/eval_default.json",
    name="abstract_20260219_01",
)
```

The prompt iteration rules (baseline first, one change at a time, compare with the baseline, analyst notes per run) are in [`AGENTS.md`](AGENTS.md), under "Prompt Engineering Workflow".

## Results app

```bash
uv run app
```

The Streamlit app reads the run artifacts and has six tabs:
- **Overview:** run metadata, ground truth table, prompt used, logs.
- **Extraction output:** the raw features returned for each record.
- **Detailed metrics:** precision, recall and F1 per field, with the mismatches and their likely cause.
- **Dataset results:** one paper at a time.
- **Compare runs:** the difference per field between two runs.
- **Trends:** how each field evolves across runs.

Tables can be exported to CSV or Markdown. Analyst notes for a run are kept in `{run}_notes.md`, next to the run file.

To run it in Docker (viewer only, without GROBID or Qdrant):

```bash
docker compose -f app/docker-compose.viewer.yml up --build
```

The app then runs at `http://localhost:8501`. Point `EVAL_VIEWER_RESULTS_DIR` to the folder of runs to show (for the deployed app, `app/prompt_eval_results`).

## Using the modules directly

Extract features from any text:

```python
from llm_metadata.gpt_extract import extract_from_text
from llm_metadata.schemas.fuster_features import DatasetFeaturesExtraction

text = """We monitored caribou populations in northern Quebec from 1999 to 2015
using GPS telemetry, for 45 individuals across three herds."""

result = extract_from_text(text, text_format=DatasetFeaturesExtraction)
features = result["output"]
print(features.species, features.temp_range_i, features.temp_range_f, features.data_type)
print(f"Cost: ${result['usage_cost']['total_cost']}")
```

Run a whole manifest in one mode, without evaluation:

```python
from llm_metadata.extraction import run_manifest_extraction
from llm_metadata.schemas.data_paper import DataPaperManifest

manifest = DataPaperManifest.load_csv("data/manifests/dev_subset_data_paper.csv")
artifact = run_manifest_extraction(manifest, mode="abstract", name="dev_subset_abstract")
print(artifact.total_cost_usd)
```

Download and parse a PDF:

```python
from llm_metadata.pdf_download import download_pdf_with_fallback
from llm_metadata.pdf_parsing import process_pdf

pdf_path = download_pdf_with_fallback(doi="10.1371/journal.pone.0128238")
tei_path, doc = process_pdf(pdf_path=pdf_path, work_id="doi_10.1371_journal.pone.0128238",
                            grobid_url="http://localhost:8070")
print(doc.title, len(doc.sections))
```

More examples for each stage (repository APIs, chunking, embeddings, vector search) are in [`docs/pipelines_guide.md`](docs/pipelines_guide.md).

## Tests

```bash
uv run python -m pytest tests/
```

Some tests call live APIs (Dryad, Zenodo, Semantic Scholar, OpenAlex) and need network access.

## Where to find things

| Looking for… | Go to |
|---|---|
| The state of the work and what's next | [`TODO.md`](TODO.md), then the plan it links to in [`plans/`](plans/) |
| How a result was obtained | [`notebooks/README.md`](notebooks/README.md) (lab journal, newest first) |
| The article plan | [`docs/article_outline.md`](docs/article_outline.md) |
| How evaluation works, field by field | [`docs/evaluation_audit_guide.md`](docs/evaluation_audit_guide.md) |
| Full project conventions (architecture, patterns, prompt workflow) | [`AGENTS.md`](AGENTS.md) |
| Institutional PDF access | [`docs/ezproxy_guide.md`](docs/ezproxy_guide.md) |

## Reference

This work builds on:

> Fuster-Calvo A, Valentin S, Tamayo WC, Gravel D. 2025. Evaluating the feasibility of automating dataset retrieval for biodiversity monitoring. *PeerJ* 13:e18853. https://doi.org/10.7717/peerj.18853

MIT License. See LICENSE for details.
