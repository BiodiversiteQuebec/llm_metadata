# PDF → Section‑aware RAG Index (Local Docker + OpenAI)

## Context

This plan extends the `llm_metadata` project to support **full-text feature extraction** from scientific PDFs. The goal is a **local-first** ingestion pipeline that:

1. detects **article sections** (Intro/Methods/Results/Discussion/etc.),
2. chunks text **without crossing section boundaries**,
3. embeds chunks with **OpenAI embeddings**,
4. stores vectors + rich metadata in **Qdrant** for downstream RAG.

This enables comparing LLM feature extraction quality between abstract-only vs full-text sources (see [TODO.md](../TODO.md) "Benchmarking from papers full text" section).

### Scope (v1)

* **Tables and figures are ignored** as structured content (no table extraction, no figure OCR). Lightweight flags like `has_figure_mention` are kept.
* **Prefect orchestration is out of scope** for v1 (see Future Extensions).

### Constraints

* Integrate with existing `src/llm_metadata/` module structure
* Services run locally via **Docker + docker-compose**
* Bibliographic metadata obtained from **existing OpenAlex integration** (`openalex.py`, `OpenAlexWork` schema)
* PDFs already downloaded via existing `pdf_download.py` pipeline to `data/pdfs/`
* Follow **notebook-first experimentation** workflow per [CLAUDE.md](../CLAUDE.md)

---

## Design decisions (centralized)

### Vector DB: Qdrant (Docker)

* Goal fit: store **vectors + JSON payload** and do fast **metadata filtering** (DOI/year/section type/author ORCID).
* Local-first: simple Docker deployment; easy to persist and back up.

### PDF structuring: GROBID (Docker) + existing Python client

* Primary extractor for scholarly PDFs.
* Produces **TEI XML** with header metadata + **section hierarchy**, which is the backbone for section-aware chunking.
* Use the **existing community Python client** (`grobid-client-python`) to call the GROBID REST service (batch-friendly, less glue code to maintain).

### Token accounting: tiktoken (Python)

* Used locally to:

  * enforce **target/max/overlap** chunk sizes in *tokens* (stable across languages),
  * prevent embedding requests that exceed model limits,
  * estimate throughput/cost and keep behavior deterministic.

### Embedding model: OpenAI `text-embedding-3-large`

* Default recommendation for scientific corpora where retrieval quality matters.
* Strong multilingual performance and higher capacity than small models.
* Practical note: you can optionally reduce vector size via the embeddings API `dimensions` parameter if storage/memory becomes a concern.

Fallback option:

* Use `text-embedding-3-small` for cheap prototyping or if cost dominates quality.

### Ignored content in v1

* **No structured extraction** of tables/figures.
* References are kept only if you want traceability, but retrieval should **exclude them by default** using an `is_references` payload flag.

---

## Workspace layout

Modules are added to the existing `src/llm_metadata/` package structure:

```
llm_metadata/
├─ .devcontainer/docker-compose.devcontainer.yml  # Qdrant + GROBID + app (devcontainer)
├─ .env                        # Existing: add GROBID/Qdrant URLs
├─ pyproject.toml              # Existing: add new dependencies
├─ src/llm_metadata/
│  ├─ __init__.py
│  ├─ pdf_download.py          # EXISTING: PDF retrieval
│  ├─ openalex.py              # EXISTING: OpenAlex API client
│  ├─ pdf_parsing.py           # NEW: GROBID client + TEI parsing
│  ├─ section_normalize.py     # NEW: heading → canonical type mapping
│  ├─ chunking.py              # NEW: section-aware chunking
│  ├─ embedding.py             # NEW: OpenAI embedding wrapper
│  ├─ vector_store.py          # NEW: Qdrant client wrapper
│  └─ schemas/
│     ├─ openalex_work.py      # EXISTING: paper metadata
│     ├─ chunk_metadata.py     # NEW: section + chunk schemas
│     └─ ...
├─ data/
│  ├─ pdfs/2024/               # EXISTING: downloaded PDFs (DOI-based naming)
│  ├─ dataset_article_mapping.csv  # EXISTING: dataset→article DOI map
│  └─ registry.sqlite          # NEW: PDF processing status tracker
├─ artifacts/
│  ├─ tei/                     # NEW: GROBID TEI XML output
│  └─ chunks/                  # NEW: chunk JSON + embeddings cache
└─ notebooks/
   └─ pdf_chunking_exploration.ipynb  # NEW: prototyping notebook
```

---

## Services (docker-compose)

### `grobid`

* Expose: `8070`
* Allocate enough RAM (e.g., 4–6 GB depending on batch size)

### `qdrant`

* Expose: `6333` (+ optional `6334`)
* Persist storage in `./qdrant_storage`

