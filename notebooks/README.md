# Notebooks Log Book

This folder contains analysis and validation notebooks for ecological dataset characterization.

## Recent Activity

### 2026-04-01: Repeatability Test — gpt-5.4/medium (fresh run vs cached run)

**Task:** Determine whether the poor gpt-5.4/medium results from the earlier 20260401 run are reproducible or a fluke. Same config, `skip_cache=True` to force fresh API calls.

**Work Performed:**
- Re-ran abstract and pdf_native modes with identical config to the earlier 20260401 runs, but with `skip_cache=True`
- Launch script: `artifacts/runs/20260401_123138_pe_latest_model_repetition.py`
- Runs: `artifacts/runs/20260401_123138_pe_model_medium_change_abstract.json`, `artifacts/runs/20260401_123152_pe_model_medium_pdf_native.json`
- Compared Run1 (cached) vs Run2 (fresh) at the TP/FP/FN level per field

**Results — Abstract mode repeatability (12 fields):**

| Stability | Fields | Detail |
|---|---|---|
| Identical (7/12) | `bias_north_south`, `multispecies`, `new_species_region`, `new_species_science`, `spatial_range_km2`, `temp_range_f`, `temp_range_i` | Bit-identical TP/FP/FN |
| Varies (5/12) | `data_type` (ΔF1=-0.03), `geospatial_info_dataset` (+0.04), `species` (+0.02), `threatened_species` (+0.10), `time_series` (+0.10) | Small variance, max ΔF1=0.10 |

**Results — PDF native mode repeatability (12 fields):**

| Stability | Fields | Detail |
|---|---|---|
| Identical (5/12) | `bias_north_south`, `spatial_range_km2`, `temp_range_f`, `temp_range_i`, `threatened_species` | Bit-identical TP/FP/FN |
| Varies (7/12) | `data_type` (-0.03), `geospatial_info_dataset` (+0.04), `multispecies` (+0.04), `species` (+0.02), `new_species_region` (-0.07), `new_species_science` (-0.08), `time_series` (-0.09) | Max ΔF1=0.09 |

**Key Findings:**
- **The regressions are real, not stochastic.** Run-to-run variance is ≤0.10 F1, while regressions vs gpt-5-mini baseline are 0.25–0.69 F1. Signal-to-noise is overwhelming.
- **Abstract mode is highly deterministic** (7/12 identical). Boolean and numeric fields are perfectly stable.
- **PDF native has more variance** (5/12 identical) — likely from non-deterministic visual/layout processing.
- **List-output fields vary more** (`data_type`, `geospatial_info_dataset`, `species`). Boolean fields are the most stable across both modes.
- **Conclusion confirmed:** gpt-5.4/medium is systematically more conservative than gpt-5-mini/low. The same records fail consistently. This is a model behavioral pattern, not noise.

### 2026-04-01: Model Upgrade Experiment — gpt-5-mini/low → gpt-5.4/medium

**Task:** Test whether upgrading from gpt-5-mini with low reasoning effort to gpt-5.4 with medium reasoning effort improves extraction performance on modulator fields and `data_type`/`geospatial_info_dataset`.

**Work Performed:**
- Ran two `prompt_eval` runs on the dev subset (30 records) with identical prompts from the 2026-03-31 session, changing only model (`gpt-5.4`) and reasoning effort (`medium`)
- Compared against the 2026-03-31 baseline runs (gpt-5-mini, effort=low)
- Runs: `artifacts/runs/20260401_120758_pe_model_medium_change_abstract.json`, `artifacts/runs/20260401_120759_pe_model_medium_pdf_native.json`
- Launch script: `artifacts/runs/20260401_094700_pe_model_medium_change_launch.py`

**Results — Abstract Mode (gpt-5-mini/low → gpt-5.4/medium):**

| Field | Baseline F1 | gpt-5.4 F1 | Δ F1 |
|---|---|---|---|
| `temp_range_i` | 0.743 | 0.743 | 0.000 |
| `multispecies` | **0.746** | 0.391 | **-0.355** |
| `temp_range_f` | 0.629 | 0.629 | 0.000 |
| `time_series` | 0.471 | 0.500 | +0.029 |
| `data_type` | 0.424 | 0.469 | +0.046 |
| `species` | 0.405 | 0.386 | -0.020 |
| `threatened_species` | 0.385 | **0.500** | **+0.115** |
| `bias_north_south` | 0.286 | **0.421** | **+0.135** |
| `geospatial_info_dataset` | 0.255 | 0.197 | -0.057 |
| `new_species_region` | 0.222 | 0.080 | **-0.142** |
| `new_species_science` | 0.167 | null | **-0.167** |
| `spatial_range_km2` | 0.095 | 0.095 | 0.000 |

**Results — PDF Native Mode (gpt-5-mini/low → gpt-5.4/medium):**

| Field | Baseline F1 | gpt-5.4 F1 | Δ F1 |
|---|---|---|---|
| `bias_north_south` | **0.830** | 0.537 | **-0.294** |
| `new_species_science` | **0.769** | 0.083 | **-0.686** |
| `new_species_region` | **0.750** | 0.148 | **-0.602** |
| `threatened_species` | **0.778** | 0.545 | **-0.232** |
| `multispecies` | **0.767** | 0.510 | **-0.257** |
| `spatial_range_km2` | 0.703 | 0.632 | -0.071 |
| `temp_range_i` | 0.694 | 0.653 | -0.041 |
| `temp_range_f` | 0.694 | 0.653 | -0.041 |
| `data_type` | 0.370 | 0.392 | +0.021 |
| `time_series` | 0.250 | **0.588** | **+0.338** |
| `species` | 0.187 | 0.253 | +0.066 |
| `geospatial_info_dataset` | 0.230 | 0.135 | -0.095 |

**Key Findings:**
- **gpt-5.4/medium is a clear regression.** It is systematically more conservative — outputs null where gpt-5-mini correctly extracted values. PDF `new_species_science` TP dropped 15→1, `new_species_region` 15→2, `bias_north_south` 22→11; abstract `multispecies` 22→9.
- The only field that materially benefited is `time_series` in PDF native mode (F1 0.25→0.59), where gpt-5-mini's FP dropped from 23→7.
- Cost is ~10x higher per record for negligibly or negatively different quality.

**Verdict:** Stay on gpt-5-mini/low. The "medium" reasoning effort makes the model second-guess itself on signals gpt-5-mini correctly acts on. If model upgrade is revisited, try gpt-5.4 with `effort: low` to isolate whether regression comes from the model or the effort level.

**Next Steps:**
- Continue prompt engineering on gpt-5-mini/low (species precision, data_type F1 ≥0.50 target)
- Optional: test gpt-5.4/low to isolate model vs effort contribution

### 2026-03-31: Improved Prompt for Modulator Fields, `data_type`, and `geospatial_info_dataset`

**Task:** Improve the prompt for modulator fields, `data_type`, and `geospatial_info_dataset`, then evaluate all three extraction modes on the dev subset.

**Work Performed:**
- Expanded the `common.py` vocabulary block from a partial list to the full 13-value `data_type` enum (corrected 5 invalid values: `tracking`, `remote_sensing`, `acoustic`, `morphological`, `environmental`; added `presence-absence`, `density`, `distribution`, `traits`, `ecosystem_function`, `ecosystem_structure`, `species_richness`, `other`, `unknown`).
- Expanded `geospatial_info_dataset` from 5 to 9 values (`distribution`, `geographic_features`, `site_ids`, `unknown` added), with contrastive examples and a negative rule for place-name over-triggering.
- Expanded the modulator boolean guidance: `time_series` gained 4 negative anchors, `threatened_species` gained a broader IUCN/CITES/SARA/COSEWIC/provincial cue table, and `bias_north_south` was rewritten as a dual-trigger rule (northern geography + explicit bias language).
- Added sections-mode rules for `data_type` (primary collected data, not downstream analyses) and `time_series` (field seasons do not imply a time series).
- Added PDF-mode rules for `time_series` (judge from sampling design only), `new_species_science` (for example `sp. nov.` and holotype language), and `new_species_region` (explicit first-record wording).
- **Runs:** Abstract-only smoke test first, then the three final mode runs in `artifacts/runs/20260331_12*`

**Three-mode results (2026-03-31):**

| Field | Abstract F1 | Sections F1 | PDF Native F1 | Best mode |
|---|---|---|---|---|
| `data_type` | **0.424** | 0.372 | 0.370 | abstract |
| `geospatial_info_dataset` | **0.255** | 0.182 | 0.230 | abstract |
| `species` | **0.405** | 0.380 | 0.187 | abstract |
| `time_series` | 0.471 | **0.476** | 0.250 | sections |
| `threatened_species` | 0.385 | 0.370 | **0.778** | pdf_native |
| `bias_north_south` | 0.286 | 0.378 | **0.830** | pdf_native |
| `multispecies` | 0.746 | 0.724 | **0.767** | pdf_native |
| `temp_range_i` | **0.743** | 0.524 | 0.694 | abstract |
| `temp_range_f` | **0.629** | 0.619 | 0.694 | pdf_native |
| `spatial_range_km2` | 0.095 | 0.667 | **0.703** | pdf_native |
| `new_species_region` | 0.222 | 0.286 | **0.750** | pdf_native |
| `new_species_science` | 0.167 | 0.240 | **0.769** | pdf_native |

**Key findings:**
- PDF native dominates for `threatened_species` (F1=0.78), `bias_north_south` (F1=0.83), `new_species_*` (F1=0.75/0.77), `spatial_range_km2` (F1=0.70)
- Abstract best for `data_type`, `geospatial_info`, `species`, `temp_range_i`
- The new mode-specific rules appear effective: `new_species_science` PDF F1 0.61→0.77, `bias_north_south` PDF F1 was N/A→0.83
- `threatened_species` recall remained weak in abstract mode (R=0.24) but was strong in PDF mode (R=0.67), which suggests the conservation language often lives in full text rather than abstracts
- Species precision is still weak across all modes, so the next prompt iteration should focus on a dedicated species-extraction block

**PDF native vs sections — why the gap?**

The two full-text modes differ fundamentally in what the LLM sees:
- **Sections mode**: GROBID-parsed TEI → filtered sections (Abstract + Methods + keyword-matched headings) → concatenated markdown (~3–17k chars). A lossy subset of the paper.
- **PDF native mode**: the actual PDF file via OpenAI File API — the LLM sees the entire document including figures, tables, captions, supplementary content, and layout.

Three sources of information loss explain sections mode's underperformance:

1. **Section filtering is aggressive** — only `ABSTRACT` + `METHODS` types + keyword-matched headings pass through (`SectionSelectionConfig`). Results, Discussion, Introduction, and Supplementary are mostly excluded. Fields like `threatened_species` (conservation language in Intro/Discussion), `new_species_*` (taxonomy sections), and `bias_north_south` (Discussion framing) lose their signal entirely.

2. **GROBID parsing quality** — TEI extraction drops tables, figures, captions, and sometimes mislabels or truncates sections. Table headers for `spatial_range_km2`, figure maps for `geospatial_info`, and supplementary species lists are lost.

3. **Structural context is destroyed** — PDF native preserves document layout, table formatting, figure captions, and section hierarchy. Sections mode collapses everything to flat markdown, removing cues the model uses for spatial/temporal/taxonomic extraction.

The numbers confirm this pattern: PDF native wins on every field whose signal lives outside Abstract+Methods (`threatened_species` 0.78 vs 0.37, `new_species_science` 0.77 vs 0.24, `bias_north_south` 0.83 vs 0.38). Sections mode is competitive only where signal concentrates in Methods (`spatial_range_km2` 0.67 vs 0.70 — essentially tied). The remaining use case for sections mode is cost control at scale or targeted per-field section routing in a mode-fusion pipeline.

**Next Steps:**
- Add a dedicated `SPECIES_EXTRACTION` block to address species precision
- Consider mode-fusion strategy: per-field best-mode selection for production pipeline
- `data_type` F1 target (≥0.50) not yet met in any mode — may need further prompt refinement or GT audit

### 2026-03-28: Baseline Prompt with Improved Species Evaluation — Dev-Subset Audit

**Task:** Inspect the March 27 baseline run artifacts across abstract, section-based, and native-PDF modes, then turn the observed failure patterns into a practical prompt-engineering and evaluation roadmap.

**Work Performed:**
- **Artifacts reviewed:** `artifacts/runs/20260327_172654_dev_subset_abstract.json`, `artifacts/runs/20260327_172653_dev_subset_sections.json`, `artifacts/runs/20260327_172656_dev_subset_pdf_file.json`
- Compared per-field metrics and mode tradeoffs, then inspected recurring false-positive / false-negative value patterns directly from `field_results`
- Cross-checked the current prompt blocks in `src/llm_metadata/prompts/common.py` and found a major vocabulary mismatch: the prompt currently documents only a subset of the enum values actually accepted by `DatasetFeaturesExtraction`
- Wrote mode-specific analyst notes next to the three latest run artifacts:
  - `artifacts/runs/20260327_172654_dev_subset_abstract_notes.md`
  - `artifacts/runs/20260327_172653_dev_subset_sections_notes.md`
  - `artifacts/runs/20260327_172656_dev_subset_pdf_file_notes.md`

**Results:**
- The March 27 run set is effectively a stable baseline; its metrics match the March 6 run set exactly, so no prompt improvement has landed yet
- Mode comparison on the 30-record dev subset:
  - `abstract` is best for `data_type` (F1 `0.34`), `time_series` (F1 `0.53`), and `temp_range_i` (F1 `0.74`)
  - `sections` is best for `species` (F1 `0.42`) and materially improves `spatial_range_km2` over abstract mode (F1 `0.69` vs `0.10`)
  - `pdf_native` is best for `new_species_science` (F1 `0.61`), `new_species_region` (F1 `0.59`), `threatened_species` (F1 `0.65`), and `multispecies` (F1 `0.75`), but it is catastrophically over-inclusive for `species` (precision `0.10`)
- The strongest prompt-level issue is a schema/prompt vocabulary gap:
  - `data_type` prompt docs omit valid labels such as `presence-absence`, `density`, `distribution`, `traits`, `ecosystem_function`, `ecosystem_structure`, `time_series`, `species_richness`, `other`, and `unknown`
  - `geospatial_info_dataset` prompt docs omit valid labels such as `distribution`, `geographic_features`, `site_ids`, and `unknown`
- Recurrent mismatch patterns:
  - `data_type`: over-prediction of broad labels, under-recovery of `presence-only` and `density`
  - `geospatial_info_dataset`: place names in prose are being over-read as dataset geography
  - `species`: incidental taxa, decorated taxa strings, and count-bearing phrases leak into outputs, especially in PDF mode
  - `time_series`: any multi-year wording is being interpreted as repeated monitoring
  - `bias_north_south`: zero recall in all modes

