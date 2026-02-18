# TODO

## Active Claude Sessions

<!--
HOW TO USE: When a Claude session starts a task, add a row below.
When done, move the row to the "Completed Sessions" table at the bottom.
This prevents duplicate work across parallel sessions.
-->

| Branch | Task ID | Description | Model | Started |
|---|---|---|---|---|
| | | *(no active sessions)* | | |

---

## Presentation Deliverables (Thursday 2026-02-19)

> **Plan:** [`plans/presentation_20260219_work_plan.md`](plans/presentation_20260219_work_plan.md)
>
> 5 deliverables: (1) SS data in pipeline, (2) modulator features, (3) abstract-only eval, (4) OA full-text eval, (5) section-based eval

### WU-A1: Extend schema — modulators + DataSource `opus` ✅

- [x] Add 6 `Optional[bool]` modulator fields to `DatasetFeatures`: `time_series`, `multispecies`, `threatened_species`, `new_species_science`, `new_species_region`, `bias_north_south`
- [x] Add `DataSource(str, Enum)` with `dryad`, `zenodo`, `semantic_scholar`, `referenced`
- [x] Add `source: Optional[DataSource]` field
- [x] Add boolean coercion validator in `DatasetFeaturesNormalized`
- [x] Update system prompts in `gpt_classify.py` for modulator extraction (all 3: SYSTEM_MESSAGE, SECTION_SYSTEM_MESSAGE, PDF_SYSTEM_MESSAGE)
- [x] Update `schemas/__init__.py` exports (`DatasetFeaturesNormalized`, `DataSource`)
- [x] Update tests for new fields + boolean coercion edge cases (`tests/test_schema_modulators.py`, 27 new tests)
- **Tag:** `CLOUD` | **Deps:** none | **Files:** `schemas/fuster_features.py`, `schemas/__init__.py`, `gpt_classify.py`, `tests/test_schema_modulators.py`

### WU-A2: Validate all-source ground truth `sonnet`

- [ ] Load `data/dataset_092624.xlsx`, validate all 418 records through updated schema
- [ ] Filter to valid records (~491 across Dryad+Zenodo+SS)
- [ ] Compute coverage stats by source (records, abstracts, DOIs, cited_articles)
- [ ] Export `data/dataset_092624_all_sources_validated.xlsx`
- **Tag:** `CLOUD` | **Deps:** WU-A1 | **Files:** `data/dataset_092624.xlsx`, notebook

### WU-B: Abstract-only extraction + evaluation `sonnet`

- [ ] Notebook: `notebooks/batch_abstract_evaluation.ipynb` (mirrors `batch_fulltext_evaluation.ipynb` / `batch_pdf_file_evaluation.ipynb`)
- [ ] Steps 1–8: load → configure → extract → prep → evaluate → analysis → cost → export
- [ ] Per-field P/R/F1 for all 16 fields (10 original + 6 modulators)
- [ ] Segment by source (Dryad vs Zenodo vs SS), feature discussion, side-by-side examples
- [ ] HTML report in `notebooks/results/`, extraction CSV for WU-D1
- **Tag:** `CLOUD` | **Deps:** WU-A2 | **Files:** `text_pipeline.py`, `gpt_classify.py`, `groundtruth_eval.py`, notebook

### WU-C1: Download OA PDFs for SS records `sonnet`

- [ ] Refactor `notebooks/download_all_fuster_pdfs.ipynb` — add SS section
- [ ] Extract article DOIs from xlsx `cited_articles` column for SS records
- [ ] Use existing fallback chain (OpenAlex → Unpaywall → EZproxy → Sci-Hub)
- [ ] Store in `data/pdfs/semantic_scholar/`, build manifest CSV
- **Tag:** `LOCAL` | **Deps:** WU-A2 | **Files:** `pdf_download.py`, `openalex.py`

### WU-C2: GROBID-parse new PDFs `haiku`

