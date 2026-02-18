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

### WU-A2: Validate All-Source Ground Truth Data
**Tag:** `CLOUD`
**Claude model:** `sonnet` — structured pandas + Pydantic validation following existing notebook patterns; no novel architecture
**Dependencies:** WU-A1

Create notebook (or extend `fuster_annotations_validation.ipynb`):
- Load `data/dataset_092624.xlsx`, validate ALL 418 records through updated `DatasetFeaturesNormalized`
- Filter to valid records (~491 across all sources)
- Compute coverage stats: records by source, with abstracts, with DOIs, with `cited_articles`
- Export: `data/dataset_092624_all_sources_validated.xlsx`
- Stats table for presentation Methods section (source breakdown, OA proportions)

---

### WU-B: Abstract-Only Extraction + Evaluation
**Tag:** `CLOUD`
**Claude model:** `sonnet` — mirrors the structure of `batch_fulltext_evaluation.ipynb` and `batch_pdf_file_evaluation.ipynb`; extraction and evaluation in a single notebook
**Dependencies:** WU-A2

Notebook: `notebooks/batch_abstract_evaluation.ipynb`

**Step 1 – Load data**
- Read `data/dataset_092624_all_sources_validated.xlsx` (output of WU-A2)
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

### WU-C1: Download OA PDFs for Semantic Scholar Records
**Tag:** `LOCAL` — requires local filesystem for PDF storage
**Claude model:** `sonnet` — scripting with existing `pdf_download.py` fallback chain; needs DOI extraction from xlsx and manifest building
**Dependencies:** WU-A2

- Extract article DOIs from xlsx `cited_articles` column for SS records
- Use existing `pdf_download.py` fallback chain (OpenAlex → Unpaywall → EZproxy → Sci-Hub)
- Check OA status via `openalex.py`
- Store PDFs in `data/pdfs/semantic_scholar/`
- Build manifest CSV (DOI, OA status, download status, file path)
- **Risk:** SS PDF yield may be low — document coverage for presentation

---

### WU-C2: GROBID-Parse New PDFs
**Tag:** `LOCAL` — requires Docker GROBID on localhost:8070
**Claude model:** `haiku` — straightforward execution of existing `pdf_parsing.py` on new files; no novel logic
**Dependencies:** WU-C1

- Parse all newly downloaded SS PDFs through GROBID via `pdf_parsing.py`
- Confirm existing Dryad+Zenodo PDFs (~45) are already parsed
- Output: TEI XML in `artifacts/tei/`, parsed document objects

---

### WU-C3: Full-Text Extraction (PDF File API) + Evaluation
**Tag:** `LOCAL` (needs PDF files) + `CLOUD` (OpenAI API)
**Claude model:** `sonnet` — follows WU-B2 evaluation patterns but with PDF pipeline; structured notebook work
**Dependencies:** WU-C1, WU-A2

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
| 3.1 Parse xlsx | WU-A2 | — |
| 4.1 Coverage analysis | WU-A2 | — |
| 5.1 Abstract eval | WU-B | — |
| 5.2 Full-text eval | WU-C3 + WU-C4 | — |
| 5.3 Presentation | WU-D1 | — |

After Thursday, the SS plan continues with API client (Task 2.2), URL fields, cited article retrieval, and broader pipeline integration.

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

1. **Schema:** `uv run --env-file .env python -m pytest tests/` passes after WU-A1
2. **Data validation:** All 418 xlsx records validate through updated schema (WU-A2)
3. **Abstract extraction + evaluation:** `batch_abstract_evaluation.ipynb` runs end-to-end on >=450 records; per-field P/R/F1 for all 16 fields, segmented by source (WU-B)
4. **Full-text:** At least the existing ~44 OA Dryad+Zenodo PDFs processed through both pipelines (WU-C3, WU-C4)
5. **Presentation:** `work_plan.md` has actual numbers, not TBD placeholders (WU-D1)