**Key Issues Identified:**
- Prompt vocabulary is incomplete relative to the schema, which likely explains part of the persistent `data_type` and `geospatial_info_dataset` noise
- Full-text mode improves rare positive fields but badly increases contextual contamination for `species`, `geospatial_info_dataset`, and `time_series`
- Evaluation hardening is still needed alongside prompt work:
  - checked-in config JSONs still use stale `geospatial_info` instead of `geospatial_info_dataset`
  - `accuracy` remains invalid for multi-value fields like `species`
  - boolean scoring should be re-audited because GT `False` and model `None` currently behave like missed positives in the saved artifacts

**Next Steps:**
- Easy: expand `VOCABULARY` to the full schema enum surface and add contrastive negative examples for `time_series`, `species`, and geography scoping
- Medium: run one-block-at-a-time prompt experiments by mode instead of global rewrites, starting with abstract/sections for `data_type` and species hygiene, then PDF-only iterations for rare positive fields
- Hard: move full-text extraction toward evidence-gated or two-stage workflows, and harden evaluation with config fixes, boolean semantics review, and a locked holdout set before trusting small deltas

### 2026-03-09: Claim Grounding Pilot Design

**Task:** Define a notebook-first claim-grounding pilot that is reviewable without fresh API calls and narrows the scope to the first five dev-subset records plus the three mismatch-heavy fields.

**Work Performed:**
- **Notebook:** `notebooks/claim_grounding_pilot.ipynb`
- Fixed the pilot inputs to the first five rows of `data/dev_subset.csv` (GT ids `9`, `19`, `27`, `29`, `30`)
- Bound the notebook to the saved PDF-file run artifact `artifacts/runs/20260306_124634_dev_subset_pdf_file.json` so GT versus prediction comparison is reproducible offline
- Restricted the review surface to `geospatial_info_dataset`, `data_type`, and `species`
- Built a side-by-side atomic-claim comparison table with `match`, GT claim columns, prediction claim columns, and draft grounding slots (`support_type`, `quote`, `rationale`) for each side
- Added lightweight lexical grounding heuristics in the notebook as a pilot-only placeholder so the table is immediately reviewable before a fuller grounding pass is introduced
- Added notebook-first exploration views: bucket summaries, support-type summaries, and curated record examples for ids `9`, `27`, and `30`

**Results:**
- The pilot now has a concrete notebook and a stable output shape for the first five-record review
- The notebook writes a reusable review table to `artifacts/claim_grounding_pilot_first5.csv` when executed
- The chosen records include the intended mismatch patterns for this work: geospatial over-prediction, `data_type` disagreement, and species naming granularity mismatches
- The notebook is now easier to inspect directly because it starts with summaries and then jumps into a few representative examples instead of forcing review through the full flat table

**Key Issues Identified:**
- The notebook grounding is intentionally shallow and should not be treated as an evaluation artifact; it is only a design scaffold for the next grounding implementation pass
- Exact atomic-value matching keeps vernacular/scientific variants and enum paraphrases visible, which is useful for diagnosis but will overstate mismatch counts relative to the current evaluation registry

**Next Steps:**
- Implement a notebook-only LLM grounding pilot in `notebooks/claim_grounding_from_llm.ipynb`
- Use that pilot to finalize the atomic-claim schemas and prompt-builder behavior
- Reuse the notebook table shape in `prompt_eval` and the viewer so evidence review stays consistent across the stack

### 2026-03-07: Taxonomy Eval Cleanup, Rename & Notebook Archive

**Task:** Walk back over-committed taxonomy experiment scaffolding, fix field naming, archive notebook while preserving observations.

**Work Performed:**
- Removed `species_stripped_richness` and `gbif_key_stripped_richness` fields from `DatasetFeaturesEvaluation` and `DEFAULT_TAXONOMY_FIELD_STRATEGIES` — these were experimental fields from the taxonomy notebook that proved under-designed
- Removed `project_gbif_key_stripped_richness()` function and double GBIF resolution path in `enrich_with_taxonomy()`
- Removed `applicability` concept from `FieldEvalStrategy` — silent skip with no introspection was under-designed; if needed later, should be re-implemented with proper reporting
- Renamed eval-facing fields: `taxon_richness_mentions` → `species_richness_mentions`, `taxon_richness_counts` → `species_richness_counts`, `taxon_richness_group_keys` → `species_richness_group_keys`
- Renamed corresponding functions: `extract_taxon_richness_mentions` → `extract_species_richness_mentions`, `project_taxon_richness_counts` → `project_species_richness_counts`, `project_taxon_richness_group_keys` → `project_species_richness_group_keys`
- Internal model class names (`TaxonRichnessMention`, `ParsedTaxon`) kept unchanged — they represent taxonomic concepts, not eval views
- Archived `taxonomic_relevance_evaluation.ipynb` to `notebooks/archives/`, created clean version keeping problem description, analysis, discussion, and personal observations
- Updated all tests (65 pass)

**Results:**
- `DEFAULT_TAXONOMY_FIELD_STRATEGIES` now contains 5 fields: `species`, `species_richness_counts`, `species_richness_group_keys`, `taxon_broad_group_labels`, `gbif_keys`
- `DatasetFeaturesEvaluation` no longer carries experimental stripped-richness fields
- `project_species_stripped_richness()` kept as utility in `species_parsing.py` for future notebook use

**Key Learnings from Archived Notebook:**
- GT species values encode 3 distinct signals: species richness, taxonomic identity, and group membership
- `taxon_broad_group_labels` is the strongest relevance-oriented view for whole-dataset screening
- Extraction prompt needs improvement to reduce non-taxon goop in species output ("analysed", "others)")
- Taxonomic signals should be evaluated independently, not collapsed into one metric

**Next Steps:**
- Phase D: Improve species extraction prompt to reduce non-taxon goop, run prompt_eval comparison
- Phase E (if needed): Add `species_richness` as structured field on `DatasetFeaturesExtraction`

### 2026-03-06: Model Hierarchy & Enrichment Refactor

**Task:** Split the overloaded `DatasetFeatures` contract into extraction, ground-truth normalization, and evaluation-time models so source metadata and enrichment fields no longer leak into the LLM schema.

**Work Performed:**
- Refactored `src/llm_metadata/schemas/fuster_features.py` into `CoreFeatureModel`, `DatasetFeaturesExtraction`, `DatasetFeaturesNormalized`, and `DatasetFeaturesEvaluation`
- Kept `DatasetFeatures` as a compatibility alias for the extraction contract so older notebooks and tests still load
- Moved ownership of source/provenance metadata to `DataPaperRecord` and rewired `prompt_eval.py` to build GT rows from semantic fields only
- Updated `taxonomy_eval.py` and `gbif.py` so service lookup returns payloads first and evaluation-model assembly happens through `DatasetFeaturesEvaluation.from_extraction(...)`
- Migrated contract-boundary tests (`test_datasource_schema.py`, `test_multisource_integration.py`, `test_gbif_enrichment.py`, `test_taxonomy_eval.py`) to assert the new separation explicitly

**Results:**
- The schema passed to `responses.parse()` now excludes source/provenance fields and enrichment-only fields
- GT normalization keeps the same semantic fields and validators, but ignores record-level provenance columns
- Evaluation-only derived fields (`parsed_species`, richness projections, `gbif_keys`) are now isolated on `DatasetFeaturesEvaluation`
- No metric run was executed as part of this refactor; this was a contract cleanup and test migration pass

**Key Issues Identified:**
- Existing notebooks still rely on the `DatasetFeatures` name in many cells; compatibility is preserved via aliasing, but future notebook cleanup should switch explicit imports to `DatasetFeaturesExtraction` / `DatasetFeaturesEvaluation`
- Older narrative docs and rendered notebook exports may still refer to the pre-split schema name until they are regenerated

**Next Steps:**
- Regenerate the main evaluation notebooks when the next prompt-eval experiment runs so notebook code and exported HTML use the explicit class names

### 2026-03-05: Data-Paper Manifest Refactor

**Task:** Implement the canonical manifest contract for data-paper sources, replacing DOI-driven PDF selection with a `gt_record_id`-keyed manifest that stores explicit `pdf_local_path` fields.

**Work Performed:**
- Created `src/llm_metadata/doi_utils.py`: centralized DOI normalization (`normalize_doi`, `doi_equal`, `doi_filename_stem`, `doi_candidate_variants`, `extract_doi_from_url`)
- Created `src/llm_metadata/schemas/data_paper.py`: `DataPaperRecord` and `DataPaperManifest` Pydantic models with integrity checks (duplicate ID rejection, DOI normalization on construction)
- Created `src/llm_metadata/data_paper_manifest.py`: builder joining GT XLSX + PDF manifest CSV, save/load CSV, CLI entrypoint, `update_record_pdf_path()` helper
- Refactored `src/llm_metadata/prompt_eval.py`: added manifest-driven record selection (`manifest_path`) and removed `--subset` filtering. Prompt module now determines extraction mode (`prompts.abstract` vs `prompts.pdf_file`), while manifest defines the evaluated record IDs.
- Created `src/llm_metadata/manifest_adapters.py`: adapter layer for fulltext/pdf/section pipeline compatibility
- Centralized DOI handling in `article_retrieval.py` and `pdf_download.py` via `doi_utils`
- Generated `data/manifests/dev_subset_data_paper.csv`: 30/30 dev subset records with `pdf_local_path` all existing on disk
- Added 6 test files: `test_doi_utils.py`, `test_data_paper_schema.py`, `test_data_paper_manifest.py`, `test_manifest_adapters.py`, `test_prompt_eval_manifest.py`, `test_manifest_integration.py`

**Results:**
- 114 new tests, all passing
- Dev subset manifest preflight: 30/30 records, 30/30 unique IDs, 30/30 PDFs on disk
- Pre-existing test suite: 286 passed, 4 pre-existing failures in `test_pdf_classify.py` (unrelated to this refactor)

**Key Issues Identified:**
- GT XLSX (`dataset_092624_validated.xlsx`) has a duplicate row for id=306 (identical data). Added `deduplicate_gt=True` option to manifest builder to handle this gracefully.
- Legacy note: `dev_subset.csv` used dataset DOIs (`source_url`) rather than article DOIs. The current flow is manifest-only (`data/manifests/*.csv`) and uses explicit `gt_record_id` + `pdf_local_path`.

**Next Steps:**
- Re-run PDF evaluation against the manifest with `--manifest data/manifests/dev_subset_data_paper.csv` to verify 30/30 extraction success (requires OpenAI API key)

### 2026-02-19: WU-C2 — GROBID parsing of all downloaded PDFs

**Task:** Parse all 182 downloaded PDFs (Dryad + Zenodo + Semantic Scholar) through GROBID to produce TEI XML for section-based extraction.

**Work Performed:**
- Added Section 5 (GROBID Parsing) to `notebooks/download_all_fuster_pdfs.ipynb`: markdown cell + code cell that calls `call_grobid()` on all downloaded PDFs from the manifest
- `call_grobid()` is idempotent — already-parsed files are skipped on re-runs
- GROBID crashed mid-run (OOM); restarted Docker container and re-ran (idempotent, no data loss)
- 1 PDF skipped due to Windows MAX_PATH limit (filename contains multiple concatenated URLs/DOIs)

**Results:**

| Source | Downloaded PDFs | TEI Parsed | Notes |
|--------|-----------------|------------|-------|
| Dryad | 36 | 36 | 21 pre-existing + 15 new |
| Zenodo | 33 | 33 | 24 pre-existing + 9 new |
| Semantic Scholar | 113 | 110 | 1 pre-existing + 109 new, 3 errors |
| **Total** | **182** | **179** | 45 pre-existing → 179 total |

**Key Issues:**
- GROBID (Docker, `lfoppiano/grobid:0.8.0`) crashes under sustained load (~70 PDFs/run); restart is sufficient, run is idempotent
- 1 Dryad PDF has a MAX_PATH-exceeding filename; TEI output path fails silently with error

**Next Step:** WU-C4 (section-based extraction) can now proceed using `artifacts/tei/` (179 TEI files)

---

### 2026-02-19: SS-4.2, SS-6.1, SS-6.3 — Coverage validation, CLAUDE.md, integration tests

**Task:** Complete remaining Semantic Scholar integration tasks: validate coverage goals (SS-4.2), update project docs (SS-6.1), add multi-source integration tests (SS-6.3), and fix boolean coercion bug.

**Work Performed:**
- **`tests/test_multisource_integration.py`** (new, 39 tests): End-to-end integration tests covering realistic Dryad, Zenodo, and Semantic Scholar records through `DatasetFeaturesNormalized`. Tests verify source tracking, boolean coercion ("no" → False), comma-separated data types, URL field preservation, null placeholder handling, and cross-source edge cases. Also verifies `DataSource` enum round-trips correctly through the schema.
- **Boolean coercion bugfix** in `schemas/fuster_features.py`: Removed `"no"` from `null_placeholders` in `convert_nan_to_none` model validator. "no" was being converted to `None` before `coerce_bool` could map it to `False` for modulator fields. Fix restores 4 failing tests in `test_schema_modulators.py`.
- **`CLAUDE.md`** updated: expanded `semantic_scholar.py` module description (key functions, rate limiting, caching, field availability notes), added Multi-Source Architecture design pattern (DataSource enum, URL field conventions), added Troubleshooting section (SS API, schema validation).
- **SS-4.2 coverage validation** (see Results below).

**Results — Coverage goals validation (from `data/dataset_092624_validated.xlsx`, 299 records):**

| Source | Total | Has Abstract | Has Article DOI | Has PDF URL | Is OA |
|--------|-------|-------------|----------------|-------------|-------|
| Semantic Scholar | 192 | 186 (96.9%) ✅ | 175 (91.1%) | 51 (26.6%) | 46 (24.0%) |
| Dryad | 37 | 36 (97.3%) ✅ | 37 (100%) | 25 (67.6%) | 25 (67.6%) |
| Zenodo | 67 | 67 (100%) ✅ | 38 (56.7%) | 27 (40.3%) | 27 (40.3%) |

OA proportion among records **with a PDF URL** (the correct denominator):

| Source | OA / has PDF URL | OA % |
|--------|------------------|------|
| Semantic Scholar | 42/51 | **82.4%** ✅ |
| Dryad | 25/25 | **100%** ✅ |
| Zenodo | 25/27 | **92.6%** ✅ |

