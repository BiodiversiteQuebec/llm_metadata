# Prompt Engineering Flow

## Context & Motivation

Running full batch extraction with unrefined prompts wastes API spend and produces misleading aggregate metrics (Micro F1 0.202 on 288 records, $1.91). Per-field analysis reveals that failures have different root causes — some are prompt problems, some are eval problems, some are irrelevant fields dragging scores down. Eval hardening must come first so prompt engineering iterations produce reliable signal.

---

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

### Phase 1 Execution Rounds

```
Round 1: WU-EH1                              (no deps)
Round 2: WU-EH2 || WU-EH4                    (deps: EH1)
Round 3: WU-EH3                              (deps: EH1, EH2)
Round 4: WU-EH5                              (deps: EH1, EH2, EH3)
```

---

## Phase 2: Prompt Infrastructure

### Goals

Build the tooling that makes prompt iteration fast and measurable: versioned prompts, a CLI/API evaluation harness, a curated dev subset, and a visualization layer for results.

### 2.1 Prompt Refactor — `prompts/` package `sonnet`

**deps:** none | **files:** `src/llm_metadata/prompts/`, `gpt_classify.py`, pipeline modules

Extract prompts from `gpt_classify.py` into a dedicated package with a shared base:

```
src/llm_metadata/prompts/
  __init__.py          # re-exports SYSTEM_MESSAGE from each module
  common.py            # Shared building blocks (see below)
  abstract.py          # Abstract extraction prompt
  pdf_file.py          # PDF File API extraction prompt
  section.py           # Section/chunk extraction prompt
```

**`common.py`** — shared instruction blocks composed by task prompts:

| Block | Content |
|-------|---------|
| `PERSONA` | EcodataGPT identity, role description |
| `PHILOSOPHY` | Conservative extraction, explicit-information-only guardrails |
| `SCOPING` | Primary dataset vs cited/referenced datasets — extract only original data |
| `OUTPUT_FORMAT` | Structured output guidance, schema compliance rules |
| `VOCABULARY` | `data_type` and `geospatial_info` enum descriptions with ecological examples |

Each task module composes: `PERSONA + PHILOSOPHY + SCOPING + task_specific + VOCABULARY + OUTPUT_FORMAT`.

Each module exposes:
- `SYSTEM_MESSAGE: str` — the assembled prompt (for direct use)
- `build_prompt(**overrides) -> str` — parameterized constructor (for experiments, e.g. injecting field-specific emphasis)

**Refactor in consuming modules:**
- `gpt_classify.py`: import `SYSTEM_MESSAGE` from `prompts.abstract` (delete inline constants)
- `section_pipeline.py` / `text_pipeline.py`: import from `prompts.section`
- `pdf_pipeline.py`: import from `prompts.pdf_file`

### 2.2 EvaluationReport serialization `sonnet`

**deps:** WU-EH1 | **files:** `groundtruth_eval.py`

Add round-trip persistence to `EvaluationReport` so runs can be saved, loaded, and compared without re-execution.

**Output JSON structure:**

```json
{
  "run_id": "abstract_20260219_01",
  "prompt_module": "prompts.abstract",
  "model": "gpt-5-mini",
  "subset": "data/dev_subset.csv",
  "timestamp": "2026-02-19T14:30:00",
  "cost_usd": 0.12,
  "config": {
    "casefold_strings": true,
    "field_strategies": {
      "species": {"match": "enhanced_species", "threshold": 70},
      "data_type": {"match": "exact"}
    }
  },
  "field_metrics": {
    "species": {"tp": 45, "fp": 12, "fn": 8, "n": 30,
                "precision": 0.789, "recall": 0.849, "f1": 0.818}
  },
  "field_results": [
    {"record_id": "10.5061/dryad.xxx", "field": "species",
     "true_value": ["Tamias striatus", "caribou"],
     "pred_value": ["Tamias striatus", "Rangifer tarandus"],
     "match": false, "tp": 1, "fp": 1, "fn": 1}
  ]
}
```

**New methods on existing classes:**

