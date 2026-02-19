# Work Plan: Presentation Preparation (Thursday 2026-02-19)

## Context

The Thursday presentation requires 5 deliverables from `docs/results_presentation_20260219/work_plan.md` (minimal list only):

1. **Include Semantic Scholar data** — 254 SS records (192 valid) already exist in the xlsx but are not yet in the pipeline
2. **Add modulator features to extraction schema** — 6 boolean fields missing from `DatasetFeatures`
3. **Run all abstract-only** with feature-based performance discussion
4. **Run all OA full-text** with feature-based performance discussion
5. **Run all OA full-text with section-based approach** with feature-based performance discussion

**Key insight:** The 254 SS records are already in `data/dataset_092624.xlsx` with abstracts and ground truth. We do NOT need the full SS API client to evaluate them — we just need to load them through the updated schema. The SS API client (plans/integrate_semantic_scholar Task 2.2) can be built after the presentation.

---

## Work Units and Parallel Flow

```
WU-A1 [CLOUD] Schema: add 6 modulator booleans + DataSource enum
    |
    v
WU-A2 [CLOUD] Validate all 491 records from xlsx (Dryad+Zenodo+SS)
    |
    +---------------------------+
    |                           |
    v                           v
WU-B [CLOUD]                 WU-C1 [LOCAL]
Abstract extraction            Download SS OA PDFs
+ evaluation notebook          (via existing fallback chain)
(batch_abstract_evaluation)    |
    |                           v
    |                        WU-C2 [LOCAL]
    |                        GROBID-parse new PDFs
    |                           |
    |                     +----+----+
    |                     |         |
    |                     v         v
    |                  WU-C3      WU-C4
    |                  [LOCAL]    [LOCAL]
    |                  Full-text  Section-based
    |                  eval       eval
    |                     |         |
    v                     v         v
WU-D1 [CLOUD] Assemble presentation materials
```

**Streams B and C run in parallel after WU-A2.**

### Model Assignment Summary

| Work Unit | Tag | Claude Model | Rationale |
|---|---|---|---|
| WU-A1 Schema extension | CLOUD | **opus** | Multi-file architectural change (schema + prompts + tests) |
| WU-A2 Data validation | CLOUD | **sonnet** | Structured pandas/Pydantic following existing patterns |
| WU-B Abstract eval notebook | CLOUD | **sonnet** | Extraction + evaluation in one notebook (mirrors batch_* pattern) |
| WU-C1 PDF download | LOCAL | **sonnet** | Scripting with existing fallback chain |
| WU-C2 GROBID parsing | LOCAL | **haiku** | Running existing code on new files |
| WU-C3 Full-text eval | LOCAL+CLOUD | **sonnet** | Structured notebook following WU-B pattern |
| WU-C4 Section-based eval | LOCAL | **sonnet** | Parallel to WU-C3, same pattern |
| WU-D1 Presentation assembly | CLOUD | **opus** | Synthesis across all streams, narrative framing |

---

## Work Unit Details

### WU-A1: Extend Schema (modulators + DataSource)
**Tag:** `CLOUD`
**Claude model:** `opus` — foundational multi-file change (schema, prompts, tests) that everything depends on; needs architectural understanding of Pydantic validators and prompt engineering
**Dependencies:** None — start immediately

**Changes to `src/llm_metadata/schemas/fuster_features.py`:**
- Add 6 `Optional[bool]` fields to `DatasetFeatures`: `time_series`, `multispecies`, `threatened_species`, `new_species_science`, `new_species_region`, `bias_north_south`
- Add `source: Optional[DataSource]` field (for ground truth tracking, not LLM extraction)
- Add boolean coercion validator in `DatasetFeaturesNormalized` (yes/no/1/0/NaN → `Optional[bool]`)

**Changes to `src/llm_metadata/gpt_classify.py`:**
- Update system prompts (`SYSTEM_MESSAGE`, `SECTION_SYSTEM_MESSAGE`, `PDF_SYSTEM_MESSAGE`) with extraction guidance for the 6 modulator boolean fields

