# Notes — pe_model_medium_change_abstract (repetition run)

**Prompt:** `prompts.abstract` · **Model:** gpt-5.4 · **Reasoning:** medium · **skip_cache:** true · **Timestamp:** 2026-04-01 · **Run file:** `artifacts/runs/20260401_123138_pe_model_medium_change_abstract.json`

**Compared against:** `20260401_120758_pe_model_medium_change_abstract` (same config, cached)

---

## Repeatability Summary

7/12 fields produced **bit-identical** TP/FP/FN across runs. 5 fields varied within ±0.10 F1.

### Perfectly stable fields (identical across runs)

- `bias_north_south` (F1=0.42): TP=8, FP=0, FN=22 — both runs
- `multispecies` (F1=0.39): TP=9, FP=7, FN=21 — both runs
- `new_species_region` (F1=0.08): TP=1, FP=2, FN=21 — both runs
- `new_species_science` (F1=null): TP=0, FP=0, FN=22 — both runs
- `spatial_range_km2` (F1=0.10): TP=1, FP=0, FN=19 — both runs
- `temp_range_f` (F1=0.63): TP=11, FP=3, FN=10 — both runs
- `temp_range_i` (F1=0.74): TP=13, FP=1, FN=8 — both runs

### Variable fields

### threatened_species (F1=0.50→0.60, P=1.00, R=0.33→0.43)
- **Pattern:** TP increased 7→9, FP stayed 0. Two additional records correctly identified as threatened species in the fresh run.
- **Interpretation:** Positive variance — model sometimes picks up conservation language, sometimes doesn't. The underlying conservatism is consistent (both runs far below gpt-5-mini baseline F1=0.39).

### time_series (F1=0.50→0.60, P=0.67→0.60, R=0.40→0.60)
- **Pattern:** TP 2→3, FP 1→2. One more correct detection but also one more false positive.
- **Interpretation:** Low-count field where ±1 record swings F1 significantly. Core behavior stable.

### data_type (F1=0.47→0.44, P=0.42→0.40, R=0.53→0.47)
- **Pattern:** TP 19→17, FP 26→25. Two fewer correct type predictions in fresh run.
- **Interpretation:** List field with inherent set-matching variance. Small fluctuation.

### geospatial_info_dataset (F1=0.20→0.23, P=0.12→0.15, R=0.50)
- **Pattern:** TP=7 stable, FP 50→39. Fewer false positives in fresh run but same recall.
- **Interpretation:** The over-prediction varies but the core recall ceiling is fixed.

### species (F1=0.39→0.41, P=0.28→0.30, R=0.62→0.65)
- **Pattern:** TP 32→34, FP 82→81. Two more correct species matches in fresh run.
- **Interpretation:** Minor fluctuation in species string matching. Core behavior stable.

## Conclusion

The catastrophic regressions vs gpt-5-mini baseline (multispecies -0.36, new_species_science -0.17, new_species_region -0.14) are deterministic and reproducible. The model consistently fails on the same records. This is not a stochastic issue.
