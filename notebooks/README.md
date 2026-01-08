# Notebooks Log Book

This folder contains analysis and validation notebooks for ecological dataset characterization.

## Recent Activity

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
- **Model Change:** Switched from `gpt-4` to `gpt-5-mini` in `classify_abstract()` call. Include new reasoning parameter (effort: "low") while loosing temperature setting. This is a new setting that can be played with for GPT-5 series models.
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