Baseline compose snippet:

```yaml
services:
  grobid:
    image: lfoppiano/grobid:0.8.0
    ports: ["8070:8070"]
    environment:
      - JAVA_OPTS=-Xmx4g
    restart: unless-stopped

  qdrant:
    image: qdrant/qdrant:latest
    ports: ["6333:6333", "6334:6334"]
    volumes:
      - ./qdrant_storage:/qdrant/storage
    restart: unless-stopped
```

---

## Python dependencies

Add to `pyproject.toml` dependencies:

```toml
dependencies = [
    # ... existing deps ...
    "lxml",              # TEI XML parsing
    "qdrant-client",     # Vector DB client
    "tiktoken",          # Token counting for chunking
    "rich",              # Progress reporting (or use existing loguru)
]

[project.optional-dependencies]
dev = [
    # ... existing dev deps ...
    "grobid-client-python",  # GROBID REST client
]
```

Note: `openai` and `pydantic` are already in the project dependencies.

---

## Why tiktoken

`tiktoken` is used to **count tokens locally** to:

* enforce chunk sizes (target/max/overlap) deterministically,
* avoid “input too large” failures,
* control cost/throughput,
* keep overlaps stable in token units.

---

## Data model (payload schema)

### Integration with existing schemas

The chunk metadata schema extends the existing `OpenAlexWork` model from `schemas/openalex_work.py`. Document-level fields are propagated from `OpenAlexWork` to each chunk.

### Document-level metadata (from OpenAlexWork + extensions)

Fields from existing `OpenAlexWork`:
* `openalex_id` → used as `work_id`
* `doi`
* `title`
* `publication_year`
* `primary_location` → extract `venue`
* `authorships` → extract `authors` list
* `open_access` → `oa_status`
* `pdf_url`, `local_pdf_path`

New fields for RAG:
* `pdf_sha256` (for deduplication/cache invalidation)
* `language` (nullable, from GROBID or OpenAlex)
* `keywords` (optional, from GROBID header)
* `parser`: `{tool: "grobid", version: "0.8.0", timestamp}`

### Section-level metadata

New Pydantic model in `schemas/chunk_metadata.py`:

```python
from enum import Enum

class SectionType(str, Enum):
    ABSTRACT = "ABSTRACT"
    INTRO = "INTRO"
    METHODS = "METHODS"
    RESULTS = "RESULTS"
    DISCUSSION = "DISCUSSION"
    CONCLUSION = "CONCLUSION"
    REFERENCES = "REFERENCES"
    ACK = "ACK"
    DATA_AVAILABILITY = "DATA_AVAILABILITY"
    SUPPLEMENT = "SUPPLEMENT"
    OTHER = "OTHER"
```

Fields:
* `section_id` (stable within doc, e.g., `{work_id}_sec_{n}`)
* `section_title_raw`
* `section_type_normalized`: `SectionType` enum
* `section_path` (e.g., `Methods > Sampling > DNA extraction`)
* `section_level` (int, 1=top-level)

### Chunk-level metadata

* `chunk_id`
* `chunk_index_in_section`
* `token_count`
* `char_start`, `char_end`
* `page_start`, `page_end` (best-effort)
* flags:

  * `is_abstract`
  * `is_references`
  * `has_equation`
  * `has_table_mention`, `has_figure_mention` (best-effort)

---

## Pipeline stages

### 0) PDF discovery (leverage existing pipeline)

PDFs are already downloaded via `pdf_download.py` to `data/pdfs/{year}/`. The registry tracks processing status:

* Read existing PDFs from `data/pdfs/`
* Compute `sha256` for each
* Use `openalex_id` as `work_id` (from `dataset_article_mapping.csv` or OpenAlex lookup)
* Store in `data/registry.sqlite`

Registry tables (SQLite):

```sql
CREATE TABLE documents (
    work_id TEXT PRIMARY KEY,      -- OpenAlex ID
    pdf_sha256 TEXT UNIQUE,
    source_path TEXT,
    doi TEXT,
    status TEXT,                   -- PENDING, PARSED, CHUNKED, INDEXED, ERROR
    parser_version TEXT,
    updated_at TIMESTAMP,
    error_message TEXT
);

CREATE TABLE chunks (
    chunk_id TEXT PRIMARY KEY,
    work_id TEXT REFERENCES documents(work_id),
    section_id TEXT,
    chunk_index_in_section INTEGER,
    vector_indexed BOOLEAN DEFAULT FALSE,
    updated_at TIMESTAMP
);
```

Idempotency:
* if sha256 unchanged and status==INDEXED → skip
* if parser_version changed → re-parse from stage 1

### 1) Parse structure (GROBID)