| Class | Method | Purpose |
|-------|--------|---------|
| `EvaluationConfig` | `to_dict()` / `from_dict(d)` | Serialize config incl. `field_strategies` |
| `EvaluationConfig` | `from_json(path)` / `to_json(path)` | File I/O for versioned configs |
| `EvaluationReport` | `save(path, **run_metadata)` | Write full report + metadata to JSON |
| `EvaluationReport` | `load(path)` (classmethod) | Reconstruct report from JSON |

Run metadata (`run_id`, `prompt_module`, `model`, `cost_usd`, etc.) is passed to `save()` as kwargs — keeps the core dataclass clean.

### 2.3 `prompt_eval` module — CLI + Python API `sonnet`

**deps:** 2.1, 2.2 | **files:** `src/llm_metadata/prompt_eval.py`

Two interfaces, one engine.

**CLI** (inner loop, fast iteration):

```bash
uv run python -m llm_metadata.prompt_eval \
  --prompt prompts.abstract \
  --subset data/dev_subset.csv \
  --config configs/eval_default.json \
  --fields species,data_type,time_series \
  --output results/abstract_20260219_01.json
```

Outputs per-field metrics table to stdout. Saves full `EvaluationReport` JSON for later analysis. Uses joblib cache — re-running the same prompt+DOI is free; only changed prompts trigger API calls.

**Python API** (notebook integration):

```python
from llm_metadata.prompt_eval import run_eval
from llm_metadata.groundtruth_eval import EvaluationReport

# Run fresh extraction + evaluation
report = run_eval(
    prompt_module="prompts.abstract",
    subset_path="data/dev_subset.csv",
    config_path="configs/eval_default.json",
)
report.save("results/abstract_20260219_01.json",
            prompt_module="prompts.abstract", model="gpt-5-mini")

# Or load a previous run for analysis
report = EvaluationReport.load("results/abstract_20260219_01.json")
report.metrics_to_pandas()
```

### 2.4 Versioned eval configs `haiku`

**deps:** 2.2 | **files:** `configs/`

```
configs/
  eval_default.json           # DEFAULT_FIELD_STRATEGIES + standard normalization
  eval_fuzzy_species.json     # same but fuzzy species at threshold=70
  eval_strict.json            # exact matching only, no fuzzy
```

CLI default: `--config configs/eval_default.json`. Notebooks load the same files via `EvaluationConfig.from_json()`. Single source of truth — no config drift.

### 2.5 Curate dev subset `sonnet`

**deps:** WU-EH5 (audit informs selection) | **files:** `data/dev_subset.csv`

```csv
doi,source,notes
10.5061/dryad.xxx,dryad,good species variety
10.5281/zenodo.yyy,zenodo,tricky spatial scope
...
```

30 records (10 per source: Dryad, Zenodo, SS). Selection criteria informed by Phase 1 audit:
- Cover hard cases: multi-dataset papers, vernacular+scientific species, ambiguous spatial scope
- Include boolean edge cases (positive examples for `time_series`, `threatened_species`, `bias_north_south`)
- Include GT-ambiguity cases (annotator intent unclear)

The file is hand-curated once and stable. Changing it breaks comparability across prompt iterations — if it must change, bump the filename (`dev_subset_v2.csv`).

### 2.6 Results visualization — notebook + Streamlit `sonnet`

**deps:** 2.2, 2.3 | **files:** `notebooks/prompt_eval_results.ipynb`, `src/llm_metadata/app_eval_viewer.py`

**Notebook template** (`notebooks/prompt_eval_results.ipynb`) — minimum viable viewer:
- Load one or more `results/*.json` files
- Per-field metrics table (sortable by F1/P/R)
- Drill into mismatches for a selected field
- Side-by-side comparison of two runs

**Streamlit app** (`src/llm_metadata/app_eval_viewer.py`) — interactive browser:

```bash
uv run streamlit run src/llm_metadata/app_eval_viewer.py
```

