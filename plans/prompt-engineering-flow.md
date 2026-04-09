# Prompt Engineering Flow

## Context & Motivation

Running full batch extraction with unrefined prompts wastes API spend and produces misleading aggregate metrics (Micro F1 0.202 on 288 records, $1.91). Per-field analysis reveals that failures have different root causes — some are prompt problems, some are eval problems, some are irrelevant fields dragging scores down. Eval hardening must come first so prompt engineering iterations produce reliable signal.

---

## Phase 1: Evaluation Hardening ✅ COMPLETE

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

#### ~~WU-EH1: FieldEvalStrategy + EvaluationConfig extension~~ ✅

#### ~~WU-EH2: Update compare_models dispatch logic~~ ✅

#### ~~WU-EH3: Tests~~ ✅

#### ~~WU-EH4: CLAUDE.md — evaluation section~~ ✅

#### ~~WU-EH5: Per-field audit~~ ✅ (done via March 27 baseline run notes)

> Audit completed 2026-03-28 via `20260327_172654_dev_subset_abstract.json`. Key findings documented in run notes. See Phase 3 for action items.

---

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

## Phase 2: Prompt Infrastructure ✅ COMPLETE

### Goals

Build the tooling that makes prompt iteration fast and measurable: versioned prompts, a CLI/API evaluation harness, a curated dev subset, and a visualization layer for results.

### ~~2.1 Prompt Refactor — `prompts/` package~~ ✅
### ~~2.2 EvaluationReport serialization~~ ✅
### ~~2.3 `prompt_eval` module — CLI + Python API~~ ✅
### ~~2.4 Versioned eval configs~~ ✅
### ~~2.5 Curate dev manifest subset~~ ✅ (30 records, `data/manifests/dev_subset_data_paper.csv`)
### ~~2.6 Results visualization — Streamlit app~~ ✅ (`app/app_eval_viewer.py`, 5 tabs)
### ~~2.7 Document agentic workflow in CLAUDE.md~~ ✅

---

### 2.1 Prompt Refactor — `prompts/` package `sonnet`

**deps:** none | **files:** `src/llm_metadata/prompts/`, `gpt_extract.py`, pipeline modules

Extract prompts from `gpt_extract.py` into a dedicated package with a shared base:

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
- `gpt_extract.py`: import `SYSTEM_MESSAGE` from `prompts.abstract` (delete inline constants)
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
  "manifest_path": "data/manifests/dev_subset_data_paper.csv",
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
  --manifest data/manifests/dev_subset_data_paper.csv \
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
    manifest_path="data/manifests/dev_subset_data_paper.csv",
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

### 2.5 Curate dev manifest subset `sonnet`

**deps:** WU-EH5 (audit informs selection) | **files:** `data/manifests/dev_subset_data_paper.csv`, `scripts/*`

30 records (10 per source: Dryad, Zenodo, SS). Selection criteria informed by Phase 1 audit:
- Cover hard cases: multi-dataset papers, vernacular+scientific species, ambiguous spatial scope
- Include boolean edge cases (positive examples for `time_series`, `threatened_species`, `bias_north_south`)
- Include GT-ambiguity cases (annotator intent unclear)

The manifest is built once from a stable GT ID list and versioned. Changing membership breaks comparability across prompt iterations — if it must change, bump the manifest name (e.g., `dev_subset_v2_data_paper.csv`).

### 2.6 Results visualization — notebook + Streamlit `sonnet`

**deps:** 2.2, 2.3 | **files:** `notebooks/prompt_eval_results.ipynb`, `app/app_eval_viewer.py`

**Notebook template** (`notebooks/prompt_eval_results.ipynb`) — minimum viable viewer:
- Load one or more `results/*.json` files
- Per-field metrics table (sortable by F1/P/R)
- Drill into mismatches for a selected field
- Side-by-side comparison of two runs

**Streamlit app** (`app/app_eval_viewer.py`) — interactive browser:

