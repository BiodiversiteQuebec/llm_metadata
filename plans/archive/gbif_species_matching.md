# GBIF Species Matching — Enrichment-Based Evaluation

## Context

The `species` field in our extraction/evaluation pipeline is a `list[str]` containing a mix of scientific binomials, common names, and count+group descriptions. Evaluation currently relies on string comparison (exact, fuzzy, or enhanced heuristic) which cannot recognize that "wood turtle" and "Glyptemys insculpta" refer to the same taxon.

**Approach:** Rather than refactoring the evaluation matcher abstraction, we add GBIF resolution as a preprocessing enrichment step that produces `gbif_keys: list[int]` for evaluation alongside the existing raw `species` field.

Architecture note:
- The canonical architecture now lives in `plans/model_hierarchy_enrichment.md`.
- `gbif_keys` belongs on `DatasetFeaturesEvaluation`, not on the extraction contract shown to the LLM.
- Source/provenance metadata is no longer the precedent here; that metadata belongs on `DataPaperRecord`.

The existing evaluation framework handles both fields independently in a single run:
- `species` → enhanced species string matching (existing, unchanged)
- `gbif_keys` → simple set comparison on integer taxon IDs (trivial, no new matching logic)

Strategy comparison is just `report.metrics_for("species")` vs `report.metrics_for("gbif_keys")`.

**Outcome:** GBIF-based species evaluation as a new field alongside existing string-based evaluation, with zero changes to the evaluation framework internals.

---

## Work Units

### WU-1: `species_parsing.py` — shared preprocessing module
`model: sonnet` | deps: none

Extract and extend `_extract_species_parts()` from `groundtruth_eval.py` into a new shared module.

**New file:** `src/llm_metadata/species_parsing.py`

**`ParsedTaxon` Pydantic model:**
- Fields: `original: str`, `scientific: str | None`, `vernacular: str | None`, `count: int | None`, `is_group_description: bool`
- `model_validator(mode='before')` accepts raw `str` input and parses it
- Preprocessing pipeline:
  1. Strip leading count via `r'^\d+\s+'` (capture count as int)
  2. Strip trailing noise words: "mock species", "species" suffix
  3. Parenthetical split: `"wood turtle (Glyptemys insculpta)"` → scientific + vernacular
  4. Scientific detection via `looks_scientific()` heuristic (existing logic from `groundtruth_eval.py:727-734`)
  5. Set `is_group_description=True` when count was present or name is a broad group term
- Top-level function `parse_species_string(raw: str) -> dict` used by the validator

**Files to modify:**
- `groundtruth_eval.py` — replace `_extract_species_parts()` calls (line 791, 792) with `ParsedTaxon` import
- `schemas/__init__.py` — export `ParsedTaxon`

**Tests:** `tests/test_species_parsing.py`
- Scientific binomials: `"Tamias striatus"` → scientific
- Common names: `"caribou"` → vernacular
- Parenthetical both orders: `"wood turtle (Glyptemys insculpta)"`, `"Glyptemys insculpta (wood turtle)"`
- Count+group: `"41 fish mock species"` → count=41, vernacular="fish", is_group=True
- Multi-word groups: `"ground-dwelling beetles"` → vernacular
- Edge cases: empty string, None-like values

---

### WU-2: `gbif.py` — GBIF Species Match API wrapper
`model: sonnet` | deps: WU-1

**New file:** `src/llm_metadata/gbif.py`

Follow `semantic_scholar.py` patterns: module docstring, `requests`, `joblib.Memory` cache, logging, `_get()` with polite delay.

**Core types:**
```python
@dataclass
class GBIFMatch:
    gbif_key: int
    scientific_name: str
    canonical_name: str
    rank: str
    confidence: int
    match_type: str  # EXACT, FUZZY, HIGHERRANK, NONE
    kingdom: str | None
```

**Functions:**
- `match_species(name: str, kingdom: str | None = None, strict: bool = False) -> GBIFMatch | None`
  - `GET https://api.gbif.org/v1/species/match?name={name}&verbose=true`
  - Returns `None` if `matchType == "NONE"` or confidence below threshold
  - `@memory.cache` for deterministic re-runs
  - Small delay between calls (politeness, no documented rate limit)

