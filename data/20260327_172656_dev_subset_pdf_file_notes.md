# Notes — 20260327_172656_dev_subset_pdf_file

**Prompt:** `prompts.pdf_file` · **Model:** gpt-5-mini · **Cost:** $0.2944 · **Timestamp:** 2026-03-27T21:26:56.190928+00:00 · **Run file:** `artifacts/runs/20260327_172656_dev_subset_pdf_file.json`

---

### species (F1=0.17, P=0.10, R=0.54)
- **Pattern:** Full-PDF mode collapses on precision. The model pulls in predators, co-occurring taxa, vegetation context, sample descriptors, and count-bearing phrases such as `49 female caribou (...)`.
- **Root cause:** prompt
- **Recommendation:** Add a hard full-text scoping rule: extract only taxa directly represented in the dataset, not all taxa mentioned anywhere in the paper. This mode likely needs evidence-gated or section-limited extraction rather than a prompt-only tweak.

### geospatial_info_dataset (F1=0.19, P=0.10, R=0.93)
- **Pattern:** Recall is extremely high, but almost every geography-related concept in the paper gets promoted into the output, especially `site`, `maps`, `administrative_units`, and `sample`.
- **Root cause:** prompt
- **Recommendation:** For full text, require explicit dataset-bearing evidence before emitting a geography label. A two-stage approach may be needed: first identify evidence-bearing sections, then classify geospatial structure from those sections only.

### data_type (F1=0.33, P=0.22, R=0.67)
- **Pattern:** PDF mode adds even more secondary labels, especially `time_series`, `abundance`, `traits`, `presence-absence`, and `distribution`.
- **Root cause:** prompt
- **Recommendation:** Add a priority rule to cap predictions to the data actually collected or stored, not downstream analyses. This field is a good candidate for a "primary vs secondary evidence" prompt revision or a separate classifier step.

### time_series (F1=0.33, P=0.20, R=1.00)
- **Pattern:** Full text maximizes false positives because repeated years, appendices, or analysis windows anywhere in the paper trigger `True`.
- **Root cause:** prompt
- **Recommendation:** Treat this as a full-text contamination problem. Restrict the judgment to dataset description / sampling design evidence, or test a claim-grounded boolean pass instead of relying on one-shot extraction.

### new_species_science (F1=0.61, P=0.79, R=0.50)
- **Pattern:** Full text clearly helps this rare field compared with abstract/section modes, but recall is still limited.
- **Root cause:** prompt
- **Recommendation:** Keep full-text mode for rare positive discovery fields and add targeted positive cues such as "sp. nov.", "new species", "described here", and taxonomic diagnosis language.

### new_species_region (F1=0.59, P=0.73, R=0.50)
- **Pattern:** Full text also helps regional-first-record detection, but some false positives remain.
- **Root cause:** prompt
- **Recommendation:** Add a contrastive rule distinguishing first record in a region from general distribution expansion, recolonization, or known-range discussion. This looks worth iterating in PDF mode rather than abstract mode.