Features:
- **Run picker**: select one or two runs from `results/` directory (side-by-side diff mode)
- **Field dashboard**: per-field P/R/F1 bar chart, sortable table, delta indicators between runs
- **Mismatch explorer**: click a field → paginated record-level mismatches with true vs pred values + raw abstract text
- **Record view**: click a record → all field results for that record, link to raw abstract

Scope this as a separate work unit after core `prompt_eval` works — don't let it block the iteration loop.

### 2.7 Document agentic workflow in CLAUDE.md `haiku`

**deps:** 2.3 | **files:** `CLAUDE.md`

Add a "Prompt Engineering Workflow" section documenting:

**Roles:**

| Role | Model | Responsibility |
|------|-------|----------------|
| Runner | haiku / sonnet | Execute `prompt_eval` on dev subset, collect metrics |
| Analyst | opus | Inspect mismatches, diagnose root causes, propose prompt edits |
| Approver | human | Review proposals, approve/reject, steer priority |

**Analyst protocol — what to read for diagnosis:**

| Source | Path | What it tells you |
|--------|------|-------------------|
| Ground truth | `data/dataset_092624_validated.xlsx` | Original human annotations, annotator's intent |
| Raw abstract | Extracted from xlsx `abstract` column | What text the LLM saw |
| Parsed PDF | `artifacts/tei/{doi}.md` or GROBID output | Full-text context — was information available? |
| Extraction output | `results/{run_id}.json` → `field_results` | What the LLM produced |

**Analyst guidelines:**
- Read raw data (xlsx, parsed PDFs) to diagnose — don't rely solely on metrics
- Orchestrate haiku sub-agents for mechanical tasks: "grep all dev-subset abstracts for 'simulation'", "count GT records with `bias_north_south=True`"
- Flag GT ambiguity explicitly — when GT annotation is questionable, note it rather than optimizing toward a possibly-wrong target
- Attempt to understand annotator intent from human annotation patterns (consistent choices, systematic biases)
- Escalate to human when: proposed changes affect >2 fields, or F1 drops on any field, or GT quality is in question

**Observation log format** (per-field, after each eval run):

```markdown
### field_name (F1=X.XX, P=X.XX, R=X.XX)
- **Pattern:** [systematic observation about mismatches]
- **Root cause:** prompt | eval | GT noise | vocab gap
- **Recommendation:** [specific action]
```

### Phase 2 Execution Rounds

```
Round 1: WU-2.1 || WU-2.2                   (no deps on each other)
Round 2: WU-2.3 || WU-2.4                   (deps: 2.1+2.2 for 2.3, 2.2 for 2.4)
Round 3: WU-2.5                              (deps: WU-EH5 audit)
Round 4: WU-2.6 || WU-2.7                   (deps: 2.2+2.3)
```

---

## Phase 3: Per-Field Prompt Iteration

### Goals

Use the infrastructure from Phase 2 to systematically improve extraction quality, field by field. Each iteration follows the loop: extract → evaluate → analyze mismatches → modify prompt → re-extract.

### 3.1 Baseline run on dev subset `sonnet`

**deps:** Phase 2 complete | **files:** `results/baseline_*.json`

- Run `prompt_eval` with current prompts (post-refactor from 2.1) on dev subset
- Save results as the baseline for all subsequent comparisons
- Log per-field metrics in `notebooks/README.md`

### 3.2 `data_type` vocabulary iteration `sonnet`

**deps:** 3.1 | **files:** `prompts/common.py` (`VOCABULARY` block)

The `data_type` enum values (`abundance`, `presence-only`, `genetic_analysis`, etc.) currently appear as bare names in the prompt. The LLM lacks ecological context to distinguish them reliably.

**Work:**
- In `prompts/common.py` `VOCABULARY` block, expand each `data_type` enum value with:
  - A 1-sentence ecological definition
  - 2–3 concrete examples from real abstracts (drawn from dev subset GT)
  - Negative examples where useful ("NOT abundance if only presence/absence is recorded")
- Similarly review `geospatial_info` enum — same treatment if WU-EH5 audit identified vocab gaps
- Re-run `prompt_eval`, compare `data_type` F1 against baseline
- Log delta and mismatch analysis

