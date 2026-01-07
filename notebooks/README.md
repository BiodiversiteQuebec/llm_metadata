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