- [ ] Extend GROBID parsing cells in `notebooks/download_all_fuster_pdfs.ipynb` (or add new cells there)
- [ ] Parse SS PDFs through GROBID via `pdf_parsing.py`
- [ ] Confirm existing Dryad+Zenodo PDFs (~45) already parsed
- **Tag:** `LOCAL` | **Deps:** WU-C1 | **Files:** `pdf_parsing.py`, `artifacts/tei/`

### WU-C3: Full-text extraction (PDF File API) + eval `sonnet`

- [ ] Refactor `notebooks/batch_pdf_file_evaluation.ipynb` — extend to SS OA PDFs + updated schema
- [ ] Run PDF File API extraction via `pdf_pipeline.py` on all OA PDFs (Dryad+Zenodo + SS)
- [ ] Evaluate against ground truth, segment by source, compare vs abstract-only (WU-B2)
- [ ] HTML report
- **Tag:** `LOCAL+CLOUD` | **Deps:** WU-C1, WU-A2 | **Files:** `pdf_pipeline.py`, notebook

### WU-C4: Section-based extraction + eval `sonnet`

- [ ] Refactor `notebooks/batch_fulltext_evaluation.ipynb` — extend to SS PDFs + updated schema
- [ ] Run section extraction via `section_pipeline.py` on all GROBID-parsed PDFs
- [ ] Evaluate, compare vs abstract-only (WU-B2) and full-text (WU-C3)
- [ ] HTML report
- **Tag:** `LOCAL` | **Deps:** WU-C2, WU-A2 | **Files:** `section_pipeline.py`, notebook

### WU-D1: Assemble presentation materials `opus`

- [ ] Three-way comparison table: Abstract vs Full-text (PDF API) vs Section-based
- [ ] Cross-source comparison: Dryad vs Zenodo vs SS
- [ ] Feature-specific analysis + modulator performance
- [ ] Cost analysis per approach
- [ ] Lab log entry in `notebooks/README.md`
- **Tag:** `CLOUD` | **Deps:** WU-B, WU-C3, WU-C4 | **Files:** `docs/results_presentation_20260219/work_plan.md`

---

## Semantic Scholar Integration

> **Plan:** [`plans/integrate_semantic_scholar/semantic_scholar_implementation_guide.md`](plans/integrate_semantic_scholar/semantic_scholar_implementation_guide.md)
> **Overview:** [`plans/integrate_semantic_scholar/README.md`](plans/integrate_semantic_scholar/README.md)
>
> Phase 1 (audit) is COMPLETE. Presentation WU-* covers tasks 2.1 (partial), 3.1, 4.1, 5.1–5.3.
> Remaining tasks below are deferred until after the presentation.

### SS-2.1b: URL field extensions `sonnet`

- [x] Add `source_url`, `journal_url`, `pdf_url` (HttpUrl), `is_oa` (bool), `cited_article_doi` (str) to schema
- [x] Validators for URL/empty handling
- **Deps:** WU-A1 (DataSource enum done there) | **Ref:** Task 2.1

### SS-2.2: Semantic Scholar API client `sonnet`

- [x] Create `src/llm_metadata/semantic_scholar.py` following `openalex.py` pattern
- [x] Functions: `get_paper_by_doi`, `get_paper_by_title`, `get_paper_citations`, `get_paper_references`
- [x] Joblib caching, 1 req/sec rate limit, API key from env
- [x] Tests with mocked responses (≥80% coverage)
- **Deps:** Phase 1 audit (done) | **Ref:** Task 2.2

### SS-2.3: Update dryad/zenodo modules for source tracking `sonnet`

- [x] Add `source=DataSource.DRYAD/ZENODO` to returned data
- [x] Update `article_retrieval.py` for SS support
- **Deps:** WU-A1 | **Ref:** Task 2.3

### SS-3.2: Cited article retrieval workflow `sonnet`

- [ ] Use SS API to retrieve citing papers for datasets
- [ ] Generate mapping CSV (`data/semantic_scholar_cited_articles.csv`)
- **Deps:** SS-2.2, WU-A2 | **Ref:** Task 3.2

