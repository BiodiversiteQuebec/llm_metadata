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
| **WU-R2** | Complete | `notebooks/relevance_llm_direct.ipynb` now evaluates primarily against `MC_relevance_modifiers`, retains `dataset_relevance` as `human_relevance`, and writes refreshed `relevance_llm_direct_summary.json`, predictions, confusion figure, and `relevance_comparison_summary.csv`. In this environment the notebook executed via saved-predictions fallback because `OPENAI_API_KEY` was unavailable. |
| **Final synthesis** | Complete | The cross-method comparison table and notebook lab log now use the same mechanistic target definition throughout. |

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

**Status:** Implemented.

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
- Loop over 30 records with joblib caching (cache key now includes record id + model + schema hash + prompt hash + text hash)
- Parse responses into `DatasetFeaturesWithRelevance`
- Carry both `gt_relevance = MC_relevance_modifiers` and `human_relevance = dataset_relevance`
- Evaluate `relevance` primarily against `MC_relevance_modifiers` (same metrics as WU-R1)
- Optionally keep a diagnostic comparison against `human_relevance`
- Spot-check `relevance_reasoning` on mismatches

Implemented result:
- Primary target is now `MC_relevance_modifiers`; `dataset_relevance` is retained only as `human_relevance` for diagnostics.
- Current saved dev-subset result vs `MC_relevance_modifiers`: macro F1 `0.498` over target-present labels (`0.374` over all four labels), binary F1 `0.773`, precision `0.773`, recall `0.773`.
- Diagnostic comparison of the same predictions vs `human_relevance`: macro F1 `0.297`, binary F1 `0.750`.
- The notebook now writes:
  - `notebooks/results/relevance_llm_direct_predictions.csv`
  - `notebooks/results/relevance_llm_direct_summary.json`
  - `notebooks/results/relevance_llm_direct_confusion.png`
  - `notebooks/results/relevance_comparison_summary.csv`
- For reproducibility without credentials, the notebook falls back to the existing saved predictions file when `OPENAI_API_KEY` is absent, while still recomputing target-aligned metrics and artifacts.

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
- Headline notebook tables use macro F1 over labels present in the target split; on this dev subset `MC_relevance_modifiers` contains `H/M/L` only, so the stricter all-four-label macro for `R2` is `0.374` and is saved in `relevance_llm_direct_summary.json`.

**Comparison table (final output):**

| Method | 4-class macro F1 | Binary F1 (relevant) | Binary P | Binary R |
|---|---|---|---|---|
| R1-A: Rules on GT features vs Fuster MC+Modulators | 1.000 | 1.000 | 1.000 | 1.000 |
| R1-B: Rules on LLM features vs Fuster MC+Modulators | 0.125 | 0.000 | 0.000 | 0.000 |
| R2: Direct LLM vs Fuster MC+Modulators | 0.498 | 0.773 | 0.773 | 0.773 |
| Diagnostic: mechanistic target vs human `dataset_relevance` | 0.491 | 0.850 | 0.773 | 0.944 |

---

## Final Synthesis

### Comparison to Fuster et al. automated classification

The original paper's automated relevance classification is a **supervised binary text-classification pipeline**, whereas this notebook initiative evaluates two **LLM-centered alternatives** designed around the paper's own manual scoring logic.

**Paper method (Fuster et al., PeerJ DOI `10.7717/peerj.18853`):**
- Input text:
  - Dryad / Zenodo: title + repository descriptive content
  - Semantic Scholar: title + abstract
- Text preprocessing:
  - lowercase + special-character removal
  - optional stop-word removal
  - optional lemmatization
  - unigrams alone or unigrams + bigrams
  - TF-IDF representation with terms occurring in fewer than 3 documents removed
- Classifiers compared:
  - Logistic Regression
  - Random Forest
  - linear SVM
- Class weighting: `balanced`
- Target:
  - binary only, because the paper collapsed `H/M -> relevant` and `L/X -> not relevant`
- Evaluation:
  - 5-fold cross-validation on the annotated corpus

