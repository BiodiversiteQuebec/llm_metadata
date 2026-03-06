# Model Hierarchy & Enrichment Pattern Refactor

## Context

`DatasetFeatures` is currently a single model containing:
- extraction-contract fields sent to the LLM,
- source tracking fields (`source`, `is_oa`, `source_url`, `pdf_url`, `cited_article_doi`),
- derived enrichment/evaluation fields (`parsed_species`, `taxon_richness_mentions`, `taxon_richness_counts`, `taxon_richness_group_keys`, `taxon_broad_group_labels`, `gbif_keys`).

These serve different purposes and different consumers. As enrichment sources multiply (GBIF, GADM, data source matching), the model becomes a God class mixing concerns.

This plan captures the design direction discussed during the GBIF planning session and refined after the taxonomic relevance notebook work.

## Current State

```
DatasetFeatures                 ← extraction + source metadata + enrichment fields
  └── DatasetFeaturesNormalized ← adds validators for ground truth cleaning
```

- Source tracking fields (`source`, `is_oa`, `pdf_url`, `source_url`, `cited_article_doi`) live on `DatasetFeatures` alongside extraction fields
- Enrichment fields (`parsed_species`, `taxon_richness_mentions`, `taxon_richness_counts`, `taxon_richness_group_keys`, `taxon_broad_group_labels`, `gbif_keys`, future `gadm_codes`) live on `DatasetFeatures`
- `compare_models()` handles mixed-field models by comparing field intersection (line 351-352), so this works but conflates concerns

## Decision

The extraction contract and GT validation contract should not carry enrichment-only fields.

- The schema sent to `responses.parse()` should include only fields the model is allowed to emit.
- The GT validation model should include only fields that can appear in manual annotations plus normalization validators.
- Enrichment/evaluation fields should live on a separate model used after preprocessing.
- Source-tracking metadata should also be separated from the extraction contract.

## Proposed Hierarchy

```
                     CoreFeatureModel
               (species, data_type, spatial_range, temporal_range,
                modulators, validity fields, ... — shared semantics)
                    /            |             \
                   /             |              \
      ExtractionFeatureModel  GroundTruthFeatureModel  SourceTrackedFeatureModel
      (LLM output contract)   (same fields + GT        (+ source metadata only)
                              normalization validators)
                   \             /
                    \           /
                 EvaluationFeatureModel
          (+ parsed_species, taxon_richness_mentions,
           taxon_richness_counts, taxon_richness_group_keys,
           taxon_broad_group_labels, gbif_keys, future derived fields)
```

- **CoreFeatureModel**: Shared semantic fields only. No source metadata, no derived enrichment outputs.
- **ExtractionFeatureModel**: What the LLM actually outputs. This is the `text_format` contract.
- **GroundTruthFeatureModel**: Same semantic field set as extraction, plus validators/coercion for spreadsheets and CSVs.
- **SourceTrackedFeatureModel**: Pipeline metadata about where the record came from. Not extracted and not part of GT semantic scoring.
- **EvaluationFeatureModel**: Derived fields for strategy comparison. Populated by enrichment preprocessing after model construction.

## Naming Notes

Current code uses `DatasetFeatures` and `DatasetFeaturesNormalized`. The exact class names can change during implementation, but the separation of concerns should not.

Recommended landing names:
- `DatasetFeaturesExtraction`
- `DatasetFeaturesNormalized`
- `DatasetFeaturesEvaluation`

Optional if source metadata stays coupled to records outside the feature model:
- `DatasetSourceMetadata`
- or a small `DataPaperRecord`-level metadata container instead of a feature subclass

## Enrichment Pattern Decisions

### Function signature convention

Every enrichment follows the same pattern:

```python
def enrich_with_X(model: DatasetFeaturesExtraction, **config) -> DatasetFeaturesEvaluation:
    """Returns a copy with derived fields populated. No mutation."""
    ...
    return model.model_copy(update={"X_keys": ...})
```

### Where enrichment logic lives

Enrichment functions live in their **API wrapper module** (`gbif.py`, future `gadm.py`), not on the model class. Rationale:

- **Avoids God class**: Model doesn't accumulate methods for every external service
- **Dependency direction**: API modules → schemas (not reversed)
- **Testing**: Enrichment testable alongside API mocks, no schema import gymnastics
- **Composition**: Notebooks chain calls: `model = enrich_with_gbif(enrich_with_gadm(model))`

If the model hierarchy is implemented, the enrichment return type should narrow to `EvaluationFeatureModel`, but the function stays in the API module.

