# Table S2 — Main Classifier Tiebreaker Decision Rules

**Source:** Fuster-Calvo et al. (2025), PeerJ 13:e18853. Supplemental Material S2.
**Converted from:** `Table_S2.docx`

---

## Authors' Original Table

> Table S2. Main classifier relevance assignment in case of disagreement. H: highly relevant, M: Moderate, L: low, X: non-relevant.

| Data type | Spatial range | Temporal range | Final relevance category |
|---|---|---|---|
| H | M (resp. L) | L (resp. M) | M |
| H | M (resp. X) | X (resp. M) | L |
| H or M | L (resp. X) | X (resp. L) | L |
| Other cases | — | — | data type relevance |

**Reading the "(resp.)" notation:** Each row covers two symmetric patterns. "M (resp. L)" and "L (resp. M)" means: spatial=M + temporal=L **or** spatial=L + temporal=M. The rule is symmetric in the two spatio-temporal classifiers.

---

## Equivalent Algorithmic Rule

The 4-row table can be expressed as a two-step algorithm:

**Step 1 — Special case (H data type with any X in spatio-temporal):**

If `data_type = H` AND (`temporal = X` OR `spatial = X`) → **result = L**

**Step 2 — General rule (all other tiebreaker cases):**

**result = min(data_type, max(temporal, spatial))**

Where score order is: H > M > L > X.

**Equivalence proof:** The general rule `min(dt, max(t,s))` produces the data type score when `max(t,s) >= dt` (i.e., at least one spatio-temporal classifier matches or exceeds the data type), and produces the best spatio-temporal score otherwise (capping the result below the data type). The special case overrides this for H + X combinations, where the general rule would give `min(H, M) = M` but the authors assign L instead — a stricter penalty for missing spatio-temporal data when data type is H.

---

## Empirical Validation

We verified the algorithmic rule against all 55 tiebreaker cases in the full annotated dataset (`data/dataset_092624.xlsx`, n=418). The rule matches 100% of observed `MC_relevance` outcomes.

### All 17 observed tiebreaker patterns

| Data type | Temporal | Spatial | MC_relevance | Rule derivation | n |
|---|---|---|---|---|---|
| H | L | M | **M** | min(H, max(L,M)) = M | 1 |
| H | L | X | **L** | Special case: H + X → L | 13 |
| H | M | L | **M** | min(H, max(M,L)) = M | 10 |
| H | M | X | **L** | Special case: H + X → L | 7 |
| H | X | L | **L** | Special case: H + X → L | 5 |
| H | X | M | **L** | Special case: H + X → L | 1 |
| L | H | M | **L** | min(L, max(H,M)) = L | 1 |
| L | H | X | **L** | min(L, max(H,X)) = L | 1 |
| L | M | H | **L** | min(L, max(M,H)) = L | 3 |
| L | M | X | **L** | min(L, max(M,X)) = L | 1 |
| L | X | H | **L** | min(L, max(X,H)) = L | 4 |
| M | L | H | **M** | min(M, max(L,H)) = M | 1 |
| M | L | X | **L** | min(M, max(L,X)) = L | 2 |
| M | X | H | **M** | min(M, max(X,H)) = M | 2 |
| M | X | L | **L** | min(M, max(X,L)) = L | 1 |
| X | L | H | **X** | min(X, max(L,H)) = X | 1 |
| X | M | H | **X** | min(X, max(M,H)) = X | 1 |

**Total tiebreaker cases: 55 / 180 records with all three MC scores (31%).**

---

## Key Observations

1. **Data type is a ceiling, not a floor.** The result is never above the data type score. Strong spatio-temporal cannot rescue a weak data type.

2. **The H+X penalty is asymmetric.** When `data_type=H` and either spatio-temporal score is X, the result is always L — not M. This is stricter than the general rule would give (`min(H,M)=M`), effectively requiring at minimum *some* spatial or temporal signal to justify an H data type's contribution.

3. **X in data type is terminal.** All records with `data_type=X` result in X, regardless of temporal and spatial scores. Modulators cannot override this (paper: "Only relevant datasets could be upgraded by Modulators").

4. **L data type cannot be upgraded by spatio-temporal.** Even with temporal=H and spatial=H, `data_type=L` stays at L (`min(L,H)=L`). The rule is asymmetric: strong spatio-temporal can sustain an M data type but cannot rescue an L.

5. **M data type is sustained by a single H in spatio-temporal.** M+X+H → M and M+L+H → M. But M+L+X → L and M+X+L → L: if neither spatio-temporal reaches H, M is penalized down.

---

## Impact on R1-A Rule Implementation

Our original `majority_vote()` function used: data_type wins tiebreaker outright, then penalized by 1 level for each X present. The correct rule is `min(data_type, max(temporal, spatial))` with the H+X special case.

Dev-subset records affected by the incorrect tiebreaker:

| id | Pattern (dt+temp+spatial) | Our mc | Correct mc | GT |
|---|---|---|---|---|
| 5 | H+L+X | M | **L** | M |
| 9 | H+L+X | M | **L** | L |
| 27 | H+M+X | M | **L** | M |
| 31 | H+M+X | M | **L** | L |
| 91 | H+M+X | M | **L** | L |
| 175 | H+X+L | M | **L** | L |

The correct tiebreaker reduces over-prediction by scoring these H+X patterns as L instead of M.
