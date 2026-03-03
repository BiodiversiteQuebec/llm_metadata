# Prompt-Eval & Viewer Improvements

Incremental improvements to `prompt_eval.py` and `app_eval_viewer.py` to support faster prompt-engineering iteration.

## Completed

| Phase | Deliverable |
|-------|-------------|
| 1 | `EvaluationReport.abstracts` field; `run_id` in `run_eval()` + CLI; abstracts persisted to JSON |
| 2 | `app_eval_viewer.py`: fixed `0.0→N/A` bug; abstract text in mismatch expanders |
| 3 | `app_eval_viewer.py`: F1 bar chart; Run B mismatch explorer section; Run B metadata sidebar |
| 4 | `app_eval_viewer.py`: Record Explorer (all fields for a selected record) |

---

## Phase 5: Re-evaluate from saved predictions `sonnet`

**deps:** Phase 1 | **files:** `prompt_eval.py`, `groundtruth_eval.py`

### Motivation

During prompt engineering iteration the most common action is:
1. Run extraction → `results/run_01.json` (costs API $)
2. Tweak eval config (threshold, strategy) or prompt analysis needs new metric
3. Re-evaluate with new config — zero new extractions needed

Currently users must re-run everything or hack around joblib cache. A `--pred-from` flag skips extraction and loads predictions from a prior run.

### Design

**Store raw predictions in the report JSON:**

Add `predictions` key to `EvaluationReport.save()` output:

```json
{
  "predictions": {
    "42": {"data_type": ["abundance"], "species": ["Rangifer tarandus"], ...},
    "57": {"data_type": ["presence-only"], "species": [], ...}
  }
}
```

`predictions` holds one dict per record_id (the Pydantic model `.model_dump()`).

**New parameters:**

- `run_eval(..., pred_from: str | None = None)` — path to a prior report JSON; skips extraction and loads predictions from `doc["predictions"]`
- CLI: `--pred-from results/run_01.json`

**Combined with `--config`:**

```bash
# Re-evaluate run_01 predictions with strict config, zero API calls:
uv run python -m llm_metadata.prompt_eval \
  --pred-from results/run_01.json \
  --config configs/eval_strict.json \
  --output results/run_01_strict.json
```

### Work Units

#### WU-5.1: Save predictions in report JSON `sonnet`

**files:** `groundtruth_eval.py`

- Add `predictions: dict[str, dict]` field to `EvaluationReport` (default `{}`)
- Update `save()` to include `predictions` in the JSON doc
- Update `load()` to restore `predictions` from JSON

#### WU-5.2: `--pred-from` in prompt_eval `sonnet`

**files:** `prompt_eval.py`

- Add `pred_from: Optional[str]` param to `run_eval()`
- When set: skip steps 7 (extraction); load `doc["predictions"]` from the path, validate each dict through `DatasetFeatures.model_validate()` to rebuild `pred_by_id`
- Add `--pred-from` arg to CLI parser
- When `--pred-from` is set and `--prompt` is not explicitly passed, skip prompt module loading

#### WU-5.3: Tests `sonnet`

**files:** `tests/test_prompt_eval.py`

- Test round-trip: `run_eval()` → `save()` → reload predictions → re-evaluate with new config
- Confirm zero API calls when `pred_from` is set (mock `classify_abstract`)

---

## Phase 6: Multi-run comparison `sonnet`

**deps:** Phase 5 | **files:** `groundtruth_eval.py`, `prompt_eval.py` (or new CLI subcommand)

### Motivation

After N prompt iterations, we want to see field-level F1 evolution across all runs in one table — not just A-vs-B. The viewer shows two runs; for a longitudinal view across 5+ iterations, a CLI table or notebook utility is more useful.

### Design

**Class method `EvaluationReport.compare_runs`:**

```python
@classmethod
def compare_runs(cls, *paths: str | Path) -> "pd.DataFrame":
    """Load multiple runs and return a per-field F1 comparison DataFrame.

    Columns: field, run_id_1_f1, run_id_2_f1, ..., delta (last - first)
    Rows: one per evaluated field, sorted by |delta| descending.
    """
```

**CLI subcommand:**

```bash
uv run python -m llm_metadata.prompt_eval compare \
  results/baseline.json \
  results/run_01.json \
  results/run_02.json
```

Outputs:

```
Field                  baseline   run_01   run_02   delta
data_type                 0.421    0.556    0.612   +0.191
species                   0.256    0.289    0.301   +0.045
time_series               0.803    0.812    0.801   -0.002
...
```

Also prints cost comparison: total and per-run.

### Work Units

#### WU-6.1: `EvaluationReport.compare_runs` `sonnet`

**files:** `groundtruth_eval.py`

- Classmethod that accepts 2+ paths, loads each, merges `metrics_to_pandas()` on `field`
- Returns wide DataFrame with per-run columns + `delta` (last - first)
- Raises `ValueError` if fewer than 2 paths provided

#### WU-6.2: `compare` CLI subcommand `sonnet`

**files:** `prompt_eval.py`

- Refactor `main()` to support subcommands: `run` (default, existing behavior) and `compare`
- `compare` subcommand: accepts 2+ positional JSON paths, calls `compare_runs`, prints table + cost summary
- Usage: `python -m llm_metadata.prompt_eval compare file1.json file2.json [file3.json ...]`

### Execution Rounds

```
Round 1: WU-6.1                    (no deps)
Round 2: WU-6.2                    (deps: 6.1)
```

---

## Summary: All Phases

```
Phase 1 ✅  Abstract tracking + run_id
Phase 2 ✅  Viewer bug fixes + abstract display
Phase 3 ✅  Viewer: bar chart, Run B mismatches, Run B metadata
Phase 4 ✅  Viewer: Record Explorer
Phase 5     Re-evaluate from saved predictions (WU-5.1, 5.2, 5.3)
Phase 6     Multi-run comparison (WU-6.1, 6.2)
```
