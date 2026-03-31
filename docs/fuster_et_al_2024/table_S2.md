# Table S2 — Tiebreaker Decision Rules for Main Classifier Majority Vote

**Source:** Fuster-Calvo et al. (2025), PeerJ 13:e18853. Supplemental Material S2.  
**Status:** Not available in the main PDF or TEI XML. **Reconstructed empirically** from the full annotated dataset (`data/dataset_092624.xlsx`, n=418) by identifying all 55 records where the three Main Classifiers (Data type, Temporal range, Spatial range) returned three different scores (no majority), then fitting the decision rule to the observed `MC_relevance` outcomes. Rule matches all 55 cases (100%).

---

## Context

The majority vote across the three Main Classifiers (Data type, Temporal range, Spatial range) produces a clear winner when at least two of three classifiers agree. When all three differ (one H, one M, one L, or any combination involving X), a tiebreaker is needed. The paper states (Methods §"Dataset relevance assignment"):

> "In case of non-majority value, we create decision rules as indicated in Table S2. By default, the relevance score of the dataset type was selected as the final relevance category, penalized if the spatio-temporal relevance was Non-relevant, Low, or Moderate."

---

## Reconstructed Rule

**Step 1 — Special case (X in spatio-temporal with H data type):**

If `Data type = H` AND (`Temporal = X` OR `Spatial = X`) → **result = L**

**Step 2 — General rule (all other patterns):**

**result = min(Data type, max(Temporal, Spatial))**

Where score order is: H > M > L > X.

In plain language: the data type score is selected as the base, then capped by the better of the two spatio-temporal classifiers. If neither temporal nor spatial reaches the data type's level, the result is pulled down to the best spatio-temporal score.

---

## Full Decision Table (all 17 observed tiebreaker patterns)

| Data type | Temporal | Spatial | MC_relevance | Rule derivation | n |
|---|---|---|---|---|---|
| H | L | M | **M** | min(H, max(L,M)) = min(H,M) = M | 1 |
| H | L | X | **L** | Special case: H + X-in-spatial → L | 13 |
| H | M | L | **M** | min(H, max(M,L)) = min(H,M) = M | 10 |
| H | M | X | **L** | Special case: H + X-in-spatial → L | 7 |
| H | X | L | **L** | Special case: H + X-in-temporal → L | 5 |
| H | X | M | **L** | Special case: H + X-in-temporal → L | 1 |
| L | H | M | **L** | min(L, max(H,M)) = min(L,H) = L | 1 |
| L | H | X | **L** | min(L, max(H,X)) = min(L,H) = L | 1 |
| L | M | H | **L** | min(L, max(M,H)) = min(L,H) = L | 3 |
| L | M | X | **L** | min(L, max(M,X)) = min(L,M) = L | 1 |
| L | X | H | **L** | min(L, max(X,H)) = min(L,H) = L | 4 |
| M | L | H | **M** | min(M, max(L,H)) = min(M,H) = M | 1 |
| M | L | X | **L** | min(M, max(L,X)) = min(M,L) = L | 2 |
| M | X | H | **M** | min(M, max(X,H)) = min(M,H) = M | 2 |
| M | X | L | **L** | min(M, max(X,L)) = min(M,L) = L | 1 |
| X | L | H | **X** | min(X, max(L,H)) = min(X,H) = X | 1 |
| X | M | H | **X** | min(X, max(M,H)) = min(X,H) = X | 1 |

**Total tiebreaker cases in dataset: 55 / 180 records with all three MC scores (31%).**

---

## Key Observations

1. **Data type is the anchor, not the tiebreaker winner.** The result is never *above* the data type score. Even if both temporal and spatial are H, a data_type=L record stays at L.

2. **The H+X penalty is asymmetric.** When data_type=H and either spatio-temporal score is X, the result is always L — not M. This means the X classifier acts as a hard downgrade when combined with the highest data type, effectively requiring at minimum some spatial or temporal signal to justify an H data type's contribution.

3. **X in data type is terminal.** All records with data_type=X result in X, regardless of temporal and spatial scores. Modulators cannot override this (paper: "Only relevant datasets could be upgraded by Modulators").

4. **L data type cannot be upgraded by spatio-temporal.** Even with temporal=H and spatial=H, data_type=L stays at L. The rule is asymmetric: strong spatio-temporal can save a mid-tier data type (M), but cannot rescue a weak one (L).

5. **M data type is saved by a single H in spatio-temporal.** M+L+H → M and M+X+H → M: as long as one spatio-temporal score is H, M data type stays at M. But M+L+X → L and M+X+L → L: if neither reaches H, M is penalized to L.

---

## Impact on Our R1-A Rule Implementation

Our `majority_vote()` function uses a different tiebreaker: **data_type wins outright, then penalized by 1 level for each X present**. The actual rule is **min(data_type, max(temporal, spatial))** with the H+X special case.

Errors caused by our incorrect tiebreaker (from the 30-record dev subset):

| id | Pattern (dt+temp+spatial) | Our pred | Authors' MC | GT | Issue |
|---|---|---|---|---|---|
| 5 | H+L+X | H (after modulator) | L (before modulator) | M | Our mc=M (correct), but we got M by wrong reasoning: authors' MC=L, not M |
| 27 | H+M+X | H (after modulator) | L (before modulator) | M | Our mc=M; correct rule → L |
| 31 | H+M+X | M (before modulator) | L | L | Our mc=M; correct rule → L |
| 91 | H+M+X | M (before modulator) | L | L | Same |
| 101 | X+M+H | L (after modulator) | X | L | Our mc=X (data_type=X is correct per rule) |
| 175 | H+X+L | M (mc before mod) | L | L | Our mc=M; correct rule → L |

The correct rule would change R1-A mc_relevance for several records, and critically **reduce over-prediction** by scoring H+M+X and H+X+M patterns as L instead of M.
