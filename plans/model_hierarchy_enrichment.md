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
                 /            |            \
                /             |             \
ExtractionFeatureModel  GroundTruthFeatureModel  EvaluationFeatureModel
(LLM output contract)   (same fields + GT        (+ derived enrichment fields only)
                        normalization validators)
```

- **CoreFeatureModel**: Shared semantic fields only. No source metadata, no derived enrichment outputs.
- **ExtractionFeatureModel**: What the LLM actually outputs. This is the `text_format` contract.
- **GroundTruthFeatureModel**: Same semantic field set as extraction, plus validators/coercion for spreadsheets and CSVs.
- **EvaluationFeatureModel**: Derived fields for strategy comparison. Populated by enrichment preprocessing after model construction.

Source/provenance metadata should not become another feature-model subclass. It already fits better on the record/manifest contract (`DataPaperRecord`) because it describes where a paper came from, not what semantic features were extracted from its text.

## Naming Notes

Current code uses `DatasetFeatures` and `DatasetFeaturesNormalized`. The exact class names can change during implementation, but the separation of concerns should not.

Recommended landing names:
- `DatasetFeaturesExtraction`
- `DatasetFeaturesNormalized`
- `DatasetFeaturesEvaluation`

Do not add a `SourceTrackedFeatureModel` unless a concrete use case appears that cannot be handled at the `DataPaperRecord` level.

## Enrichment Pattern Decisions

### Function signature convention

Every enrichment should follow a two-step pattern:

```python
payload = resolve_with_X(model.species, **config)
enriched = DatasetFeaturesEvaluation.from_extraction(model, x=payload)
```

### Where lookup logic lives

External lookup logic lives in its **API wrapper module** (`gbif.py`, future `gadm.py`), not on the model class. Rationale:

- **Avoids God class**: Model doesn't accumulate methods for every external service
- **Dependency direction**: API modules → schemas (not reversed)
- **Testing**: Enrichment testable alongside API mocks, no schema import gymnastics
- **Composition**: notebooks can resolve one or more payloads, then build one evaluation model from them

These functions may return typed payloads such as `list[ResolvedTaxon]`, `list[int]`, or a small enrichment result model. They should not construct `EvaluationFeatureModel` themselves.

### Where contract construction lives

Construction of the enriched evaluation contract should live on the evaluation model itself via classmethods or copy helpers that do **no I/O**:

```python
class DatasetFeaturesEvaluation(CoreFeatureModel):
    @classmethod
    def from_extraction(
        cls,
        model: DatasetFeaturesExtraction | DatasetFeaturesNormalized,
        *,
        gbif: Optional[list[ResolvedTaxon]] = None,
        gadm: Optional[list[GadmMatch]] = None,
    ) -> "DatasetFeaturesEvaluation":
        ...
```

This keeps external service access out of the model while still making the evaluation contract the canonical place where derived fields are assembled.

### Why not methods on the model

Methods that perform network lookups on the model were discussed and rejected. They create a God class, invert dependencies, and hide I/O inside what should be a pure data contract.

Pure constructor/copy methods on the evaluation model are acceptable and preferred, because they only assemble already-resolved enrichment payloads into the typed contract.

### Why not Pydantic validators

Validators must be pure and fast. Enrichment involves network I/O (GBIF API, GADM lookups). Validators normalize (splits, strips, vocabulary mapping). Enrichment is a separate pipeline step.

## Migration Scope

The hierarchy refactor touches:
- `schemas/fuster_features.py` — split `DatasetFeatures` into role-specific models
- `prompt_eval.py`, `extraction.py`, and any direct `responses.parse()` call sites — use extraction model only
- GT loading and validation paths — use GT-normalized model only
- `taxonomy_eval.py`, `gbif.py`, future `nominatim.py` — return lookup payloads or feed evaluation-model constructors
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
- Keep source metadata on `DataPaperRecord` unless a concrete counterexample emerges.
- Keep current ingest/manifest workflows working without forcing prompt changes.

#### WU-MH3: Rewire extraction and GT validation entry points `sonnet`

**deps:** WU-MH1, WU-MH2 | **files:** `src/llm_metadata/prompt_eval.py`, `src/llm_metadata/extraction.py`, `src/llm_metadata/gpt_extract.py`, notebooks that pass `text_format=...`

- Ensure `responses.parse()` and extraction pipelines use the extraction-only model.
- Ensure spreadsheet/CSV/manual annotation loading uses the GT-normalized model.
- Remove enrichment-only fields from any schema shown to the LLM.

#### WU-MH4: Move taxonomy enrichment onto evaluation model `sonnet`

**deps:** WU-MH3 | **files:** `src/llm_metadata/species_parsing.py`, `src/llm_metadata/taxonomy_eval.py`, `src/llm_metadata/gbif.py`, `tests/test_species_parsing.py`, `tests/test_taxonomy_eval.py`, `tests/test_gbif_enrichment.py`

- Change service helpers to return lookup payloads, not evaluation models.
- Add evaluation-model constructors/copy helpers that assemble derived fields from those payloads.
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
- Evaluation-model constructors are pure: no network I/O, no hidden lookups.
- Existing evaluation notebooks continue to run after updating imports/model names.
- At least one test asserts the extraction schema and evaluation schema differ intentionally.