**Changes to `tests/`:**
- Update existing schema tests to cover new fields
- Test boolean coercion edge cases

---

### WU-A2: Validate All-Source Ground Truth Data (includes SS Phase 3 Task 3.1)
**Tag:** `CLOUD`
**Claude model:** `sonnet` — structured pandas + Pydantic validation following existing notebook patterns; no novel architecture
**Dependencies:** WU-A1
**Also covers:** Semantic Scholar implementation guide Task 3.1 (Parse and Validate SS Records from xlsx)

Edit existing notebook `notebooks/fuster_annotations_validation.ipynb`:
- Load `data/dataset_092624.xlsx`, validate ALL records (Dryad+Zenodo+SS) through updated `DatasetFeaturesNormalized`
- Filter to valid records (~491 across all sources)
- Parse URL fields for SS records (journal URLs vs search URLs, map to schema fields, handle empty/malformed)
- Compute coverage stats: records by source, with abstracts, with DOIs, with `cited_articles`
- Validation error breakdown by source
- Export: `data/dataset_092624_validated.xlsx`
- Stats table for presentation Methods section (source breakdown, OA proportions)

---

### WU-B: Abstract-Only Extraction + Evaluation
**Tag:** `CLOUD`
**Claude model:** `sonnet` — mirrors the structure of `batch_fulltext_evaluation.ipynb` and `batch_pdf_file_evaluation.ipynb`; extraction and evaluation in a single notebook
**Dependencies:** WU-A2

Notebook: `notebooks/batch_abstract_evaluation.ipynb`

**Step 1 – Load data**
- Read `data/dataset_092624_validated.xlsx` (output of WU-A2)
- Filter to records with non-null abstracts
- Validate ground truth through `DatasetFeaturesNormalized`
- Coverage table: record count by source

**Step 2 – Configure**
- `TextClassificationConfig`: `model="gpt-5-mini"`, `reasoning={"effort": "low"}`, `system_message=SYSTEM_MESSAGE`

**Step 3 – Extract**
- Build `List[TextInputRecord]` (id=DOI or dataset_id, text=abstract)
- Run `text_classification_flow()` — Prefect flow, `ThreadPoolTaskRunner(max_workers=5)`
- Joblib cache ensures reruns are free

**Step 4 – Prep**
- Convert `TextOutputRecord` list to `DatasetFeaturesNormalized` Pydantic models
- Build `pred_by_id` dict keyed by record id

**Step 5 – Evaluate**
- Run `evaluate_indexed()` on all 16 fields (10 original + 6 modulators)
- `EvaluationConfig(casefold_strings=True, treat_lists_as_sets=True, fuzzy_match_fields={"species": FuzzyMatchConfig(threshold=80)})`
- Micro P/R/F1 + Macro F1

**Step 6 – Analysis**
- Per-field metrics table (all 16 fields)
- Segment by source: Dryad vs Zenodo vs SS
- Feature discussion: which fields extract well/poorly, cross-source variation
- Side-by-side mismatch examples for presentation

**Step 7 – Cost analysis**
- Total cost, cost per record, cost by source
- Token count note vs full-text approaches

**Step 8 – Export**
- HTML report → `notebooks/results/<timestamped>/`
- Extraction results CSV for WU-D1

---

### WU-C1: Download All PDFs (Dryad + Zenodo + SS)
**Tag:** `LOCAL` — requires local filesystem for PDF storage
**Claude model:** `sonnet` — scripting with existing `pdf_download.py` fallback chain; needs DOI extraction from xlsx and manifest building
**Dependencies:** WU-A3 (xlsx already enriched with `pdf_url`, `is_oa`, `cited_article_doi`)
**Notebook:** refactor `notebooks/download_all_fuster_pdfs.ipynb` — replace `dataset_article_mapping.csv` source with `dataset_092624_validated.xlsx`; unified flow for all sources

