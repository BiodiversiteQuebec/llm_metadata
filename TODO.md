# TODO

## Data-Paper Manifest Refactor ✅

> **Plan:** [`plans/archive/data-papers-manifest-refactor.md`](plans/archive/data-papers-manifest-refactor.md)
>
> All 8 work units complete. Acceptance criteria met.

- [x] WU-SR1: `src/llm_metadata/doi_utils.py` + `schemas/data_paper.py` (`DataPaperRecord`, `DataPaperManifest`) + tests
- [x] WU-SR2: `src/llm_metadata/schemas/data_paper.py` — builder joining GT XLSX + PDF manifest, save/load CSV, CLI entrypoint + tests
- [x] WU-SR3: `prompt_eval.py` — `--manifest` / `manifest_path` arg; PDF mode uses `pdf_local_path` directly; backward compat preserved + tests
- [x] WU-SR4: DOI normalization centralized via `doi_utils` in `article_retrieval.py` and `pdf_download.py`; `update_record_pdf_path()` helper in manifest module
- [x] WU-SR5: merged into `src/llm_metadata/extraction.py` / `src/llm_metadata/schemas/data_paper.py` during explicit-mode refactor
- [x] WU-SR6: `data/manifests/dev_subset_data_paper.csv` generated — 30/30 records with `pdf_local_path` on disk
- [x] WU-SR7: Integration tests in `tests/test_manifest_integration.py` — preflight passes (30/30 PDF coverage), duplicate ID rejection, backward compat
- [x] WU-SR8: TODO.md + notebooks/README.md updated

**Acceptance criteria:**
- PDF eval mode uses manifest `pdf_local_path` (no DOI name inference required) ✅
- DOI normalization centralized in `doi_utils.py` ✅
- dev_subset manifest at `data/manifests/dev_subset_data_paper.csv` with 30/30 PDFs on disk ✅
- Provider provenance fields available in `DataPaperRecord` without raw API blobs ✅
- Existing extraction modes now run through the unified explicit-mode engine ✅

---

## Prompt Engineering — Phase 2 ✅

> **Plan:** [`plans/prompt-engineering-flow.md`](plans/prompt-engineering-flow.md)
>
> Phase 1 eval hardening (WU-EH1, WU-EH2) and Phase 2 prompt infrastructure complete.

- [x] WU-EH1: `FieldEvalStrategy` + `field_strategies` + `DEFAULT_FIELD_STRATEGIES` added to `groundtruth_eval.py`
- [x] WU-EH2: `compare_models` dispatches by `field_strategies` when populated; backward compat preserved
- [x] WU-2.1: `src/llm_metadata/prompts/` package — `common.py`, `abstract.py`, `section.py`, `pdf_file.py`; `gpt_extract.py` now imports from prompts
- [x] WU-2.2: `EvaluationConfig.to_dict/from_dict/to_json/from_json` + `EvaluationReport.save/load` methods
- [x] WU-2.3: `src/llm_metadata/prompt_eval.py` — `run_eval()` Python API + CLI (`python -m llm_metadata.prompt_eval --help`)
- [x] WU-2.4: `configs/eval_default.json`, `configs/eval_fuzzy_species.json`, `configs/eval_strict.json`
- [x] WU-2.5: `data/dev_subset.csv` — 30 curated records (10/source: Dryad/Zenodo/SS); covers time_series, threatened_species, bias_north_south positives
- [x] WU-2.6: `notebooks/prompt_eval_results.ipynb` viewer + `app/app_eval_viewer.py` Streamlit app
- [x] WU-2.7: "Prompt Engineering Workflow" section added to `CLAUDE.md`

**Next:** Phase 3 — Per-Field Prompt Iteration (WU-3.1 baseline run requires API key)

---

## Prompt-Eval & Viewer Improvements

> **Plan:** [`plans/prompt-eval-viewer-improvements.md`](plans/prompt-eval-viewer-improvements.md)

- [x] Phase 1: `EvaluationReport.abstracts` field; `run_id` in `run_eval()` + CLI; abstracts persisted in JSON
- [x] Phase 2: `app_eval_viewer.py` bug fixes — `0.0→N/A` display; abstract text in mismatch expanders
- [x] Phase 3: F1 bar chart; Run B mismatch explorer; Run B metadata sidebar
- [x] Phase 4: Record Explorer — all field results for a selected record
- [ ] Phase 5: Re-evaluate from saved predictions (`--pred-from`) — WU-5.1, 5.2, 5.3
- [ ] Phase 6: Multi-run comparison (`compare` CLI subcommand) — WU-6.1, 6.2

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
- [x] Update system prompts in `gpt_extract.py` for modulator extraction (all 3: SYSTEM_MESSAGE, SECTION_SYSTEM_MESSAGE, PDF_SYSTEM_MESSAGE)
- [x] Update `schemas/__init__.py` exports (`DatasetFeaturesNormalized`, `DataSource`)
- [x] Update tests for new fields + boolean coercion edge cases (`tests/test_schema_modulators.py`, 27 new tests)
- **Tag:** `CLOUD` | **Deps:** none | **Files:** `schemas/fuster_features.py`, `schemas/__init__.py`, `gpt_extract.py`, `tests/test_schema_modulators.py`