**Expected format in prompt:**

```
data_type values:
- abundance: Count or density of individuals per area/time. Examples: "population counts of 12 bird species",
  "density estimates from transect surveys". NOT: presence/absence records, genetic samples.
- presence-only: Records of species occurrence without abundance. Examples: "occurrence records from
  citizen science platforms", "species checklists from field surveys".
- genetic_analysis: Molecular/genomic data. Examples: "microsatellite genotyping of 200 individuals",
  "eDNA metabarcoding of water samples".
...
```

### 3.3 Dataset scoping iteration `sonnet`

**deps:** 3.1 | **files:** `prompts/common.py` (`SCOPING` block)

Address the core scoping problem: LLM extracts features from cited/referenced datasets instead of restricting to the primary dataset(s) produced or analyzed by the study.

**Work:**
- Draft the `SCOPING` instruction block in `prompts/common.py`:
  - Define "primary dataset" = data collected, generated, or curated by the study authors
  - Define "referenced dataset" = previously published data used for context, calibration, or comparison
  - Explicit instruction: "Extract features ONLY from primary datasets. Ignore referenced datasets."
  - Include 2–3 examples from dev subset showing the distinction
- Re-run `prompt_eval`, compare `species`, `data_type`, `geospatial_info` against baseline
- These three fields are most affected by scoping confusion
- Log which mismatches were resolved vs persisted

### 3.4 Field-priority iterations `sonnet`

**deps:** 3.1, WU-EH5 (audit results) | **files:** `prompts/common.py`, `prompts/abstract.py`

Address field-specific issues identified by the Phase 1 audit (WU-EH5). Work on fields in priority order based on F1 impact and actionability:

**Likely priorities** (to be confirmed by audit):
- `time_series`: over-prediction — LLM infers temporal data implies time series; add negative examples
- `threatened_species`: under-prediction — LLM misses conservation status cues; add positive signal words
- `multispecies`: threshold ambiguity — does "2 species" count? Clarify in prompt
- `new_species_science` / `new_species_region`: rare positives, may need few-shot examples

Each iteration: modify prompt → `prompt_eval` → compare to baseline → log observations.

### 3.5 Batch validation `sonnet`

**deps:** 3.2, 3.3, 3.4 | **files:** `results/batch_*.json`, `notebooks/README.md`

- Run winning prompts on the **full** validated dataset (not just dev subset)
- Compare against the original batch baseline (Micro F1 0.202)
- Per-field delta table: which fields improved, which regressed
- Cost comparison
- Final lab log entry with comprehensive results

### Phase 3 Execution Rounds

```
Round 1: WU-3.1                              (baseline)
Round 2: WU-3.2 || WU-3.3                   (independent prompt changes)
Round 3: WU-3.4                              (deps: audit + baseline)
Round 4: WU-3.5                              (deps: all iterations done)
```

---

## Appendix: File Layout (after Phase 2)

```
src/llm_metadata/
  prompts/
    __init__.py
    common.py                 # Shared blocks: PERSONA, PHILOSOPHY, SCOPING, VOCABULARY, OUTPUT_FORMAT
    abstract.py               # Abstract extraction prompt
    pdf_file.py               # PDF File API extraction prompt
    section.py                # Section/chunk extraction prompt
  prompt_eval.py              # CLI + Python API for extract-evaluate loop
  groundtruth_eval.py         # EvaluationConfig, FieldEvalStrategy, EvaluationReport (with save/load)
  app_eval_viewer.py          # Streamlit results viewer

configs/
  eval_default.json           # DEFAULT_FIELD_STRATEGIES + standard normalization
  eval_fuzzy_species.json
  eval_strict.json

data/
  dev_subset.csv              # 30-record curated subset (stable, versioned)
  dataset_092624_validated.xlsx

results/                      # prompt_eval output (JSON), gitignored except baselines
  baseline_abstract.json
  ...

notebooks/
  prompt_eval_results.ipynb   # Template for loading and analyzing results
```