- Load `dataset_092624_validated.xlsx`; filter to records with `cited_article_doi`
- Use `pdf_url` from xlsx (pre-fetched by WU-A3) as primary download URL
- Run `download_pdf_with_fallback()` for **all** records regardless of OA status (OpenAlex URL → Unpaywall → EZproxy → Sci-Hub)
- Store all PDFs in `data/pdfs/fuster/` (no separate SS folder)
- Save manifest CSV (`data/pdfs/fuster/manifest.csv`) with columns: `article_doi`, `source`, `is_oa`, `status`, `file_path`
- End with a synthesis cell: download stats segmented by source (Dryad / Zenodo / SS)

---

### WU-C2: GROBID-Parse New PDFs
**Tag:** `LOCAL` — requires Docker GROBID on localhost:8070
**Claude model:** `haiku` — straightforward execution of existing `pdf_parsing.py` on new files; no novel logic
**Dependencies:** WU-C1
**Notebook:** extend `notebooks/download_all_fuster_pdfs.ipynb` — add GROBID parsing cells for SS PDFs (or add new cells there if not already present)

- Parse all newly downloaded SS PDFs through GROBID via `pdf_parsing.py`
- Confirm existing Dryad+Zenodo PDFs (~45) are already parsed
- Output: TEI XML in `artifacts/tei/`, parsed document objects

---

### WU-C3: Full-Text Extraction (PDF File API) + Evaluation
**Tag:** `LOCAL` (needs PDF files) + `CLOUD` (OpenAI API)
**Claude model:** `sonnet` — follows WU-B2 evaluation patterns but with PDF pipeline; structured notebook work
**Dependencies:** WU-C1, WU-A2
**Notebook:** refactor `notebooks/batch_pdf_file_evaluation.ipynb` — extend to include SS OA PDFs alongside existing Dryad+Zenodo PDFs; update schema to include modulator fields

- Run OpenAI native PDF File API extraction via `pdf_pipeline.py` on ALL OA PDFs (Dryad+Zenodo existing + new SS)
- Updated schema with modulators
- Evaluate against ground truth, segment by source
- Compare vs abstract-only (WU-B)
- Feature-based performance discussion
- HTML report in `notebooks/results/`

---

### WU-C4: Section-Based Extraction + Evaluation
**Tag:** `LOCAL` — requires GROBID output
**Claude model:** `sonnet` — parallel to WU-C3; same evaluation notebook pattern with section pipeline
**Dependencies:** WU-C2, WU-A2
**Notebook:** refactor `notebooks/batch_fulltext_evaluation.ipynb` — extend to include SS GROBID-parsed PDFs alongside existing Dryad+Zenodo PDFs; update schema to include modulator fields

- Run section-based extraction via `section_pipeline.py` on ALL GROBID-parsed PDFs
- Updated schema with modulators
- Evaluate against ground truth, segment by source
- Compare vs abstract-only (WU-B) and full-text PDF API (WU-C3)
- Feature-based performance discussion
- HTML report in `notebooks/results/`

---

### WU-D1: Assemble Presentation Materials
**Tag:** `CLOUD`
**Claude model:** `opus` — synthesizes results from all streams into coherent narrative; needs judgment for framing, figure selection, and discussion points
**Dependencies:** WU-B, WU-C3, WU-C4

- Update `docs/results_presentation_20260219/work_plan.md` with actual numbers and results
- Three-way comparison table: Abstract-only vs Full-text (PDF API) vs Section-based
- Cross-source comparison: Dryad vs Zenodo vs SS
- Feature-specific analysis and modulator performance
- Cost analysis per approach
- Lab log entry in `notebooks/README.md`

---

## Critical Path

**Fastest path to core deliverable (abstract-only for all sources):**
```
WU-A1 → WU-A2 → WU-B → WU-D1 (partial)
```
All CLOUD — can run entirely in this environment.

**Full-text paths run in parallel but are LOCAL-dependent:**
```
WU-A2 → WU-C1 → WU-C2 → WU-C3/WU-C4 → WU-D1
```

