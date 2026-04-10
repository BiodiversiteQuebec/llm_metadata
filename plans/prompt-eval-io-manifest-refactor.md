# Plan: prompt_eval IO & Manifest Refactor

## Goal

Decouple `prompt_eval` from xlsx ground truth loading and prompt module indirection. Make the Python API accept plain data structures (lists, dicts, strings) and relegate file parsing to the CLI adapter.

## Design Decisions

### Prompt: collapse to `prompt: str`

- **Python API**: `prompt: Optional[str]` — the actual instruction text. `None` → mode picks default internally.
- **CLI**: `--prompt path/to/prompt.txt` — reads file, passes as text.
- **Composability is the caller's responsibility** when overriding. Notebook users import blocks from `prompts/common.py` and compose themselves. The `prompts/` package remains importable — it just stops being a load mechanism.
- `RunArtifact` keeps `system_message` (full text sent to LLM). Drop `prompt_module` field.

### GT: `list[dict]` with fixed join convention

- **Python API**: `gt: list[dict]` — each dict must contain `gt_record_id` (fixed convention, not a parameter).
- **CLI**: `--gt-manifest path.json` — JSON array of dicts, loaded and passed through.
- **Deprecated**: `--gt path.xlsx` — still works with `DeprecationWarning`, calls old xlsx loader internally.
- GT prep (xlsx → validated JSON) moves to a notebook or prep script, not `prompt_eval`.
- Internally, `run_eval` validates each dict against the eval schema and keys by `gt_record_id`.

### Manifest: `list[DataPaperRecord]`

- **Python API**: `manifest: list[DataPaperRecord]` — plain list of Pydantic models.
- **CLI**: `--manifest path.csv` — `DataPaperManifest.load_csv(path).records`.
- `DataPaperManifest` stays as a builder/loader utility. `run_eval` receives the plain list.

### Provenance digests (borrowed from MLflow/SageMaker pattern)

Add content hashes to `RunArtifact` for reproducibility tracking:

```python
class RunArtifact(BaseModel):
    ...
    gt_digest: Optional[str] = None        # sha256 of serialized GT input
    manifest_digest: Optional[str] = None   # sha256 of serialized manifest
```

Cheap to compute, answers "did the GT change between these two runs?"

### What we're NOT building

- No JSONL (scale is hundreds of records, not millions)
- No channel/artifact registry (named function params are the channels)
- No configurable `join_key` (fixed convention is simpler; a 2-line adapter if ever needed)
- No generic framework abstractions

---

## Target Python API

```python
def run_eval(
    *,
    mode: ExtractionMode | str,
    manifest: list[DataPaperRecord],
    gt: list[dict],
    prompt: Optional[str] = None,
    text_format: Type[BaseModel] = DatasetFeaturesExtraction,
    model: str = "gpt-5-mini",
    reasoning_effort: str = "low",
    config: Optional[EvaluationConfig] = None,
    fields: Optional[list[str]] = None,
    name: Optional[str] = None,
    description: Optional[str] = None,
    skip_cache: bool = False,
) -> EvaluationReport:
```

## Target CLI (thin adapter)

```
uv run python -m llm_metadata.prompt_eval \
  --mode abstract \
  --manifest data/manifests/dev_subset_data_paper.csv \
  --gt-manifest data/gt/fuster_gt.json \
  --prompt prompts/my_custom_prompt.txt \
  --config configs/eval_default.json \
  --fields species,data_type \
  --name my_run_01
```

| CLI flag | Adapter logic | Python API param |
|----------|--------------|------------------|
| `--manifest path.csv` | `DataPaperManifest.load_csv(path).records` | `manifest` |
| `--gt-manifest path.json` | `json.load(f)` | `gt` |
| `--gt path.xlsx` | deprecated shim → old xlsx loader | `gt` |
| `--prompt path.txt` | `Path(p).read_text()` | `prompt` |
| `--mode abstract` | pass through | `mode` |
| `--config path.json` | `EvaluationConfig.from_json(path)` | `config` |

---

## Work Units

