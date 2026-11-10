# Module guide

Code examples for each stage of the pipeline. The [README](../README.md) covers the main path: a `prompt_eval` run on a manifest, then the results app. This guide is for when you want to call the modules yourself, in a notebook or a script.

Run everything through `uv run` so the project environment and `.env` are used.

---

## Stage 1: data ingestion

### Datasets and papers from the repositories

```python
from llm_metadata.dryad import search_datasets, get_dataset
from llm_metadata.zenodo import get_record_by_doi, get_record_by_doi_list
from llm_metadata.semantic_scholar import get_paper_by_doi, get_open_access_pdf_url

# Dryad: keyword search, or one dataset by DOI
results = search_datasets("biodiversity Quebec Canada", per_page=10)
dataset = get_dataset("doi:10.5061/dryad.n726pq6")

# Zenodo (needs ZENODO_ACCESS_TOKEN): one record or a batch
record = get_record_by_doi("10.5061/dryad.2n5h6")
records = get_record_by_doi_list(["10.5061/dryad.2n5h6", "10.5061/dryad.3nh72"])

# Semantic Scholar: paper metadata and open-access PDF link
paper = get_paper_by_doi("10.1371/journal.pone.0128238")
pdf_url = get_open_access_pdf_url("10.1371/journal.pone.0128238")
```

### Article metadata from OpenAlex

```python
from llm_metadata.openalex import get_work_by_doi, extract_abstract, extract_pdf_url

work = get_work_by_doi("10.1371/journal.pone.0128238")
abstract = extract_abstract(work)   # OpenAlex stores abstracts as an inverted index
pdf_url = extract_pdf_url(work)
```

### PDF download

`download_pdf_with_fallback` tries the open-access sources first (OpenAlex, then Unpaywall), then institutional access. For the article, only open-access PDFs are used.

```python
from llm_metadata.pdf_download import download_pdf_with_fallback

pdf_path = download_pdf_with_fallback(doi="10.1371/journal.pone.0128238")
```

Institutional access needs browser cookies. See [`ezproxy_guide.md`](ezproxy_guide.md).

### Full-text parsing with GROBID

Start GROBID first: `docker compose up -d grobid`.

```python
from pathlib import Path
from llm_metadata.pdf_parsing import process_pdf

tei_path, doc = process_pdf(
    pdf_path=Path("data/pdfs/article.pdf"),   # where downloads are stored
    work_id="W123",                       # OpenAlex work ID
    grobid_url="http://localhost:8070",   # default: from env or localhost
)
print(doc.title, len(doc.sections))
```

The TEI XML and the parsed document JSON are saved under `artifacts/`.

---

## Stage 2: schemas and full-text search

### Feature schemas

```python
from llm_metadata.schemas.fuster_features import (
    DatasetFeaturesExtraction,   # what the LLM must return
    DatasetFeaturesNormalized,   # cleans manual annotations
    DatasetFeaturesEvaluation,   # adds derived fields (GBIF keys)
    EBVDataType,
)
```

### Chunks, embeddings and vector search

Start Qdrant first: `docker compose up -d qdrant`.

```python
from llm_metadata.chunking import chunk_document, ChunkingConfig
from llm_metadata.embedding import embed_chunks
from llm_metadata.vector_store import init_collection, upsert_chunks, search_chunks

# Split a parsed document into section-aware chunks
config = ChunkingConfig(target_tokens=450, max_tokens=650, overlap_tokens=80)
chunks = chunk_document(doc, config=config)

# Embed (cached locally) and store
embeddings, _records = embed_chunks(chunks)
init_collection()
upsert_chunks(chunks, embeddings)

# Search with a query vector, filtered on section type
hits = search_chunks(query_vector=embeddings[0], limit=5, section_types=["METHODS"])
```

This full-text search path was explored but is not used in the current evaluations.

---

## Stage 3: LLM inference

### One text

```python
from llm_metadata.gpt_extract import extract_from_text
from llm_metadata.schemas.fuster_features import DatasetFeaturesExtraction

result = extract_from_text(
    "We monitored caribou in northern Quebec from 1999 to 2015 using GPS telemetry.",
    text_format=DatasetFeaturesExtraction,
)
features = result["output"]                       # a DatasetFeaturesExtraction
print(result["usage_cost"]["total_cost"])         # cost in USD
```

Calls are cached with joblib. Pass `skip_cache=True` to force a fresh call.

### A whole manifest

```python
from llm_metadata.extraction import run_manifest_extraction
from llm_metadata.schemas.data_paper import DataPaperManifest

manifest = DataPaperManifest.load_csv("data/manifests/dev_subset_data_paper.csv")
artifact = run_manifest_extraction(
    manifest,
    mode="sections",       # abstract | pdf_text | pdf_native | sections
    name="dev_subset_sections",
)
print(artifact.total_cost_usd)
```

---

## Stage 4: evaluation

### Validate the manual annotations

```python
import pandas as pd
from llm_metadata.schemas.validation import DataFrameValidator
from llm_metadata.schemas.fuster_features import DatasetFeaturesNormalized

df = pd.read_excel("data/dataset_092624.xlsx")
report = DataFrameValidator(DatasetFeaturesNormalized).validate(df)
print(report.summary())
valid_df = report.valid_rows_to_dataframe()
errors_df = report.errors_to_dataframe()
```

### Compare extractions with the ground truth

```python
from llm_metadata.groundtruth_eval import (
    DEFAULT_FIELD_STRATEGIES, EvaluationConfig, evaluate_indexed, micro_average, macro_f1,
)

config = EvaluationConfig(field_strategies=DEFAULT_FIELD_STRATEGIES)

# Both dicts map a record ID (e.g. a DOI) to a Pydantic feature model
report = evaluate_indexed(true_by_id=gt_by_doi, pred_by_id=pred_by_doi, config=config)

species = report.metrics_for("species")
print(species.precision, species.recall, species.f1)

overall = micro_average(report.field_metrics.values())
print(overall.f1, macro_f1(report.field_metrics.values()))

report.metrics_to_pandas()     # one row per field
report.save("artifacts/runs/my_report.json")
```

The same strategies are saved in `configs/eval_default.json` (fuzzy species: `eval_fuzzy_species.json`; exact only: `eval_strict.json`). The field-by-field logic is explained in [`evaluation_audit_guide.md`](evaluation_audit_guide.md).

### Species to GBIF keys

```python
from llm_metadata.gbif import match_species, enrich_with_gbif

match = match_species("Rangifer tarandus")
evaluated = enrich_with_gbif(features)   # returns a DatasetFeaturesEvaluation with gbif_keys
```

### Extraction and evaluation in one call

```python
from llm_metadata.prompt_eval import run_eval
```

`run_eval` combines the two steps and writes a run artifact. See the README, under "Running evaluations".