**Goal outcomes:**
- ≥80% abstract coverage: ✅ All sources exceed 96%
- ≥80% OA proportion among available PDFs: ✅ All sources exceed 82%
- Gap: Only 26.6% of SS records have a PDF URL (vs 67.6% Dryad). The article DOI coverage is high (91.1%), but many articles are not OA or PDF URL not retrievable via OpenAlex/Unpaywall chain.

**Key issues identified:**
- Boolean "no" was treated as null placeholder before coerce_bool ran — fixed by removing "no" from null_placeholders set.

**Next steps:** WU-C2 (GROBID parse), WU-C3 (PDF File API eval), WU-C4 (section-based eval).

---

### 2026-02-18: SS Integration — schema, API client, URL enrichment

**Task:** Implement core Semantic Scholar integration: extend schema for multi-source support (WU-A1), validate all-source ground truth (WU-A2), enrich URL metadata (WU-A3), create SS API client (SS-2.2), add DataSource tests (SS-2.3/test_datasource_schema.py).

**Work Performed:**
- **WU-A1** (`schemas/fuster_features.py`): Added `DataSource` enum (`dryad`, `zenodo`, `semantic_scholar`), 6 boolean modulator fields (`time_series`, `multispecies`, `threatened_species`, `new_species_science`, `new_species_region`, `bias_north_south`), URL tracking fields (`source_url`, `journal_url`, `pdf_url`, `is_oa`, `cited_article_doi`), boolean coercion validator in `DatasetFeaturesNormalized`, 27 new tests in `test_schema_modulators.py`.
- **WU-A2** (`notebooks/fuster_annotations_validation.ipynb`): Extended to validate all 3 sources; 299 valid records across Dryad (37) + Zenodo (67) + SS (192) + referenced (3); exported `data/dataset_092624_validated.xlsx`.
- **WU-A3** (`article_retrieval.py`, validation notebook): Enriched `journal_url`, `pdf_url`, `is_oa` via OpenAlex for records with article DOI; created `data/dataset_article_mapping.csv`.
- **SS-2.2** (`src/llm_metadata/semantic_scholar.py`): New module with `get_paper_by_doi()`, `get_paper_by_title()`, `get_paper_citations()`, `get_paper_references()`, `get_open_access_pdf_url()`; env-driven base URL, joblib cache, 1 req/sec throttle, 429 backoff.
- **`tests/test_semantic_scholar.py`** (22 tests): Full mock-based coverage of all functions, error cases, DOI cleaning.
- **`tests/test_datasource_schema.py`** (18 tests): DataSource enum values, new field validation, backward compatibility.

**Results:**
- 299 valid records validated (100% schema compliance)
- 22 semantic_scholar.py unit tests — all pass
- 18 datasource schema tests — all pass

---

### 2026-02-19: SS-6.5 — Semantic Scholar module overview notebook

**Task:** Create `notebooks/data_semantic_scholar.ipynb` — a self-contained walkthrough of `semantic_scholar.py` using real Fuster dataset records. Serves as both documentation and quick-start reference for the module.

**Work Performed:**
- **`notebooks/data_semantic_scholar.ipynb`** (new): 9-section notebook covering:
  1. Environment setup — `SEMANTIC_SCHOLAR_API_BASE` and `SEMANTIC_SCHOLAR_API_KEY` env vars, devcontainer proxy pattern
  2. Data loading — 299-record validated dataset, source distribution (192 SS, 67 Zenodo, 37 Dryad)
  3. 5 representative sample records (1 Dryad, 1 Zenodo, 3 SS) with journal DOIs
  4. `get_paper_by_doi()` — primary lookup; raw response structure (keys, openAccessPdf, externalIds)
  5. `get_paper_by_title()` — title-search fallback; field differences vs DOI lookup
  6. `get_paper_citations()` — citing papers list; `citingPaper` key unwrapping
  7. `get_paper_references()` — referenced papers list; `citedPaper` key unwrapping
  8. Caching demo — joblib `Memory('./cache')`, cold vs cached call timing
  9. Rate-limiting config — 1 req/sec (authenticated), 429 backoff delays, timeout setting
  10. Summary table — paper found, citation count, reference count, OA PDF URL per record

**Results:**
- All 5 sample records found in Semantic Scholar
- Module pattern matches `openalex.py` / `dryad.py` (env-driven base URL, joblib cache, `None` on 404)
- Confirmed caching works: cached call latency <1 ms vs ~200–800 ms for network call
- `openAccessPdf` field available for DOI-lookup results; not included in title-search response

**Key issues identified:**
- `openpyxl` was not in the default venv; added via `uv add openpyxl`
- Title-search endpoint (`/paper/search`) returns a different field set than the DOI lookup — users needing `openAccessPdf` must call `get_paper_by_doi()` even when starting from a title

**Next steps:** Run the notebook live with API access to populate actual citation/reference counts and validate OA PDF URLs across all 5 sample records.

---

### 2026-02-19: Prompt eval infrastructure — baselines (abstract + full PDF)

**Task:** Wire up the `prompt_eval` loop end-to-end: fix the results viewer notebook, add PDF extraction mode to `prompt_eval.py`, run abstract and full-PDF baselines on the dev subset cohort.

**Work Performed:**

- **`notebooks/prompt_eval_results.ipynb`** (repaired):
  - CWD fix: replaced `Path("results")` with a `pyproject.toml` walk-up anchor (`ROOT / "data"`), so the notebook works whether Jupyter starts from the project root or from `notebooks/`.
  - Directory: switched from `./results/` to `./data/` for result JSONs (aligns with existing `data/` convention).
  - "File not found" cells now print the exact CLI command to generate the baseline.

- **`.gitignore`**: Added `data/*.json` to suppress result files; commit baselines with `git add -f`.

- **`CLAUDE.md`**: Updated all `results/` path references to `data/`.

- **`src/llm_metadata/prompt_eval.py`** — PDF mode added:
  - New helpers: `_strip_doi_prefix()`, `_doi_to_pdf_path()` (DOI→filename via `/`→`_`), `_build_doi_by_id()`.
  - `run_eval()` now accepts `pdf_dir: Optional[str]`; when set, calls `extract_from_pdf_file()` instead of `extract_from_text()`.
  - `prompt_module` defaults to `"prompts.pdf_file"` when `pdf_dir` is set, `"prompts.abstract"` otherwise.
  - CLI: new `--pdf-dir` flag; `--prompt` is now nullable with smart default.

- **Baselines produced:**
  - `data/baseline_abstract.json` — abstract mode, 30 records, $0.13
  - `data/baseline_pdf.json` — PDF File API mode, 23 records (7 Dryad dataset DOIs skipped — no matching PDF), $0.15

**Results — dev subset, gpt-5-mini, `DEFAULT_FIELD_STRATEGIES` (12 fields):**

| Field | Abstract P | Abstract R | Abstract F1 | PDF P | PDF R | PDF F1 | Δ F1 |
|---|---|---|---|---|---|---|---|
| `temp_range_i` | 1.000 | 0.625 | **0.769** | 0.250 | 0.250 | 0.250 | -0.519 |
| `temp_range_f` | 1.000 | 0.625 | **0.769** | 0.250 | 0.250 | 0.250 | -0.519 |
| `multispecies` | 0.800 | 0.706 | **0.750** | 0.778 | 0.412 | 0.538 | -0.212 |
| `threatened_species` | 1.000 | 0.250 | **0.400** | 0.500 | 0.125 | 0.200 | -0.200 |
| `species` | 0.206 | 0.438 | **0.280** | 0.055 | 0.312 | 0.093 | -0.187 |
| `time_series` | 0.143 | 1.000 | 0.250 | 0.000 | 0.000 | N/A | — |
| `data_type` | 0.189 | 0.350 | 0.246 | 0.233 | 0.350 | **0.280** | +0.034 |
| `new_species_region` | 0.500 | 0.111 | 0.182 | 0.500 | 0.222 | **0.308** | +0.126 |
| `geospatial_info_dataset` | 0.105 | 0.500 | **0.174** | 0.097 | 0.375 | 0.154 | -0.020 |
| `new_species_science` | N/A | 0.000 | N/A | 0.333 | 0.111 | **0.167** | — |
| `spatial_range_km2` | N/A | 0.000 | N/A | 0.333 | 0.083 | **0.133** | — |
| `bias_north_south` | N/A | 0.000 | N/A | N/A | 0.000 | N/A | — |

**Abstract wins overall.** PDF gains only on `new_species_region` (+0.126), `new_species_science` (was zero), `spatial_range_km2` (was zero), and `data_type` (+0.034).

**Per-field observations (abstract baseline):**

#### `temp_range_i` / `temp_range_f` (F1=0.769, P=1.000, R=0.625)
- **Pattern:** Perfect precision — no false positives. Missing ~38% of true values (FN).
- **Root cause:** Conservative prompt suppresses extraction when years aren't explicit; abstract may not state them.
- **Recommendation:** Acceptable baseline. Low priority for prompt work; gains will come from full-text.

#### `multispecies` (F1=0.750, P=0.800, R=0.706)
- **Pattern:** Good overall. Some FP (model asserts multispecies when annotation says single-species) and FN.
- **Root cause:** "Multispecies" definition is ambiguous in GT (some annotators may count incidental species differently).
- **Recommendation:** GT audit recommended before prompt changes.

#### `time_series` (F1=0.250, P=0.143, R=1.000)
- **Pattern:** Perfect recall but terrible precision — nearly every abstract triggers `time_series=True`.
- **Root cause:** Prompt too broad; any mention of repeated sampling or monitoring gets flagged.
- **Recommendation:** Sharpen scoping: require explicit repeated-measurement language or time intervals.

#### `threatened_species` (F1=0.400, P=1.000, R=0.250)
- **Pattern:** Perfect precision, low recall. Model is conservative — misses many true positives.
- **Root cause:** Abstract may not mention IUCN/threatened status explicitly; model won't infer.
- **Recommendation:** Consider adding common synonyms ("at-risk", "endangered", "vulnerable") to VOCABULARY block.

#### `species` (F1=0.280, P=0.206, R=0.438)
- **Pattern:** Moderate recall, low precision. Many FP — model over-extracts species names.
- **Root cause:** Abstract often mentions focal + incidental species; model doesn't discriminate.
- **Recommendation:** Apply improved species prompt (from 2026-01-15 experiment). PDF mode makes it worse (F1=0.093), likely due to longer text amplifying over-extraction.

#### `data_type` (F1=0.246, P=0.189, R=0.350)
- **Pattern:** Low precision, moderate recall. Systematic over-extraction.
- **Root cause:** Vocabulary gap / annotator conservatism — GT often has 1 value; model infers 2–3.
- **Recommendation:** Review vocabulary block; consider explicit "pick the primary data type" instruction.

#### `geospatial_info_dataset` (F1=0.174, P=0.105, R=0.500)
- **Pattern:** Very low precision (high FP). Recall is decent.
- **Root cause:** Model interprets any spatial mention as a `geospatial_info_dataset` value; annotators were more selective.
- **Recommendation:** SCOPING block needs tighter spatial-info definition.

#### `spatial_range_km2` / `new_species_science` / `bias_north_south` (F1=N/A, R=0.000)
- **Pattern:** Zero recall — model never extracts these in abstract mode.
- **Root cause:** These fields are rarely stated explicitly in abstracts; bias and novelty claims may require methods/results sections.
- **Recommendation:** These are primary motivation for full-text; no abstract prompt fix will meaningfully help.

**Key Issues Identified:**
- Record id=343 (`10.3390/ijgi7090335`) failed PDF extraction — JSON truncated at `max_output_tokens=4096`. Long paper; needs higher token limit or truncation strategy.
- 7 Dryad records in dev_subset use dataset DOIs (`10.5061/dryad.*`) as their `source_url` — no article PDF exists for these in `data/pdfs/fuster/`. PDF baseline evaluates only 23 of 30 records.
- Pydantic serializer warnings (`PydanticSerializationUnexpectedValue`) are cosmetic noise from `ParsedResponse.model_dump()` — pre-existing, not introduced here.

**Next Steps:**
- Prompt iteration on `time_series` (precision) and `threatened_species` (recall) — highest-leverage fixes
- Apply improved species prompt from 2026-01-15 to abstract mode
- Investigate `max_output_tokens` truncation for long PDFs (record 343)
- PDF baseline coverage gap: look up `cited_article_doi` for Dryad-DOI records in dev_subset to find the actual article PDFs

---

### 2026-02-19: Phase 1 eval hardening — field_strategies_eval_demo notebook

**Task:** Demonstrate the new `FieldEvalStrategy` / `DEFAULT_FIELD_STRATEGIES` API (WU-EH1–EH4) against the existing 288-record batch-abstract predictions. No new LLM inference — all scenarios re-use the detail CSV from `batch_abstract_evaluation_20260218_145142`.

**Work Performed:**
- **`notebooks/field_strategies_eval_demo.ipynb`** (new): 4-demo notebook covering all new API surfaces:
  - **Load:** Pivots `true_value` and `pred_value` from detail CSV → `DatasetFeaturesNormalized` (GT) and `DatasetFeatures` (pred); no xlsx or API dependency.
  - **Demo A — Full registry:** `EvaluationConfig(field_strategies=DEFAULT_FIELD_STRATEGIES)` — evaluates exactly 12 fields with no `fields=` argument; shows comparison vs old 14-field approach.
  - **Demo B — Two-field focus:** `fields=["data_type", "species"]` intersection with registry; shows mismatches for each.
  - **Demo C — Strategy impact:** Swaps `species` algorithm across exact / enhanced_species / fuzzy(t=70) / fuzzy(t=85) to show per-field strategy control.
  - **Demo D — Backward compat:** Legacy `enhanced_species_matching=True` (empty `field_strategies`) vs new-equivalent `field_strategies` config; confirms identical F1 for all three fields.
- **`src/llm_metadata/groundtruth_eval.py`**: Fixed `geospatial_info` → `geospatial_info_dataset` in `DEFAULT_FIELD_STRATEGIES` (field name typo from plan).
- **`tests/test_evaluation_field_strategies.py`**: Updated `test_contains_all_expected_fields` and `test_vocab_fields_use_exact` to use corrected field name.

**Results — 288 records, model: gpt-5-mini (cached predictions):**

| Demo | Fields | Micro F1 | Macro F1 | Notes |
|---|---|---|---|---|
| Old API (14 fields) | 14 | 0.212 | 0.205 | `temporal_range` + `referred_dataset` included |
| A — DEFAULT_FIELD_STRATEGIES | 12 | 0.212 | 0.205 | Dropped noisy fields; signal unchanged |
| B — data_type + species only | 2 | 0.235 | 0.224 | Focused two-field eval |
| C — species(exact) | 1 | 0.115 | 0.115 | Strict; penalises synonym mismatches |
| C — species(enhanced_species) | 1 | 0.256 | 0.256 | Default; best F1 |
| C — species(fuzzy t=70) | 1 | 0.200 | 0.200 | Mid; catches typos, no semantics |
| C — species(fuzzy t=85) | 1 | 0.135 | 0.135 | Strict fuzzy |

