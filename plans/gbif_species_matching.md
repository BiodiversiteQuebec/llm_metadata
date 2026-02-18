# GBIF Species Matching & Evaluation Matcher Refactor

## Context

The `species` field in our extraction/evaluation pipeline is a `list[str]` containing a mix of scientific binomials, common names, and count+group descriptions. Evaluation currently relies on string comparison (exact, fuzzy, or enhanced heuristic) which cannot recognize that "wood turtle" and "Glyptemys insculpta" refer to the same taxon. Adding GBIF backbone resolution enables semantic species comparison by taxon key.

This also addresses accumulated tech debt: `compare_models()` in `groundtruth_eval.py` has 3 matching strategies with duplicated TP/FP/FN logic and an orphaned `EnhancedSpeciesMatchConfig` class. Adding a 4th strategy (GBIF) without refactoring would make it worse.

**Outcome:** GBIF-based species matching as a new evaluation strategy, cleanly integrated via a strategy pattern that simplifies the existing code.

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
  3. Parenthetical split: `"wood turtle (Glyptemys insculpta)"` -> scientific + vernacular
  4. Scientific detection via `looks_scientific()` heuristic (existing logic)
  5. Set `is_group_description=True` when count was present or name is a broad group term
- Top-level function `parse_species_string(raw: str) -> dict` used by the validator

**Files to modify:**
- `groundtruth_eval.py` — replace `_extract_species_parts()` calls with `ParsedTaxon` import
- `schemas/__init__.py` — export `ParsedTaxon`

**Tests:** `tests/test_species_parsing.py`
- Scientific binomials: `"Tamias striatus"` -> scientific
- Common names: `"caribou"` -> vernacular
- Parenthetical both orders: `"wood turtle (Glyptemys insculpta)"`, `"Glyptemys insculpta (wood turtle)"`
- Count+group: `"41 fish mock species"` -> count=41, vernacular="fish", is_group=True
- Multi-word groups: `"ground-dwelling beetles"` -> vernacular
- Edge cases: empty string, None-like values

---

### WU-2: Refactor evaluation matchers to strategy pattern
`model: sonnet` | deps: WU-1

Refactor `compare_models()` in `groundtruth_eval.py` to eliminate duplicated set-comparison logic.

**New type:**
```python
MatchStrategy = Callable[[list[str], list[str]], tuple[set[str], set[str]]]
```

**Changes to `EvaluationConfig`:**
- Add `field_matchers: dict[str, MatchStrategy]` (default empty)
- Keep `fuzzy_match_fields`, `enhanced_species_matching`, `enhanced_species_threshold` as backward-compatible shorthands
- Internal resolution order: `field_matchers[field]` > `enhanced_species_matching` (if field=="species") > `fuzzy_match_fields[field]` > standard normalization

**Matcher factories (in `groundtruth_eval.py`):**
```python
def fuzzy_matcher(threshold: int = 80) -> MatchStrategy
def enhanced_species_matcher(threshold: int = 70) -> MatchStrategy
```

**Refactor `compare_models()`:**
- Extract shared set-comparison -> FieldResult construction into `_compare_sets()` helper
- Single code path for all list-field matching: resolve strategy -> call it -> `_compare_sets()`
- Delete orphaned `EnhancedSpeciesMatchConfig` (line 870)

**Files:**
- `groundtruth_eval.py` — refactor internals, add factories, update imports
- Export `MatchStrategy`, `fuzzy_matcher`, `enhanced_species_matcher` from module

**Tests:** Update `tests/test_evaluation_fuzzy.py`
- Existing tests pass unchanged (backward compat via shorthand flags)
- New tests using `field_matchers={"species": enhanced_species_matcher(70)}` produce identical results
- Test `_compare_sets()` helper directly

---

### WU-3: `gbif.py` — GBIF Species Match API wrapper
`model: sonnet` | deps: WU-1

**New file:** `src/llm_metadata/gbif.py`

Follow `semantic_scholar.py` patterns: module docstring, `requests`, `joblib.Memory` cache, logging.

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
    # ... higher taxonomy fields
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
- Test `ParsedTaxon` -> GBIF routing (scientific preferred over vernacular)
- Test confidence threshold filtering
- Test caching behavior

---

### WU-4: `gbif_matcher()` — evaluation strategy + integration
`model: sonnet` | deps: WU-2, WU-3

Wire GBIF matching into the evaluation framework via the strategy pattern.

**New factory in `gbif.py`:**
```python
def gbif_matcher(confidence_threshold: int = 80, accept_higherrank: bool = True) -> MatchStrategy:
```

**Logic:**
1. Resolve both `true_items` and `pred_items` via `resolve_species_list()`
2. Build normalized sets using GBIF keys as canonical identifiers (e.g., `"gbif:8024251"`)
3. Items that fail GBIF resolution: fall back to lowercase string (existing behavior)
4. Return `(true_set, pred_set)` for standard set intersection

**Usage:**
```python
config = EvaluationConfig(
    field_matchers={"species": gbif_matcher(confidence_threshold=80)}
)
```

**Files:**
- `gbif.py` — add `gbif_matcher` factory
- `schemas/__init__.py` — export `gbif_matcher`

**Tests:** `tests/test_evaluation_gbif.py`
- Mock GBIF: "wood turtle" -> key 8024251, "Glyptemys insculpta" -> key 8024251 -> TP
- Mock GBIF: "Tamias striatus" -> key 2437752, no match for "caribou" -> falls back to string
- "41 fish mock species" -> HIGHERRANK to Actinopterygii (accepted)
- Test alongside other field matchers (GBIF for species, fuzzy for data_type)

---

## Execution Rounds

```
Round 1:  WU-1 (species_parsing)     <- no deps, start immediately
          model: sonnet

Round 2:  WU-2 (matcher refactor)  ||  WU-3 (gbif.py)    <- both depend on WU-1 only
          model: sonnet                model: sonnet        <- run in parallel

Round 3:  WU-4 (gbif_matcher integration)                  <- depends on WU-2 + WU-3
          model: sonnet
```

## Verification

1. `python -m pytest tests/test_species_parsing.py` — parsing logic
2. `python -m pytest tests/test_evaluation.py tests/test_evaluation_fuzzy.py` — backward compat (existing tests pass unchanged)
3. `python -m pytest tests/test_gbif.py` — GBIF wrapper with mocked API
4. `python -m pytest tests/test_evaluation_gbif.py` — GBIF matcher integration
5. `python -m pytest tests/` — full suite green
6. Notebook smoke test: run GBIF matcher on a few real species strings against live API to validate end-to-end