```bash
uv run streamlit run app/app_eval_viewer.py
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

## Phase 3: Per-Field Prompt Iteration ✅ COMPLETE (common.py blocks)

> Species prompt work (WU-T1/T1b) tracked separately in [`plans/taxonomic-relevance-refactor.md`](taxonomic-relevance-refactor.md).

### Goals

Use the infrastructure from Phase 2 to systematically improve extraction quality, field by field. Each iteration follows the loop: extract → evaluate → analyze mismatches → modify prompt → re-extract.

### ~~3.1 Baseline run on dev subset~~ ✅

Three baseline runs completed 2026-03-27:

| Run artifact | Mode | Notes file |
|---|---|---|
| `artifacts/runs/20260327_172654_dev_subset_abstract.json` | abstract | `data/20260327_172654_dev_subset_abstract_notes.md` |
| `artifacts/runs/20260327_172653_dev_subset_sections.json` | sections | `data/20260327_172653_dev_subset_sections_notes.md` |
| `artifacts/runs/20260327_172656_dev_subset_pdf_file.json` | pdf_native | `data/20260327_172656_dev_subset_pdf_file_notes.md` |

**Abstract baseline metrics (fields with diagnosis):**

| Field | F1 | P | R | Root cause |
|---|---|---|---|---|
| `data_type` | 0.34 | 0.24 | 0.58 | vocab gap — schema enums absent from prompt |
| `geospatial_info_dataset` | 0.14 | 0.09 | 0.43 | prompt — place names over-trigger predictions |
| `species` | 0.40 | 0.29 | 0.65 | prompt — decorated forms + context taxa leak |
| `time_series` | 0.53 | 0.36 | 1.00 | prompt — over-prediction, multi-year ≠ time series |
| `threatened_species` | 0.38 | 1.00 | 0.24 | prompt — missing recall cues (IUCN, red-listed, etc.) |
| `bias_north_south` | N/A | N/A | 0.00 | prompt — no lexical triggers defined |

Mode comparison (from 2026-03-28 lab log): `abstract` best for `data_type`/`time_series`/`temp_range`; `sections` best for `species`/`spatial_range`; `pdf_native` best for `new_species_*` fields.

---

### ~~3.2 `data_type` + `geospatial_info_dataset` vocabulary iteration~~ ✅

**deps:** 3.1 (done) | **files:** `src/llm_metadata/prompts/common.py` (`VOCABULARY` block)

> **Sequencing note:** This work unit and WU-T1 in `plans/taxonomic-relevance-refactor.md` both modify `common.py`. Run them in the same session or sequentially — not in parallel.

**Problem:** Prompt VOCABULARY only documents 8 `data_type` values and 5 `geospatial_info` values. The schema accepts additional values (`presence-absence`, `density`, `distribution`, `traits`, `ecosystem_function`, etc.) that are completely absent from the vocabulary guidance.

**Enum audit (already done — do not re-derive):**

`EBVDataType` — 13 valid values: `abundance`, `presence-absence`, `presence-only`, `density`, `distribution`, `traits`, `ecosystem_function`, `ecosystem_structure`, `genetic_analysis`, `time_series`, `species_richness`, `other`, `unknown`. Current prompt documents only 3 of these correctly; 5 values it documents (`tracking`, `remote_sensing`, `acoustic`, `morphological`, `environmental`) do not exist in the schema.

`GeospatialInfoType` — 9 valid values: `sample`, `site`, `range`, `distribution`, `geographic_features`, `administrative_units`, `maps`, `site_ids`, `unknown`. Current prompt is missing: `distribution`, `geographic_features`, `site_ids`, `unknown`.

**Work:**
- Expand each `data_type` value with:
  - 1-sentence ecological definition
  - 2–3 examples from dev subset GT
  - Negative contrastive examples (`presence-only` vs `distribution`, `abundance` vs `density`)
- Expand `geospatial_info_dataset` section with:
  - Negative rule: named places in background text do not imply dataset geography
  - Positive examples: coordinates, site identifiers, explicit distribution output
- Re-run `prompt_eval --mode abstract`, compare `data_type` and `geospatial_info_dataset` F1 vs baseline
- Log delta + mismatch analysis in run notes

**Success criterion:** `data_type` F1 ≥ 0.50 without regressing other fields.

---

### ~~3.4 Boolean field cue expansion~~ ✅

**deps:** 3.1 (done), 3.2 | **files:** `src/llm_metadata/prompts/common.py` (`MODULATOR_FIELDS` block)

**Confirmed issues from audit:**

| Field | F1 | Issue | Action |
|---|---|---|---|
| `time_series` | 0.53 (P=0.36) | Over-prediction: multi-year window ≠ repeated monitoring | Add negative examples |
| `threatened_species` | 0.38 (R=0.24) | Under-prediction: misses IUCN/red-list cues | Expand cue list |
| `bias_north_south` | N/A (R=0.00) | Two missing trigger types: geographic AND explicit-bias language | Add both trigger classes |

---

#### `time_series`

**Current text** (already partially correct but too weak):
> "true if the dataset contains repeated measurements at the same locations/populations over time (e.g. 'annual surveys from 2005 to 2015', 'monitored monthly'). A single snapshot is NOT a time series."

**Problem:** The model fires on any multi-year phrasing. The distinction that matters is **longitudinal intent** — same sites/populations re-visited to track change — vs **temporal coverage** — data collected across multiple years as a cross-sectional effort.

**What to add — negative anchors:**
- "Data collected in 2006 and 2007" → NOT a time series (two-year window, no stated repeat)
- "Samples collected across three field seasons" → NOT a time series unless same sites revisited
- "Data from 1990–2020 compiled from multiple studies" → NOT a time series (compilation, not repeated monitoring)
- Multi-treatment experimental repeats → NOT a time series

**Revised anchor text for prompt:**
```
- **time_series**: true if the dataset contains repeated measurements at the SAME locations
  or populations across multiple time periods, with the explicit intent to track change over
  time (e.g., "annual surveys 2005–2015 at 12 fixed plots", "monthly water quality monitoring",
  "long-term population census"). NOT a time series: data collected across multiple years
  as independent snapshots, multi-year compilations from different sites, short study windows
  ("sampled in 2006 and 2007"), or experimental treatment repeats.
