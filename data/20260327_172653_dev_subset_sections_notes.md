# Notes — 20260327_172653_dev_subset_sections

**Prompt:** `prompts.section` · **Model:** gpt-5-mini · **Cost:** $0.2201 · **Timestamp:** 2026-03-27T21:26:53.635385+00:00 · **Run file:** `artifacts/runs/20260327_172653_dev_subset_sections.json`

---

### data_type (F1=0.30, P=0.21, R=0.56)
- **Pattern:** Section mode is even noisier than abstract mode for `data_type`, with many records accumulating long label lists including `presence-absence`, `species_richness`, `ecosystem_function`, `unknown`, and `time_series`.
- **Root cause:** vocab gap
- **Recommendation:** Keep the full enum vocabulary expansion from abstract mode, then add a section-mode rule to prefer only the dataset's principal observed data modalities rather than every analyzable concept mentioned in methods text.

### geospatial_info_dataset (F1=0.15, P=0.09, R=0.57)
- **Pattern:** Sections improve recall slightly, but the model still adds `administrative_units` and `site` too readily and sometimes piles on `maps` or `sample` together.
- **Root cause:** prompt
- **Recommendation:** Add tie-breaker guidance for geospatial outputs: coordinates and station codes imply dataset geography; narrative study-area text alone does not. Encourage the model to emit the smallest justified set instead of every plausible geography label.

### species (F1=0.42, P=0.32, R=0.60)
- **Pattern:** Section mode slightly improves species F1, but it still emits contextual or over-specific variants such as `female caribou`, `forest-dwelling sedentary caribou`, and expanded scientific-name hybrids.
- **Root cause:** prompt
- **Recommendation:** Reuse the species hygiene block and add a section-mode reminder that participant subgroups, life stages, sex classes, and habitat associates are not separate species outputs.

### time_series (F1=0.42, P=0.26, R=1.00)
- **Pattern:** Recall remains perfect, but methods/results sections make the over-prediction problem worse because any repeated measurement phrasing is interpreted as longitudinal monitoring.
- **Root cause:** prompt
- **Recommendation:** Add a stronger exclusion rule for experimental repeats, multi-year sampling campaigns, or multiple treatment periods unless the text explicitly states repeated observation of the same population/site over time.

### spatial_range_km2 (F1=0.69, P=0.92, R=0.55)
- **Pattern:** Section mode is much stronger on this field than abstract mode, which suggests the information is often present once methods text is available.
- **Root cause:** prompt
- **Recommendation:** Preserve this mode as the likely best candidate for spatial-range prompt work. When iterating, prioritize fields that can exploit section-specific detail instead of forcing everything through abstract mode.

### bias_north_south (F1=N/A, P=N/A, R=0.00)
- **Pattern:** Like abstract mode, section mode never predicts the field.
- **Root cause:** prompt
- **Recommendation:** Treat this as a rare-field prompt experiment rather than expecting incidental recovery. If recall remains zero after explicit cueing, consider moving it out of the main optimization loop.
