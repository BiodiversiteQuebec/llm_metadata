# Plan: Named runs + self-contained JSON for prompt_eval

## Context

The eval viewer app (`app_eval_viewer.py`) currently depends on two xlsx files for per-record metadata (title, DOI, abstract, etc.) and imports the prompt module at runtime to render the system message. This makes it impossible to use the app on a machine without the source data or source code. The `prompt_eval` CLI also lacks a convenient `--name` flag — callers must always specify a full `--output` path.

**Goal:** Make `prompt_eval` output self-contained JSON files that the app can display without any external data, and add a `--name` convenience flag for naming runs.

## Files to modify

| File | Changes |
|------|---------|
| `src/llm_metadata/prompt_eval.py` | Add `name` param, bundle records + system_message into JSON |
| `app/app_eval_viewer.py` | Read records/prompt from JSON first, xlsx/import fallback |
| `CLAUDE.md` | Update docs for `--name` flag and self-contained output |
| `notebooks/prompt_eval_results.ipynb` | Update example CLI in markdown cell |

**No changes to** `groundtruth_eval.py` — `EvaluationReport.save()` already accepts `**run_metadata` that gets merged into the top-level JSON.

---

## Change 1: Named runs in `prompt_eval.py`

### 1a. Add `name` parameter to `run_eval()` (line 257)

```python
def run_eval(
    *,
    prompt_module: Optional[str] = None,
    manifest_path: Optional[str] = None,
    ...
    name: Optional[str] = None,       # NEW
) -> EvaluationReport:
```

After evaluation (line 447), when `name` is set and no explicit save was requested, auto-save to `data/{name}.json`. Attach records and system_message as run metadata.

### 1b. Add `--name` CLI flag (after `--output`, line 527)

```
--name  Run name. Auto-saves to data/{name}.json. --output takes precedence.
```

CLI logic:
- `--output` given → save to `--output` path (existing behavior), include `name` in metadata if provided
- `--name` given (no `--output`) → auto-save to `data/{name}.json`
- Neither → return report without saving (existing behavior)

---

## Change 2: Bundle record metadata + system_message into JSON

### 2a. Helper: `_build_records_dict()` in `prompt_eval.py`

Columns to bundle (from `_GT_META_COLS` in app + abstract):

```python
_RECORD_META_COLS = [
    "title", "source_url", "journal_url", "pdf_url",
    "is_oa", "cited_article_doi", "source",
    "valid_yn", "reason_not_valid", "has_abstract",
]
```

Build `{record_id: {col: val, ..., "abstract": text}}` for every record in the evaluation. Convert NaN → None, booleans stay as-is.

### 2b. Include `system_message` text in saved JSON

The `system_message` string (resolved at line 314) is passed to `report.save()` as `system_message=system_message`. This eliminates the app's need to `importlib.import_module()` at runtime.

### 2c. Wire into save calls

Both auto-save (from `name`) and explicit `--output` save include:
```python
report.save(
    path,
    name=name,
    prompt_module=...,
    model=...,
    cost_usd=...,
    records=records_dict,
    system_message=system_message,
    manifest_path=manifest_path,  # track which manifest defined the run subset
)
```

Attach `records` and `system_message` as attributes on the report object so callers using the Python API can pass them to their own `save()` calls.

---

## Change 3: App reads from JSON first, xlsx fallback

### 3a. Add `_records_from_meta(meta)` helper

Builds a `gt_index`-compatible DataFrame from `meta["records"]` dict. Returns `None` if key is missing (backward compat with old JSON files).

### 3b. Add `_abstracts_from_meta(meta)` helper

Extracts `{id: abstract}` dict from `meta["records"]`. Returns empty dict if missing.

### 3c. Add `_system_message_from_meta(meta)` helper

Returns `meta.get("system_message")` — simple but keeps the pattern consistent.

### 3d. Update data loading (line 194-196)

```python
report_a, meta_a = load_report(run_a_name)

# Primary: records from JSON; Fallback: xlsx files
gt_index = _records_from_meta(meta_a) or load_gt_index()
abstracts = _abstracts_from_meta(meta_a) or load_abstracts()
```

### 3e. Update prompt rendering (line 232-245)

Check `meta_a.get("system_message")` first; fall back to `importlib.import_module()` only if missing.

---

## Change 4: CLAUDE.md updates

- Inner Loop CLI example: add `--name` flag
- Python API example: add `name` parameter
- Eval Viewer data dependencies table: mark xlsx as "Fallback only"
- Add `manifest_path` to saved metadata fields

---

## Change 5: Notebook update

`notebooks/prompt_eval_results.ipynb` — update the example CLI string in the markdown/error cell (line 112) to show `--name` usage.

---

## Execution Flow

### Round 1 — parallel `sonnet`

#### WU-1: prompt_eval name + records bundling `sonnet`

**deps:** none | **files:** `src/llm_metadata/prompt_eval.py`

- Add `name` parameter to `run_eval()` (Change 1a)
- Add `--name` CLI flag (Change 1b)
- Add `_build_records_dict()` helper (Change 2a)
- Bundle `records`, `system_message`, `manifest_path` into save calls (Change 2b, 2c)
- Attach `records` and `system_message` as report attributes for Python API callers

#### WU-2: app self-contained loading `sonnet`

**deps:** none | **files:** `app/app_eval_viewer.py`

- Add `_records_from_meta()` and `_abstracts_from_meta()` helpers (Change 3a, 3b)
- Update data loading to prefer JSON records, xlsx fallback (Change 3d)
- Update prompt rendering to use `system_message` from JSON (Change 3e)

### Round 2 — parallel `haiku`

#### WU-3: CLAUDE.md docs `haiku`

**deps:** WU-1 | **files:** `CLAUDE.md`

- Update CLI example, Python API example, data dependencies table (Change 4)

#### WU-4: notebook update `haiku`

**deps:** WU-1 | **files:** `notebooks/prompt_eval_results.ipynb`

- Update example CLI string to show `--name` usage (Change 5)

### Round 3 — `sonnet`

#### WU-5: verification `sonnet`

**deps:** WU-1, WU-2, WU-3, WU-4

- Run tests, CLI smoke test, app smoke test, backward compat check

---

## Verification

1. **Unit test:** `python -m pytest tests/` — ensure no regressions
2. **CLI smoke test:**
   ```bash
   uv run python -m llm_metadata.prompt_eval \
     --prompt prompts.abstract \
     --manifest data/manifests/dev_subset_data_paper.csv \
     --name test_selfcontained \
     --fields species
   ```
   Then verify `data/test_selfcontained.json` contains `records` and `system_message` keys.
3. **App smoke test:**
   ```bash
    uv run streamlit run app/app_eval_viewer.py
   ```
   Select the `test_selfcontained.json` run → verify Dataset Results tab shows titles, abstracts, and prompt renders without xlsx files.
4. **Backward compat:** Load an old JSON file (without `records`) → app should fall back to xlsx gracefully.
