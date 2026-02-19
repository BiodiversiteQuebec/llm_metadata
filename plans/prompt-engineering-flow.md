# Prompt Engineering Flow

## Context & Motivation

Running full batch extraction with unrefined prompts wastes API spend and produces misleading aggregate metrics (Micro F1 0.202 on 288 records, $1.91). Per-field analysis reveals that failures have different root causes — some are prompt problems, some are eval problems, some are irrelevant fields dragging scores down. Eval hardening must come first so prompt engineering iterations produce reliable signal.

## Phase 1: Evaluation Hardening

### Decisions (from discussion 2026-02-19)

| Decision | Choice |
|---|---|
| Aggregate metrics | Not a priority; per-field analysis matters |
| Drop fields | `temporal_range` (redundant with `temp_range_i`/`temp_range_f`), `referred_dataset` (too rare, noisy GT) |
| Audit fields | `spatial_range_km2` (numeric tolerance TBD), `bias_north_south` (enough positive examples?), `geospatial_info` / `data_type` (enum coverage of GT vocabulary) |
| Matching strategy | Per-field, declared in `FieldEvalStrategy` registry on `EvaluationConfig` |
| Normalization symmetry | Already handled — `DatasetFeaturesNormalized` only adds validators for manual data cleaning, doesn't change field semantics |
| Backward compat | Old `EvaluationConfig` parameters (`fuzzy_match_fields`, `enhanced_species_matching`, `enhanced_species_threshold`) kept; new `field_strategies` takes precedence when populated |
| Observation logging | Per-field notes after each eval run, tracked in lab log |

### Field Eval Registry (source of truth)

```python
DEFAULT_FIELD_STRATEGIES = {
    # Numeric — exact
    "temp_range_i":        FieldEvalStrategy(match="exact"),
    "temp_range_f":        FieldEvalStrategy(match="exact"),
    "spatial_range_km2":   FieldEvalStrategy(match="exact"),  # audit: numeric tolerance TBD

    # Controlled vocabulary — exact (enums handle synonyms via Pydantic validators)
    "data_type":           FieldEvalStrategy(match="exact"),
    "geospatial_info":     FieldEvalStrategy(match="exact"),  # audit: enum coverage of GT vocab

    # Free-text list — enhanced species matching
    "species":             FieldEvalStrategy(match="enhanced_species", threshold=70),

    # Booleans — exact
    "time_series":         FieldEvalStrategy(match="exact"),
    "multispecies":        FieldEvalStrategy(match="exact"),
    "threatened_species":  FieldEvalStrategy(match="exact"),
    "new_species_science": FieldEvalStrategy(match="exact"),
    "new_species_region":  FieldEvalStrategy(match="exact"),
    "bias_north_south":    FieldEvalStrategy(match="exact"),  # audit: positive example count
}
# temporal_range: DROPPED — redundant with temp_range_i/temp_range_f
# referred_dataset: DROPPED — too rare in GT, noisy annotations
```

### Global normalization (unchanged, applies to all fields)

- `casefold_strings: True`
- `strip_strings: True`
- `collapse_whitespace: True`
- `treat_lists_as_sets: True`

List comparison mechanism unchanged: set-based TP/FP/FN via intersection/difference. The per-field strategy controls item-level matching within that structure.

---

### Work Units

#### WU-EH1: FieldEvalStrategy + EvaluationConfig extension `sonnet`

**deps:** none | **files:** `groundtruth_eval.py`

- Add `FieldEvalStrategy` frozen dataclass: `match: str = "exact"`, `threshold: int = 80`
- Add `field_strategies: dict[str, FieldEvalStrategy]` to `EvaluationConfig` (default: `{}`)
- Add `DEFAULT_FIELD_STRATEGIES` module-level constant (12 fields, as above)
- Keep existing parameters (`fuzzy_match_fields`, `enhanced_species_matching`, `enhanced_species_threshold`) — they continue to work when `field_strategies` is empty

#### WU-EH2: Update compare_models dispatch logic `sonnet`