**Fallback if SS PDF coverage is low:** Present abstract-only results for all 491 records + full-text results for existing Dryad+Zenodo OA PDFs (~44 records). Note SS full-text as future work.

---

## Compatibility with plans/integrate_semantic_scholar

| SS Plan Task | Covered Here | Deferred |
|---|---|---|
| 2.1 Schema extension | WU-A1 (DataSource + source field) | URL fields (source_url, journal_url, pdf_url) |
| 2.2 SS API client | — | Full API client not needed for xlsx evaluation |
| 2.3 Module updates | — | Not needed for evaluation pipeline |
| 3.1 Parse xlsx | WU-A2 (merged) | — |
| 4.1 Coverage analysis | WU-A2 | — |
| 5.1 Abstract eval | WU-B | — |
| 5.2 Full-text eval | WU-C3 + WU-C4 | — |
| 5.3 Presentation | WU-D1 | — |

After Thursday, the SS plan continues with API client (Task 2.2), URL fields, cited article retrieval, and broader pipeline integration.

---

## Notebooks

*Sidebar navigation guide — hop through these notebooks in presentation order. Each entry notes how completely the notebook covers its presentation element and whether it reflects the current state of `src/llm_metadata/`.*

### Quick reference

| # | Presentation element | Notebook | Scope | Currency |
|---|---|---|---|---|
| 1 | Data sources & ground truth | `notebooks/fuster_annotations_validation.ipynb` | ✓ Good | ✓ Current |
| 2 | PDF download coverage | `notebooks/download_all_fuster_pdfs.ipynb` | ✓ Good | ✓ Current |
| 3 | Abstract-only extraction & eval | `notebooks/batch_abstract_evaluation.ipynb` | ✓ Good | ~ Minor gap |
| 4 | Field evaluation strategy | `notebooks/field_strategies_eval_demo.ipynb` | ~ Partial | ✓ Current |
| 5 | PDF File API extraction | `notebooks/batch_pdf_file_evaluation.ipynb` | ~ Partial | ✗ Stale |
| 6 | Section-based extraction | `notebooks/batch_fulltext_evaluation.ipynb` | ~ Partial | ✗ Stale |
| 7 | Species field deep dive | `notebooks/species_recall_improvement.ipynb` | ✓ Good | ✓ Current |
| 8 | Evidence / confidence cost | `notebooks/single_doi_extraction_with_evidence.ipynb` | ~ Partial | ✗ Stale |

---

### 1. `notebooks/fuster_annotations_validation.ipynb`
**Presentation element:** Data pipeline — sources, ground truth cleaning, coverage stats.

**Scope:** Covers the full annotation validation flow: load raw xlsx (418 records), Pydantic validation via `DataFrameValidator`, filter to 299 valid records, OpenAlex enrichment (`journal_url`, `pdf_url`, `is_oa`), export `dataset_092624_validated.xlsx`. Output includes per-source coverage table (cited DOI 83.6%, pdf_url 63.2%, OA 64.9%) — ready to present as-is.

**Currency:** Current. Imports `article_retrieval`, `schemas.fuster_features`, `schemas.validation` — all match current src layout. Was the final notebook run for WU-A2/WU-A3; outputs on disk are fresh.

---

### 2. `notebooks/download_all_fuster_pdfs.ipynb`
**Presentation element:** PDF acquisition — coverage by source, fallback chain effectiveness.

**Scope:** Covers the 4-tier fallback chain (`pdf_url` → Unpaywall → EZproxy → Sci-Hub) for all 250 records with a cited DOI. Results segmented by source: Dryad 97.3%, Zenodo 86.8%, SS 64.6%, overall 72.8% (182/250). Good for a "how we got the data" slide. Does not include GROBID parsing (WU-C2 incomplete).

**Currency:** Current. Uses `pdf_download.download_pdf_with_fallback` and `ezproxy` — both exist unchanged. Minor note: notebook still references the older `dataset_article_mapping.csv` source in early cells before being refactored to use xlsx (WU-C1); double-check the top cells before presenting.

