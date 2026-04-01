# Automated Relevance Classification

## Context & Motivation

Fuster et al. (2025) manually scored dataset relevance using a two-tier system: three Main Classifiers (data type, temporal extent, spatial extent) combined by majority vote, then upgraded by Modulators (multispecies, threatened species, new to science, new to region, northern Quebec). The process is labor-intensive and does not scale.

Two automated approaches are compared here:

| Method | Description |
|---|---|
| **Mechanistic** | LLM extracts features → rule-based scoring replicates the Fuster logic |
| **Direct LLM** | Single LLM call extracts features AND outputs a relevance verdict with reasoning |

Both are notebook-only. No modifications to `src/`.

## Current Status

| Work unit | Status | Notes |
|---|---|---|
| **WU-R1A** | Complete | `notebooks/relevance_mechanistic.ipynb` now reproduces the annotated Fuster mechanistic system exactly on the 30-record dev subset (`30/30` on all audited `MC_*` columns; macro F1 `1.00` vs `MC_relevance_modifiers`). |
| **WU-R1B** | Complete | The same notebook evaluates rules on LLM-extracted features against `MC_relevance_modifiers`; current saved dev-subset result is macro F1 `0.125`. |
| **WU-R2** | Partially complete | `notebooks/relevance_llm_direct.ipynb` exists and runs, but it still evaluates against `dataset_relevance` rather than the paper-faithful mechanistic target. |
| **Final synthesis** | Remaining | The comparison framing and lab log need one final refresh so all headline rows use the same target definition. |

---

## Ground Truth & Data

**Record scope:** 30-record dev subset (`data/manifests/dev_subset_data_paper.csv`). Join on `id` / `record_id` to pull GT columns from the raw xlsx.

**GT source:** `data/dataset_092624.xlsx` — columns `dataset_relevance`, `MC_dataset_type`, `MC_spatial_range`, `MC_temporal_range`, `MC_relevance`, `MC_relevance_modifiers`, and all extracted feature columns.

**Primary mechanistic target:** `MC_relevance_modifiers`

- This is the paper-faithful output of the explicit Fuster rule system: Main Classifiers followed by Modulators.
- `WU-R1` should be evaluated against this column.

**Secondary diagnostic label:** `dataset_relevance`

- This is the spreadsheet's final manual relevance label.
- Keep it in the notebooks as `human_relevance` for diagnostic comparison only.
- Do not use it as the ceiling target for rule reconstruction.

Full-dataset `dataset_relevance` distribution for reference:

| Value | Meaning | Full dataset count |
|---|---|---|
| H | High relevance | 23 |
| M | Moderate relevance | 57 |
| L | Low relevance | 77 |
| X | Non-relevant | 35 |
| No dataset | No dataset in record | 87 |
| cant access | Inaccessible | 28 |

**Evaluation target preparation:**
- For `dataset_relevance`: collapse `No dataset` → `X`, strip whitespace, drop `cant access`.
- For `MC_relevance_modifiers`: keep only `H/M/L/X`.
- Check actual dev subset distribution at runtime; the dev subset currently contains no `X` in `MC_relevance_modifiers`.

**Input text:** `full_text` column from raw xlsx — the Dryad/Zenodo repository description. This is identical to what the existing `abstract` extraction mode uses (see `_merge_raw_abstracts()` in `data_paper.py`).

**Notebook normalization rule:**
- Normalize notebook-relevant GT feature inputs through `DatasetFeaturesNormalized` before scoring.
- Preserve the raw spreadsheet `data_type` string separately, because `DatasetFeaturesNormalized` collapses both `genetic analysis` and `EBV genetic analysis` to `genetic_analysis`, while the mechanistic reconstruction needs that distinction.

**Reference columns** (for rule reconstruction and audit):
- `MC_dataset_type`, `MC_spatial_range`, `MC_temporal_range` — individual classifier scores
- `MC_relevance`, `MC_relevance_modifiers` — mechanistic output by authors (direct audit target for WU-R1)

---

## Scoring Rules (from Fuster et al.)

### Main Classifiers

This plan follows the annotated rule behavior that reproduces the released `MC_*` columns, even where the paper prose is a little ambiguous.

| Score | Types |
|---|---|
| H | abundance, density, EBV genetic analysis |
| M | distribution, presence-absence |
| L | presence-only, relative abundance, species richness, non-EBV genetic analysis |
| X | no species/biodiversity data |

Decision note: the raw spreadsheet label `genetic analysis` is interpreted as non-EBV genetic analysis (`L`) unless `EBV genetic` is explicit.

**Temporal extent** (reconstructed from annotated behavior):
| Score | Duration |
|---|---|
| H | >= 12 years |
| M | 3-11 years |
| L | 1-2 years |
| X | not stated |

**Spatial extent** (`spatial_range_km2`, thresholds inferred from GT data):
| Score | Range |
|---|---|
| H | > ~15,000 km² |
| M | ~5,000–15,000 km² |
| L | < ~5,000 km² |
| X | not stated |

