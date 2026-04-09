# TODO

## Prompt Engineering — Phase 3 ← **CURRENT FOCUS**

> **Plans:** [`plans/prompt-engineering-flow.md`](plans/prompt-engineering-flow.md) · [`plans/taxonomic-relevance-refactor.md`](plans/taxonomic-relevance-refactor.md)
> **Sequencing:** WU-3.2 and WU-T1 both modify `common.py` — run in the same session or sequentially.

- [x] WU-3.1 — Baseline runs (abstract / sections / pdf_native) on dev subset, 2026-03-27
- [x] WU-3.1 audit — Per-field mismatch analysis documented in run notes (2026-03-28)
- [ ] WU-3.2 — Expand VOCABULARY block: full `data_type` (13 values) + `geospatial_info_dataset` (9 values) with definitions + contrastive examples `sonnet`
- [ ] WU-T1 — Add `SPECIES_EXTRACTION` block to `common.py`: decorated strings, count signals, broad groups, focal-taxa scoping `sonnet`
- [ ] WU-T1b — Mode-specific species overrides for `section.py` + `pdf_file.py` `sonnet`
- [ ] WU-3.4 — Boolean cue expansion: `time_series` neg examples, `threatened_species` cue list, `bias_north_south` dual-trigger (geographic + bias language) `sonnet`
- [ ] WU-3.4b — Mode-specific tuning: `data_type` sections rule, `time_series` sections/PDF rules, `new_species_*` PDF cues `sonnet`

---

## Claim Grounding

> **Plan:** [`plans/claim-grounding.md`](plans/claim-grounding.md)

- [x] Phase 0: Research synthesis (`WU-E0`)
- [x] Phase 1: Notebook pilot design (`WU-E1`) — `notebooks/claim_grounding_pilot.ipynb`
- [ ] Phase 1B: Notebook LLM grounding pilot (`WU-E1B`) — `notebooks/claim_grounding_from_llm.ipynb`
- [ ] Phase 2: Grounding contracts + prompt builder (`WU-E2`)
- [ ] Phase 3: `prompt_eval` integration (`WU-E3`)
- [ ] Phase 4: Viewer integration (`WU-E4`)
- [ ] Phase 5: Lab logging + plan update (`WU-E5`)

---

## Assemble article outline materials `opus`

- [ ] Three-way comparison table: Abstract vs Full-text (PDF API) vs Section-based
- [ ] Cross-source comparison: Dryad vs Zenodo vs SS
- [ ] Feature-specific analysis + modulator performance
- [ ] Cost analysis per approach
- [ ] Lab log entry in `notebooks/README.md`
- **Tag:** `CLOUD` | **Deps:** WU-B, WU-C3, WU-C4 | **Files:** `docs/article_outline.md`


---

## Automated Relevance Classification

> **Plan:** [`plans/automated_relevance_classification.md`](plans/automated_relevance_classification.md)

- [x] WU-R1: `notebooks/relevance_mechanistic.ipynb` — rule-based scoring (Part A: GT features ceiling test; Part B: LLM features end-to-end)
- [x] WU-R2: `notebooks/relevance_llm_direct.ipynb` — direct LLM classification with extended schema
- [x] Combined comparison table + lab log entry

---

## Research Backlog

- [ ] Research: types of data from dataset
- [ ] Research: grey literature for biodiversity data
- [ ] Research: single shot vs multiple shots and LLMs (tested gpt-4o-mini vs gpt-5-mini)
- [ ] Prompt engineering for feature extraction and model refinement

---

## Feature Extraction — Advanced Schema

### Taxonomic Relevance Features Refactor — Phase 2+ (after Phase 3 prompt work stable)

> **Plan:** [`plans/taxonomic-relevance-refactor.md`](plans/taxonomic-relevance-refactor.md) · Phase 1 items (WU-T1, WU-T1b) are in Prompt Engineering Phase 3 above.

- [ ] WU-T2: `ExtractedTaxon` Pydantic model — `{name, taxon_type, count, scientific_name, common_name}` replacing flat `list[str]` `sonnet`
- [ ] WU-T3: Eval matcher refactor — eliminate 3× TP/FP/FN duplication, `ParsedTaxonComparator`, delete orphaned `EnhancedSpeciesMatchConfig` `sonnet`
- [ ] WU-T4: GBIF enrichment on clean `scientific_name` field (backlog) `sonnet`

### Backlog

- [ ] Geographic information model incl subnational admin units (MRCs, admin regions, cities), protected areas, ecosystem
  > **Plan:** [`plans/nominatim_enrichment.md`](plans/nominatim_enrichment.md) — `location_text` extraction field + `location_ids` enrichment via Nominatim (Wikidata QID primary, `osm_type:osm_id` fallback)
- [ ] Demo notebook `notebooks/eval_nominatim_location_test.ipynb` — modelled on `notebooks/species_recall_improvement.ipynb`; reuse existing extractions (no new LLM calls); compare `location_text` fuzzy string vs `location_ids` set-comparison P/R/F1
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
| main | WU-3.1 | Baseline runs (abstract/sections/pdf_native) + per-field audit | sonnet | 2026-03-28 |
| `claude/wu-a1-dlX7N` | WU-A1 | Extend schema — modulators + DataSource | opus | 2026-02-18 |
| `claude/implement-wu-a2-ePym7` | WU-A2 | Validate all-source ground truth | sonnet | 2026-02-18 |
| `claude/implement-wu-a3-Y1iX9` | WU-A3 | Enrich URL metadata (source_url, journal_url, pdf_url, is_oa) | sonnet | 2026-02-18 |
| `claude/implement-wu-b-classification-Knvz2` | WU-B | Abstract-only extraction + evaluation notebook | sonnet | 2026-02-18 |
| `claude/implement-gbif-key-enrichment-9mcv1` | GBIF WU-1,2,3 | GBIF species matching enrichment | sonnet | 2026-02-18 |
| `claude/semantic-scholar-implementation-Kjlq1` | SS-6.5, WU-C1✅, SS-3.2✅ | SS overview notebook + mark completed tasks | haiku | 2026-02-19 |
| `claude/implement-semantic-scholar-Kwa4C` | SS-4.2, SS-6.1, SS-6.2, SS-6.3 | Coverage validation, CLAUDE.md, lab logs, 39 integration tests, bugfix boolean coercion | sonnet | 2026-02-19 |
| `claude/prompt-engineering-phase-1-8IeHD` | WU-EH1,EH2,EH3,EH4 | Phase 1 eval hardening (FieldEvalStrategy, DEFAULT_FIELD_STRATEGIES, dispatch, tests, CLAUDE.md) | sonnet | 2026-02-19 |
| `claude/phase-2-prompt-engineering-0fwQc` | Phase 2 (EH1,EH2,2.1-2.7) | Prompt infra: prompts/ pkg, prompt_eval, eval configs, dev subset, visualization | sonnet | 2026-02-19 |
