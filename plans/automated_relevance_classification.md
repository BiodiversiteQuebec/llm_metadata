# Automated Relevance Classification

## Context & Motivation

Fuster et al. (2025) manually scored dataset relevance using a two-tier system: three Main Classifiers (data type, temporal extent, spatial extent) combined by majority vote, then upgraded by Modulators (multispecies, threatened species, new to science, new to region, northern Quebec). The process is labor-intensive and does not scale.

Two automated approaches are compared here:

| Method | Description |
|---|---|
| **Mechanistic** | LLM extracts features → rule-based scoring replicates the Fuster logic |
| **Direct LLM** | Single LLM call extracts features AND outputs a relevance verdict with reasoning |

Both are notebook-only. No modifications to `src/`.

---

## Ground Truth & Data

**Record scope:** 30-record dev subset (`data/manifests/dev_subset_data_paper.csv`). Join on `id` / `record_id` to pull GT columns from the raw xlsx.

**GT source:** `data/dataset_092624.xlsx` — columns `dataset_relevance`, `MC_dataset_type`, `MC_spatial_range`, `MC_temporal_range`, `MC_relevance`, `MC_relevance_modifiers`, and all extracted feature columns.

**GT column:** `dataset_relevance` (human manual annotation). Full-dataset distribution for reference:

| Value | Meaning | Full dataset count |
|---|---|---|
| H | High relevance | 23 |
| M | Moderate relevance | 57 |
| L | Low relevance | 77 |
| X | Non-relevant | 35 |
| No dataset | No dataset in record | 87 |
| cant access | Inaccessible | 28 |

**Evaluation target:** Collapse `No dataset` → `X`. Drop `cant access` (no GT signal). Final: 4-class H/M/L/X. Check actual dev subset distribution at runtime.

**Input text:** `full_text` column from raw xlsx — the Dryad/Zenodo repository description. This is identical to what the existing `abstract` extraction mode uses (see `_merge_raw_abstracts()` in `data_paper.py`).

**Reference columns** (for rule reconstruction, not evaluation target):
- `MC_dataset_type`, `MC_spatial_range`, `MC_temporal_range` — individual classifier scores
- `MC_relevance`, `MC_relevance_modifiers` — mechanistic output by authors (useful for comparison)

---

## Scoring Rules (from Fuster et al.)

### Main Classifiers

<!-- **Data type** (EBV hierarchy, from paper Table 2): -->
| Score | Types |
|---|---|
| H | abundance, density, EBV genetic analysis |
| M | distribution, presence-absence, species richness, relative abundance |
| L | presence-only, non-EBV genetic analysis |
| X | no species/biodiversity data |

**Temporal extent** (`temp_range_f − temp_range_i`):
| Score | Duration |
|---|---|
| H | > 10 years |
| M | 3–10 years |
| L | < 3 years |
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

Upgrade: L → M, M → H. Already H stays H. Cannot upgrade X.

**Multispecies restriction** (paper Methods §"Dataset relevance assignment"): *"For multispecies datasets, only the north-south modulator was noted."* When `multispecies=True`, only `bias_north_south` can trigger an upgrade; `threatened_species`, `new_species_science`, `new_species_region` are suppressed.

---

## Notebooks

### WU-R1: `notebooks/relevance_mechanistic.ipynb` `sonnet`

**deps:** none | **files:** `notebooks/relevance_mechanistic.ipynb`

**Part A — Rule validation on GT features (ceiling test)**

Apply the Fuster scoring rules to the human-annotated features already in the xlsx. No LLM involved. This answers: *"if features were extracted perfectly, how accurately do the rules reconstruct human relevance judgments?"*

Steps:
- Load dev subset manifest (`data/manifests/dev_subset_data_paper.csv`), join with raw xlsx on `id`/`record_id`
- Implement `score_data_type()`, `score_temporal()`, `score_spatial()` as Python functions
- Implement `majority_vote()` and `apply_modulators()`
- Apply full pipeline to GT features
- Compare output to `dataset_relevance` (collapsed)
- Metrics: 4-class accuracy + macro F1, binary (H+M vs L+X) P/R/F1, confusion matrix
- Compare to authors' `MC_relevance_modifiers` to sanity-check rule reconstruction

Expected finding: rules will not perfectly reconstruct `dataset_relevance` even with perfect features — documenting this gap is the point.

**Part B — End-to-end with LLM-extracted features**

Run existing extraction on all 418 records, apply the same rules, compare to GT.

Steps:
- Load `data/manifests/dev_subset_data_paper.csv` as the manifest (already in the right format for `run_manifest_extraction`)
- Run `run_manifest_extraction(mode="abstract", ...)` — uses joblib cache, won't re-call API for records already cached
- Apply Part A rule functions to LLM-extracted features (`data_type`, `temp_range_i`, `temp_range_f`, `spatial_range_km2`, `multispecies`, `threatened_species`, `new_species_science`, `new_species_region`, `bias_north_south`)
- Join results with raw xlsx GT on `record_id` / `id` for comparison
- Delta table vs Part A: how much does imperfect feature extraction degrade relevance scoring?

### WU-R2: `notebooks/relevance_llm_direct.ipynb` `sonnet`

**deps:** none (independent of WU-R1) | **files:** `notebooks/relevance_llm_direct.ipynb`

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
- Evaluate `relevance` field against GT (same metrics as WU-R1)
- Spot-check `relevance_reasoning` on mismatches

---

## Evaluation Protocol (shared)

**GT preparation:**
```python
subset_ids = pd.read_csv("data/manifests/dev_subset_data_paper.csv")["record_id"]
raw = pd.read_excel("data/dataset_092624.xlsx")
df = raw[raw["id"].isin(subset_ids)].copy()
df["gt_relevance"] = df["dataset_relevance"].replace({"No dataset": "X", " X": "X"})
eval_df = df[df["gt_relevance"].isin(["H", "M", "L", "X"])]  # drop cant access
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
| Authors' MC_relevance_modifiers (reference) | | | | |

---

## Execution Order

```
Round 1: WU-R1 || WU-R2      (independent notebooks, can run in parallel)
Round 2: Combined comparison table + lab log entry
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