### SS-4.2: Validate coverage goals `haiku`

- [ ] Check ≥80% abstract coverage, ≥80% OA PDF proportion
- [ ] Gap analysis and recommendations
- **Deps:** WU-A2 | **Ref:** Task 4.2

### SS-6.1: Update CLAUDE.md `haiku`

- [ ] Add SS module to Stage 1, multi-source architecture, troubleshooting
- **Deps:** SS-2.2 | **Ref:** Task 6.1

### SS-6.2: Lab log entries in notebooks/README.md `haiku`

- [ ] Date-headed entries for all integration work
- **Deps:** all eval tasks | **Ref:** Task 6.2

### SS-6.3: Tests for new functionality `sonnet`

- [ ] Unit tests for `semantic_scholar.py`, integration tests for multi-source validation
- [ ] Full suite passes, ≥80% coverage on new code
- **Deps:** SS-2.2, SS-2.3 | **Ref:** Task 6.3

---

## Research Backlog

- [ ] Research: types of data from dataset
- [ ] Research: grey literature for biodiversity data
- [ ] Research: single shot vs multiple shots and LLMs (tested gpt-4o-mini vs gpt-5-mini)
- [ ] Prompt engineering for feature extraction and model refinement

---

## Feature Extraction — Advanced Schema

### GBIF Species Matching

> **Plan:** [`plans/gbif_species_matching.md`](plans/gbif_species_matching.md)

- [ ] WU-1: `species_parsing.py` — ParsedTaxon model + shared preprocessing
- [ ] WU-2: Refactor evaluation matchers to strategy pattern
- [ ] WU-3: `gbif.py` — GBIF Species Match API wrapper
- [ ] WU-4: `gbif_matcher()` — evaluation strategy integration

### Backlog

- [ ] Geographic information model incl GADM level, protected areas, ecosystem
- [ ] Taxonomic information model incl species, paraphyletic groups
- [ ] Taxonomic & geographic referencing pipeline

---

## Production Readiness

- [ ] Streamline artifacts, manifests, data storage
- [ ] Workflow orchestration with Prefect
- [ ] Full DB model (articles, datasets, features, runs, evaluations) + Postgres
- [ ] Refactor tests to reflect pipeline structure
- [ ] Refactor classification modules to reflect pipeline structure
- [ ] Web app dashboard

---

## Completed

<details>
<summary>Benchmarking from abstracts</summary>

- [x] Pydantic model for benchmark dataset + normalization
- [x] Species field refinement (covers annotated data values)
- [x] valid_yn and reason_not_valid as enum
- [x] Test run on sample annotated abstracts
- [x] GPT wrapper and model update
- [x] Metrics definition & utils (evaluation.py with P/R/F1)
- [x] Benchmark report generation
</details>

<details>
<summary>Full-text infrastructure</summary>

- [x] Article DOI retrieval from Excel cited_articles (24.4% coverage)
- [x] Article DOI retrieval from Dryad/Zenodo APIs (fallback)
- [x] Dataset-to-article mapping CSV (75 article DOIs from 299 valid)
- [x] Coverage: Dryad 100%, Zenodo 56.7%
- [x] PDF download via OpenAlex + Unpaywall + Sci-Hub
- [x] Docker: GROBID + Qdrant compose
- [x] TEI parsing, section normalization, chunking, embeddings, vector store
- [x] Chunk metadata schema, Registry SQLite
- [x] Section-specific extraction (methods) — great results on 1 article
</details>

<details>
<summary>Semantic Scholar audit (Phase 1)</summary>

- [x] Task 1.1: Audit API client modules (dryad, zenodo, openalex, unpaywall)
- [x] Task 1.2: Audit validation and schema modules
- [x] Task 1.3: Audit PDF download pipeline
</details>

---

## Completed Sessions

| Branch | Task ID | Description | Model | Finished |
|---|---|---|---|---|
| `claude/wu-a1-dlX7N` | WU-A1 | Extend schema — modulators + DataSource | opus | 2026-02-18 |