- `resolve_species_list(species: list[str], confidence_threshold: int = 80, accept_higherrank: bool = True) -> list[ResolvedTaxon]`
  - Uses `ParsedTaxon` to preprocess each string
  - Sends `.scientific` first, falls back to `.vernacular`
  - Skips or attempts group descriptions based on `accept_higherrank`
  - Returns `ResolvedTaxon(original, parsed, gbif_match)` for each item

**Tests:** `tests/test_gbif.py`
- Mock `requests.get` responses for EXACT, FUZZY, HIGHERRANK, NONE matchTypes
- Test `ParsedTaxon` → GBIF routing (scientific preferred over vernacular)
- Test confidence threshold filtering
- Test caching behavior

---

### WU-3: Evaluation field + lookup assembly
`model: sonnet` | deps: WU-2

Add `gbif_keys` to the evaluation-oriented feature contract and assemble it from GBIF lookup payloads.

**Schema change in `schemas/fuster_features.py`:**
```python
gbif_keys: Optional[list[int]] = Field(
    None,
    description="GBIF backbone taxon keys resolved from species field. "
                "Populated by preprocessing, not extracted by LLM."
)
```

**Lookup + assembly pattern:**
```python
resolved = resolve_species_list(model.species, confidence_threshold, accept_higherrank)
enriched = DatasetFeaturesEvaluation.from_extraction(model, gbif=resolved)
```

`gbif.py` should perform the external lookup and return typed payloads. `DatasetFeaturesEvaluation` should provide the pure constructor/copy helper that maps those payloads to `gbif_keys` and any related derived fields.

**Notebook usage pattern:**
```python
# Preprocess both sides
true_enriched = {
    doi: DatasetFeaturesEvaluation.from_extraction(
        m, gbif=resolve_species_list(m.species or [])
    )
    for doi, m in true_by_id.items()
}
pred_enriched = {
    doi: DatasetFeaturesEvaluation.from_extraction(
        m, gbif=resolve_species_list(m.species or [])
    )
    for doi, m in pred_by_id.items()
}

# Single evaluation run — both fields evaluated independently
report = evaluate_indexed(
    true_by_id=true_enriched,
    pred_by_id=pred_enriched,
    fields=["species", "gbif_keys", ...],
    config=EvaluationConfig(enhanced_species_matching=True),
)

# Compare strategies
report.metrics_for("species")     # enhanced string matching P/R/F1
report.metrics_for("gbif_keys")   # set comparison on taxon IDs P/R/F1
```

**Files:**
- `schemas/fuster_features.py` — add `gbif_keys` to the evaluation model
- `gbif.py` — add lookup helpers returning typed payloads
- `schemas/fuster_features.py` or adjacent schema module — add evaluation-model constructor/copy helper
- `schemas/__init__.py` — ensure exports are updated

**Tests:** `tests/test_gbif_enrichment.py`
- Build evaluation model from known species lookup payload → `gbif_keys` populated
- Build evaluation model with `species=None` → `gbif_keys` stays None
- Build evaluation model with unmatchable species payload → `gbif_keys` empty/None
- End-to-end: resolve both sides, build evaluation models, run `evaluate_indexed`, verify `gbif_keys` metrics exist

---

## Execution Rounds

```
Round 1:  WU-1 (species_parsing)        ← no deps, start immediately
          model: sonnet

Round 2:  WU-2 (gbif.py)               ← depends on WU-1
          model: sonnet

Round 3:  WU-3 (schema + enrichment)    ← depends on WU-2
          model: sonnet
```

Note: WU-2 and WU-3 could be a single WU, but separating them allows the GBIF API wrapper to be tested in isolation before wiring into the schema/evaluation.

## Verification

1. `uv run python -m pytest tests/test_species_parsing.py` — parsing logic
2. `uv run python -m pytest tests/test_gbif.py` — GBIF wrapper with mocked API
3. `uv run python -m pytest tests/test_gbif_enrichment.py` — enrichment + eval integration
4. `uv run python -m pytest tests/test_evaluation.py tests/test_evaluation_fuzzy.py` — existing tests unchanged (backward compat)
5. `uv run python -m pytest tests/` — full suite green
6. Notebook smoke test: enrich a few real records via live GBIF API, run evaluation, compare `species` vs `gbif_keys` metrics