```

---

#### `threatened_species`

**Current text** (keywords present but incomplete):
> "true if any studied species are described as threatened, endangered, vulnerable, at-risk, or listed under IUCN/CITES/national red lists."

**Problem:** Model has perfect precision (P=1.00) but low recall (R=0.24). It fires conservatively only on exact keyword matches. Real abstracts use indirect or regulatory-framework language.

**What to add — expanded cue list:**

| Framework | Trigger language |
|---|---|
| IUCN Red List | "IUCN-listed", "Red List", "critically endangered", "endangered", "vulnerable", "near threatened" |
| CITES | "CITES Appendix I/II/III", "CITES-listed", "international trade restriction" |
| Canada (federal) | "Species at Risk Act", "SARA", "COSEWIC", "Committee on the Status of Endangered Wildlife" |
| Canada (BC/QC/provincial) | "provincial red list", "species of concern", "conservation status" |
| General | "at-risk species", "conservation concern", "listed species", "protected species", "declining population" |

Also note: if a well-known threatened species is named (e.g., polar bear, beluga whale, woodland caribou, monarch butterfly), the model may infer threatened status from its ecological knowledge when no explicit status language appears — this is acceptable but should be noted in the prompt as an exception to the conservative philosophy.

**Revised anchor text for prompt:**
```
- **threatened_species**: true if any studied species are described as threatened, endangered,
  vulnerable, at-risk, or conservation-listed. Explicit cues include: IUCN Red List categories
  (critically endangered, endangered, vulnerable, near threatened), CITES Appendix listings,
  Species at Risk Act (SARA) / COSEWIC designations, provincial red lists, "species of
  conservation concern", "at-risk", "declining", "protected species". If a well-known
  threatened taxon is named without explicit status language, use ecological knowledge
  to confirm status only when you are certain.
```

---

#### `bias_north_south`

**Root cause of zero recall:** The field actually has **two distinct trigger conditions** that the current prompt collapses into one narrow description. The Fuster et al. (2025) paper defines the field as a Quebec-specific modulator where **either** condition qualifies:

1. **Geographic criterion**: The dataset is from **northern Quebec** — defined in the paper as "the territory that extends north of the 49th parallel and north of the St. Lawrence River and the Gulf of St. Lawrence" (Fuster et al., sec. 7). These regions are systematically under-sampled due to the south-north human population density gradient (sec. 2).

2. **Explicit bias criterion**: The paper explicitly discusses north-south sampling bias, geographic underrepresentation, or data gaps in northern/undersampled regions — at any spatial scale (Quebec, Canada, or global).

**Current prompt** only mentions the explicit-bias criterion ("explicitly discusses geographic bias toward the Global North") and misses the geographic criterion entirely.

**Geographic keywords for trigger 1 (northern Quebec / northern Canada):**

| Category | Keywords |
|---|---|
| Named territories | "Nunavik", "James Bay" / "Baie James", "Hudson Bay" / "Baie d'Hudson", "Ungava", "Labrador", "Côte-Nord" |
| Political/administrative | "northern Quebec" / "nord du Québec", "northern Canada", "Canadian Arctic", "Northwest Territories", "Nunavut", "Yukon" |
| Latitude thresholds | "north of the 49th parallel", "above 49°N", "above 50°N", "above 55°N", "above 60°N", explicit lat > 49 |
| Ecosystem types | "tundra", "taiga", "subarctic", "arctic", "boreal" (only when combined with northern or remote framing) |
| Geographic references | "north of the St. Lawrence", "north shore", "Laurentian", "Shield" (northern Precambrian Shield contexts) |

**Caution:** "boreal" alone is too broad (covers southern Quebec too). Require geographic modifier or latitude context. "Arctic" alone is a strong signal. "Nunavik" is unambiguous.

**Explicit-bias keywords for trigger 2:**

| Category | Keywords |
|---|---|
| Sampling gaps | "undersampled", "data gap", "poorly documented", "lack of data", "data deficiency" |
| Geographic bias | "geographic bias", "sampling bias", "spatial bias", "north-south gradient", "north-south bias" |
| Representation | "underrepresented region", "underrepresented area", "uneven distribution", "Global North", "Global South" |
| Climate/zone framing | "temperate overrepresentation", "tropical underrepresentation", "biodiversity hotspot bias" |
| Explicit context match | "south-north human population density gradient", "remote areas", "northern territories poorly documented" |

**Revised anchor text for prompt:**
```
- **bias_north_south**: true under EITHER of two conditions:
  (1) GEOGRAPHIC — the dataset is located in northern Quebec or northern Canada, defined as
  territory north of the 49th parallel, or north of the St. Lawrence River/Gulf. Trigger on
  named regions (Nunavik, James Bay, Hudson Bay, Ungava, Côte-Nord, northern Quebec), latitude
  references (above 49°N, above 55°N), ecosystem types in northern context (tundra, subarctic,
  Arctic), or explicit "northern Quebec" / "north of the St. Lawrence" framing.
  (2) EXPLICIT BIAS — the text explicitly discusses north-south sampling bias, underrepresentation
  of northern or tropical regions, data gaps in remote areas, or Global North/South disparities.
  Trigger on: "undersampled", "data gap", "geographic bias", "north-south gradient",
  "underrepresented region", "Global North/South", "poorly documented northern territories".
  A dataset located in northern Quebec automatically qualifies regardless of whether it mentions bias.