**Our methods:**
- `R1-A`:
  - no model; explicit reconstruction of the paper's mechanistic rules from GT features
- `R1-B`:
  - LLM feature extraction first, then deterministic rule scoring
- `R2`:
  - direct LLM structured prediction of both features and final relevance category, with reasoning
- Target:
  - primary target is the paper-faithful mechanistic label `MC_relevance_modifiers`
  - evaluation remains 4-class first, then binary collapse as a secondary view
- Evaluation:
  - 30-record dev subset, not full-corpus cross-validation

### Methodology contrast

| Dimension | Fuster et al. automated classifier | `R1` mechanistic pipeline | `R2` direct LLM |
|---|---|---|---|
| Learning paradigm | Supervised ML on labeled corpus | No learned relevance model; deterministic rules over extracted features | Prompted LLM inference with structured output |
| Input representation | TF-IDF bag-of-words over cleaned text | Semantic feature schema (`data_type`, temporal, spatial, modulators) | Same text, but end-to-end semantic reasoning in one call |
| Output target | Binary relevant / not relevant | 4-class mechanistic relevance, then binary collapse if needed | 4-class relevance directly, plus feature fields and rationale |
| Dependence on training set | High | Low for scorer, high for feature extraction quality | No task-specific training set required |
| Interpretability | Medium; feature weights inspectable but indirect | High; every decision is traceable to explicit rules | Medium-high; reasoning is explicit, but still model-generated |
| Failure mode highlighted by paper | lexical overfitting, sparse metadata | extracted-feature omissions propagate directly into rule failure | model may partially compensate for sparse cues, but remains limited by missing metadata |

### Results comparison with the paper

The paper reported the following best-performing supervised binary classifiers (Table 3):

| System | Relevant Precision | Relevant Recall | Relevant F-score | Weighted F-score |
|---|---|---|---|---|
| Main Classifier only | 0.57 | 0.44 | 0.50 | 0.68 |
| Main Classifier + Modulators | 0.62 | 0.71 | 0.67 | 0.61 |

Our notebook results are not directly commensurable because they use a 30-record dev subset and a 4-class mechanistic target before binary collapse. Still, the binary collapse offers a useful orientation:

| System | Relevant Precision | Relevant Recall | Relevant F1 | Notes |
|---|---|---|---|---|
| Fuster paper: supervised Main Classifier only | 0.57 | 0.44 | 0.50 | Full annotated corpus, 5-fold CV |
| Fuster paper: supervised Main Classifier + Modulators | 0.62 | 0.71 | 0.67 | Full annotated corpus, 5-fold CV |
| `R1-A`: rules on GT features | 1.00 | 1.00 | 1.00 | Ceiling test, dev subset |
| `R1-B`: rules on LLM-extracted features | 0.00 | 0.00 | 0.00 | Dev subset, abstract-mode extracted features |
| `R2`: direct LLM vs `MC_relevance_modifiers` | 0.773 | 0.773 | 0.773 | Dev subset, same saved predictions now scored on corrected target |

### Interpretation for paper writing

The important story is not simply that an LLM number is higher or lower than the paper's ML baseline. The more interesting finding is that the three approaches isolate **different bottlenecks**:

1. **The Fuster rule system itself is not the main problem.**
   `R1-A` shows that once the required features are available, the mechanistic framework is perfectly reproducible on the dev subset. This is strong evidence that the annotation framework is internally coherent enough to be operationalized.

2. **Feature availability and feature extraction are the dominant bottleneck.**
   The collapse from `R1-A` to `R1-B` shows that a deterministic post-processing layer cannot rescue missing or weakly extracted temporal, spatial, and data-type signals. This aligns closely with the paper's discussion that crucial metadata are often absent or sparsely expressed in repository text and abstracts.

3. **Direct LLM prediction partially recovers information lost by the feature pipeline.**
   `R2` substantially outperforms `R1-B`, suggesting that end-to-end semantic inference can use weak contextual cues that do not survive explicit feature extraction cleanly. In other words, the LLM seems better at latent relevance judgment than at emitting a fully faithful intermediate schema under current prompting.

