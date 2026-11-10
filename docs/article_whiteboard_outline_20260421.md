# Article whiteboard outline (21 April 2026)

Transcription of the whiteboard drafted with Alex Fuster on **21 April 2026** (photo taken 15:15). The meeting came four days after Alex and Dominique agreed, on 17 April, that the article presents **both** relevance scoring approaches rather than direct GPT classification alone.

How to read this file:
- **On the board**: what is written, as faithfully as the handwriting allows. `[?]` marks a word I could not read with confidence.
- **Interpretation**: how it maps to the work in this repo. These are my readings, to check with Alex.

---

## 1. The two approaches (top left)

**On the board**

> Approaches
> 1. Relevance score based on **rules applied to extracted features**
> 2. Relevance scoring based on **rules prompted to LLM** (LLM direct)

**Interpretation**

| Board | Repo name | Notebooks |
|---|---|---|
| Approach 1: rules applied to extracted features | Mechanistic scoring: `R1-A` (short text), `R1-B` (PDF) | `relevance_mechanistic.ipynb`, `relevance_mechanistic_pdf.ipynb` |
| Approach 2: rules prompted to the LLM | Direct LLM classification: `R2-A` (short text), `R2-B` (PDF) | `relevance_llm_direct.ipynb`, `relevance_llm_direct_pdf.ipynb` |

The ceiling test from the human annotations (`R0`) is not on the board. It probably belongs in Methods as a check that the scoring rules reproduce the Fuster et al. (2025) categories exactly.

---

## 2. Pipeline diagram (centre): becomes Figure 1

**On the board**

```
Context                     Instructions (prompt engineering)  ↺
                                           │
[Article PDF] ─┐                           ▼            Model
[Abstract]     ├── OR ──▶  LLM                       ──▶  Struct output
[Data paper    ┘           1) Feature extraction          [{ features }]
 description]              2) FE + Scoring                      │
                           3) Scoring only                      ▼
                                                              EVAL ──▶ Outcomes:
[GT] ──▶ Normalizing ── "Same data model" ───────────────────▶      confusion matrix,
                                                                    r[ecall], prec, F1
```

**Interpretation**

- **Inputs, "short" vs "long".** The abstract and the data paper (repository) description are the short texts. The article PDF is the long text. This split becomes the columns of Table 1.
- **The three LLM tasks:**
  1. *Feature extraction*: approach 1. The LLM extracts the features and the rules are applied in code.
  2. *FE + Scoring*: one call extracts the features **and** gives the relevance category. **This variant does not exist in the repo yet.** Confirm whether it is a real third condition or only an idea on the board.
  3. *Scoring only*: approach 2 (direct classification).
- **The prompt-engineering loop** around the instructions is the prompt iteration (vocabulary, modulator fields, rules per mode). Per your 14 April email, it gets its own section in Methods.
- **"Same data model".** The LLM output and the ground truth go through the same Pydantic contract (`DatasetFeaturesExtraction` → `DatasetFeaturesNormalized`) before evaluation. This is the normalization step in `schemas/fuster_features.py` and `groundtruth_eval.py`.
- **EVAL outputs** are the confusion matrix plus precision, recall and F1.

---

## 3. Figures

**On the board** (green)

> Fig 1: conceptual fig. / workflow fig.
> Fig 2: method clarification fig.

**Interpretation**

- **Figure 1, workflow**: the centre diagram above. Inputs → LLM (three tasks) → structured output → evaluation against the normalized ground truth.
- **Figure 2, method clarification**: probably the faded sketch on the left of the board. It shows the anatomy of an LLM call:
  - model / parameters;
  - instructions that provide context (system prompt);
  - reasoning effort `[?]`;
  - prompt;
  - user input;
  - → output.

  It reads as an explainer for an ecology audience: what a "prompt", "reasoning effort" and "user input" are, and which of them differ between approach 1 and approach 2.
- **Bottom sketch**: `scoring --- (taxa) ---> GPT direct`, with a curved arrow. My guess is that it contrasts the two routes. Mechanistic scoring has to go through extracted taxa, the weakest feature, while direct GPT skips that step. To confirm.

---

## 4. Tables

### Table 1: relevance scoring performance (main)

**On the board**: a grid with rows ① and ② (the approaches) and columns **short** and **long**. Each cell holds P, R, F.

