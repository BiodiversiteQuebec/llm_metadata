# Notes — 20260327_172654_dev_subset_abstract

**Prompt:** `prompts.abstract` · **Model:** gpt-5-mini · **Cost:** $0.2068 · **Timestamp:** 2026-03-27T21:26:54.621212+00:00 · **Run file:** `artifacts/runs/20260327_172654_dev_subset_abstract.json`

---

### data_type (F1=0.34, P=0.24, R=0.58)
- **Pattern:** The model over-predicts broad labels such as `abundance`, `traits`, `ecosystem_structure`, `distribution`, `time_series`, and `species_richness`, while missing GT labels like `presence-only` and `density`.
- **Root cause:** vocab gap
- **Recommendation:** Expand the prompt vocabulary to cover the full enum actually accepted by the schema, not the current subset. Add contrastive guidance for `presence-only` vs `distribution`, `abundance` vs `density`, and `other` vs domain-specific labels.

### geospatial_info_dataset (F1=0.14, P=0.09, R=0.43)
- **Pattern:** Abstract mode frequently predicts `administrative_units` and `site` whenever a place name appears, even when the GT expects `distribution`, `sample`, or `site_ids`.
- **Root cause:** prompt
- **Recommendation:** Add a stricter geography rule: named places in background or study-area descriptions do not automatically imply dataset geospatial structure. Include negative examples for "province named in prose" vs positive examples for coordinates, site identifiers, or distribution outputs.

### species (F1=0.40, P=0.29, R=0.65)
- **Pattern:** The model often extracts decorated forms of the focal species (`woodland caribou (Rangifer tarandus caribou)`) or contextual taxa rather than the GT's canonical dataset-facing label. False positives also include tree species and non-focal taxa mentioned in habitat context.
- **Root cause:** prompt
- **Recommendation:** Add a species hygiene block: extract focal dataset taxa only, strip counts/adjectives/sex qualifiers, and ignore predators, hosts, vegetation context, and discussion-only taxa unless they are explicitly part of the dataset.

### time_series (F1=0.53, P=0.36, R=1.00)
- **Pattern:** Precision is low because repeated years, multiple sampling windows, or interannual comparisons are being treated as time series even when the abstract describes a short study window rather than repeated monitoring.
- **Root cause:** prompt
- **Recommendation:** Add negative examples showing that "data collected in 2006 and 2007" is not sufficient by itself. Require explicit repeated observation language such as annual monitoring, long-term survey, monthly sampling, or repeated measures at the same site/population.

### threatened_species (F1=0.38, P=1.00, R=0.24)
- **Pattern:** The model is conservative enough to avoid false positives, but it misses many explicit conservation-status cues.
- **Root cause:** prompt
- **Recommendation:** Add a cue list for endangered, threatened, vulnerable, at-risk, red-listed, IUCN-listed, and CITES-listed wording so the model can recover recall without relaxing scoping elsewhere.

### bias_north_south (F1=N/A, P=N/A, R=0.00)
- **Pattern:** The model never predicts this field. The GT has 10 `True` cases on the dev subset, so this is not just a class-imbalance issue.
- **Root cause:** prompt
- **Recommendation:** Add explicit lexical triggers for Global North, Global South, underrepresentation, geographic bias, and sampling inequality. Also audit whether boolean evaluation should distinguish `False` from `None` more explicitly.