---

### 3. `notebooks/batch_abstract_evaluation.ipynb`
**Presentation element:** Abstract-only extraction — main results table, per-field P/R/F1, cross-source comparison.

**Scope:** Good coverage of the core deliverable. 288 records (36 Dryad + 67 Zenodo + 185 SS), gpt-5-mini, $1.91 total. Per-field table for 14 fields (8 core + 6 modulators). Cross-source Micro F1: Dryad 0.259, Zenodo 0.273, SS 0.148. Mismatch examples present. This is the primary results notebook for the presentation.

**Currency:** Minor gap. Imports `text_pipeline`, `gpt_classify.SYSTEM_MESSAGE`, `DatasetFeaturesNormalized`, `groundtruth_eval` — all current. However it uses the older `EvaluationConfig(fuzzy_match_fields=...)` API rather than `DEFAULT_FIELD_STRATEGIES` from `groundtruth_eval.py`. The 12-field registry (dropping `temporal_range` and `referred_dataset`) established in `field_strategies_eval_demo.ipynb` is not reflected here. Metrics are slightly different as a result (14 fields vs 12). Not a blocker for the presentation, but note the discrepancy if showing both notebooks.

---

### 4. `notebooks/field_strategies_eval_demo.ipynb`
**Presentation element:** Evaluation methodology — FieldEvalStrategy registry, species matching comparison.

**Scope:** Partial — this is a methodology/infrastructure demo, not a results notebook. It documents the `DEFAULT_FIELD_STRATEGIES` API, explains why `temporal_range` and `referred_dataset` were dropped, and shows the species strategy comparison (exact F1=0.115, enhanced_species F1=0.256, fuzzy F1=0.200). Useful as a "how we measure" slide, not a "here are the results" slide.

**Currency:** Most up-to-date evaluation notebook. Imports only `groundtruth_eval.DEFAULT_FIELD_STRATEGIES` and `DatasetFeaturesNormalized` — both current. Was the last notebook committed after WU-EH5.

---

### 5. `notebooks/batch_pdf_file_evaluation.ipynb`
**Presentation element:** PDF File API extraction — full-text results, comparison to abstract-only.

**Scope:** Partial. Covers 38 OA records (Dryad + Zenodo only — no SS). Evaluates 7 core fields (pre-modulator schema, missing the 6 boolean modulators). Micro F1 0.357 vs abstract-only 0.202 shows meaningful gain. Good for a comparison slide if you scope it clearly as "existing Dryad+Zenodo OA subset." WU-C3 (extending to SS OA PDFs + modulator fields) is not done.

**Currency:** Stale on two fronts. (1) Schema: predates WU-A1 — evaluates only 7 of 14 fields; modulator booleans missing. (2) Scope: 38 records only, SS not included. The `pdf_pipeline` and `gpt_classify.PDF_SYSTEM_MESSAGE` imports are current, but the evaluation config uses the old API. Presenting raw outputs risks confusion about field count mismatch with WU-B results.

---

### 6. `notebooks/batch_fulltext_evaluation.ipynb`
**Presentation element:** Section-based extraction — GROBID pipeline results, section selection strategy.

**Scope:** Partial. Covers 45 Dryad records using GROBID-parsed sections via `section_pipeline`. Includes section selection stats (avg 14.1 sections, avg 7,778 tokens vs 315 for abstract). Micro F1 0.289 / Macro F1 0.407 on 7 fields. Good for showing the pipeline architecture, but narrower than the final deliverable. WU-C4 (extending to SS + modulator schema) not done.

**Currency:** Stale on the same two axes as `batch_pdf_file_evaluation.ipynb`. (1) Schema: pre-WU-A1, 7 fields only. (2) Scope: 45 Dryad records only. `section_pipeline`, `pdf_parsing`, `section_normalize`, `chunk_metadata` imports are all current modules. The evaluation config uses old API. Same presenting caveat as notebook 5.

---