### Aggregation

Majority vote across the three Main Classifiers → `MC_relevance`. When all three differ (no majority), apply tiebreaker from Table S2 (see [`docs/fuster_et_al_2024/table_S2.md`](../docs/fuster_et_al_2024/table_S2.md)):

1. **Special case:** If `data_type = H` AND (`temporal = X` OR `spatial = X`) → **L**
2. **General rule:** `result = min(data_type, max(temporal, spatial))`

Score order: H > M > L > X.

### Modulators

| Modulator field | Paper criterion |
|---|---|
| `multispecies` | > 10 species |
| `threatened_species` | IUCN-listed species present |
| `new_species_science` | Novel species discovery |
| `new_species_region` | Species new to Quebec |
| `bias_north_south` | Location in northern Quebec (≥ 49th parallel) |

Reconstruction note: the released `MC_relevance_modifiers` annotations empirically behave as if modulators can upgrade `X -> L` and can still upgrade some multispecies records through non-north modulators. The mechanistic notebook therefore follows the annotated column behavior rather than enforcing the prose restriction literally.

---

## Notebooks

### WU-R1: `notebooks/relevance_mechanistic.ipynb` `sonnet`

**deps:** none | **files:** `notebooks/relevance_mechanistic.ipynb`

**Status:** Implemented.

**Part A — Rule validation on GT features (ceiling test)**

Apply the reconstructed Fuster scoring rules to the human-annotated features already in the xlsx. No LLM involved. This answers: *"if features were extracted perfectly, do the rules reproduce the authors' mechanistic labels?"*

Steps:
- Load dev subset manifest (`data/manifests/dev_subset_data_paper.csv`), join with raw xlsx on `id`/`record_id`
- Normalize GT feature inputs with `DatasetFeaturesNormalized`, while preserving raw `data_type` for the genetic ambiguity
- Implement `score_data_type()`, `score_temporal()`, `score_spatial()` as Python functions
- Implement `majority_vote()` and `apply_modulators()`
- Apply full pipeline to GT features
- Compare output to `MC_relevance_modifiers`
- Metrics: 4-class accuracy + macro F1, binary (H+M vs L+X) P/R/F1, confusion matrix
- Audit computed `mc_data_type`, `mc_temporal`, `mc_spatial`, `mc_relevance`, and `pred_relevance` directly against the five `MC_*` columns
- Keep a separate diagnostic comparison against `dataset_relevance` / `human_relevance`

Implemented result:
- Dev subset audit is exact on all five `MC_*` columns (`30/30` each)
- `R1-A` metrics vs `MC_relevance_modifiers`: accuracy `1.00`, macro F1 `1.00`

**Part B — End-to-end with LLM-extracted features**

Run existing extraction on the dev subset, apply the same rules, compare to `MC_relevance_modifiers`.

Steps:
- Load `data/manifests/dev_subset_data_paper.csv` as the manifest (already in the right format for `run_manifest_extraction`)
- Run `run_manifest_extraction(mode="abstract", ...)` — uses joblib cache, won't re-call API for records already cached
- Apply Part A rule functions to LLM-extracted features (`data_type`, `temp_range_i`, `temp_range_f`, `spatial_range_km2`, `multispecies`, `threatened_species`, `new_species_science`, `new_species_region`, `bias_north_south`)
- Join results with raw xlsx GT on `record_id` / `id` for comparison
- Delta table vs Part A: how much does imperfect feature extraction degrade relevance scoring?

Implemented result:
- Current saved dev-subset result vs `MC_relevance_modifiers`: macro F1 `0.125`, binary F1 `0.00`
- No additional implementation is pending in `WU-R1` unless we want to refresh outputs after future prompt/model changes

### WU-R2: `notebooks/relevance_llm_direct.ipynb` `sonnet`

**deps:** none (independent notebook, but should now be aligned to the same target definition as WU-R1) | **files:** `notebooks/relevance_llm_direct.ipynb`

**Status:** Partially implemented; remaining notebook work is here.

**Schema (defined locally in notebook — no src changes)**

```python
from llm_metadata.schemas.fuster_features import DatasetFeaturesExtraction
from typing import Literal
from pydantic import Field

class DatasetFeaturesWithRelevance(DatasetFeaturesExtraction):
    has_dataset: bool = Field(
        description="True if the record describes an actual dataset produced or curated by the authors."
    )
    relevance: Literal["H", "M", "L", "X"] = Field(
        description=(
            "Overall dataset relevance for Quebec biodiversity monitoring. "
            "H=High, M=Moderate, L=Low, X=Non-relevant or no dataset."
        )
    )
    relevance_reasoning: str = Field(
        description="1–3 sentences explaining the relevance verdict based on data type, temporal/spatial extent, and modulators."
    )
```

**Prompt additions (injected into existing abstract prompt)**

Append a RELEVANCE block after the existing VOCABULARY block:

