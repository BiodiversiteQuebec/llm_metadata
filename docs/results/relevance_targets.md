# Relevance targets: human label versus rule label

Every relevance result in the article is shown against two targets. This note
says how far apart the two targets are, because that gap is the realistic
ceiling for any system that predicts relevance.

- **Human label**: column `dataset_relevance` in `data/dataset_092624.xlsx`. One
  person's overall judgment: H, M, L or X.
- **Rule label**: column `MC_relevance_modifiers`. The output of the Fuster
  rules (three classifiers by majority vote, then a one-level upgrade when a
  modulator applies). The rules are coded in `src/llm_metadata/relevance_rules.py`.

Numbers come from `uv run python scripts/audit_relevance_rules.py`.

## What was compared

- Valid records only (`valid_yn = yes`): 299.
- Only records that carry both labels as a class (H, M, L or X): **180**. The
  other 119 are marked `No dataset` or `cant access` and have no relevance class.
  The held-out set has 68 valid records, 42 of them with both labels.
- Two readings: **four classes** (H, M, L, X) and **binary**. Binary means H and M
  are "relevant", L and X are "not relevant". This is the same collapse the earlier
  notebooks used (`binary_collapse` in `notebooks/relevance_mechanistic.ipynb`
  and its PDF variant); the module function `binarize` keeps it.
- Agreement is the share of records with the same label. Cohen's kappa is the
  agreement beyond chance (0 = chance, 1 = perfect). Roughly: 0.2 to 0.4 is fair,
  0.4 to 0.6 is moderate.

## All records with both labels (180)

Rows are the human label, columns the rule label.

| human \ rule | H | M | L | X | total |
|---|---|---|---|---|---|
| H | 21 | 1 | 1 | 0 | 23 |
| M | 25 | 20 | 12 | 0 | 57 |
| L | 5 | 23 | 39 | 9 | 76 |
| X | 0 | 3 | 4 | 17 | 24 |
| total | 51 | 47 | 56 | 26 | 180 |

| human \ rule | relevant | not relevant | total |
|---|---|---|---|
| relevant | 67 | 13 | 80 |
| not relevant | 31 | 69 | 100 |
| total | 98 | 82 | 180 |

- Four classes: 97 of 180 agree, **53.9 %**, kappa 0.37.
- Binary: 136 of 180 agree, **75.6 %**, kappa 0.52.

This matches the expectation (about 54 % and 76 %).

## Dev subset (30 records)

| human \ rule | H | M | L | X | total |
|---|---|---|---|---|---|
| H | 6 | 0 | 0 | 0 | 6 |
| M | 4 | 7 | 1 | 0 | 12 |
| L | 0 | 5 | 6 | 0 | 11 |
| X | 0 | 0 | 1 | 0 | 1 |
| total | 10 | 12 | 8 | 0 | 30 |

| human \ rule | relevant | not relevant | total |
|---|---|---|---|
| relevant | 17 | 1 | 18 |
| not relevant | 5 | 7 | 12 |
| total | 22 | 8 | 30 |

- Four classes: 19 of 30, **63.3 %**, kappa 0.46.
- Binary: 24 of 30, **80.0 %**, kappa 0.56.

## Held-out set (aggregate only, 42 records with both labels)

| human \ rule | H | M | L | X | total |
|---|---|---|---|---|---|
| H | 4 | 0 | 0 | 0 | 4 |
| M | 6 | 3 | 2 | 0 | 11 |
| L | 2 | 7 | 9 | 2 | 20 |
| X | 0 | 0 | 1 | 6 | 7 |
| total | 12 | 10 | 12 | 8 | 42 |

| human \ rule | relevant | not relevant | total |
|---|---|---|---|
| relevant | 13 | 2 | 15 |
| not relevant | 9 | 18 | 27 |
| total | 22 | 20 | 42 |

- Four classes: 22 of 42, **52.4 %**, kappa 0.36.
- Binary: 31 of 42, **73.8 %**, kappa 0.48.

The held-out numbers are counts only. No record is shown.

## Reading the tables

- The two labels agree about half the time on four classes and three times in
  four on the binary reading. A system cannot be expected to beat these figures
  against either target by much. Show them next to every relevance result.
- The disagreement is not random. The rules give a higher class than the human
  in 60 of the 83 disagreeing four-class cases (for example 25 records the human
  calls M that the rules call H). Part of this comes from the upgrade for
  multispecies datasets (the multispecies flag counts as a modulator).
- The dev subset agrees more (63 %) than the full corpus (54 %). Results tuned on
  dev will look better against the ceiling than they will on new records.

## How well the rules reproduce the released rule columns

Reproduction of the five `MC_*` columns by the coded rules, on the 180 valid
records that carry a class:

| Column | Reproduced | Dev | Other valid | Held-out |
|---|---|---|---|---|
| MC_dataset_type | 180 / 180 | 30 / 30 | 108 / 108 | 42 / 42 |
| MC_temporal_range | 179 / 180 | 30 / 30 | 107 / 108 | 42 / 42 |
| MC_spatial_range | 178 / 180 | 30 / 30 | 107 / 108 | 41 / 42 |
| MC_relevance | 178 / 180 | 30 / 30 | 107 / 108 | 41 / 42 |
| MC_relevance_modifiers | 178 / 180 | 30 / 30 | 107 / 108 | 41 / 42 |

On the held-out set, one record is not reproduced for spatial range and the same
one for the two final columns. Nothing more is said about it.

Mismatches outside the held-out set (two records):

- Record 344, temporal range. Data from 1690 to 2004 (315 years), released class
  L. The rules say H. Looks like an annotation slip.
- Record 176, spatial range. The annotated value is the text `0,5` (comma as
  decimal mark). The cleaning step reads it as 0.5 km2 (class L); the released
  class is X, as if the value had not been read. Because no temporal range is given
  either, the released final class is X instead of L.

## One change from the notebook

The notebook matched the whole data type text at once. For `density, species
richness` the phrase `species richness` (L) took precedence and the result was L,
but the released class is H. The module now classifies each comma-separated type
and keeps the best one. This fixes record 131 and changes no other record.

## Thresholds and where they come from

| Rule | Cut points | Source |
|---|---|---|
| Spatial range | more than 15,000 km2 = H; 5,000 to 15,000 = M; below 5,000 = L; missing = X | Paper results text gives these three bins; boundary handling reconstructed |
| Temporal range | duration in inclusive calendar years (end - start + 1): 12 or more = H; 3 to 11 = M; 1 to 2 = L; missing = X | **Reconstructed.** Paper prose says "more than 10 years" for H; the released column fits 12 or more |
| Dataset type | abundance, density, EBV genetic = H; distribution, presence-absence = M; presence-only, non-EBV genetic, species richness = L; other, unknown, empty = X | Paper Table 2; plain "genetic analysis" counted as non-EBV is reconstructed |
| Majority vote | two or more equal classes win; all different: H with an X for time or space gives L, otherwise min(dataset type, max(time, space)) | Paper Table S2 |
| Modulators | one level up if any of multispecies, threatened, new species to science, new species to region, north-south bias is true; X goes to L | **Reconstructed** from released labels. The paper says only relevant datasets are upgraded and treats multispecies differently |

The rules do not use the annotated duration class (`temporal_duration_y`, values
such as `<1`, `>1`). They compute duration from start and end years.
