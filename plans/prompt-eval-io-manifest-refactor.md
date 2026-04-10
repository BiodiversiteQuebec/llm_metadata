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

### WU-IO1: GT prep utility `sonnet`

**deps:** none | **files:** `src/llm_metadata/schemas/data_paper.py`, notebook TBD

- Add `export_gt_json(gt_path, output_path, subset_ids)` — xlsx → validate as `DatasetFeaturesNormalized` → JSON array of dicts with `gt_record_id`
- Create `data/gt/fuster_gt.json` from current xlsx (one-time prep)
- Notebook or script to run the export + verify round-trip

### WU-IO2: Simplify `prompt` param in `extraction.py` `sonnet`

**deps:** none | **files:** `src/llm_metadata/extraction.py`

- Rename `prompt_module: Optional[str]` → `prompt: Optional[str]` on `run_manifest_extraction`
- When `prompt` is None → load default from mode (keep `DEFAULT_PROMPT_MODULES` + `_load_system_message` as internal default logic)
- When `prompt` is a non-empty string → use as-is (the text, not a module path)
- Delete `_load_system_message` and `_default_system_message` from public surface (fold into internal default resolution)

### WU-IO3: Refactor `run_eval` signature in `prompt_eval.py` `sonnet`

**deps:** WU-IO1, WU-IO2 | **files:** `src/llm_metadata/prompt_eval.py`

- New signature: `manifest: list[DataPaperRecord]`, `gt: list[dict]`, `prompt: Optional[str]`
- Remove `gt_path`, `manifest_path` params from `run_eval`
- Delete `_load_ground_truth()`, `_build_true_by_id()`, `_parse_excel_val()`
- Internal: validate GT dicts against eval schema, key by `gt_record_id`, call `evaluate_indexed()`

### WU-IO4: CLI adapter refactor + docs `sonnet`

**deps:** WU-IO3 | **files:** `src/llm_metadata/prompt_eval.py` (CLI `main()`), `AGENTS.md`

- `--gt-manifest path.json` → new primary GT input
- `--gt path.xlsx` → deprecated shim with `DeprecationWarning`
- `--prompt path.txt` → read text file
- `--manifest path.csv` → `DataPaperManifest.load_csv().records`
- Update `_build_recreate_command()` for new flags
- Update `AGENTS.md`: "Prompt Engineering Workflow" inner loop examples, CLI usage, `run_eval()` Python API signature, "Running Scripts" one-liner, Eval Viewer data dependencies (drop `prompt_module` references)

### WU-IO5: `RunArtifact` cleanup + digests `sonnet`

**deps:** WU-IO3 | **files:** `src/llm_metadata/schemas/data_paper.py`

- Drop `prompt_module` field from `RunArtifact`
- Add `gt_digest: Optional[str]` and `manifest_digest: Optional[str]` (sha256)
- Compute digests in `run_eval` before extraction

### WU-IO6: Eval viewer + test updates `sonnet`

**deps:** WU-IO5 | **files:** `src/llm_metadata/app/app_eval_viewer.py`, `tests/`

- Viewer: stop reading `prompt_module` from artifact, rely on `system_message`
- Handle both old artifacts (with `prompt_module`) and new (without) gracefully
- Update test fixtures for new `run_eval` signature

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