```
RELEVANCE SCORING
=================
After extracting all features, assign an overall relevance score for Quebec biodiversity
monitoring using these criteria:

Main Classifiers (majority vote):
- Data type: H=abundance/genetic (EBV-compliant), M=richness/relative abundance,
  L=presence-only, X=no biodiversity data
- Temporal extent: H=>10 years, M=3-10 years, L=<3 years, X=not stated
- Spatial extent: H=>15000 km², M=5000-15000 km², L=<5000 km², X=not stated

Modulators — upgrade score by one level (cannot upgrade X) if any of:
- multispecies: dataset covers >10 species
- threatened_species: IUCN-listed species present
- new_species_science or new_species_region: novel or range-extending species
- bias_north_south: study area in northern Quebec (≥49th parallel)

Set has_dataset=False and relevance="X" if no primary dataset is described.
```

**Execution**

Use `get_openai_client()` from `openai_io.py` and call `client.responses.parse()` directly with `DatasetFeaturesWithRelevance` as the response format. Mirror the pattern in `gpt_extract.py` — no import of the extraction engine itself.

Steps:
- Build client from `openai_io.get_openai_client()`
- Load dev subset manifest; join with raw xlsx for `full_text`
- Loop over 30 records with joblib caching (cache key = record id + model + schema hash)
- Parse responses into `DatasetFeaturesWithRelevance`
- Carry both `gt_relevance = MC_relevance_modifiers` and `human_relevance = dataset_relevance`
- Evaluate `relevance` primarily against `MC_relevance_modifiers` (same metrics as WU-R1)
- Optionally keep a diagnostic comparison against `human_relevance`
- Spot-check `relevance_reasoning` on mismatches

Remaining tasks:
- Update notebook framing so it explains the same target distinction already documented in `relevance_mechanistic.ipynb`
- Replace the current `dataset_relevance`-based headline metrics and saved outputs with `MC_relevance_modifiers`-based ones
- Re-run the notebook and refresh `relevance_llm_direct_summary.json`, predictions, and confusion figure

---

## Evaluation Protocol (shared)

**GT preparation:**
```python
subset_ids = pd.read_csv("data/manifests/dev_subset_data_paper.csv")["record_id"]
raw = pd.read_excel("data/dataset_092624.xlsx")
df = raw[raw["id"].isin(subset_ids)].copy()
df["human_relevance"] = df["dataset_relevance"].replace({"No dataset": "X", " X": "X"}).str.strip()
df["gt_relevance"] = df["MC_relevance_modifiers"].fillna("").str.strip()
eval_df = df[df["gt_relevance"].isin(["H", "M", "L", "X"])].copy()
```

**Metrics:**
- 4-class: `sklearn.metrics.classification_report(labels=["H","M","L","X"])`
- Binary: collapse H+M → "relevant", L+X → "not relevant"; compute P/R/F1
- Confusion matrix heatmap

**Comparison table (final output):**

| Method | 4-class macro F1 | Binary F1 (relevant) | Binary P | Binary R |
|---|---|---|---|---|
| R1-A: Rules on GT features | | | | |
| R1-B: Rules on LLM features | | | | |
| R2: Direct LLM | | | | |
| Diagnostic: mechanistic target vs human `dataset_relevance` | | | | |

Current known values:

| Method | 4-class macro F1 | Binary F1 (relevant) | Binary P | Binary R |
|---|---|---|---|---|
| R1-A: Rules on GT features vs Fuster MC+Modulators | 1.000 | 1.000 | 1.000 | 1.000 |
| R1-B: Rules on LLM features vs Fuster MC+Modulators | 0.125 | 0.000 | 0.000 | 0.000 |
| Diagnostic: Fuster MC+Modulators vs human `dataset_relevance` | 0.491 | 0.850 | 0.773 | 0.944 |
| R2: Direct LLM | pending refresh against `MC_relevance_modifiers` | pending | pending | pending |

---

## Execution Order

```
Round 1: Refresh WU-R2 target/framing/output files
Round 2: Update combined comparison table + lab log entry using consistent `MC_relevance_modifiers` target
```

---

## Key Files

| File | Purpose |
|---|---|
| `notebooks/relevance_mechanistic.ipynb` | WU-R1: rule-based approach |
| `notebooks/relevance_llm_direct.ipynb` | WU-R2: direct LLM approach |
| `data/manifests/dev_subset_data_paper.csv` | 30-record dev subset manifest |
| `data/dataset_092624.xlsx` | Raw GT (all 418 records) — joined for GT labels + MC columns |
| `src/llm_metadata/schemas/fuster_features.py` | `DatasetFeaturesExtraction` base schema |
| `src/llm_metadata/openai_io.py` | `get_openai_client()` factory |
| `src/llm_metadata/gpt_extract.py` | Reference for `client.responses.parse()` pattern |
| `src/llm_metadata/extraction.py` | `run_manifest_extraction()` used in WU-R1-B |
