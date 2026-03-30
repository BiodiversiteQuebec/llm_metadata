# Taxonomic Relevance Features Refactor

## Context & Motivation

Two notebooks have identified systematic problems with species extraction and evaluation that go beyond prompt tuning:

- **`notebooks/species_recall_improvement.ipynb`**: Tested a refined prompt on 10 open-access PDFs. Achieved F1=0.82 (+0.32), precision 74% (+34%), FP −66%. The improvements are documented and proven; they just need to be integrated into the shared prompt infrastructure.
- **`notebooks/taxonomic_relevance_evaluation.ipynb`**: Analyzed signal mismatches between GT annotations and LLM extractions. Identified that GT and model encode fundamentally different signals (count summaries vs enumerations, group labels vs species lists, vernacular vs scientific names) — these mismatches inflate apparent FP rates beyond what prompt changes can fix.

The refactor has two separable layers:
1. **Prompt-only (Phase 1)** — apply proven species extraction rules to shared prompt blocks. No schema or eval changes. Delivers immediate F1 improvement.
2. **Schema + eval (Phase 2+)** — structured taxon output model, decoupled evaluation signals, eval matcher cleanup. Requires schema and eval changes; scoped as follow-on work.

---

## Phase 1: Species Prompt Integration `sonnet` ← **do this now**

> **Sequencing note:** WU-T1 and WU-3.2 in `plans/prompt-engineering-flow.md` both modify `common.py`. Run them in the same session or sequentially — not in parallel.

### Prior findings (do not re-derive)

**From `species_recall_improvement.ipynb`:**

| Metric | Baseline | Improved prompt | Delta |
|---|---|---|---|
| Recall | 66.7% | 93.3% | +26.6% |
| Precision | 40.0% | 73.7% | +33.7% |
| F1 | 0.50 | 0.82 | +0.32 |
| False positives | 15 | 5 | −66% |

The precision improvement came from explicit focal-taxa scoping and negative examples (predators, hosts, comparison species). The recall improvement came from keeping decorated strings and using enhanced matching.

**From `taxonomic_relevance_evaluation.ipynb`:**

Signal mismatches that inflate apparent FP rates:
- GT `"73 weevil species"` vs model enumerates 73 names → mass FPs, not a real extraction error
- GT `"Caribou"` vs model `"Rangifer tarandus caribou"` → naming style, not wrong
- GT `"benthic intertidal community"` vs model lists annelids, molluscs → level-of-abstraction mismatch

---

### WU-T1: Add `SPECIES_EXTRACTION` block to `common.py` `sonnet`

**deps:** none | **files:** `src/llm_metadata/prompts/common.py`, `src/llm_metadata/prompts/abstract.py`

Add a named block `SPECIES_EXTRACTION` in `common.py` and include it in all mode prompts (abstract, section, pdf_file). Contents:

#### Rule 1 — Keep decorated strings (do NOT strip to canonical form)

`"common name (Scientific name)"` format is correct output. The `enhanced_species` matcher (threshold=70, containment-based) handles all of these cleanly:
- `"wood turtle (Glyptemys insculpta)"` → matches GT `"Glyptemys insculpta"` ✅
- `"raccoon (Procyon lotor L.)"` → matches GT `"raccoons"` ✅
- `"woodland caribou (Rangifer tarandus caribou)"` → matches GT `"caribou"` ✅

**Only strip:** subpopulation labels, sex/age qualifiers, habitat adjectives from the *surrounding words*:
- `"49 female caribou (Rangifer tarandus)"` → `"caribou (Rangifer tarandus)"` ✅
- `"forest-dwelling sedentary caribou"` → `"caribou"` ✅

#### Rule 2 — Count signals: group label, not enumeration

When the abstract states a count without naming individuals:
> "If the text says 'surveyed 73 weevil species' or '12 bird species were recorded' without listing them, output the group label with count: `'weevils (73 spp.)'` or `'birds (12 spp.)'`. Do NOT invent or enumerate individual species names to fill the count."

#### Rule 3 — Broad group labels are valid outputs

> "If focal taxa are described only at group level (order, family, common group), output the group label as-is: `'fish'`, `'ground-dwelling beetles'`, `'benthic invertebrates'`. Do not resolve group labels to specific species unless individual species are explicitly named in the text."