### WU-A2: Validate all-source ground truth (includes SS Task 3.1) `sonnet` ✅

- [x] Edit `notebooks/fuster_annotations_validation.ipynb` (do NOT create a new notebook)
- [x] Load `data/dataset_092624.xlsx`, validate all records (Dryad+Zenodo+SS) through updated schema
- [x] Parse URL fields for SS records (journal URLs vs search URLs)
- [x] Filter to valid records (299 across Dryad+Zenodo+SS)
- [x] Compute coverage stats by source (records, abstracts, DOIs, cited_articles)
- [x] Overwrite `data/dataset_092624_validated.xlsx` with all-source validated output
- **Tag:** `CLOUD` | **Deps:** WU-A1 | **Files:** `data/dataset_092624.xlsx`, `notebooks/fuster_annotations_validation.ipynb`

### WU-A3: Enrich URL metadata (source_url, journal_url, pdf_url, is_oa) `sonnet` ✅

> **Plan:** [`plans/archive/enrich_url_metadata.md`](plans/archive/enrich_url_metadata.md)

- [x] Add `enrich_article_metadata()` to `article_retrieval.py` (OpenAlex + SS fallback)
- [x] Column rename in validation notebook (`url` → `source_url`, `cited_articles` → `cited_article_doi`)
- [x] Fill `cited_article_doi` for SS records (extract DOI from `source_url`)
- [x] Enrich `journal_url`, `pdf_url`, `is_oa` via OpenAlex for all records with article DOI
- [x] Update `dataset_article_mapping.csv` with new columns
- [x] Re-export `dataset_092624_validated.xlsx` with all fields populated
- **Tag:** `CLOUD` | **Deps:** WU-A2 | **Files:** `article_retrieval.py`, `fuster_annotations_validation.ipynb`

### WU-B: Abstract-only extraction + evaluation `sonnet` ✅

- [x] Notebook: `notebooks/batch_abstract_evaluation.ipynb` (mirrors `batch_fulltext_evaluation.ipynb` / `batch_pdf_file_evaluation.ipynb`)
- [x] Steps 1–8: load → configure → extract → prep → evaluate → analysis → cost → export
- [x] Per-field P/R/F1 for all 14 evaluatable fields (8 core + 6 modulators)
- [x] Segment by source (Dryad vs Zenodo vs SS), cross-source summary table, mismatch examples
- [x] HTML report in `notebooks/results/`, extraction CSV for WU-D1
- [x] Abstract extraction now runs through the unified explicit-mode engine
- **Tag:** `CLOUD` | **Deps:** WU-A2 | **Files:** `extraction.py`, `gpt_extract.py`, `groundtruth_eval.py`, notebook
- **Note:** Notebook created; needs execution (OpenAI API key required). Cache lands at `{PROJECT_ROOT}/cache/` (not gitignored — committable and syncable).

### WU-C1: Download all PDFs (Dryad + Zenodo + SS) `sonnet` ✅

- [x] Refactor `notebooks/download_all_fuster_pdfs.ipynb` — load from `dataset_092624_validated.xlsx` (all sources, already enriched with `pdf_url`/`is_oa` by WU-A3), not `dataset_article_mapping.csv`
- [x] Download **all** records with `cited_article_doi`, regardless of OA status, using existing fallback chain (OpenAlex URL → Unpaywall → EZproxy → Sci-Hub)
- [x] Store all PDFs in `data/pdfs/fuster/` (no separate SS folder)
- [x] Save manifest CSV; end with synthesis cell segmented by source (Dryad / Zenodo / SS)
- **Tag:** `LOCAL` | **Deps:** WU-A3 | **Files:** `pdf_download.py`, `openalex.py`, notebook
- **Result:** 182/250 PDFs downloaded (72.8% success rate)

### WU-C2: GROBID-parse new PDFs `haiku` ✅

- [x] Extend GROBID parsing cells in `notebooks/download_all_fuster_pdfs.ipynb` (Section 5 added)
- [x] Parse all downloaded PDFs through GROBID via `pdf_parsing.py` (idempotent; restarted GROBID once)
- [x] Confirmed existing Dryad+Zenodo TEIs (45 pre-existing); total now 179 TEI files
- **Tag:** `LOCAL` | **Deps:** WU-C1 | **Files:** `pdf_parsing.py`, `artifacts/tei/`
- **Result:** 179/182 downloaded PDFs parsed (98.9%); 1 skipped (MAX_PATH), 2 GROBID errors on SS PDFs

