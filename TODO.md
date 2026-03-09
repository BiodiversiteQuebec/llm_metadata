# TODO

## Prompt Engineering — Phase 3

- [ ] Phase 3 — Per-Field Prompt Iteration (WU-3.1 baseline run requires API key)

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

## Assemble article outline materials `opus`

- [ ] Three-way comparison table: Abstract vs Full-text (PDF API) vs Section-based
- [ ] Cross-source comparison: Dryad vs Zenodo vs SS
- [ ] Feature-specific analysis + modulator performance
- [ ] Cost analysis per approach
- [ ] Lab log entry in `notebooks/README.md`
- **Tag:** `CLOUD` | **Deps:** WU-B, WU-C3, WU-C4 | **Files:** `docs/article_outline.md`


---

## Research Backlog

- [ ] Research: types of data from dataset
- [ ] Research: grey literature for biodiversity data
- [ ] Research: single shot vs multiple shots and LLMs (tested gpt-4o-mini vs gpt-5-mini)
- [ ] Prompt engineering for feature extraction and model refinement

---

## Feature Extraction — Advanced Schema

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

- [x] Split `DatasetFeatures` into role-specific models: `CoreFeatureModel` → `DatasetFeaturesExtraction` / `DatasetFeaturesNormalized` / `DatasetFeaturesEvaluation`
- [x] Keep source/provenance metadata (`is_oa`, `source_url`, etc.) on `DataPaperRecord`, not a feature subclass
- [x] Move derived evaluation fields (`gbif_keys`, future `gadm_codes`, `location_ids`) to `DatasetFeaturesEvaluation`
- [x] Standardize enrichment flow: external lookup in service modules, pure assembly via evaluation-model constructors/copy helpers
- [x] Update notebooks, extraction, and tests to use correct subclass

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