#### Rule 4 — Focal taxa scoping (proven effective: FP −66%)

> **Extract only focal dataset taxa — exclude context organisms.**
>
> - **Include:** species that are the direct subject of data collection; the primary study organisms
> - **Exclude:** predators, prey, parasites, host species, habitat/vegetation context taxa, species mentioned only in background, literature comparison, or discussion
>
> **Negative examples:**
> - Caribou study mentions wolves as predators → do NOT extract wolves
> - Fish survey mentions riparian vegetation → do NOT extract plant species
> - Abstract cites a prior bear study for comparison → do NOT extract bears
> - "We collected data in spruce-fir forests" → do NOT extract spruce or fir

#### Rule 5 — Subspecies: defer to the text's level of specificity

If the abstract says "caribou", output `"caribou"`. If it says "woodland caribou (*Rangifer tarandus caribou*)", output that. Do not promote or demote taxonomic resolution beyond what the text states.

---

### WU-T1b: Mode-specific species additions `sonnet`

**deps:** WU-T1 | **files:** `src/llm_metadata/prompts/section.py`, `src/llm_metadata/prompts/pdf_file.py`

After the shared block is in place, add mode-specific overrides:

**Sections mode** — add to `section.py`:
> "Participant subgroups, life stages (juvenile, adult), sex classes (male, female), and habitat ecotypes (forest-dwelling, migratory) are NOT separate taxa. Output the parent taxon only."

**PDF native mode** — add to `pdf_file.py`:
> "In full-text mode, extract ONLY taxa stated as part of the dataset collected by this study. Ignore all taxa in: introduction, literature review, discussion, comparisons with other studies, habitat descriptions, predator/prey relationships, and cited prior work."
>
> This is a hard exclusion — full text contains many more incidental taxon mentions than abstracts.

---

### WU-T1 Run protocol

1. Apply `SPECIES_EXTRACTION` block to `common.py` and include it in all three mode prompts
2. Run `prompt_eval --mode abstract`, compare `species` P/R/F1 vs March 27 baseline (P=0.29, R=0.65, F1=0.40)
3. Spot-check `data_type` and `geospatial_info_dataset` for regressions
4. After abstract stable: run sections and pdf_native modes, compare vs their baselines
5. Log per-field observations in run notes

**Success criteria:**
- Abstract mode: precision ≥ 0.50, F1 ≥ 0.55
- PDF native mode: precision ≥ 0.25 (from 0.10); if not, escalate to evidence-gated extraction (see Phase 2 note below)
- No regression on other fields

---

## Phase 2: Structured Taxon Schema `sonnet`

> **Status: backlog — do not start until Phase 1 is complete and stable.**

The flat `species: list[str]` field conflates three distinct signals that GT and model encode differently. A structured output model decouples them and enables principled evaluation.

### WU-T2: `ExtractedTaxon` Pydantic model

**deps:** WU-T1 | **files:** `src/llm_metadata/schemas/fuster_features.py`, `src/llm_metadata/prompts/common.py`

Replace `species: Optional[list[str]]` with `species: Optional[list[ExtractedTaxon]]` on `DatasetFeaturesExtraction`.

```python
class TaxonType(str, Enum):
    SPECIES = "species"         # individual species (named)
    GROUP = "group"             # taxonomic group / family / order
    COMMUNITY = "community"     # community-level label (e.g. "benthic intertidal")

class ExtractedTaxon(BaseModel):
    name: str                           # as it appears in text (decorated ok)
    taxon_type: TaxonType = TaxonType.SPECIES
    count: Optional[int] = None         # from "73 weevil species"
    scientific_name: Optional[str] = None
    common_name: Optional[str] = None
```

**Why:** Separating `count` from `name` solves the mass-FP problem from Rule 2 at the eval level, not just the prompt level. Separating `taxon_type` allows independent evaluation of species-level vs group-level extraction.

**Prompt change:** Update `SPECIES_EXTRACTION` block to request structured output. Examples:
- `"73 weevil species"` → `{name: "weevils (73 spp.)", taxon_type: "group", count: 73}`
- `"wood turtle (Glyptemys insculpta)"` → `{name: "wood turtle (Glyptemys insculpta)", taxon_type: "species", scientific_name: "Glyptemys insculpta", common_name: "wood turtle"}`