### WU-C3: Full-text extraction (PDF File API) + eval `sonnet`

- [ ] Refactor `notebooks/batch_pdf_file_evaluation.ipynb` — extend to SS OA PDFs + updated schema
- [ ] Run `pdf_native` extraction mode via `extraction.py` / `prompt_eval.py` on all OA PDFs (Dryad+Zenodo + SS)
- [ ] Evaluate against ground truth, segment by source, compare vs abstract-only (WU-B2)
- [ ] HTML report
- **Tag:** `LOCAL+CLOUD` | **Deps:** WU-C1, WU-A2 | **Files:** `extraction.py`, notebook

### WU-C4: Section-based extraction + eval `sonnet`

- [ ] Refactor `notebooks/batch_fulltext_evaluation.ipynb` — extend to SS PDFs + updated schema
- [ ] Run `sections` extraction mode via `extraction.py` / `prompt_eval.py` on all GROBID-parsed PDFs
- [ ] Evaluate, compare vs abstract-only (WU-B2) and full-text (WU-C3)
- [ ] HTML report
- **Tag:** `LOCAL` | **Deps:** WU-C2, WU-A2 | **Files:** `extraction.py`, notebook

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
> Phase 1 (audit) is COMPLETE. Presentation WU-* covers tasks 2.1 (partial), 4.1, 5.1–5.3.
> **Task 3.1 merged into WU-A2** (validate all-source ground truth in `fuster_annotations_validation.ipynb`).
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

### SS-3.2: Cited article retrieval workflow `sonnet` ✅

- [x] Use SS API to retrieve citing papers for datasets
- [x] Generate mapping CSV (`data/semantic_scholar_cited_articles.csv`)
- **Deps:** SS-2.2, WU-A2 | **Ref:** Task 3.2

### SS-4.2: Validate coverage goals `haiku` ✅

- [x] Check ≥80% abstract coverage, ≥80% OA PDF proportion
- [x] Gap analysis and recommendations
- **Deps:** WU-A2 | **Ref:** Task 4.2
- **Result:** SS abstract 96.9% ✅, OA proportion 82.4% (among records with PDF URL) ✅. Gap: only 26.6% of SS records have a PDF URL (91.1% have article DOI but many not OA).

### SS-6.1: Update CLAUDE.md `haiku` ✅

- [x] Add SS module to Stage 1, multi-source architecture, troubleshooting
- **Deps:** SS-2.2 | **Ref:** Task 6.1

### SS-6.2: Lab log entries in notebooks/README.md `haiku` ✅

- [x] Date-headed entries for all integration work (2026-02-18 schema/API, 2026-02-19 coverage/tests)
- **Deps:** all eval tasks | **Ref:** Task 6.2

### SS-6.3: Tests for new functionality `sonnet` ✅

- [x] Unit tests for `semantic_scholar.py` (22 tests in `test_semantic_scholar.py`)
- [x] Integration tests for multi-source validation (39 tests in `test_multisource_integration.py`)
- [x] Full suite passes (202 passed, 0 failed)
- [x] Fixed boolean coercion bug: removed `"no"` from null_placeholders so "no" → False (not None) for modulator fields
- **Deps:** SS-2.2, SS-2.3 | **Ref:** Task 6.3

### SS-6.5: Semantic Scholar overview notebook `sonnet` ✅

- [x] Create `notebooks/data_semantic_scholar.ipynb` demonstrating semantic_scholar.py with real Fuster records
- [x] Show `get_paper_by_doi`, `get_paper_by_title`, `get_paper_citations`, `get_paper_references` in action
- [x] Summary table: per Fuster record — paper found, citation count, reference count, OA PDF URL
- [x] Highlight rate limiting, caching, env-driven base URL features
- **Deps:** SS-2.2 | **Ref:** Task 6.5
- **Result:** 5/5 papers found (100%), 4/5 with OA PDF, avg 11.6 citations, avg 45.6 references

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

- [x] WU-1: `species_parsing.py` — ParsedTaxon model + shared preprocessing
- [x] WU-2: `gbif.py` — GBIF Species Match API wrapper
- [x] WU-3: Schema `gbif_keys` field + enrichment function
- [ ] WU-4: Demo notebook — GBIF vs enhanced_species evaluation comparison `sonnet`
  - Template: `notebooks/species_recall_improvement.ipynb` (same 10 OA PDF extractions)
  - Reuse existing extracted predictions (load from artifacts, no re-extraction)
  - Enrich both ground truth and predictions with `enrich_with_gbif()`
  - Run `evaluate_indexed()` with `fields=["species", "gbif_keys"]`
  - Side-by-side P/R/F1 table: enhanced_species matching vs GBIF key set comparison
  - Qualitative analysis: which species strings GBIF resolves vs fails (vernacular, groups, count+name)
  - Save notebook as `notebooks/eval_gbif_vs_enhanced_species_test.ipynb`