### Why not methods on the model

Discussed and rejected for multiple enrichment sources. Works fine for one source but creates God class at three. Lazy imports mitigate circular deps but don't solve the cohesion problem.

### Why not Pydantic validators

Validators must be pure and fast. Enrichment involves network I/O (GBIF API, GADM lookups). Validators normalize (splits, strips, vocabulary mapping). Enrichment is a separate pipeline step.

## Migration Scope

The hierarchy refactor touches:
- `schemas/fuster_features.py` — split `DatasetFeatures` into role-specific models
- `prompt_eval.py`, `extraction.py`, and any direct `responses.parse()` call sites — use extraction model only
- GT loading and validation paths — use GT-normalized model only
- `taxonomy_eval.py`, `gbif.py`, future `nominatim.py` — return evaluation model only
- notebooks constructing `DatasetFeatures` — pick the right subclass
- tests — update model construction and assertions

Estimate: medium effort, mechanical but wide-reaching. Best done as a standalone initiative, not bolted onto a feature task.

## Execution Rounds

Round 1: WU-MH1 || WU-MH2
Round 2: WU-MH3
Round 3: WU-MH4 || WU-MH5
Round 4: WU-MH6

#### WU-MH1: Define target model split `sonnet`

**deps:** none | **files:** `src/llm_metadata/schemas/fuster_features.py`, `src/llm_metadata/schemas/__init__.py`

- Introduce separate core, extraction, GT-normalized, and evaluation-oriented models.
- Keep field semantics unchanged for the shared core fields.
- Preserve backward compatibility with aliases or transitional exports where feasible.

#### WU-MH2: Separate source metadata from extraction contract `sonnet`

**deps:** none | **files:** `src/llm_metadata/schemas/fuster_features.py`, `src/llm_metadata/schemas/data_paper.py`, `tests/test_multisource_integration.py`, `tests/test_datasource_schema.py`

- Remove source-tracking fields from the extraction model.
- Decide whether source metadata belongs on a dedicated feature subclass or on `DataPaperRecord`.
- Keep current ingest/manifest workflows working without forcing prompt changes.

#### WU-MH3: Rewire extraction and GT validation entry points `sonnet`

**deps:** WU-MH1, WU-MH2 | **files:** `src/llm_metadata/prompt_eval.py`, `src/llm_metadata/extraction.py`, `src/llm_metadata/gpt_extract.py`, notebooks that pass `text_format=...`

- Ensure `responses.parse()` and extraction pipelines use the extraction-only model.
- Ensure spreadsheet/CSV/manual annotation loading uses the GT-normalized model.
- Remove enrichment-only fields from any schema shown to the LLM.

#### WU-MH4: Move taxonomy enrichment onto evaluation model `sonnet`

**deps:** WU-MH3 | **files:** `src/llm_metadata/species_parsing.py`, `src/llm_metadata/taxonomy_eval.py`, `src/llm_metadata/gbif.py`, `tests/test_species_parsing.py`, `tests/test_taxonomy_eval.py`, `tests/test_gbif_enrichment.py`

- Change enrichment helpers to return the evaluation-oriented model.
- Keep enrichment as explicit preprocessing, not validators.
- Confirm notebook-oriented derived fields remain available only after enrichment.

#### WU-MH5: Align future enrichment plans with hierarchy `haiku`

**deps:** WU-MH3 | **files:** `plans/gbif_species_matching.md`, `plans/nominatim_enrichment.md`, `TODO.md`

- Update related plans so new enrichment fields target the evaluation model rather than the extraction contract.
- Remove stale assumptions that enrichment fields belong on `DatasetFeatures`.

#### WU-MH6: Notebook and test migration sweep `haiku`

**deps:** WU-MH4, WU-MH5 | **files:** `notebooks/`, `tests/`, `notebooks/README.md`

- Update notebooks to use the correct model at each step.
- Add at least one regression test asserting enrichment fields are absent from the extraction schema sent to the LLM.
- Log the refactor and any metric changes caused by contract cleanup.

## Acceptance Criteria

- The schema passed to `responses.parse()` contains no source-tracking or enrichment-only fields.
- GT validation still accepts the same human-annotated semantic fields as before.
- Taxonomy enrichment helpers still support `parsed_species`, richness projections, broad-group labels, and `gbif_keys`.
- Existing evaluation notebooks continue to run after updating imports/model names.
- At least one test asserts the extraction schema and evaluation schema differ intentionally.
