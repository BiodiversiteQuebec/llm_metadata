# Notes — pe_model_medium_pdf_native (repetition run)

**Prompt:** `prompts.pdf_file` · **Model:** gpt-5.4 · **Reasoning:** medium · **skip_cache:** true · **Timestamp:** 2026-04-01 · **Run file:** `artifacts/runs/20260401_123152_pe_model_medium_pdf_native.json`

**Compared against:** `20260401_120759_pe_model_medium_pdf_native` (same config, cached)

---

## Repeatability Summary

5/12 fields produced **bit-identical** TP/FP/FN across runs. 7 fields varied within ±0.09 F1.

### Perfectly stable fields (identical across runs)

- `bias_north_south` (F1=0.54): TP=11, FP=0, FN=19 — both runs
- `spatial_range_km2` (F1=0.63): TP=12, FP=6, FN=8 — both runs
- `temp_range_f` (F1=0.65): TP=16, FP=12, FN=5 — both runs
- `temp_range_i` (F1=0.65): TP=16, FP=12, FN=5 — both runs
- `threatened_species` (F1=0.55): TP=9, FP=3, FN=12 — both runs

### Variable fields

### new_species_science (F1=0.08→null, P=0.50→0.00, R=0.05→0.00)
- **Pattern:** TP 1→0, FP 1→1. The single TP from run1 was lost in the fresh run.
- **Interpretation:** With only 1 TP at baseline, this field is at the noise floor. Both runs confirm near-total failure (vs gpt-5-mini baseline F1=0.77). The regression is real.

### new_species_region (F1=0.15→0.08, P=0.40→0.25, R=0.09→0.05)
- **Pattern:** TP 2→1, FP 3→3. One fewer correct detection in fresh run.
- **Interpretation:** Same story — near-zero recall in both runs confirms the regression (vs baseline F1=0.75).

### time_series (F1=0.59→0.50, P=0.42→0.36, R=1.00→0.80)
- **Pattern:** TP 5→4, FP 7→7. One record flipped from TP to FN.
- **Interpretation:** The improvement over baseline (F1=0.25) is confirmed in both runs. This is the one field where gpt-5.4/medium genuinely helps.

### multispecies (F1=0.51→0.55, P=0.62→0.67, R=0.43→0.47)
- **Pattern:** TP 13→14, FP 8→7. Slight improvement in fresh run.
- **Interpretation:** Both runs confirm the regression vs baseline (F1=0.77). The ΔF1=0.04 between runs is noise.

### data_type (F1=0.39→0.36, P=0.31→0.29, R=0.53→0.47)
- **Pattern:** TP 19→17, FP 42→41. Two fewer correct predictions.
- **Interpretation:** List field variance. Both runs confirm no improvement vs baseline (F1=0.37).

### geospatial_info_dataset (F1=0.13→0.18, P=0.08→0.10, R=0.50→0.64)
- **Pattern:** TP 7→9, FP 83→79. Two more correct predictions, fewer FP.
- **Interpretation:** Precision is terrible in both runs. The over-prediction problem is consistent.

### species (F1=0.25→0.27, P=0.16→0.17, R=0.60→0.62)
- **Pattern:** TP 31→32, FP 162→152. Small improvement in fresh run.
- **Interpretation:** Core problem (massive FP from full-text species mentions) is consistent.

## Conclusion

The regressions vs gpt-5-mini/low baseline are fully reproducible:
- `new_species_science`: F1 0.77 → 0.08/null (both runs)
- `new_species_region`: F1 0.75 → 0.15/0.08 (both runs)
- `bias_north_south`: F1 0.83 → 0.54 (perfectly stable across runs)
- `multispecies`: F1 0.77 → 0.51/0.55 (both runs)

PDF native mode shows more run-to-run variance than abstract mode (7/12 vs 5/12 variable fields), likely from non-deterministic PDF visual processing. But the variance magnitude (max ΔF1=0.09) is far smaller than the regression magnitude (0.25–0.69). The conclusion is unambiguous: gpt-5.4/medium is worse for this task.