Module: `src/llm_metadata/pdf_parsing.py`

* Use `grobid-client-python` to call local GROBID `processFulltextDocument` endpoint
* Save TEI XML: `artifacts/tei/{work_id}.tei.xml`
* Parse TEI → structured document model using `lxml`
* Save normalized JSON: `artifacts/chunks/{work_id}.doc.json`

Fallback (v1.1): if GROBID fails, use `pymupdf` with heuristic section detection.

### 2) Normalize sections

Module: `src/llm_metadata/section_normalize.py`

Deterministic rules (regex + synonyms) mapping headings → `SectionType` enum:

```python
SECTION_PATTERNS = {
    SectionType.ABSTRACT: [r"^abstract$", r"^summary$"],
    SectionType.INTRO: [r"^introduction$", r"^background$"],
    SectionType.METHODS: [r"^methods?$", r"^materials?\s*(and|&)\s*methods?$", r"^experimental"],
    SectionType.RESULTS: [r"^results?$", r"^findings$"],
    SectionType.DISCUSSION: [r"^discussion$", r"^interpretation$"],
    SectionType.CONCLUSION: [r"^conclusions?$", r"^concluding"],
    SectionType.REFERENCES: [r"^references?$", r"^bibliography$", r"^literature\s*cited$"],
    SectionType.ACK: [r"^acknowledgm?ents?$"],
    SectionType.DATA_AVAILABILITY: [r"^data\s*(availability|access)"],
    # ... etc
}
```

Store: raw heading, normalized type, hierarchical `section_path`.

### 3) Chunking (section-aware)

Module: `src/llm_metadata/chunking.py`

Default parameters (tuned for `text-embedding-3-large` 8191 token limit):

* `target_tokens=450`
* `max_tokens=650`
* `overlap_tokens=80`

Rules:
* Never cross section boundaries
* Keep Abstract as 1–2 chunks (typically fits in one)
* Mark References chunks with `is_references=True` (excluded by default in retrieval)
* Use `tiktoken` with `cl100k_base` encoding for token counting

Output: `artifacts/chunks/{work_id}.chunks.json`

### 4) Embedding (OpenAI)

Module: `src/llm_metadata/embedding.py`

* Embed each chunk text via OpenAI `text-embedding-3-large`
* Batch requests (up to 2048 tokens per batch for efficiency)
* Cache embeddings: `artifacts/chunks/{work_id}.embeddings.jsonl`
* Include model name + dimensions in cache for reproducibility

Uses existing `OPENAI_API_KEY` from `.env`.

### 5) Index into Qdrant

Module: `src/llm_metadata/vector_store.py`

Collection: `papers_chunks`

* `id = chunk_id`
* `vector = embedding` (3072 dims for `text-embedding-3-large`)
* `payload = chunk + section + document metadata`

Payload indexes for filtered retrieval:
* `doi` (keyword)
* `publication_year` (integer)
* `section_type_normalized` (keyword)
* `is_references` (bool)
* `author_orcids` (keyword array, flattened from authors)

---

## Retrieval conventions (for RAG downstream)

Default filters:

* `is_references == false` Optional user-driven filters:
* limit to `section_type_normalized in {METHODS, RESULTS}`
* filter by `doi`, `publication_year`, `venue`, `author_orcids`

Citations in answers should include:

* title + DOI
* section path
* page range (if available)

---

## Milestones

1. **Infrastructure**: Docker compose up + connectivity tests (GROBID health, Qdrant ready)
2. **Prototyping notebook**: `notebooks/pdf_chunking_exploration.ipynb` with manual GROBID + chunking tests
3. **TEI parsing**: Parse TEI → section tree extraction → JSON doc model
4. **Section normalization + chunking**: Implement with tiktoken, validate token counts
5. **Embedding + indexing**: OpenAI embedding → Qdrant upsert, verify retrieval
6. **Registry integration**: SQLite tracking, idempotent re-runs

Per [CLAUDE.md](../CLAUDE.md), document progress in `notebooks/README.md` with results and metrics.

---

## Future extensions (out of scope for v1)

* **Prefect orchestration**: Create `prefect_ingest_pipeline.py` using `ThreadPoolTaskRunner` pattern from existing `prefect_pipeline.py` for batch PDF processing
* **OCR fallback**: `ocrmypdf` → re-parse for scanned PDFs
* **Reranking**: Cross-encoder reranking for improved retrieval precision
* **Citation formatting**: Answer citation with title + DOI + section path + page range
* **Smart section classifier**: ML-based section normalization (fallback from regex)
* **Reference matching**: Citation graph extraction (separate module)
* **Evaluation integration**: Extend `groundtruth_eval.py` to measure RAG retrieval quality