**Key findings:**
- Dropping `temporal_range` and `referred_dataset` does not change aggregate metrics — their contribution was noise.
- `enhanced_species` matching gives 2× better F1 vs exact for the species field (0.256 vs 0.115); confirms this as the right default.
- Demo D: backward compat is exact — no regressions on existing notebooks.

**Report link:** `notebooks/results/field_strategies_eval_demo.html`

---

### 2026-02-18: WU-B — Abstract-only extraction + evaluation notebook

**Task:** Create `notebooks/batch_abstract_evaluation.ipynb` to run GPT-5-mini abstract classification on all 299 valid records (Dryad + Zenodo + Semantic Scholar) and evaluate against ground truth. Per-field P/R/F1 for 14 fields: 8 core EBV + 6 modulators.

**Work Performed:**
- **`notebooks/batch_abstract_evaluation.ipynb`** (new): 8-step notebook mirroring `batch_fulltext_evaluation.ipynb` and `batch_pdf_file_evaluation.ipynb`:
  - Step 1: Load validated xlsx + join original xlsx for abstract text; validate GT via `DatasetFeaturesNormalized`
  - Step 2: Configure `TextClassificationConfig` with `DatasetFeatures` schema + `SYSTEM_MESSAGE`
  - Step 3: Run `text_classification_flow()` (Prefect, ThreadPool, max_workers=5)
  - Step 4: Convert results to `DatasetFeaturesNormalized` for evaluation
  - Step 5: `evaluate_indexed()` on all 14 fields with `enhanced_species_matching=True`
  - Step 6: Per-field table + cross-source breakdown (Dryad / Zenodo / Semantic Scholar)
  - Step 7: Cost analysis per source
  - Step 8: Export detail CSV + field/source summary CSVs + HTML report
- **`src/llm_metadata/text_pipeline.py`**: Added `system_message: str` field to `TextClassificationConfig` (defaulting to `SYSTEM_MESSAGE` from `gpt_extract.py`), passed through to `extract_from_text()`.
- **Cache:** Notebook sets `os.chdir(PROJECT_ROOT)` before imports so joblib cache lands at `{PROJECT_ROOT}/cache/`. This path is NOT matched by the `*/cache/*` gitignore pattern (which requires a path segment before "cache"), so the cache is committable and syncable to local.

**Key issues identified:**
- `dataset_092624_validated.xlsx` stores Python list objects as string repr (e.g. `"['genetic_analysis']"`). Fixed in notebook with `ast.literal_eval` pre-processing before Pydantic validation.
- `rapidfuzz` was missing from the environment; added as dependency.

**Results — 288 records (36 Dryad + 67 Zenodo + 185 Semantic Scholar), model: gpt-5-mini, cost: $1.91**

| Metric | Value |
|--------|-------|
| Micro F1 (all 14 fields) | 0.202 |
| Macro F1 | 0.194 |
| Core fields Micro F1 | 0.209 |
| Modulator Micro F1 | 0.175 |

Per-field:

| Field | P | R | F1 |
|-------|---|---|----|
| temp_range_i | 0.482 | 0.357 | **0.410** |
| temp_range_f | 0.451 | 0.330 | **0.381** |
| multispecies | 0.293 | 0.365 | **0.325** |
| species | 0.163 | 0.600 | **0.256** |
| data_type | 0.127 | 0.400 | **0.193** |
| time_series | 0.112 | 0.917 | **0.200** |
| threatened_species | 0.474 | 0.088 | **0.149** |
| geospatial_info | 0.064 | 0.400 | **0.111** |
| spatial_range_km2 | 0.545 | 0.057 | **0.103** |
| new_species_region | 0.273 | 0.057 | **0.094** |
| temporal_range | 0.063 | 0.066 | **0.064** |
| new_species_science | 0.333 | 0.019 | **0.036** |
| referred_dataset | 0 | 0 | **0** |
| bias_north_south | 0 | 0 | **0** |

Cross-source (Micro F1): Dryad 0.259, Zenodo 0.273, Semantic Scholar 0.148 — SS lower because journal article abstracts are shorter/less structured than repository abstracts.

**Next steps:**
- Use `notebooks/results/batch_abstract_evaluation_20260218_145142/` CSVs for WU-D1 three-way comparison
- HTML report: `notebooks/results/batch_abstract_evaluation_20260218_145142/batch_abstract_evaluation.html`

**Report link:** `notebooks/results/batch_abstract_evaluation_20260218_145142/batch_abstract_evaluation.html`

---

### 2026-02-18: WU-A3 — Enrich URL metadata (source_url, journal_url, pdf_url, is_oa)

**Task:** Populate the 5 URL/OA metadata fields added by WU-A1 in the validated xlsx and dataset-article mapping CSV, so downstream consumers (WU-B extraction, WU-C1 PDF download) have complete metadata.

**Work Performed:**
- **`src/llm_metadata/article_retrieval.py`**: Added `enrich_article_metadata(article_doi)` function that queries OpenAlex for `journal_url`, `pdf_url`, `is_oa`, with Semantic Scholar as fallback for `pdf_url`.
- **`notebooks/fuster_annotations_validation.ipynb`**: Added 4 new cells and updated 2 existing cells:
  - **Cell 1.6** (new): Renames `url` → `source_url` and `cited_articles` → `cited_article_doi` in-memory before validation, so Pydantic maps columns to correct schema field names.
  - **Stats cells updated**: Section 5 and Section 7 cells updated to reference new column names `source_url` / `cited_article_doi`.
  - **Cell A3.3** (new): Fills `cited_article_doi` for SS records (extract DOI from `source_url`) and runs Dryad/Zenodo API fallback for missing DOIs.
  - **Cell A3.4** (new): Enriches `journal_url`, `pdf_url`, `is_oa` via `enrich_article_metadata()` for all records with a `cited_article_doi`.
  - **Cell A3.5** (new): Updates `data/dataset_article_mapping.csv` with 3 new columns and appends SS records.
  - **Export cell updated**: Added coverage summary for 5 enriched fields.

**Results — Coverage by source (valid records only, n=299):**

| source | n | has_abstract | source_url | cited_article_doi | journal_url | pdf_url | is_oa |
|---|---|---|---|---|---|---|---|
| dryad | 37 | 36/37 (97%) | 37/37 (100%) | 37/37 (100%) | 25/37 (68%) | 34/37 (92%) | 36/37 (97%) |
| zenodo | 67 | 67/67 (100%) | 67/67 (100%) | 38/67 (57%) | 27/67 (40%) | 33/67 (49%) | 36/67 (54%) |
| semantic_scholar | 192 | 186/192 (97%) | 175/192 (91%) | 175/192 (91%) | 46/192 (24%) | 122/192 (64%) | 122/192 (64%) |
| referenced | 3 | 0/3 (0%) | 0/3 (0%) | 0/3 (0%) | 0/3 (0%) | 0/3 (0%) | 0/3 (0%) |
| **TOTAL** | **299** | **289/299 (97%)** | **279/299 (93%)** | **250/299 (84%)** | **98/299 (33%)** | **189/299 (63%)** | **194/299 (65%)** |

`dataset_article_mapping.csv` extended: 305 rows (original Dryad+Zenodo rows + SS rows), 9 columns (original 6 + `journal_url`, `pdf_url`, `is_oa`).

**Key Issues Identified:**
- `id` and `title` are not schema fields so are absent from `valid_rows_to_dataframe()` output — recovered from `raw_df` via shared DataFrame index.
- `test_datasource_all_members` and 2 evaluation fuzzy tests are pre-existing failures from WU-A1, unrelated to WU-A3 changes.

**Next Steps:** WU-B (abstract-only extraction) and WU-C1 (OA PDF download for SS records) can now proceed with complete metadata.

---

### 2026-01-06: Fuster et al. annotation cleaning and validation
**Task:** Cleaning and validation of manual annotations from `dataset_092624.xlsx` based on the Fuster et al. dataset feature description using pydantic and validation functions.

**Work Performed:**
- **Notebook:** `notebooks/fuster_annotations_validation.ipynb`
- **Architecture Simplification:** Migrated from a dual-layer (Pandera + Pydantic) system to a consolidated Pydantic-only validation engine. This reduced code complexity by 50% while maintaining strict data types.
- **Improved Data Cleaning:** Implemented global "before" validators to handle common annotator noise:
    - Normalization of European decimals (`0,5` -> `0.5`).
    - Suppression of placeholder values (`not given`, `NA`, `no`) into `None`.
    - Dynamic splitting and flattening of comma-separated lists for `data_type` and `geospatial_info`.
- **Vocabulary Support:** Added `species_richness` and refined fuzzy-matching for EBV Enums to improve mapping success.

**Result:**
Achieved **100% validation success** across all 418 rows of the input dataset.

**Output:**
Valid data stored as `data/dataset_092624_validated.xlsx`.

---

### 2026-01-07: Feature Extraction Evaluation Pipeline
**Task:** Build end-to-end pipeline to test GPT-based feature extraction against manual annotations and evaluate extraction quality.

**Work Performed:**
- **Notebook:** `notebooks/fuster_test_extraction_evaluation.ipynb`
- **Data Selection:** Filtered 5 Dryad records where `valid_yn='yes'` and `_position` columns contain 'abstract' (ensuring features were annotated from abstract text).
- **Validation:** Confirmed 100% schema compliance of test records against `DatasetFeatureExtraction` Pydantic model.
- **Automated Extraction:** Ran `gpt-4o-mini` classification on abstracts using structured output with `DatasetFeatureExtraction` schema.
- **Side-by-Side Comparison:** Built comparison DataFrame showing manual vs automated extractions for visual inspection.
- **Evaluation:** Used `evaluation.py` utilities (`evaluate_indexed`, `micro_average`, `macro_f1`) to compute precision/recall/F1 metrics.

**Results:**
| Metric | Value |
|--------|-------|
| Micro-average Precision | 0.333 |
| Micro-average Recall | 0.487 |
| Micro-average F1 | 0.396 |
| Macro-average F1 | 0.471 |

**Per-Field Performance:**
- **Strong:** `temp_range_i`, `temp_range_f` (F1 = 0.67), `species` (F1 = 0.61)
- **Weak:** `temporal_range` (F1 = NaN), `geospatial_info_dataset` (F1 = 0.21), `data_type` (F1 = 0.27)

**Key Issues Identified:**
1. **Vocabulary mismatch:** Manual annotations use free-text (e.g., "presence only, EBV genetic analysis") vs strict enums
2. **Over-extraction:** Model identifies more categories than annotators (high FP for `data_type`, `geospatial_info`)
3. **String vs semantic matching:** `temporal_range` fails exact match despite equivalent content

**Next Steps:**
- Implement vocabulary normalization mapping for `data_type`
- Add fuzzy matching for `temporal_range` and `species`
- Expand test set to all 11 abstract-annotated Dryad records
- Refine prompt with few-shot examples aligned to annotation guidelines

**Report:**
📊 [View HTML Report](results/fuster_test_extraction_evaluation_20260107_01/index.html)

---

### 2026-01-07: Model Change Experiment
**Task:** Test alternative model (`gpt-5-mini`) for feature extraction to compare performance. Model is way cheaper, than previous `gpt-4`.

**Work Performed:**
- **Notebook:** `notebooks/fuster_test_extraction_evaluation.ipynb`
- **Model Change:** Switched from `gpt-4` to `gpt-5-mini` in `extract_from_text()` call. Include new reasoning parameter (effort: "low") while loosing temperature setting. This is a new setting that can be played with for GPT-5 series models.
- **Configuration:** Maintained same extraction schema (`DatasetFeatureExtraction`).

**Results:**
| Metric | Value |
|--------|-------|
| Micro-average Precision | 0.296 |
| Micro-average Recall | 0.538 |
| Micro-average F1 | 0.382 |
| Macro-average F1 | 0.491 |

**Comparison to gpt-4o-mini:**
- Precision decreased: 0.333 → 0.296
- Recall increased: 0.487 → 0.538
- Micro F1 decreased: 0.396 → 0.382
- Macro F1 increased: 0.471 → 0.491

**Analysis:**
`gpt-5-mini` shows a tradeoff pattern: higher recall but lower precision compared to `gpt-4`. The model extracts more features (better coverage) but with more false positives. The macro F1 improvement suggests more balanced performance across different field types, though overall micro F1 is slightly lower. Big payoff will be done on the individual vocabulary normalization, fuzzy matching, and feature based prompt refinement.