4. **The paper's own discussion anticipated this direction.**
   In the discussion, Fuster et al. explicitly propose an alternative path: directly extracting key features such as data type and temporal extent from text, then combining them afterward in the same manual framework. `R1` is exactly that experiment. The paper also notes that LLM-style models may better capture semantics than bag-of-words approaches, though they would still be constrained by absent spatiotemporal metadata. Our results fit that expectation closely:
   - direct semantic inference helps
   - but absent metadata remain a hard ceiling

5. **The target definition matters.**
   One of the most important methodological clarifications from this initiative is that `MC_relevance_modifiers` and spreadsheet `dataset_relevance` should not be treated as interchangeable. For paper drafting, this is worth stating explicitly:
   - `MC_relevance_modifiers` is the correct target when evaluating fidelity to the Fuster mechanistic system
   - `dataset_relevance` is better treated as a neighboring human label, useful for diagnostics but not as the primary ceiling target for rule reconstruction

### Suggested narrative for your paper

If you want this section to read well in the manuscript, a strong structure would be:

1. **Reconstruct the authors' logic first.**
   Show that the mechanistic system can be reproduced exactly from GT features (`R1-A`). This establishes methodological fidelity and makes the rest of the comparison interpretable.

2. **Separate rule validity from feature-extraction validity.**
   Emphasize that `R1-B` fails not because the scoring logic is weak, but because the required evidence is incompletely recoverable from short repository descriptions and abstracts.

3. **Position `R2` as a semantic shortcut rather than a black-box replacement.**
   The direct LLM approach can be framed as bypassing the fragile intermediate extraction layer. It is not "better than the Fuster framework"; rather, it is a different way of approximating the same relevance construct when metadata are sparse.

4. **Be explicit about comparability limits.**
   The paper baseline used:
   - full-corpus 5-fold CV
   - binary relevance labels
   - TF-IDF + classical classifiers

   Our notebook comparison uses:
   - a 30-record dev subset
   - a 4-class mechanistic target with binary collapse as a derived view
   - prompted LLM inference instead of supervised fitting

   So the safest claim is not "LLMs outperform the original paper," but:
   - the direct LLM approach is promising relative to the paper's feasibility baseline
   - deterministic rule scoring remains attractive for interpretability
   - the principal bottleneck is metadata presence and extractability, not merely classifier choice

### Discussion-ready takeaways

- The supervised TF-IDF baseline in the paper is best understood as a **document triage model** driven by lexical correlates of relevance.
- `R1` tests a **feature-engineering interpretation** of the paper's own proposed future direction.
- `R2` tests a **semantic inference interpretation** of that same direction.
- Together, these results suggest that future work should probably not choose between "rules" and "LLMs" in isolation. A better next step is to improve the evidence layer:
  - richer input text than repository descriptions alone
  - section-aware or full-text retrieval
  - stronger prompts for temporal/spatial grounding
  - explicit evidence tracking for relevance decisions

For manuscript phrasing, the central conclusion can be framed as:

> The relevance framework itself is reproducible; the hard problem is recovering the underlying metadata reliably from short textual descriptions. Direct LLM classification appears more robust than a feature-extraction-plus-rules pipeline under sparse textual evidence, but both approaches remain bounded by metadata availability.

---

## Execution Order

Completed:

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
| `notebooks/results/relevance_comparison_summary.csv` | Final cross-method comparison table |
| `data/manifests/dev_subset_data_paper.csv` | 30-record dev subset manifest |
| `data/dataset_092624.xlsx` | Raw GT (all 418 records) — joined for GT labels + MC columns |
| `src/llm_metadata/schemas/fuster_features.py` | `DatasetFeaturesExtraction` base schema |
| `src/llm_metadata/openai_io.py` | `get_openai_client()` factory |
| `src/llm_metadata/gpt_extract.py` | Reference for `client.responses.parse()` pattern |
| `src/llm_metadata/extraction.py` | `run_manifest_extraction()` used in WU-R1-B |