### ~~WU-IO1~~: GT prep utility `sonnet` ✓ 2026-04-10

**deps:** none | **files:** `src/llm_metadata/schemas/data_paper.py`, `data/gt/fuster_gt.json`

- ✓ Added `export_gt_json(gt_path, output_path, subset_ids)` — xlsx → validate as `DatasetFeaturesNormalized` → JSON array of dicts with `gt_record_id`
- ✓ Created `data/gt/fuster_gt.json` (299 records)
- Note: notebook round-trip skipped (function is importable and verified by test)

### ~~WU-IO2~~: Simplify `prompt` param in `extraction.py` `sonnet` ✓ 2026-04-10

**deps:** none | **files:** `src/llm_metadata/extraction.py`

- ✓ Renamed `prompt_module: Optional[str]` → `prompt: Optional[str]` on `run_manifest_extraction`
- ✓ When `prompt` is None → load default from mode; when string → use as-is as system message
- Note: `_load_system_message` and `_default_system_message` kept as private internals (not removed)

### ~~WU-IO3~~: Refactor `run_eval` signature in `prompt_eval.py` `sonnet` ✓ 2026-04-10

**deps:** WU-IO1, WU-IO2 | **files:** `src/llm_metadata/prompt_eval.py`

- ✓ New signature: `manifest: list[DataPaperRecord]`, `gt: list[dict]`, `prompt: Optional[str]`
- ✓ Removed `gt_path`, `manifest_path` params from `run_eval`
- ✓ Deleted `_load_ground_truth()`, `_build_true_by_id()`, `_parse_excel_val()`

### ~~WU-IO4~~: CLI adapter refactor + docs `sonnet` ✓ 2026-04-10

**deps:** WU-IO3 | **files:** `src/llm_metadata/prompt_eval.py` (CLI `main()`), `AGENTS.md`

- ✓ `--gt-manifest path.json` → new primary GT input (default: `data/gt/fuster_gt.json`)
- ✓ `--gt path.xlsx` → deprecated shim with `DeprecationWarning`
- ✓ `--prompt path.txt` → reads file, passes text to `run_eval()`
- ✓ `--manifest path.csv` → `DataPaperManifest.load_csv().records`
- ✓ Updated `AGENTS.md`: CLI usage, Python API signature, "Running Scripts" one-liner, Key Files table

### ~~WU-IO5~~: `RunArtifact` cleanup + digests `sonnet` ✓ 2026-04-10

**deps:** WU-IO3 | **files:** `src/llm_metadata/schemas/data_paper.py`

- ✓ Made `prompt_module: Optional[str] = None` (backward-compatible, kept for old artifact loading)
- ✓ Added `gt_digest: Optional[str]` and `manifest_digest: Optional[str]` (sha256)
- ✓ Computed digests in `run_eval` after manifest extraction

### ~~WU-IO6~~: Eval viewer + test updates `sonnet` ✓ 2026-04-10

**deps:** WU-IO5 | **files:** `src/llm_metadata/app/app_eval_viewer.py`, `tests/`

- ✓ Viewer handles `prompt_module=None` gracefully (falls back to `"custom"` label)
- ✓ Guards `importlib` fallback against `prompt_module == "custom"`
- ✓ Test fixtures updated for new `run_eval` signature (`manifest=`, `gt=`); 26 tests pass

---

## Execution Rounds

```
Round 1: WU-IO1 || WU-IO2          (no deps, parallel)
Round 2: WU-IO3                     (deps: IO1, IO2)
Round 3: WU-IO4 || WU-IO5          (deps: IO3, parallel)
Round 4: WU-IO6                     (deps: IO5)
```

## Deprecation Summary

| What | Action | Timeline |
|------|--------|----------|
| `--gt path.xlsx` | `DeprecationWarning`, still works via old loader | Remove after GT JSON is validated in production |
| `prompt_module` on `run_eval` | Not exposed on new API | Old `RunArtifact` JSON files still loadable (field ignored) |
| `DataPaperManifest.build()` from xlsx | Stays as prep utility | Not called by `run_eval` |