**Interpretation**

| Approach | Short text (abstract / data paper description) | Long text (article PDF) |
|---|---|---|
| ① Rules on extracted features | `R1-A`: P, R, F1 | `R1-B`: P, R, F1 |
| ② LLM direct | `R2-A`: P, R, F1 | `R2-B`: P, R, F1 |

The four cells already exist in [`plans/automated_relevance_classification.md`](../plans/automated_relevance_classification.md). Add the baseline from Fuster et al. (2025), the supervised bag-of-words classifier with F1 0.67, as a reference row. Note that the evaluation settings differ.

### Table 2: feature extraction performance (main)

**On the board**: row ① only (approach 1 has features to evaluate), with two column groups: **EBVs** (P, R, F) and **Modulators** (P, R, F).

**Interpretation**

- **EBV features:** `data_type`, `species`, `temp_range_i` / `temp_range_f`, `spatial_range_km2`, `geospatial_info_dataset`, `time_series`.
- **Modulators:** `multispecies`, `threatened_species`, `new_species_science`, `new_species_region`, `bias_north_south`.

These are the fields of `DEFAULT_FIELD_STRATEGIES`. The table probably also needs the short vs long split (abstract / sections / PDF), as in the prompt-eval runs of 27–31 March.

### Evaluation note "②" (right edge)

**On the board**: a circled ② next to `H <?= H  T` and `H == H  F` `[?]`.

**Interpretation**: approach 2 produces a relevance category directly (H = high, M = moderate, L = low, X = not relevant), so it is evaluated on category agreement. The board seems to weigh two rules:
- **exact match** (`H == H`);
- **ordinal / tolerant match** (`<=`: is the prediction at or below the true class?).

The T / F are probably true / false outcomes. To confirm. Either way, it links to the binary (relevant vs not) and four-class macro F1 results already computed.

### Table 3 (marked "+3", optional): confusion matrices

**On the board**: "Confusion matrices: over / under estimating relevance".

**Interpretation**: one confusion matrix per approach and input, showing whether each method tends to overrate or underrate relevance. This answers the question from your 14 April email: which criteria the LLM describes well or badly against the ground truth, and what bias that brings to prioritization.

### Table 4 (marked "+4?", optional): model quality

**On the board**: "Model quality effect on relevance scoring".

**Interpretation**: compare models or reasoning effort, for example `gpt-5-mini` at low effort vs `gpt-5.4` at medium effort (runs and repeatability test of 9 April). The "?" marks it as uncertain.

---

## 5. Supplementary material

**On the board**

> S1. Taxa extraction is shit

**Interpretation**: species (taxa) extraction is the weakest feature, so the analysis moves to the supplement. It is the open species prompt block in `TODO.md` plus the taxonomic refactor plan ([`plans/taxonomic-relevance-refactor.md`](../plans/taxonomic-relevance-refactor.md)). It also explains why approach 2, which avoids extracting taxa, can do better.

**S2**: not visible in the photo. It may have been on a part of the board that was not photographed, or decided verbally.

---

## 6. Case study

**On the board** (red)

> \* Study case: **Insects in north Quebec**

**Interpretation**: an applied demonstration that runs the pipeline on a real priority-gap question. It connects to Alex's insect work in Nunavik: the "Insect data for Quebec - Sentinelles de Nunavik" emails of 15–18 June 2026, and "Pollénisateurs du Nunavik - Projet de Alex" in the coordination notes of 7 May 2026.

---

## 7. Gaps between the board and the repo

| Item on the board | Status in repo (last commit 10 April 2026) |
|---|---|
| Table 1, four cells | Done (`R1-A`, `R1-B`, `R2-A`, `R2-B`) |
| Table 2, EBVs + modulators | Done on the 30-record evaluation subset. Not run on the full corpus |
| Third LLM task, "FE + Scoring" | Not started |
| Table 3, confusion matrices | Partly done (four-class results exist; no figure yet) |
| Table 4, model quality | Partly done (one `gpt-5.4` run and a repeatability test) |
| S1, taxa extraction | Analysis exists; species prompt block still open |
| Figures 1 and 2 | Not started |
| Insect case study | Not started |
| Introduction and Discussion | Being written by Alex (Google Doc "intro&discussion_GPT") |