**GT migration:** `DatasetFeaturesNormalized` keeps `species: list[str]` for backward compat with existing GT. Add a `@validator` that coerces `list[str]` → `list[ExtractedTaxon]` with `taxon_type=SPECIES` by default. This keeps GT loading unchanged.

---

### WU-T3: Evaluation matcher refactor

**deps:** WU-T2 | **files:** `src/llm_metadata/groundtruth_eval.py`

Currently `compare_models()` has 3× duplicated TP/FP/FN logic for exact / fuzzy / enhanced_species paths. The `EnhancedSpeciesMatchConfig` is orphaned (superseded by `FieldEvalStrategy`).

**Work:**
- Extract a single `_compute_field_metrics(pred, true, strategy)` function used by all paths
- Delete `EnhancedSpeciesMatchConfig`
- Add `ParsedTaxonComparator` — matches `ExtractedTaxon` lists by normalized `scientific_name` / `common_name` fields (more principled than heuristic fuzzy containment)
- Register new `"structured_taxon"` match type in `FieldEvalStrategy`
- Update `DEFAULT_FIELD_STRATEGIES["species"]` from `enhanced_species` → `structured_taxon` once WU-T2 is deployed

**Separate evaluation signals** (from taxonomic_relevance_evaluation.ipynb findings):

| Signal | Field | Strategy |
|---|---|---|
| Species-level recovery | `species` filtered to `taxon_type=SPECIES` | `structured_taxon` |
| Group-level recovery | `species` filtered to `taxon_type=GROUP` | `exact` |
| Richness counts | `species.count` aggregated | numeric tolerance |
| Broad taxonomic relevance | `taxon_broad_group_labels` (derived) | `exact` set comparison |

`taxon_broad_group_labels` is a `DatasetFeaturesEvaluation`-only derived field: normalize all extracted taxa to coarse EBV group labels (mammals, birds, fish, etc.) for dataset-level relevance screening. Computed post-extraction, not by the LLM.

---

### WU-T4: GBIF enrichment integration (backlog)

**deps:** WU-T2, WU-T3 | **files:** `src/llm_metadata/gbif.py`, `src/llm_metadata/schemas/fuster_features.py`

Once `ExtractedTaxon.scientific_name` is a clean field (vs decorated string), GBIF key lookup becomes reliable. Update the enrichment pipeline to populate `DatasetFeaturesEvaluation.gbif_keys` from `scientific_name` rather than the raw decorated string.

Use `gbif_keys` beyond evaluation for actual data gap analysis — this is the end goal.

---

## Execution Rounds

```
Phase 1 (now):
  Round 1: WU-T1                    (SPECIES_EXTRACTION block, common.py)
  Round 2: WU-T1b                   (mode-specific overrides, section.py + pdf_file.py)
  Round 3: eval runs + observations  (abstract → sections → pdf_native)

Phase 2 (after Phase 1 stable):
  Round 1: WU-T2                    (ExtractedTaxon schema + GT migration)
  Round 2: WU-T3                    (eval matcher refactor + ParsedTaxonComparator)
  Round 3: WU-T4                    (GBIF enrichment on clean scientific_name)
```

## Key files

| File | Role |
|---|---|
| `src/llm_metadata/prompts/common.py` | `SPECIES_EXTRACTION` block (Phase 1) |
| `src/llm_metadata/prompts/section.py` | Mode-specific override (Phase 1) |
| `src/llm_metadata/prompts/pdf_file.py` | Mode-specific override (Phase 1) |
| `src/llm_metadata/schemas/fuster_features.py` | `ExtractedTaxon`, `TaxonType` (Phase 2) |
| `src/llm_metadata/groundtruth_eval.py` | Matcher refactor, `ParsedTaxonComparator` (Phase 2) |
| `notebooks/species_recall_improvement.ipynb` | Prior experiment — reference for prompt rules |
| `notebooks/taxonomic_relevance_evaluation.ipynb` | Signal mismatch analysis — reference for eval design |
