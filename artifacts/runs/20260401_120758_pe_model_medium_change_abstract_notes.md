# Notes — pe_model_medium_change_abstract

**Prompt:** `prompts.abstract` · **Model:** gpt-5.4 · **Reasoning:** medium · **Cost:** $0.18 (cached) · **Timestamp:** 2026-04-01T16:07:58+00:00 · **Run file:** `artifacts/runs/20260401_120758_pe_model_medium_change_abstract.json`

**Baseline:** `20260331_120539_prompt_engineering_abstract` (gpt-5-mini, effort=low)

---

### multispecies (F1=0.39, P=0.56, R=0.30) — baseline F1=0.75

- **Pattern:** Massive recall collapse (TP 22→9). The model outputs null for papers that clearly describe multi-species datasets. The "medium" reasoning effort appears to make the model demand stronger explicit evidence before committing to true.
- **Root cause:** model behavior (over-conservatism at higher reasoning effort)
- **Recommendation:** Do not use gpt-5.4/medium for this field. gpt-5-mini/low is correct more often.

### bias_north_south (F1=0.42, P=1.00, R=0.27) — baseline F1=0.29

- **Pattern:** Modest improvement — TP 5→8 with zero FP maintained. The model picks up 3 additional northern geography signals. Still severely under-recalling (22 FN).
- **Root cause:** prompt (abstract text rarely contains explicit northern geography or bias language)
- **Recommendation:** This field is fundamentally limited by abstract content. PDF mode (F1=0.83 baseline) is the correct mode for this field.

### threatened_species (F1=0.50, P=1.00, R=0.33) — baseline F1=0.39

- **Pattern:** Improvement — TP 5→7 with zero FP. The model correctly identifies 2 additional threatened species mentions. Still 14 FN.
- **Root cause:** prompt (conservation status language often absent from abstracts)
- **Recommendation:** Marginal gain here does not justify the model switch given regressions elsewhere.

### data_type (F1=0.47, P=0.42, R=0.53) — baseline F1=0.42

- **Pattern:** Small improvement — TP 18→19, FP 31→26. Slightly better precision. Still below the 0.50 target.
- **Root cause:** mixed — some GT ambiguity, vocab complexity
- **Recommendation:** Prompt refinement on gpt-5-mini is more promising than model upgrade.

### new_species_science (F1=null, P=null, R=0.00) — baseline F1=0.17

- **Pattern:** Complete collapse — zero TP. The model never predicts true for this field from abstracts. gpt-5-mini at least found 2 positives.
- **Root cause:** model behavior (extreme conservatism on rare positive fields)
- **Recommendation:** Abstract mode is inherently weak for this field. PDF mode is required.

### new_species_region (F1=0.08, P=0.33, R=0.05) — baseline F1=0.22

- **Pattern:** Near-collapse — TP 3→1. Model became too conservative to detect first regional records from abstract text.
- **Root cause:** model behavior
- **Recommendation:** Same as new_species_science — PDF mode required.

### geospatial_info_dataset (F1=0.20, P=0.12, R=0.50) — baseline F1=0.25

- **Pattern:** Precision degraded (FP 34→50) while recall held at 0.50. The model is over-predicting geospatial categories more than the baseline.
- **Root cause:** model behavior (more categories predicted per record)
- **Recommendation:** No benefit from model upgrade. Prompt refinement on gpt-5-mini needed.

### Overall verdict

gpt-5.4/medium is worse than gpt-5-mini/low for abstract extraction. The few improvements (threatened_species, bias_north_south) are small and offset by catastrophic regressions on multispecies, new_species_*, and geospatial_info.