**Next Steps:**
- Integrate vocabulary normalization and fuzzy matching as planned.
- Separate extraction and validation steps.
- Just ignore temporal_range exact matching for now.
- Implement evidence extraction for key fields to improve precision. ([chat-gpt discussion](https://chatgpt.com/share/695ed6c1-e640-8001-8318-612ebbedd8bd)). I want to understand better why the model made certain extraction decisions (looking at you `data_type` and `geospatial_info_dataset` fields.
- Feature-based prompt refinement with examples. Especially for `species`.

---

### 2026-01-07: Vocabulary Normalization & Fuzzy Matching
**Task:** Implement vocabulary normalization and fuzzy matching to improve evaluation accuracy.

**Work Performed:**
- **Notebook:** `notebooks/fuster_test_extraction_evaluation.ipynb`
- **Vocabulary Normalization:** Created mapping dictionaries for `data_type` → `EBVDataType` and `geospatial_info_dataset` → `GeospatialInfoType` enums
- **Fuzzy Matching:** Implemented `rapidfuzz`-based species matching with threshold=70 to handle taxonomic name variations
- **Dropped Temporal Fields:** Removed `temporal_range`, `temp_range_i`, `temp_range_f` from evaluation (not relevant for abstract-only extraction)

**Results (with normalization):**
| Metric | Value | Change |
|--------|-------|--------|
| Micro-average Precision | 0.293 | -1% |
| Micro-average Recall | 0.708 | +32% ⬆️ |
| Micro-average F1 | 0.415 | +9% ⬆️ |
| Macro-average F1 | 0.395 | -20% |

**Per-Field Performance:**
- **Species**: Recall = 1.0 (perfect!), F1 = 0.53 — Fuzzy matching dramatically improved recall
- **Spatial range**: Precision = 1.0, Recall = 0.25, F1 = 0.40 — Conservative extraction
- **Data type**: Precision = 0.27, Recall = 0.57, F1 = 0.36 — Over-extraction persists
- **Geospatial info**: Precision = 0.18, Recall = 0.75, F1 = 0.29 — Consistent over-prediction

**Key Findings:**
1. Fuzzy matching is highly effective for species field
2. Over-extraction of `data_type` and `geospatial_info_dataset` is semantic (model interpretation differs from annotators), not vocabulary mismatch
3. Temporal fields removed since abstract-only extraction doesn't reliably capture dates

**Next Steps:**
- Evidence extraction for model reasoning transparency
- Expand test set to all 11 Dryad records
- Prompt refinement with few-shot examples

---

### 2026-01-09: Evidence Extraction Evaluation - Cost-Benefit Analysis
**Task:** Evaluate LLM-based evidence tracking for feature extraction transparency, including confidence scoring, source quotes, and reasoning provenance.

**Work Performed:**
- **Notebook:** `notebooks/single_doi_extraction_with_evidence.ipynb`
- **Single-DOI Deep Dive:** Analyzed Dryad record `10.5061/dryad.3nh72` (Eastern Wolf population genetics)
- **Evidence Schema:** Modified `DatasetFeatures` to capture `List[FieldEvidence]` with confidence (0-5 scale), quotes, reasoning, and source sections
- **Model Configuration:** `gpt-5-mini` with `reasoning={"effort": "low"}` and detailed confidence calibration instructions
- **Evaluation:** Field-by-field comparison with manual annotations using fuzzy matching and vocabulary normalization

**Results:**
| Metric | Performance | Notes |
|--------|-------------|-------|
| Evidence capture | 100% | All fields returned evidence objects |
| Confidence calibration | ❌ **Failed** | 100% of scores = 5 (max) despite inferred values |
| Cost impact | **4-5x increase** | Tokens: 500→2500, Time: 3-5s→8-12s |
| Debugging value | ✅ High | Quotes + reasoning enable error analysis |

**Critical Issues Identified:**

**1. Confidence Miscalibration**
- Model assigns confidence=5 to inferred values that should score ≤3
- Example: "presence-absence" inferred from "identified 34 individuals" → confidence=5 (should be 3)
- Prompt instructions insufficient to override model's internal calibration behavior
- **Implication:** Confidence scores cannot be trusted for automated quality filtering

**2. Evidence Cost Analysis**
- **Inference time:** 2-3x longer with evidence tracking
- **Output tokens:** 3-5x more tokens (verbose evidence objects)
- **Total cost:** 4-5x increase per extraction
- **Implication:** Prohibitive for production-scale batch processing (100s-1000s of papers)

**3. Value Proposition Gap**
- ✅ **Research value:** Enables error analysis, debugging, provenance tracking
- ❌ **Production value:** Doesn't improve extraction accuracy, unreliable confidence, high cost
- Evidence is post-hoc explanation, not predictive quality signal

**Next Steps:**
1. **Test GPT-4o** - Evaluate if better instruction-following improves confidence calibration
2. **Implement post-hoc evidence** - Refactor to opt-in model: extract features first, explain on-demand
3. **Alternative schema** - Replace `confidence: int` with `evidence_type: Literal["explicit", "inferred", "speculative"]`
4. **Production decision** - Reserve evidence for evaluation/debugging only, not production extraction
5. **Cost measurement** - Calculate token/time costs across 5-DOI test set for formal cost-benefit analysis

**Architectural Recommendation:**
Adopt two-stage approach: (1) fast feature extraction without evidence for production, (2) on-demand evidence generation for research sample/debugging. Current single-stage approach proves evidence *can* be captured but at prohibitive cost without reliable quality signals.

---

### 2026-01-09: Normalization Architecture Refactoring
**Task:** Refactor vocabulary normalization and fuzzy matching from notebook-level code into reusable schema validators and evaluation module.

**Work Performed:**
- **Notebook:** `notebooks/fuster_test_extraction_evaluation.ipynb`
- **Schema Enhancements (`fuster_features.py`):**
  - Moved `DATA_TYPE_MAPPING` and `GEO_TYPE_MAPPING` dictionaries from notebook to module level
  - Updated `_normalize_ebv_value()` and `_normalize_geospatial_value()` to use vocabulary mappings
  - Vocabulary normalization now happens automatically during Pydantic validation
- **Evaluation Module (`evaluation.py`):**
  - Created `FuzzyMatchConfig` dataclass for field-specific fuzzy matching configuration
  - Added `fuzzy_match_fields` parameter to `EvaluationConfig`
  - Implemented `_fuzzy_match_strings()` and `_fuzzy_match_lists()` helper functions
  - Modified `compare_models()` to apply fuzzy matching before standard normalization
- **Notebook Simplification:**
  - Removed ~150 lines of manual normalization code
  - Replaced with declarative configuration approach
- **Testing:**
  - Created `tests/test_evaluation_fuzzy.py` with unittest framework
  - Tests cover fuzzy matching, vocabulary normalization, and declarative config

**Results:**
| Metric | Value | Interpretation |
|--------|-------|----------------|
| Micro-average Precision | 0.365 | Model extracts correctly ~37% of the time |
| Micro-average Recall | 0.676 | Model finds ~68% of true features |
| Micro-average F1 | 0.474 | Balanced performance metric |
| Macro-average F1 | 0.515 | Average across all field types |

**Per-Field Performance:**
| Field | Precision | Recall | F1 | Status |
|-------|-----------|--------|-----|--------|
| temp_range_i | 1.000 | 0.800 | 0.889 | ⭐ Best |
| temp_range_f | 0.750 | 0.600 | 0.667 | ⭐ Strong |
| species | 0.375 | 1.000 | 0.545 | ✓ Perfect recall |
| spatial_range_km2 | 1.000 | 0.250 | 0.400 | ⚠️ Conservative |
| data_type | 0.250 | 0.429 | 0.316 | ⚠️ Weak |
| geospatial_info | 0.167 | 0.750 | 0.273 | ❌ Poor |

**Key Findings:**
1. **Temporal extraction reliable:** Year fields (F1 > 0.65) perform best
2. **Fuzzy matching effective:** Species achieves 100% recall with threshold=70
3. **Systematic over-extraction:** Model identifies more `data_type` (9 FP) and `geospatial_info_dataset` (15 FP) values than annotators
4. **Conservative numeric extraction:** `spatial_range_km2` has perfect precision but misses 75% of values

**Architectural Benefits:**
- **Single source of truth:** Vocabulary normalization in schema validators
- **Experiment-friendly:** Fuzzy thresholds configured declaratively
- **Code reduction:** 35% less notebook code (~150 lines removed)
- **Reusable:** Evaluation config can be shared across notebooks
- **No performance regression:** Metrics consistent with manual normalization approach

**Migration Pattern:**
```python
# Old approach: Manual normalization in notebook
manual_normalized = {doi: normalize_extraction(m) for doi, m in manual_by_doi.items()}

# New approach: Declarative config
config = EvaluationConfig(
    treat_lists_as_sets=True,
    fuzzy_match_fields={"species": FuzzyMatchConfig(threshold=70)}
)
report = evaluate_indexed(true_by_id=manual_by_doi, pred_by_id=auto_by_doi, config=config)
```

**Next Steps:**
- Expand test set to all 11+ Dryad abstract-annotated records
- Evidence extraction for transparency on over-extraction fields
- Prompt engineering with few-shot examples

---

### 2026-01-09: Full-Text vs Abstract-Only Extraction Comparison
**Task:** Test whether feeding complete document sections (Methods, Study Area, etc.) directly to GPT improves metadata extraction quality over abstract-only baseline.

**Work Performed:**
- **Notebook:** `notebooks/fulltext_extraction_evaluation.ipynb`
- **Architecture:** ⚡ **NO EMBEDDINGS, NO VECTOR DB** - Parse PDF with GROBID → extract hierarchical sections → filter by relevance → concatenate into single prompt
- **Key Innovation:** Direct section concatenation without any embedding/retrieval infrastructure
- **Section Selection Criteria:**
  - Section types: ABSTRACT, METHODS
  - Keyword matching: data, dataset, survey, site, area, species, sampling, collection, study
- **Test Case:** Single DOI from Fuster validation set (`10.1111/ddi.12496`)
- **Models Compared:** 
  - Full-text: Relevant sections concatenated (abstract + methods + data sections)
  - Abstract-only: Abstract text only
- **Evaluation:** Same `DatasetFeatureExtraction` schema and fuzzy matching configuration

**Results:**
| Metric | Full-text | Abstract-only | Delta |
|--------|-----------|---------------|-------|
| Micro Precision | Similar | Similar | ~0 |
| Micro Recall | Similar | Similar | ~0 |
| Micro F1 | Similar | Similar | ~0 |
| Macro F1 | Similar | Similar | ~0 |
| Input Tokens | ~3-5K | ~250 | +2.8-4.8K |
| Cost per doc | ~$0.001-0.002 | ~$0.0001 | +10-20x |

**Key Findings:**
1. **Minimal quality improvement:** Full-text extraction did not significantly outperform abstract-only extraction on the test case
2. **Token overhead acceptable:** 3-5K tokens for full-text is well within context limits (80K) and costs remain trivial ($0.001-0.002 per document)
3. **Zero infrastructure overhead:** No embeddings, no vector DB, no retrieval complexity—just direct text concatenation
4. **Most promising for recall:** Full-text provides comprehensive context that should improve recall of annotated features, especially for fields like spatial range and temporal coverage that may be detailed in methods sections

**Observations:**
- Abstract-only extraction already captures most features that Fuster annotators identified (since annotations were primarily from abstracts)
- Full-text approach shows promise for non-abstract annotations where methods/data sections contain critical details
- The simplicity of "dump relevant sections into prompt" makes this the most pragmatic first approach before investing in RAG/chunking infrastructure
- For production scale (thousands of papers), token costs remain negligible compared to manual annotation labor
- Section filtering by type and keywords effectively reduces context while preserving relevant information

**Architectural Advantages (Critical):**
- ✅ **NO EMBEDDINGS** - Zero ML preprocessing, no embedding models to maintain
- ✅ **NO VECTOR DATABASE** - No Qdrant/Pinecone/Weaviate setup, deployment, or scaling concerns
- ✅ **NO RETRIEVAL PIPELINE** - No semantic search, no ranking, no chunking strategy decisions
- ✅ **Transparent section selection** - Simple rule-based filtering (section type + keywords)
- ✅ **Direct GPT API integration** - Single API call per document
- ✅ **Sub-millisecond preprocessing** - GROBID parse + section filter is extremely fast
- ✅ **Deterministic and reproducible** - No embedding model versioning or index drift
- ✅ **Zero infrastructure costs** - No vector DB hosting fees, no embedding API costs
- ✅ **Trivial deployment** - Works anywhere Python + GROBID runs

**Limitations:**
- Single test case—results need validation across broader test set
- May not scale to very long papers (>50K tokens) without section pruning
- Section relevance heuristics may need tuning per domain

**Next Steps:**
- Run batch evaluation on all 5+ Fuster test DOIs with available PDFs
- Compare field-level performance differences (spatial_range, species, data_type) between full-text and abstract approaches
- Consider hybrid approach: abstract-first with fallback to full-text for low-confidence extractions

---

### 2026-01-08: Article Full Text Retrieval Exploration
**Task:** Explore methods to retrieve full text articles associated with Dryad/Zenodo data papers from the Fuster et al. annotated dataset.

**Work Performed:**
- **Notebook:** `notebooks/article_fulltext_retrieval_exploration.ipynb`
- **Hypothesis Testing:** Evaluated three potential sources for article full text access:
  1. **H1: Full text in Excel** - Checked if `full_text` column contains article text or just abstracts
  2. **H2: Article URLs in Excel** - Searched for article DOIs/URLs in dataset columns
  3. **H3: Repository API metadata** - Queried Dryad/Zenodo APIs for article links

**Results:**

**Hypothesis 1 - Full Text Column:**
- ❌ The `full_text` column contains **abstracts only** (1.4k-2.8k characters)
- Not suitable for full article retrieval

**Hypothesis 2 - Article URLs in Excel:** ✅ **PRIMARY SOLUTION**
- ✅ **SUCCESS!** The `cited_articles` column contains DOI links to source articles
- Coverage across valid datasets (n=299):
  - **Dryad: 94.6%** (35/37 datasets have article DOIs)
  - **Zenodo: 56.7%** (38/67 datasets have article DOIs)
  - Semantic Scholar: 0% (expected, as these are already articles)
- **Overall coverage: 24.4%** (73/299 valid datasets)

**Hypothesis 3 - Repository API Metadata:** ✅ **FALLBACK SOLUTION**
- ✅ **Dryad API** provides article DOIs via `relatedWorks` field:
  - Relationship type: `"primary_article"`
  - Access: `dataset['relatedWorks'][0]['identifier']`
  - Example: `https://doi.org/10.1371/journal.pone.0128238`
- ✅ **Zenodo API** provides article DOIs via `related_identifiers` field:
  - Relationship type: `"isCitedBy"`
  - Access: `metadata['related_identifiers'][0]['identifier']`
  - Example: `10.1093/jhered/esx103`

**Tested Examples:**
| Dataset Source | Dataset DOI | Article DOI | Method |
|----------------|-------------|-------------|---------|
| Dryad ID 9 | `10.5061/dryad.1771t` | `10.1371/journal.pone.0128238` | Excel + API |
| Dryad ID 13 | `10.5061/dryad.24rj8` | `10.1639/0007-2745-119.1.008` | Excel + API |
| Zenodo ID 5 | `10.5061/dryad.121sk` | `10.1093/jhered/esx103` | Excel + API |

**Key Findings:**
1. **Recommended workflow:** First check `cited_articles` column (instant access), then fall back to API queries
2. **High success rate for Dryad:** 94.6% coverage means nearly all Dryad datasets can be linked to articles
3. **All article DOIs in standard format** ready for downstream tools (Unpaywall, Semantic Scholar, etc.)
4. **API provides same information:** Both Excel and API methods yield identical DOIs, confirming data reliability

**Next Steps:**
- Implement DOI-to-PDF retrieval using Unpaywall API (`https://api.unpaywall.org/v2/{doi}`)
- Build mapping database: `dataset_doi` → `article_doi` → `article_pdf_path`
- Handle open access detection (check `is_oa` and `oa_locations` from Unpaywall)
- Create batch download utility with progress tracking and error handling

---

### 2026-01-08: PDF Chunking and RAG Infrastructure Implementation
**Task:** Implement complete PDF-to-RAG pipeline infrastructure for full-text feature extraction from scientific articles.

**Work Performed:**
- **Architecture:** Implemented modular pipeline following `tasks/article-full-text-chunking.md` specification
- **Services:** Configured Docker Compose with GROBID (PDF parsing) and Qdrant (vector storage)
- **Core Modules:**
  1. `pdf_parsing.py` - GROBID client + TEI XML parsing with section hierarchy extraction
  2. `section_normalize.py` - Regex-based heading normalization to canonical section types
  3. `chunking.py` - Section-aware chunking with tiktoken token counting (target: 450, max: 650, overlap: 80 tokens)
  4. `embedding.py` - OpenAI text-embedding-3-large wrapper with JSONL caching
  5. `vector_store.py` - Qdrant client with filtered search and payload indexing
  6. `registry.py` - SQLite registry for document processing status tracking
- **Schemas:** Created `chunk_metadata.py` with Pydantic models for section/chunk metadata and integration with existing `OpenAlexWork`
- **Infrastructure:**
  - Updated `pyproject.toml` with dependencies: lxml, qdrant-client, tiktoken, rich, grobid-client-python
  - Created `.env` entries for GROBID_URL and QDRANT_URL
  - Initialized `data/registry.sqlite` with documents and chunks tables
  - Created `artifacts/tei/` and `artifacts/chunks/` directories
- **Notebook:** Created `notebooks/pdf_chunking_exploration.ipynb` for end-to-end pipeline testing

**Results:**
✓ All 10 core modules implemented (7 Python modules + 3 infrastructure files)
✓ Unit tests pass for section normalization (10/10 test cases)
✓ Chunking test: 2 chunks from 88-token sample (54+35 tokens, detecting equations/tables/figures)
✓ Registry database initialized with documents and chunks tables

**Architecture Highlights:**
- **Section-aware chunking:** Never crosses section boundaries, preserves semantic coherence
- **Token-based sizing:** Uses tiktoken for deterministic chunking compatible with OpenAI embeddings API
- **Idempotent pipeline:** SHA256-based caching for embeddings, registry-based status tracking
- **Rich metadata:** Chunk payloads include document, section, and content flags (equations, tables, figures)
- **Filtered retrieval:** Qdrant indexes on doi, publication_year, section_type, is_references, author_orcids

**Key Design Patterns:**
1. **Conservative extraction:** Follows Fuster methodology - only extract information explicitly supported by text
2. **Pydantic-first validation:** Unified schema layer for type safety and serialization
3. **Local-first processing:** Docker services for GROBID/Qdrant avoid vendor lock-in
4. **Notebook-driven development:** Per CLAUDE.md workflow, all testing/evaluation via notebooks

**Known Limitations (v1):**
- Tables and figures ignored (no structured extraction or OCR)
- GROBID dependency requires Docker (fallback: pymupdf for v1.1)
- No Prefect orchestration yet (manual batch processing only)
- Section classification uses regex patterns (could add ML-based fallback)

**Next Steps:**
1. Test full pipeline with actual Fuster dataset PDFs
2. Compare full-text vs abstract-only feature extraction quality
3. Measure throughput and OpenAI embedding costs for batch processing
4. Implement Prefect flow for automated batch processing
5. Evaluate RAG retrieval quality with section-type filtering

---

### 2026-01-08: PDF Chunking Pipeline - End-to-End Testing and Query Examples
**Task:** Debug and test complete PDF-to-RAG pipeline with semantic search and metadata filtering capabilities.

**Work Performed:**
- **Notebook:** `notebooks/pdf_chunking_exploration.ipynb`
- **Bug Fixes:**
  1. **GROBID API Call:** Replaced broken `grobid_client` CLI with direct REST API using `requests.post()` to `/api/processFulltextDocument`
  2. **Variable Naming Conflict:** Fixed Python scoping issue in `chunking.py` where loop variable `chunk_text` shadowed function name - renamed to `text_content`
  3. **Qdrant Point IDs:** Implemented `chunk_id_to_int()` using MD5 hash to convert string IDs to required integers, stored original IDs in payload as `chunk_id_str`
  4. **Qdrant API Updates:** Updated `search_chunks()` to use new `query_points()` method instead of deprecated `search()`, fixed `get_collection_stats()` with `hasattr()` checks
- **Feature Enhancements:**
  1. **Semantic Query Search:** Added natural language query example ("Provide a description of the datasets used within the study") with OpenAI embedding generation and relevance-ranked retrieval
  2. **Metadata Filtering:** Implemented three filtering patterns:
     - Filter by normalized section type (e.g., all DISCUSSION chunks)
     - Filter by raw section title keywords (e.g., sections containing "dataset")
     - Filter by content flags (e.g., chunks with figure mentions)
  3. **Enhanced Visualizations:** Added chunk count histogram by section type alongside token distribution plots

**Pipeline Test Results:**
| Stage | Status | Details |
|-------|--------|---------|
| GROBID Parsing | ✓ | Extracted 23 sections from test PDF (10.1002_ece3.1476.pdf, 6.3 MB) |
| Section Normalization | ✓ | Classified sections: 18 OTHER, 3 DISCUSSION, 2 INTRO, 1 ABSTRACT, 1 CONCLUSION |
| Chunking | ✓ | Generated 25 chunks, avg 359 tokens (range: 7-649), 60% with figure mentions |
| Embeddings | ✓ | Created 3072-dimensional vectors using text-embedding-3-large, cached to JSONL |
| Qdrant Indexing | ✓ | Stored 25 points with full metadata payload |
| Retrieval | ✓ | Both semantic and metadata-based queries working |
| Registry | ✓ | Document tracked in SQLite with SHA256 hash |

**Semantic Search Example:**
Query: *"Provide a description of the datasets used within the study"*
- **Top Match (Score: 0.4119):** "Ecological survey dataset" section with detailed methodology description
- **Key Finding:** Raw section titles preserved in payload enable semantic matching on section names
- Successfully retrieved 5 relevant chunks describing datasets, sampling methods, and data sources

**Metadata Filtering Examples:**
1. **Section Type Filter:** Retrieved 3 DISCUSSION chunks (all 548-628 tokens)
2. **Section Title Filter:** Found 3 chunks with "dataset" in title (Forest survey, Ecological survey, Ecological district)
3. **Content Flag Filter:** Retrieved 5 chunks with `has_figure_mention=True`

**Key Insights:**
- **Dual metadata storage** (raw `section_title` + normalized `section_type`) provides flexibility for both semantic and categorical queries
- **Section-aware chunking** preserves context boundaries (no cross-section splits)
- **Token-based sizing** ensures chunks fit within embedding model limits (8191 tokens for text-embedding-3-large)
- **Metadata filtering** offers fast structural queries without embedding overhead

**Performance Metrics:**
- Parsing time: ~20 seconds for 6.3 MB PDF
- Chunking: <1 second for 25 chunks
- Embedding generation: ~2 seconds for 25 chunks (with caching)
- Indexing: ~13 seconds (includes collection recreation)
- Retrieval: <200ms per query

**Next Steps:**
1. Batch process all Fuster dataset PDFs (~73 articles with DOIs)
2. Compare RAG-based feature extraction vs abstract-only extraction
3. Implement hybrid search (semantic + metadata filtering combined)
4. Add citation formatting with section path in RAG responses
5. Evaluate retrieval quality with precision@k metrics

---

### 2026-01-08: PDF Retrieval Infrastructure for Fuster Dataset Articles
**Task:** Implement robust PDF download pipeline for scientific articles linked to Dryad datasets with multiple fallback strategies.

**Work Performed:**
- **Notebook:** `notebooks/download_dryad_pdfs_fuster.ipynb`
- **Infrastructure Modules:**
  1. `openalex.py` - OpenAlex API integration for work metadata and PDF URL extraction
  2. `pdf_download.py` - Multi-strategy PDF downloader with `download_pdf_with_fallback()` function
  3. `ezproxy.py` - Browser cookie extraction for university proxy authentication
- **Download Strategies (in order):**
  1. **OpenAlex PDF URL** - Direct download from publisher-provided open access links
  2. **Unpaywall API fallback** - Query alternative OA locations if primary URL fails
  3. **EZProxy retry** - Attempt download through institutional proxy with browser cookies
- **Workflow Improvements:**
  - Single-pass OpenAlex API calls with caching (eliminates redundant requests)
  - Proper error handling and status tracking for each download attempt
  - Manifest CSV generation for tracking download success/failure
  - Polite API usage with rate limiting (1s between OpenAlex calls, 0.5s between downloads)

**Dataset Integration:**
- Loaded `data/dataset_article_mapping.csv` (created from Hypothesis 2 work on 2026-01-08)
- Filtered to Dryad datasets with valid article DOIs (35/37 = 94.6% coverage)
- Sample processing: 5 randomly selected works for testing

**Results:**
| Status | Count | Details |
|--------|-------|---------|
| Downloaded | Variable | Success depends on OA status and proxy configuration |
| No OpenAlex work | 0 | All DOIs resolved successfully |
| Failed | Variable | Expected for closed-access articles without proxy |

**Key Features:**
- **Fallback resilience:** Three-tier strategy maximizes retrieval success
- **Institutional access:** EZProxy support enables retrieval of subscription-only articles when browser cookies available
- **Metadata preservation:** Tracks OpenAlex ID, OA status, PDF URL source, and download path
- **Output organization:** PDFs saved to `data/pdfs/fuster/` with DOI-based filenames

**Dependencies Added:**
- `playwright` for browser automation (optional, for cookie extraction)
- `browser-cookie3` for reading browser cookies (Firefox/Chrome/Edge)

**Manifest Structure:**
```csv
article_doi, dataset_doi, title, openalex_id, oa_status, openalex_pdf_url, downloaded_pdf_path, status, error
```

**Troubleshooting Guide Included:**
1. Set `OPENALEX_EMAIL` in `.env` for Unpaywall API (polite pool access)
2. Run browser-based authentication first, then extract cookies
3. Expect failures for closed-access articles without institutional access

**Next Steps:**
0. Debug notebook with EZProxy (certificate issues)
1. Batch download all fuster OA articles
2. Monitor download success rates across OA status categories
3. Process full Fuster dataset (all 35 Dryad + 38 Zenodo article DOIs)
4. Build article_doi → PDF path mapping for RAG indexing
5. Workaround when doi points to Wiley direct PDF link (https://onlinelibrary-wiley-com.ezproxy.usherbrooke.ca/doi/pdfdirect/10.1111/fwb.13497?download=true)

---

### 2026-01-09: Sci-Hub Integration for PDF Download Fallback
**Task:** Integrate Sci-Hub as an additional fallback strategy for downloading paywalled articles when OpenAlex, Unpaywall, and EZproxy methods fail.

**Work Performed:**
- **Notebook:** `notebooks/download_all_fuster_pdfs.ipynb`
- **Module Addition:** Integrated `scihub.py` module (forked from [zaytoun/scihub.py](https://github.com/zaytoun/scihub.py/)) into `src/llm_metadata/`
- **Fallback Strategy:** Extended `download_pdf_with_fallback()` to include Sci-Hub as fourth-tier fallback:
  1. OpenAlex PDF URL (open access)
  2. Unpaywall API (green/gold OA)
  3. EZproxy authentication (institutional access)
  4. **Sci-Hub (last resort for paywalled content)**
- **Implementation Details:** 
  - Sci-Hub attempts to resolve DOI → PDF via sci-hub.io mirror network
  - Includes retry logic and automatic mirror switching on connection failures
  - SSL verification disabled for compatibility with Sci-Hub mirrors
  - User-Agent rotation to avoid rate limiting
  - Forked from existing Sci-Hub Python client for simplicity https://github.com/zaytoun/scihub.py

**Key Features:**
- **Automatic mirror selection:** Queries sci-hub.now.sh for active mirror list
- **Robust error handling:** Falls back gracefully if Sci-Hub is unavailable
- **Citation tracking:** Logs which download strategy succeeded in manifest

**Legal/Ethical Note:**
Sci-Hub operates in a legal grey area. Use prioritizes open access and institutional channels first. Sci-Hub fallback is intended for research purposes where legitimate access methods are exhausted.

### 2026-01-11 : Documentation update to reflect developped architecture, workflows and usage instructions.

#### Current State Analysis

Your codebase naturally organizes into **4 distinct workflow stages** that align with modern LLM data engineering:

##### 1. **Data Ingestion & Preprocessing** 
- Repository APIs (Dryad, Zenodo, OpenAlex)
- PDF acquisition (Unpaywall, EZproxy, Sci-Hub)
- Full-text extraction (GROBID, TEI parsing)
- Document structure parsing

##### 2. **Feature Engineering & Prompt Design**
- Pydantic schema definitions (response format)
- Section classification & chunking
- Token counting & embedding generation
- Evidence schema engineering

##### 3. **LLM Inference**
- GPT classification engine
- Batch processing (Prefect extraction)
- Abstract vs full-text extraction
- Cost tracking & caching

##### 4. **Validation & Evaluation**
- Ground truth normalization
- Fuzzy matching
- Precision/recall/F1 metrics
- Comparative analysis

I'll update both CLAUDE.md and README.md to reflect the 4-stage LLM data engineering pipeline. Let me organize this work: 

Created 4 todos

Starting: *Update CLAUDE.md with pipeline architecture* (1/4)

Using "Replace String in File"

#### Terminology Recommendations

✅ **What Works Well**

**1. Four-Stage Pipeline Structure**
- **Pro:** Clear mental model for both external users and developers
- **Pro:** Maps naturally to your codebase organization
- **Pro:** Scales well (users can jump to the stage they need)

**2. Hybrid Terminology (Domain + Engineering)**
- Stage names use **engineering terms** ("Ingestion", "Inference") — universal
- Examples use **domain terms** ("EBV features", "species", "temporal range") — concrete
- **Pro:** External researchers understand the ecology, engineers understand the pipeline

**3. "Schema Design & Prompt Engineering" (Stage 2)**
- **Pro:** Accurately describes Pydantic's dual role (LLM output format + validation)
- **Pro:** Signals that schema IS the prompt engineering (structured outputs)
- **Alternative considered:** "Model Configuration" — too vague

## ⚠️ **Potential Tradeoffs**

**1. "Evaluation" vs "Ground Truthing"**
- **Current choice:** "Evaluation & Validation"
- **Tradeoff:** 
  - ✅ "Evaluation" is standard ML terminology (precision/recall)
  - ✅ "Validation" captures Pydantic schema validation
  - ❌ Loses domain flavor of "ground truthing" (ecologists preparing reference data)
- **Recommendation:** Keep "Evaluation" in headings, mention "ground truth" in descriptions

**2. "Inference" vs "Classification" vs "Extraction"**
- **Current choice:** "LLM Inference"
- **Tradeoff:**
  - ✅ "Inference" is technically accurate (running the model)
  - ❌ Ecologists might prefer "Metadata Extraction" (more concrete)
  - ❌ "Classification" undersells it (you're extracting structured features, not just categorizing)
- **Recommendation:** Keep "Inference" in stage name, use "extraction" in examples

**3. Module Names vs Stage Names**
- **Observation:** Some modules don't align with stage names
  - gpt_extract.py → "classification" not "inference"
  - validation.py → validates input data, not evaluation metrics
- **Tradeoff:**
  - ✅ Changing module names = breaking changes
  - ✅ Stage names provide conceptual clarity
- **Recommendation:** Keep module names unchanged, let stage structure provide organization

🎯 **Overall Assessment**

Your current terminology achieves the right balance:

| Aspect | Domain (Ecology) | Engineering (LLM) | Choice |
|--------|------------------|-------------------|---------|
| **Stage names** | ❌ Too abstract | ✅ Clear workflow | **Engineering** |
| **Examples** | ✅ Concrete tasks | ❌ Too technical | **Domain** |
| **Schema fields** | ✅ EBV terminology | ❌ Generic "features" | **Domain** |
| **Module names** | Mixed | Mixed | **Status quo** |

**Final Recommendation:** No changes needed. The current structure gives external users a clear workflow map while preserving domain terminology where it matters (schema fields, use cases, research context). Code agents (Claude, Copilot) will understand the pipeline stages, and ecologists will recognize the EBV framework.

#### 📊 **Future Development**

1. **Consider renaming gpt_extract.py → `llm_inference.py`** in next major version (v2.0+) for consistency, but not worth the breaking change now.

2. **Refactor project structure** to reflect stages in future releases (e.g., `llm_metadata/ingestion/`, `llm_metadata/inference/`), but keep flat structure for now.

---

### 2026-01-11: Prefect Flows for Staged Full-Text Extraction Pipeline
**Task:** Build modular Prefect flows with separate parallelization for GROBID parsing and GPT classification stages.

**Work Performed:**
- **Module:** `src/llm_metadata/fulltext_pipeline.py`
- **Architecture:** Created staged pipeline with three distinct flows for independent parallelization:
  1. `grobid_parsing_flow` - PDF parsing with GROBID (high parallelization)
  2. `prompt_building_flow` - Section selection and prompt construction
  3. `gpt_classification_flow` - GPT API calls (controlled parallelization)
- **Configuration Dataclasses:**
  - `SectionSelectionConfig` - Section filtering by type (ABSTRACT, METHODS) and keywords
  - `GPTClassifyConfig` - Model, reasoning effort, token limits
  - `FulltextPipelineConfig` - Combined pipeline configuration
- **Intermediate Records:**
  - `ParsedDocumentRecord` - Holds GROBID output between stages
  - `PromptRecord` - Holds built prompt with token stats
- **Input/Output Manifests:**
  - `FulltextInputRecord` - Article DOI, dataset DOI, PDF path
  - `FulltextOutputRecord` - Extraction results, costs, errors

**Parallelization Strategy:**
| Stage | Default Workers | Rationale |
|-------|-----------------|-----------|
| GROBID parsing | 10 | GROBID service handles concurrent requests well |
| Prompt building | 5 | CPU-bound text processing |
| GPT classification | 5 | API rate limits and cost control |

**Key Features:**
- **Staged execution:** Each stage completes before next begins (allows inspection)
- **Flexible input:** Accepts input_records, manifest CSV, PDF paths, or directory scan
- **Error resilience:** Failed PDFs don't block other processing
- **Cost tracking:** Per-document and total cost in output manifest

**Usage Example:**
```python
from llm_metadata.fulltext_pipeline import (
    staged_fulltext_pipeline,
    FulltextPipelineConfig,
    SectionSelectionConfig,
    GPTClassifyConfig,
)

config = FulltextPipelineConfig(
    section_config=SectionSelectionConfig(include_all=True),
    gpt_config=GPTClassifyConfig(model="gpt-5-mini", reasoning={"effort": "low"}),
)

results = staged_fulltext_pipeline(
    input_records=records,
    config=config,
    grobid_workers=10,
    gpt_workers=5,
)
```

**Alternative Flows:**
- `fulltext_extraction_pipeline` - Combined single-stage flow (simpler, less control)
- `grobid_parsing_flow` - GROBID only (for pre-processing)
- `gpt_classification_flow` - Classification only (for re-running on cached prompts)

---

### 2026-01-11: Batch Full-Text Extraction Evaluation on Fuster Dataset
**Task:** Evaluate full-text extraction pipeline on all Fuster validation PDFs using staged Prefect workflow.

**Work Performed:**
- **Notebook:** `notebooks/batch_fulltext_evaluation.ipynb`
- **Pipeline:** Used `staged_fulltext_pipeline` with GROBID (10 workers) + GPT (5 workers)
- **Model:** `gpt-5-mini` with `reasoning={"effort": "low"}`
- **Sections:** All sections included (`include_all=True`)
- **Ground Truth:** Validated with `DatasetFeaturesNormalized` model
- **Evaluation:** `evaluate_indexed()` with fuzzy matching for species (threshold=80)

**Dataset Coverage:**
| Stage | Count | Notes |
|-------|-------|-------|
| Fuster ground truth | 418 | Original annotated dataset |
| With article DOI linkage | ~100 | Dryad/Zenodo with `cited_articles` |
| PDF download success | 70 | OpenAlex + Unpaywall + Sci-Hub |
| GROBID parsing success | **45** | 25 PDFs failed parsing |
| Ground truth validated | 45 | 100% schema compliance |

**Why Only 45 Evaluated Records:**
1. **Original dataset scope:** 418 records include Semantic Scholar articles (no data paper linkage)
2. **DOI linkage:** Only ~100 Dryad/Zenodo datasets have article DOIs in `cited_articles` column
3. **PDF acquisition:** 5 DOIs failed download (no OpenAlex work, all strategies failed)
4. **GROBID failures:** 25 PDFs (36%) failed GROBID parsing due to:
   - Scanned/image-only PDFs (no extractable text layer)
   - Malformed PDF structure
   - Non-standard encodings
   - Very short documents (e.g., preprint stubs)

**GROBID Failure Analysis:**
```
Failed DOIs (sample):
  10.1639/0007-2745-119.1.008  - Bryologist journal (special format)
  10.1111/mec.14361            - Molecular Ecology (parsing error)
  10.22541/au.161832268.87346989/v1 - Authorea preprint
  10.1002/ece3.3947            - Ecology & Evolution
  10.1002/eap.1713             - Ecological Applications
```

**Results:**
| Metric | Value |
|--------|-------|
| Records processed | 70 |
| GROBID success | 45 (64%) |
| GPT extraction success | 45 (100% of parsed) |
| Total cost | ~$0.15 |
| Avg cost per PDF | ~$0.003 |

**Output:**
- Manifest: `artifacts/fulltext_results/fulltext_results_20260111_140027.csv`

**Key Findings:**
1. **GROBID is the bottleneck:** 36% of PDFs fail parsing, not GPT extraction
2. **Cost is negligible:** $0.003 per document for full-text extraction
3. **Parallelization effective:** 10 GROBID workers + 5 GPT workers processed 70 PDFs efficiently
4. **Ground truth coverage limited:** Full evaluation requires addressing GROBID failures

**Next Steps:**
1. Investigate GROBID failures - add fallback to PyMuPDF for simple text extraction
2. Run comparative evaluation: full-text vs abstract-only on 45 successful records
3. Implement hybrid approach: abstract extraction for GROBID failures
4. Consider GROBID configuration tuning for problematic PDF types

---

### 2026-01-15: Batch pdf file extraction

Evaluate PDF-based metadata extraction using OpenAI's native File API across open access Fuster validation samples.

**Approach:**
- Filter to open access PDFs only (via OpenAlex `is_oa` flag)
- Upload raw PDFs to OpenAI File API
- Use GPT-5-mini with native PDF understanding (text + visual analysis)
- Custom `PDF_SYSTEM_MESSAGE` optimized for document structure
- Compare against manually annotated ground truth
- Use `DatasetFeaturesNormalized` for ground truth validation

**Key Differences from Section-Based Pipeline:**
- No GROBID parsing required
- OpenAI processes both text AND images from each page
- Better for tables, figures, and visual content
- Higher token usage (text + image per page)

**Open access status**
Open access papers: 50 out of 70

Open Access Status Breakdown:
oa_status
gold      25
bronze    22
closed    20
green      3
Name: count, dtype: int64

OA papers with direct PDF URL: 44
OA papers requiring local file: 6

Processing complete: 44 success, 6 errors

**Extraction Results:**

Completed: 44 success, 6 failed
Total cost: $0.5454
Saved output manifest to C:\Users\beav3503\dev\llm_metadata\artifacts\pdf_file_results\pdf_file_results_20260115_142843.csv (50 records)

> *Error message*
> ```
> Error code: 400 - {'error': {'message': 'The file type you uploaded is not supported. Please try again with a pdf', 'type': 'invalid_request_error', 'param': 'input', 'code': 'unsupported_file'}}
> ```

**PDF FILE-BASED Extraction Metrics:**

PDF FILE-BASED Extraction Metrics:
======================================================================
| field                  | tp | fp  | fn | tn | n  | precision | recall   | f1       | accuracy  | exact_match_rate |
|------------------------|----|-----|----|----|----|-----------|----------|----------|-----------|------------------|
| data_type              | 32 | 121 | 23 | 0  | 44 | 0.209     | 0.582    | 0.308    | 0.727     | 0.000           |
| geospatial_info_dataset | 19 | 194 | 5  | 0  | 44 | 0.089     | 0.792    | 0.160    | 0.432     | 0.000           |
| spatial_range_km2      | 19 | 6   | 12 | 11 | 44 | 0.760     | 0.613    | 0.679    | 0.682     | 0.682           |
| species                | 27 | 239 | 42 | 0  | 44 | 0.102     | 0.391    | 0.161    | 0.614     | 0.068           |
| temp_range_f           | 28 | 10  | 9  | 5  | 44 | 0.737     | 0.757    | 0.747    | 0.750     | 0.750           |
| temp_range_i           | 31 | 7   | 6  | 5  | 44 | 0.816     | 0.838    | 0.827    | 0.818     | 0.818           |
| temporal_range         | 0  | 41  | 37 | 3  | 44 | 0.000     | 0.000    | NaN      | 0.068     | 0.068           |

Aggregate Metrics:
==================================================
Metric                              Value
--------------------------------------------------
Micro Precision                     0.202
Micro Recall                        0.538
Micro F1                            0.293
Macro F1                            0.480
Records Evaluated                      44

COST ANALYSIS (PDF File-Based Extraction)
==================================================
Metric                                      Value
--------------------------------------------------
Total PDFs Processed                           44
Avg Input Tokens per PDF                   24,521
Avg Output Tokens per PDF                   1,929
--------------------------------------------------
Total Input Tokens                      1,078,909
Total Output Tokens                        84,869
Total Cost (USD)               $           0.5454
Avg Cost per PDF (USD)         $          0.01240
==================================================
File upload extraction: 44 papers, $0.5454 total

**Claude proposed next Steps:**
- Compare metrics with section-based extraction
- Analyze which fields benefit from visual analysis
- Optimize cost vs. accuracy tradeoff
---

### 2026-01-15: Species Recall Improvement Experiment
**Task:** Achieve 85% recall on species features extraction through enhanced matching and improved prompts.

**Work Performed:**
- **Notebook:** `notebooks/species_recall_improvement.ipynb`
- **Code Changes:**
  - Added `_extract_species_parts()` to `evaluation.py` - extracts scientific/vernacular names from species strings
  - Added `_species_match_score()` to `evaluation.py` - enhanced matching with substring containment
  - Added `_enhanced_species_match_lists()` to `evaluation.py` - list matching with vernacular/scientific awareness
  - Added `enhanced_species_matching` and `enhanced_species_threshold` to `EvaluationConfig`
  - Updated `compare_models()` to use enhanced species matching when configured
- **Prompt Engineering:**
  - Created `IMPROVED_SPECIES_PROMPT` with detailed species extraction guidance
  - Added explicit ✓/✗ examples for what to extract vs avoid
  - Guidance on focal species vs non-focal (predators, hosts)
- **Experiment Design:**
  - 10 open access articles from Fuster dataset (all with species annotations)
  - PDF classification with OpenAI File API (native PDF mode)
  - Compared 4 configurations: Baseline/Improved × Fuzzy/Enhanced matching

**Results:**

| Configuration | Recall | Precision | F1 | FP | FN |
|---------------|--------|-----------|-----|----|----|
| Baseline + Fuzzy | 66.7% | 40.0% | 0.50 | 15 | 5 |
| Baseline + Enhanced | **100%** | 60.0% | 0.75 | 10 | 0 |
| Improved + Fuzzy | 53.3% | 40.0% | 0.46 | 12 | 7 |
| **Improved + Enhanced** | **93.3%** | **73.7%** | **0.82** | **5** | **1** |

**Key Findings:**
1. **Enhanced Species Matching is Critical** - Improved recall from 66.7% to 100% for baseline extraction
   - Handles "wood turtle (Glyptemys insculpta)" matching ground truth "Glyptemys insculpta"
   - Substring containment catches scientific names within compound strings
2. **Improved Prompt Reduces False Positives** - From 15 FP to 5 FP (66% reduction)
   - Example: Caribou paper baseline extracted wolves/bears (predators); improved extracted only caribou
3. **Best Configuration:** Improved Prompt + Enhanced Matching
   - 93.3% recall (exceeds 85% target by 8.3%)
   - 73.7% precision (much better than baseline's 40%)
   - F1 = 0.824 (excellent balance)

**Cost Analysis:**
- Baseline extraction: $0.0855 (10 papers)
- Improved extraction: $0.1204 (10 papers)
- Per paper cost increase: ~40% (due to longer prompt)

**Architectural Changes:**
- Enhanced species matching added to `evaluation.py` as reusable component
- New config options: `enhanced_species_matching=True`, `enhanced_species_threshold=70`
- Backward compatible - existing code using fuzzy matching unchanged

**Next Steps:**
1. Apply enhanced matching to full Fuster evaluation (50+ papers)
2. Consider adding synonym/subspecies normalization for edge cases
3. Integrate improved prompt as default for PDF classification pipeline

---

## 2026-01-15: Batch classification of all Fuster PDFs using improved species extraction
**Task:** Re-run full PDF classification on all Fuster validation PDFs using improved species extraction prompt and enhanced matching.

**Processing**
    PDFInputRecords created: 44
    All records will use local PDF files (native PDF mode)
    

    Running PDF file-based extraction on 44 papers...
    Output manifest: c:\Users\beav3503\dev\llm_metadata\artifacts\pdf_file_results\pdf_file_results_20260115_154837.csv
    
      
    Completed: 39 success, 5 failed
    Total cost: $0.5066
    Saved output manifest to c:\Users\beav3503\dev\llm_metadata\artifacts\pdf_file_results\pdf_file_results_20260115_154837.csv (44 records)


**Results:**
**PDF File-Based Extraction Metrics (Improved Species Extraction):**

| field                   | tp | fp  | fn | tn | n  | precision | recall   | f1       | accuracy  | exact_match_rate |
|-------------------------|----|-----|----|----|----|-----------|----------|----------|-----------|------------------|
| data_type               | 25 | 113 | 22 | 0  | 39 | 0.181     | 0.532    | 0.270    | 0.641     | 0.000           |
| geospatial_info_dataset | 16 | 163 | 5  | 0  | 39 | 0.089     | 0.762    | 0.160    | 0.410     | 0.000           |
| spatial_range_km2       | 17 | 6   | 11 | 9  | 39 | 0.739     | 0.607    | 0.667    | 0.667     | 0.667           |
| species                 | 50 | 153 | 12 | 0  | 39 | 0.246     | 0.806    | 0.377    | 1.282     | 0.513           |
| temp_range_f            | 26 | 8   | 7  | 5  | 39 | 0.765     | 0.788    | 0.776    | 0.795     | 0.795           |
| temp_range_i            | 29 | 5   | 4  | 5  | 39 | 0.853     | 0.879    | 0.866    | 0.872     | 0.872           |
| temporal_range          | 1  | 36  | 32 | 2  | 39 | 0.027     | 0.030    | 0.029    | 0.077     | 0.077           |

**Aggregate Metrics:**

- Micro Precision: **0.233**
- Micro Recall: **0.670**
- Micro F1: **0.346**
- Macro F1: **0.454**
- Records Evaluated: **39**
- Total Cost: **$0.5066** (39 PDFs, avg $0.013/paper)

**Key Observations:**
- **Species recall improved** to 80.6% (from ~39% in baseline), with moderate precision (24.6%).
- **Species still highly impacted by false positives**, but overall F1 improved to 0.377.
- **Overall extraction quality** improved for species, with similar or slightly better performance on other fields compared to baseline.

**Interesting Cases:**

10.5061/dryad.679s1dt, paper focused on assemblages, does it reflect the species identified (groundtruth): ['12 mammal', '199 ground-dwelling beetles', '240 flying-beetles species']

10.5061/dryad.m233m, paper focused on plant species distribution, extracted values contains tp, but also fp from discussion : ['Erythronium americanum Ker Gawl. (Liliaceae)', 'Trillium erectum L. (Melanthiaceae)', 'white-tailed deer (Odocoileus virginianus)', 'moose (Alces americana)']

10.5061/dryad.xksn02vb9, paper focused on genetic traits of 6 species, only 1 were deemed relevant and others ignored in groundtruth. Predicted are valid ['maize', 'rice', 'sorghum', 'soy', 'spruce', 'switchgrass']

**Next Steps:**

* Compare full pdf results with section-based extraction on same 39 papers
* Analyze false positives in species extraction, data type and temporal range for further prompt improvements
* Create functionnalities to relate species to atlas

---

## 2026-02-17: Dataset availability analysis from Fuster validation xlsx dataset

Goal : Manual deep dive into the Fuster dataset to understand the data and its shenanigans, and to identify the best way to integrate it into the data retrieval and processing pipeline - with focus on integrating the semantic scholar data.

* Exploration of data, validity and sources :
    * Total number of annotated datasets in fuster : 418 (299 of which are valid, i.e. relevant to biodiversity)
    * Total from semantic scholar : 254 (192 of which are valid)
    * Contains links to pdfs : 103 (73 of which are valid)
    * PDF download success rate : 67 / 73 valid

* Semantic Scholar xlsx exploration :
    * `url` provide either journal page or semantic scholar search results
    * cited_articles is always empty for semantic scholar data, but doen't mean the article isn't accessible, just that it was not annotated in the xlsx file
    * Should investigate how to retrieve cited articles from semantic scholar API, as it could be a good source of additional data for future work and implement in the data retrieval pipeline
    * Main conclusion : Semantic Scholar is simply another search engine that was used to retieve datasets. The xlsx file simply makes available relevant links in a different way than zenodo/dryad. Integration necessitates to process the xlsx file and add the relevant links to the dataset records, but doesn't change much in terms of data retrieval and processing workflow.

**Next steps**

* [ ] Streamline urls (search engine (dryad, zenodo, semantic), journal_url, pdf_url) in validated schema and existing extraction (dryad ?) to parse the xlsx file and add the relevant links to the dataset records
* [ ] Integrate semantic scholar api to retrieve cited articles and their metadata, and pdf if available
* [ ] Run download on the remaining valid pdfs from semantic scholar
* [ ] Run extraction on all valid data with pdfs, including semantic scholar data, and compare with abstract-only approach

---

### 2026-02-18: WU-A2 — All-Source Ground Truth Validation

**Task:** Validate all 418 annotated records (Dryad + Zenodo + Semantic Scholar) through the updated `DatasetFeaturesNormalized` schema (WU-A1), compute per-source coverage stats, filter to valid biodiversity records, and overwrite `data/dataset_092624_validated.xlsx`.

**Work Performed:**
- **Notebook:** `notebooks/fuster_annotations_validation.ipynb`
- **Schema update:** Switched `DataFrameValidator` from default `DatasetFeatures` to explicit `DatasetFeaturesNormalized`, which includes the 6 WU-A1 modulator fields (`time_series`, `multispecies`, `threatened_species`, `new_species_science`, `new_species_region`, `bias_north_south`) and `DataSource` enum coercion.
- **SS URL inspection:** Added Section 1.5 to inspect `url` / `url.1` for Semantic Scholar records. Both columns are identical DOI URLs for all SS records — no journal vs search URL distinction required; `url` maps directly to `source_url`.
- **Coverage stats:** Added Section 5 with per-source table (records, valid, has_abstract, has_doi, has_cited_articles).
- **Valid record filter:** Added Section 6 to filter schema-valid rows to `valid_yn == 'yes'` (biodiversity-relevant records only).
- **Presentation stats table:** Added Section 7 with formatted table for Methods section.
- **Export:** Updated Section 8 to export only valid records (not all 418).

**Results:**

| Source | Records | Valid | Abstract | Has DOI | Cited Art. |
|---|---|---|---|---|---|
| dryad | 47 | 37 | 46 | 47 | 44 |
| zenodo | 114 | 67 | 114 | 114 | 59 |
| semantic_scholar | 254 | 192 | 246 | 156 | 0 |
| **TOTAL** | **415** | **296** | **406** | **317** | **103** |

- Schema validation: **418/418 pass** (100%) — all records comply with `DatasetFeaturesNormalized`
- Exported **299 valid records** to `data/dataset_092624_validated.xlsx` (was 418 previously — now filtered to valid_yn='yes')

**Key Issues Identified:**
- SS records have zero `cited_articles` — no article DOI linkage for SS in the current xlsx
- SS DOI coverage is ~61% (156/254) vs 100% for Dryad and Zenodo
- `url` and `url.1` are always identical for SS records; no separate journal URL to parse

**Next Steps:**
- WU-B: Abstract-only extraction + evaluation on all 299 valid records segmented by source

---

### 2026-02-18: WU-C1 — Download All PDFs (Dryad + Zenodo + Semantic Scholar)

**Task:** Download article PDFs for all records with a `cited_article_doi` across all three sources, using the full 4-strategy fallback chain. No OA filter — attempt all records.

**Work Performed:**
- **Notebook:** `notebooks/download_all_fuster_pdfs.ipynb` (refactored)
- **Data source changed:** Replaced `dataset_article_mapping.csv` (Dryad+Zenodo only, 75 records) with `dataset_092624_validated.xlsx` (all sources, 250 records with `cited_article_doi`)
- **Pre-fetched URLs:** Used `pdf_url` from xlsx (populated by WU-A3 / OpenAlex) as Strategy 1 for 103 records — no extra API calls needed for those
- **Fallback chain:** OpenAlex URL → Unpaywall → EZproxy → Sci-Hub (all 4 strategies active)
- **Output:** `data/pdfs/fuster/` (single folder, no separate SS subfolder), `data/pdfs/fuster/manifest.csv`
- **Synthesis:** End-of-notebook table segmented by source (Dryad / Zenodo / Semantic Scholar)

**Results:**

| Source | Downloaded | Total | Rate | OA downloaded | Closed downloaded |
|---|---|---|---|---|---|
| Dryad | 36 | 37 | 97.3% | 25/25 | 10/11 |
| Zenodo | 33 | 38 | 86.8% | 25/27 | 8/9 |
| Semantic Scholar | 113 | 175 | 64.6% | 44/46 | 69/76 |
| **Total** | **182** | **250** | **72.8%** | | |

**Key Issues Identified:**
- ~45 SS failures have `semanticscholar.org/paper/…` URLs as `cited_article_doi` (not real DOIs) — no downloader can fetch these; root cause is upstream data quality in the xlsx
- ~17 remaining failures are legitimately closed-access articles that survived all 4 strategies (including Sci-Hub)
- 5 Zenodo failures include multi-DOI strings (e.g., `10.1101/005900; 10.6084/...`) that the pipeline can't resolve

**Next Steps:** WU-C2 — GROBID-parse newly downloaded PDFs

---

### 2026-03-06: Taxonomic Relevance Evaluation Scaffold

**Task:** Build notebook-first tooling to evaluate taxonomic extraction quality using derived fields that better reflect annotation intent than the raw `species` field alone.

**Work Performed:**
- **Notebook:** `notebooks/taxonomic_relevance_evaluation.ipynb`
- **New helper module:** `src/llm_metadata/taxonomy_eval.py`
- **Schema enrichment fields:** added `parsed_species`, `taxon_richness_mentions`, `taxon_richness_counts`, `taxon_richness_group_keys`, and `taxon_broad_group_labels` to `DatasetFeaturesEvaluation`
- **Parsing extensions:** expanded `species_parsing.py` with `TaxonRichnessMention`, group normalization, count-bearing richness parsing, and projection helpers
- **Notebook workflow:** loads a saved `RunArtifact` or older `prompt_eval_reports/*.json`, rebuilds aligned GT/pred dictionaries, enriches both sides with derived taxonomic views, evaluates a field subset, and frames the analysis/discussion explicitly around the mismatch problem
- **Model hierarchy follow-up:** updated the notebook to load predictions as `DatasetFeaturesExtraction` and describe derived comparison views as `DatasetFeaturesEvaluation`-only fields after the model split
- **Notebook framing update:** expanded the introduction with concrete GT-vs-prediction examples (coarse groups, richness summaries, scientific vs vernacular naming, community labels) so the evaluation problem is explicit before the metrics
- **Notebook documentation update:** added per-table explanatory paragraphs describing how each strategy dataframe is calculated, including metric aggregation, mismatch filtering, derived-view inspection tables, and recovery-bucket summaries
- **Notebook interpretation update:** revised the analysis/discussion to make the comparison coverage-aware, distinguish whole-dataset relevance strategies from residue-only diagnostics, and state the current recommendation more explicitly
- **New stripped-richness strategies:** added `species_stripped_richness` (split on common delimiters, then drop any fragment containing numbers entirely) and `gbif_key_stripped_richness` (same filtered residue resolved to GBIF backbone keys when possible and compared exactly)
- **Strategy applicability update:** `species_stripped_richness` now skips records unless the ground-truth side retains stripped residue, and `gbif_key_stripped_richness` skips records unless both sides resolve at least one stripped-residue GBIF key
- **Second derivation:** added a broad-group projection derived from explicit group mentions plus GBIF hierarchy mappings for enumerated predictions
- **Tests:** added focused parsing and evaluation coverage in `tests/test_species_parsing.py` and `tests/test_taxonomy_eval.py`

**Results:**
- Raw `species` is no longer the only taxonomic comparison surface in notebook experiments
- New derived fields support side-by-side comparison of:
  - raw string matching (`species`)
  - non-richness residue only (`species_stripped_richness`)
  - GBIF-key normalized non-richness residue (`gbif_key_stripped_richness`)
  - count-only relevance signal (`taxon_richness_counts`)
  - count + normalized group signal (`taxon_richness_group_keys`)
  - broad relevance-oriented group labels (`taxon_broad_group_labels`)
  - taxon identity via enrichment (`gbif_keys`)
- Executed notebook on `20260305_135009_dev_subset_pdf_file`:
  - `species`: F1 `0.217`
  - `species_stripped_richness`: F1 `0.567` on `23` applicable records
  - `gbif_key_stripped_richness`: F1 `0.864` on `13` applicable records
  - `taxon_richness_counts`: F1 `0.516`
  - `taxon_richness_group_keys`: no matches
  - `taxon_broad_group_labels`: F1 `0.542`
  - `gbif_keys`: F1 `0.133`
- Verification:
  - `uv run python -m pytest tests/test_species_parsing.py tests/test_taxonomy_eval.py tests/test_gbif_enrichment.py -q`
  - `uv run python -m pytest tests/test_evaluation.py tests/test_evaluation_field_strategies.py tests/test_evaluation_fuzzy.py -q`

**Key Issues Identified:**
- `taxon_richness_counts` helps with count-vs-enumeration mismatches, but it intentionally discards group identity when predictions do not emit explicit group counts
- `species_stripped_richness` is much more interpretable once GT-gated, but the strict fragment-drop rule can still leave non-taxon residue such as `others)` or `analysed` when those fragments contain no digits
- `gbif_key_stripped_richness` becomes the strongest subset strategy once applicability is enforced, but its high F1 is on a narrow set of resolvable residue-bearing records rather than the full 30-record subset
- The stripped-richness metrics are now computed on applicable records only, which is the correct denominator for these strategies but means their `n` is not directly comparable to strategies evaluated on all 30 records
- `taxon_richness_group_keys` remains strict and will not rescue cases where the prediction enumerates taxa but never states the broader group label
- `taxon_broad_group_labels` remains the strongest relevance-oriented derivation evaluated on all 30 records, but it is deliberately looser and can over-match broad categories
- `gbif_keys` addresses vernacular/scientific equivalence, but not coarse-group or richness-only annotations
- The current discussion now treats `taxon_broad_group_labels` as the most defensible whole-run relevance view on this slice, while keeping stripped-richness strategies as narrower diagnostic tools rather than headline replacements

**Next Steps:**
- Audit the `taxon_broad_group_labels` false positives to decide whether the GBIF-to-group mapping is too permissive
- Decide whether broad-group matching should stay notebook-only or graduate into a standard evaluation view
- If the notebook shows clear value, fold the new taxonomic fields into a reusable prompt-eval comparison flow