```

**Implementation note:** This field has 10 positive cases in the dev subset (confirmed in audit notes). After adding these triggers, if recall remains below 0.30 across two prompt iterations, consider whether the GT annotations require more information than is present in the abstract (in which case sections/pdf_native mode would be needed for this field, not just prompt changes).

---

**Work steps:**
1. Revise each of the three fields in `MODULATOR_FIELDS` block in `common.py` using the text above
2. Re-run `prompt_eval --mode abstract`, compare each field vs baseline independently
3. If `bias_north_south` recall improves with abstract mode, also test sections mode (geographic cues often appear in study area descriptions, not abstracts)
4. Log per-field observations in run notes

**Success criteria:**
- `time_series`: precision ≥ 0.55 (currently 0.36); F1 net positive vs 0.53 baseline
- `threatened_species`: recall ≥ 0.50 (currently 0.24); precision stays ≥ 0.80
- `bias_north_south`: F1 > 0 (currently N/A); recall ≥ 0.30 after 1–2 iterations

---

### ~~3.4b Mode-specific prompt tuning~~ ✅

**deps:** 3.2, 3.4 | **files:** `src/llm_metadata/prompts/section.py`, `src/llm_metadata/prompts/pdf_file.py`

Sections and PDF mode prompts share the `common.py` blocks but need additional mode-specific rules. These were identified in the March 27 baseline run notes.

#### Sections mode (`section.py`)

**`data_type`** (F1=0.30, worse than abstract): Methods text causes the model to pile on secondary labels for every analytical concept mentioned (e.g., `ecosystem_function` because an ecosystem analysis is described, `time_series` because repeated sampling is mentioned). Add a sections-specific instruction:
> "Classify `data_type` for the primary data *collected or stored*, not downstream analyses or derived products. Ignore methods that describe analysis techniques; focus on what kind of observations or measurements are in the dataset."

**`spatial_range_km2`** (F1=0.69, P=0.92, R=0.55 — sections is the strongest mode for this field): No change needed. Note this as the preferred mode for spatial range extraction — the information is usually explicit in methods text and rarely in abstracts. This observation should inform mode selection logic in future pipeline design.

**`time_series`** (F1=0.42 vs 0.53 abstract — worse in sections): Experimental repeats and multi-period sampling windows in methods text trigger the model more aggressively than in abstract mode. Add a section-mode exclusion:
> "Experimental treatment periods, field seasons, or sampling rounds within a single study are NOT time series unless the study design explicitly states repeated observation of the same sites or populations over successive years."

#### PDF native mode (`pdf_file.py`)

**`new_species_science`** (F1=0.61, P=0.79, R=0.50): Full text is clearly the best mode for this rare field. Add positive trigger cues:
> "Positive signals: 'sp. nov.', 'new species', 'described here for the first time', 'holotype', 'taxonomic diagnosis', 'new to science', formal species description language."

**`new_species_region`** (F1=0.59, P=0.73, R=0.50): Full text helps recall but some false positives remain from confusing known-range discussion with first records. Add contrastive guidance:
> "True only for a first confirmed record in a defined region — explicit language like 'first record for', 'new to', 'not previously recorded in'. NOT: general range expansion discussion, recolonization, modeled range extension, or species known to occur nearby."

**`species`** (F1=0.17, P=0.10 — PDF mode): Handled in [`plans/taxonomic-relevance-refactor.md`](taxonomic-relevance-refactor.md) WU-T1b — out of scope here.

**`time_series`** (F1=0.33, P=0.20 — worst mode): Any repeated year or appendix in the full text triggers True. Add:
> "In full-text mode: base the `time_series` judgment ONLY on the dataset description, sampling design section, or explicit data collection methodology. Repeated analyses, model runs, or appendix tables do not constitute a time series."

**Run order:** Run sections and PDF mode evals against their respective baselines (March 27 runs) after shared `common.py` changes from WU-3.2–3.4 are applied. Evaluate shared-block improvements first to avoid confounding.

### Phase 3 Execution Rounds

```
Round 1: ~~WU-3.1~~ ✅ done (2026-03-27)
Round 2: ~~WU-3.2~~ ✅ done (2026-03-31) — VOCABULARY block expanded
Round 3: ~~WU-3.4~~ ✅ done (2026-03-31) — MODULATOR_FIELDS cue expansion
Round 4: ~~WU-3.4b~~ ✅ done (2026-03-31) — mode-specific section.py + pdf_file.py
```

### Phase 3 Results Summary (2026-03-31)

Three-mode eval after all prompt changes (`artifacts/runs/20260331_12*`):

| Field | Abstract F1 | Sections F1 | PDF Native F1 | Best mode |
|---|---|---|---|---|
| `data_type` | **0.424** | 0.372 | 0.370 | abstract |
| `geospatial_info_dataset` | **0.255** | 0.182 | 0.230 | abstract |
| `species` | **0.405** | 0.380 | 0.187 | abstract |
| `time_series` | 0.471 | **0.476** | 0.250 | sections |
| `threatened_species` | 0.385 | 0.370 | **0.778** | pdf_native |
| `bias_north_south` | 0.286 | 0.378 | **0.830** | pdf_native |
| `multispecies` | **0.746** | 0.724 | 0.767 | pdf_native |
| `temp_range_i` | **0.743** | 0.524 | 0.694 | abstract |
| `temp_range_f` | **0.629** | 0.619 | 0.694 | pdf_native |
| `spatial_range_km2` | 0.095 | **0.667** | 0.703 | pdf_native |
| `new_species_region` | 0.222 | 0.286 | **0.750** | pdf_native |
| `new_species_science` | 0.167 | 0.240 | **0.769** | pdf_native |

**Key takeaways:**
- PDF native dominates for `threatened_species`, `bias_north_south`, `new_species_*`, `spatial_range_km2`
- Abstract best for `data_type`, `geospatial_info`, `species`, `temp_range_i`
- Species precision still weak across all modes — WU-T1 (SPECIES_EXTRACTION block) is the next lever
- `bias_north_south` dual-trigger working well in PDF mode (F1=0.83); abstract mode still limited (F1=0.29)

> Species prompt work (previously WU-3.3) is now tracked separately in [`plans/taxonomic-relevance-refactor.md`](taxonomic-relevance-refactor.md) WU-T1/T1b and runs in parallel with this plan.

**Mode-field priority matrix** (from March 27 baseline notes):

| Field | Best mode | Notes |
|---|---|---|
| `data_type` | abstract | sections adds noise from methods text |
| `geospatial_info_dataset` | abstract | PDF mode over-predicts heavily |
| `species` | sections | abstract best for precision; sections best for recall |
| `time_series` | abstract | sections/PDF both worse due to contamination |
| `spatial_range_km2` | **sections** | rarely in abstract; explicit in methods |
| `new_species_science` | **pdf_native** | full text needed for rare positives |
| `new_species_region` | **pdf_native** | full text needed for rare positives |
| `threatened_species` | abstract | status language usually in abstract |
| `bias_north_south` | abstract (test sections too) | geographic cues may appear in study area section |

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
  manifests/dev_subset_data_paper.csv  # 30-record curated subset manifest (stable, versioned)
  dataset_092624_validated.xlsx

results/                      # prompt_eval output (JSON), gitignored except baselines
  baseline_abstract.json
  ...

notebooks/
  prompt_eval_results.ipynb   # Template for loading and analyzing results
```
