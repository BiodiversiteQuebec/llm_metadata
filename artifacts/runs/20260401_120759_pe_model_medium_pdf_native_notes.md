# Notes — pe_model_medium_pdf_native

**Prompt:** `prompts.pdf_file` · **Model:** gpt-5.4 · **Reasoning:** medium · **Cost:** $2.35 · **Timestamp:** 2026-04-01T16:07:59+00:00 · **Run file:** `artifacts/runs/20260401_120759_pe_model_medium_pdf_native.json`

**Baseline:** `20260331_120734_prompt_engineering_pdf_native` (gpt-5-mini, effort=low)

---

### new_species_science (F1=0.08, P=0.50, R=0.05) — baseline F1=0.77

- **Pattern:** Catastrophic collapse. TP 15→1, recall 0.68→0.05. The model fails to detect "sp. nov.", holotype language, and species descriptions that gpt-5-mini reliably found. One of the worst regressions in the experiment.
- **Root cause:** model behavior (gpt-5.4/medium ignores taxonomic description signals that gpt-5-mini acts on)
- **Recommendation:** Do not use gpt-5.4/medium. gpt-5-mini/low is dramatically better for this field.

### new_species_region (F1=0.15, P=0.40, R=0.09) — baseline F1=0.75

- **Pattern:** Same pattern as new_species_science. TP 15→2. The model demands stronger evidence than "first record for" or "new to [region]" language.
- **Root cause:** model behavior
- **Recommendation:** Same — stay on gpt-5-mini/low.

### bias_north_south (F1=0.54, P=1.00, R=0.37) — baseline F1=0.83

- **Pattern:** TP 22→11, recall halved. The model misses northern geography signals (Nunavik, James Bay, above 49°N) that gpt-5-mini correctly detected from full-text context. Zero FP maintained.
- **Root cause:** model behavior (over-conservatism)
- **Recommendation:** Stay on gpt-5-mini/low.

### multispecies (F1=0.51, P=0.62, R=0.43) — baseline F1=0.77

- **Pattern:** TP 23→13. The model fails to recognize multi-species datasets from full text even when species lists or community-level study designs are described.
- **Root cause:** model behavior
- **Recommendation:** Stay on gpt-5-mini/low.

### threatened_species (F1=0.55, P=0.75, R=0.43) — baseline F1=0.78

- **Pattern:** TP 14→9, and 3 new FP introduced (baseline had only 1 FP). Both precision and recall degraded.
- **Root cause:** model behavior
- **Recommendation:** Stay on gpt-5-mini/low.

### time_series (F1=0.59, P=0.42, R=1.00) — baseline F1=0.25

- **Pattern:** The one bright spot. TP 4→5 (perfect recall), FP 23→7. The model correctly rejects false time-series signals (multi-year compilations, experimental repeats) that gpt-5-mini incorrectly flagged. This aligns with the PDF-mode-specific `time_series` prompt rule.
- **Root cause:** model behavior (higher reasoning helps distinguish true monitoring from multi-year data)
- **Recommendation:** gpt-5.4/medium is genuinely better here, but this one improvement does not justify the regression on 9 other fields.

### species (F1=0.25, P=0.16, R=0.60) — baseline F1=0.19

- **Pattern:** FP 248→162. The model is less over-inclusive with incidental species mentions. Precision improved from 0.11→0.16, still very weak.
- **Root cause:** mixed — PDF full text inherently has many species mentions
- **Recommendation:** Marginal improvement, not enough to justify model switch.

### spatial_range_km2 (F1=0.63, P=0.67, R=0.60) — baseline F1=0.70

- **Pattern:** Small regression — TP 13→12, FP 4→6. Slightly more false positives.
- **Root cause:** model behavior
- **Recommendation:** No benefit from model upgrade.

### data_type (F1=0.39, P=0.31, R=0.53) — baseline F1=0.37

- **Pattern:** Essentially flat. TP unchanged (20→19), FP decreased slightly (52→42). Recall identical.
- **Root cause:** prompt/GT ambiguity
- **Recommendation:** Neither model solves the data_type challenge. Prompt work needed.

### geospatial_info_dataset (F1=0.13, P=0.08, R=0.50) — baseline F1=0.23

- **Pattern:** Precision collapsed — FP 94→83 but TP stayed at 7 (baseline had 14 TP). Wait — baseline had TP=14 with R=1.00 and this run has TP=7 with R=0.50. The model missed half the true positives while still producing massive FP.
- **Root cause:** model behavior
- **Recommendation:** Worse in every way. Stay on gpt-5-mini/low.

### Overall verdict

gpt-5.4/medium is dramatically worse than gpt-5-mini/low for PDF native extraction. Only `time_series` improved meaningfully. The model's higher reasoning effort causes it to over-filter evidence that gpt-5-mini correctly acts on, especially for rare boolean fields (`new_species_*`, `bias_north_south`, `threatened_species`). Cost is ~10x higher. No reason to adopt this configuration.