**deps:** WU-EH1 | **files:** `groundtruth_eval.py`

- When `field_strategies` is non-empty:
  - Use registry keys as default field list (replaces model-field intersection)
  - `fields` parameter still restricts further (intersection with registry keys)
  - For each field, dispatch to matching algorithm based on `strategy.match`:
    - `"exact"` → current standard normalized comparison path
    - `"fuzzy"` → current `_fuzzy_match_lists` / `_fuzzy_match_strings` path using `strategy.threshold`
    - `"enhanced_species"` → current `_enhanced_species_match_lists` path using `strategy.threshold`
- When `field_strategies` is empty → current behavior unchanged (backward compat)

#### WU-EH3: Tests `sonnet`

**deps:** WU-EH1, WU-EH2 | **files:** `tests/test_evaluation.py`, `tests/test_evaluation_fuzzy.py`

- Test `FieldEvalStrategy` defaults
- Test `DEFAULT_FIELD_STRATEGIES` contains exactly 12 fields, excludes `temporal_range` and `referred_dataset`
- Test `compare_models` with `field_strategies` populated: only registry fields are evaluated
- Test `compare_models` with `field_strategies` populated + `fields` parameter: intersection behavior
- Test backward compat: empty `field_strategies` + old `fuzzy_match_fields` still works
- Test backward compat: empty `field_strategies` + old `enhanced_species_matching` still works
- Existing tests must pass unmodified

#### WU-EH4: CLAUDE.md — evaluation section `haiku`

**deps:** WU-EH1 | **files:** `CLAUDE.md`

- Add subsection under Architecture documenting:
  - Field eval registry pattern and `DEFAULT_FIELD_STRATEGIES`
  - Dropped fields and rationale
  - Per-field observation protocol (format for logging field-level analysis)
  - Backward compatibility with old EvaluationConfig parameters

#### WU-EH5: Per-field audit `opus`

**deps:** WU-EH1, WU-EH2, WU-EH3 | **files:** notebook (TBD), `notebooks/README.md`

- Use new registry to run eval on existing batch_abstract results (no new extraction needed — reuse cached predictions)
- For each of the 12 evaluated fields, inspect 10–15 mismatches:
  - What did the LLM extract vs GT?
  - Is the mismatch a prompt problem, eval problem, or GT noise?
  - Systematic pattern or random?
- Flagged fields get deeper treatment:
  - `spatial_range_km2`: inspect numeric mismatches, recommend tolerance strategy or keep exact
  - `bias_north_south`: count positive examples in GT, assess if field is evaluatable
  - `data_type` / `geospatial_info`: check if enum vocabulary covers GT values
- Log per-field observations in `notebooks/README.md` using format:

```markdown
### field_name (F1=X.XX, P=X.XX, R=X.XX)
- **Pattern:** [systematic observation about mismatches]
- **Root cause:** prompt | eval | GT noise | vocab gap
- **Recommendation:** [specific action for prompt engineering phase]
```

### Execution Rounds

```
Round 1: WU-EH1                              (no deps)
Round 2: WU-EH2 || WU-EH4                    (deps: EH1)
Round 3: WU-EH3                              (deps: EH1, EH2)
Round 4: WU-EH5                              (deps: EH1, EH2, EH3)
```

---

## Phase 2: Prompt Infrastructure (future, not planned in detail)

- Extract prompts from `gpt_classify.py` into `prompts/` directory as versioned text files
- Build `prompt_eval.py` script: run extraction + evaluation on dev subset, output per-field metrics
- Curate 30-record dev subset (10 per source: Dryad, Zenodo, SS) with known-good GT
- Add dataset scoping instruction to all system prompts (primary vs cited datasets)

## Phase 3: Per-Field Prompt Iteration (future)

- Per-field prompt engineering loop: extract → evaluate → analyze mismatches → modify prompt → re-extract
- Priority fields: `time_series` (over-prediction), `species`/`data_type` (scoping), `threatened_species` (under-prediction)
- Agentic workflow: haiku runs extract/eval, opus analyzes mismatches and proposes prompt changes, human approves