### 7. `notebooks/species_recall_improvement.ipynb`
**Presentation element:** Species field deep dive — prompt vs matching strategy comparison.

**Scope:** Good, focused experiment. 10 OA Dryad PDFs, 2×2 grid: {baseline, improved prompt} × {basic fuzzy, enhanced species matching}. Best config: improved prompt + enhanced matching — F1=0.824, recall=0.933. Shows the value of both prompt tuning and smarter matching. Self-contained result, does not depend on incomplete WU work.

**Currency:** Current. Uses `pdf_pipeline`, `gpt_classify.PDF_SYSTEM_MESSAGE`, `groundtruth_eval`, `DatasetFeaturesNormalized` — all present in current src. The `enhanced_species` matching aligns with `DEFAULT_FIELD_STRATEGIES` (threshold=70). Only caveat: `PDF_SYSTEM_MESSAGE` has been updated since this ran (WU-A1 added modulator guidance), so a re-run would use the newer prompt.

---

### 8. `notebooks/single_doi_extraction_with_evidence.ipynb`
**Presentation element:** Evidence tracking — cost-benefit analysis, confidence calibration failure.

**Scope:** Partial. Single-DOI case study (`10.5061/dryad.3nh72`). Key finding: evidence tracking costs 4–5x more in output tokens, and confidence scores are uniformly miscalibrated (all = 5 regardless of prompt instructions). Good for a "what we tried and why we ruled it out" slide. Not a full evaluation.

**Currency:** Stale. Imports `llm_metadata.schemas.evidence` (the `add_evidence_field()` function) — this module is **not listed** in current src. It was likely experimental and removed or never committed. Before using this notebook in a live session, verify the import resolves or skip to presenting the conclusions from the output cells only.

---

### Not recommended for live presentation

| Notebook | Reason |
|---|---|
| `fuster_test_extraction_evaluation.ipynb` | Early 5-record POC predating `text_pipeline`; uses `classify_abstract()` directly and old `DataFrameValidator` import path. Stale. |
| `fulltext_extraction_evaluation.ipynb` | Single-DOI feasibility stub; imports `DatasetFeatureExtraction` (old model name). Stale, inconclusive. |
| `prompt_eval_results.ipynb` | Utility viewer template; no outputs populated — `results/baseline_abstract.json` not present. |

---

## Critical Files

| File | Work Units | Changes |
|---|---|---|
| `src/llm_metadata/schemas/fuster_features.py` | WU-A1 | +6 modulator fields, +DataSource enum, +source field, +validators |
| `src/llm_metadata/gpt_classify.py` | WU-A1 | Update system prompts for modulator extraction |
| `src/llm_metadata/groundtruth_eval.py` | WU-B | Minor: verify boolean field comparison works |
| `src/llm_metadata/text_pipeline.py` | WU-B | Use for batch abstract extraction |
| `src/llm_metadata/pdf_pipeline.py` | WU-C3 | Use for PDF File API extraction |
| `src/llm_metadata/section_pipeline.py` | WU-C4 | Use for section-based extraction |
| `src/llm_metadata/pdf_download.py` | WU-C1 | Use as-is (no changes) |
| `src/llm_metadata/pdf_parsing.py` | WU-C2 | Use as-is (no changes) |
| `data/dataset_092624.xlsx` | WU-A2 | Read-only input |
| `docs/results_presentation_20260219/work_plan.md` | WU-D1 | Update with results |

---

## Verification

1. **Schema:** `uv run python -m pytest tests/` passes after WU-A1
2. **Data validation:** All 418 xlsx records validate through updated schema (WU-A2)
3. **Abstract extraction + evaluation:** `batch_abstract_evaluation.ipynb` runs end-to-end on >=450 records; per-field P/R/F1 for all 16 fields, segmented by source (WU-B)
4. **Full-text:** At least the existing ~44 OA Dryad+Zenodo PDFs processed through both pipelines (WU-C3, WU-C4)
5. **Presentation:** `work_plan.md` has actual numbers, not TBD placeholders (WU-D1)