### Backlog

- [ ] Geographic information model incl subnational admin units (MRCs, admin regions, cities), protected areas, ecosystem
  > **Plan:** [`plans/nominatim_enrichment.md`](plans/nominatim_enrichment.md) — `location_text` extraction field + `location_ids` enrichment via Nominatim (Wikidata QID primary, `osm_type:osm_id` fallback)
- [ ] Demo notebook `notebooks/eval_nominatim_location_test.ipynb` — modelled on `notebooks/species_recall_improvement.ipynb`; reuse existing extractions (no new LLM calls); compare `location_text` fuzzy string vs `location_ids` set-comparison P/R/F1
- [ ] Taxonomic information model incl species, paraphyletic groups
- [ ] Taxonomic & geographic referencing pipeline
- [ ] `ExtractedTaxon` structured schema — LLM extracts `{name, type, count}` instead of flat `list[str]` (improves GBIF preprocessing, requires prompt + ground truth changes)
- [ ] Evaluation matcher refactor — strategy pattern to eliminate 3x duplicated TP/FP/FN logic in `compare_models()` + delete orphaned `EnhancedSpeciesMatchConfig`
- [ ] *(ready, out of scope)* Species eval via `ParsedTaxon` — replace fuzzy enhanced_species matching with structured comparator in `evaluate_indexed()`: parse both GT and predictions through `ParsedTaxon`, match on normalized `scientific_name`/`common_name` fields; more principled than heuristic fuzzy, improves precision; requires custom comparator hook in `EvaluationConfig` `sonnet`
- [ ] Pipeline enrichment — use `gbif_keys` beyond evaluation for data gap analysis with real taxon IDs

### Model Hierarchy & Enrichment Pattern

> **Plan:** [`plans/model_hierarchy_enrichment.md`](plans/model_hierarchy_enrichment.md)

- [ ] Split `DatasetFeatures` into role-specific models: `CoreFeatureModel` → `DatasetFeaturesExtraction` / `DatasetFeaturesNormalized` / `DatasetFeaturesEvaluation`
- [ ] Keep source/provenance metadata (`is_oa`, `source_url`, etc.) on `DataPaperRecord`, not a feature subclass
- [ ] Move derived evaluation fields (`gbif_keys`, future `gadm_codes`, `location_ids`) to `DatasetFeaturesEvaluation`
- [ ] Standardize enrichment flow: external lookup in service modules, pure assembly via evaluation-model constructors/copy helpers
- [ ] Update notebooks, extraction, and tests to use correct subclass

---

## Production Readiness

- [ ] Streamline artifacts, manifests, data storage
- [ ] Standardize logging, error handling across modules
- [ ] Harden extraction io using manifest with BaseModel and classes serialization
- [ ] Decide whether workflow orchestration is still needed after the explicit-mode simplification
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
| `claude/implement-wu-a2-ePym7` | WU-A2 | Validate all-source ground truth | sonnet | 2026-02-18 |
| `claude/implement-wu-a3-Y1iX9` | WU-A3 | Enrich URL metadata (source_url, journal_url, pdf_url, is_oa) | sonnet | 2026-02-18 |
| `claude/implement-wu-b-classification-Knvz2` | WU-B | Abstract-only extraction + evaluation notebook | sonnet | 2026-02-18 |
| `claude/implement-gbif-key-enrichment-9mcv1` | GBIF WU-1,2,3 | GBIF species matching enrichment | sonnet | 2026-02-18 |
| `claude/semantic-scholar-implementation-Kjlq1` | SS-6.5, WU-C1✅, SS-3.2✅ | SS overview notebook + mark completed tasks | haiku | 2026-02-19 |
| `claude/implement-semantic-scholar-Kwa4C` | SS-4.2, SS-6.1, SS-6.2, SS-6.3 | Coverage validation, CLAUDE.md, lab logs, 39 integration tests, bugfix boolean coercion | sonnet | 2026-02-19 |
| `claude/prompt-engineering-phase-1-8IeHD` | WU-EH1,EH2,EH3,EH4 | Phase 1 eval hardening (FieldEvalStrategy, DEFAULT_FIELD_STRATEGIES, dispatch, tests, CLAUDE.md) | sonnet | 2026-02-19 |
| `claude/phase-2-prompt-engineering-0fwQc` | Phase 2 (EH1,EH2,2.1-2.7) | Prompt infra: prompts/ pkg, prompt_eval, eval configs, dev subset, visualization | sonnet | 2026-02-19 |
