# Model Hierarchy & Enrichment Pattern Refactor

## Context

`DatasetFeatures` is currently a single model containing extraction fields, source tracking fields (`is_oa`, `source_url`), and soon derived evaluation fields (`gbif_keys`). These serve different purposes and different consumers. As enrichment sources multiply (GBIF, GADM, data source matching), the model becomes a God class mixing concerns.

This plan captures the design direction discussed during the GBIF planning session for future implementation.

## Current State

```
DatasetFeatures              ← all Optional fields in one flat model
  └── DatasetFeaturesNormalized  ← adds validators for ground truth cleaning
```

- Source tracking fields (`source`, `is_oa`, `pdf_url`, `source_url`, `cited_article_doi`) live on `DatasetFeatures` alongside extraction fields
- Enrichment fields (`gbif_keys`, future `gadm_codes`) will also land on `DatasetFeatures`
- `compare_models()` handles mixed-field models by comparing field intersection (line 351-352), so this works but conflates concerns

## Proposed Hierarchy

```
                     BaseFeatureModel
                  (species, data_type, spatial_range, temporal_range,
                   modulators, ... — core annotated/extracted fields)
                      /                    \
       SourcesFeatureModel            ExtractionFeatureModel
    (+ source, is_oa, pdf_url,       (= identical to Base,
     source_url, cited_article_doi)    what the LLM produces)
                                            \
                                      EvaluationFeatureModel
                                     (+ gbif_keys, gadm_codes,
                                      other derived comparison fields)
```

- **BaseFeatureModel**: Fields that annotators fill in AND that the LLM extracts. The shared contract.
- **SourcesFeatureModel**: Pipeline metadata about where the data came from. Not annotated, not extracted.
- **ExtractionFeatureModel**: What the LLM actually outputs. May be identical to Base or add extraction-specific metadata (cost, model used).
- **EvaluationFeatureModel**: Derived fields for strategy comparison. Populated by enrichment preprocessing.

## Enrichment Pattern Decisions

### Function signature convention

Every enrichment follows the same pattern:

```python
def enrich_with_X(model: DatasetFeatures, **config) -> DatasetFeatures:
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

If the model hierarchy is implemented, the enrichment return type narrows to `EvaluationFeatureModel`, but the function stays in the API module.

### Why not methods on the model

Discussed and rejected for multiple enrichment sources. Works fine for one source but creates God class at three. Lazy imports mitigate circular deps but don't solve the cohesion problem.

### Why not Pydantic validators

Validators must be pure and fast. Enrichment involves network I/O (GBIF API, GADM lookups). Validators normalize (splits, strips, vocabulary mapping). Enrichment is a separate pipeline step.

## Migration Scope

The hierarchy refactor touches:
- `schemas/fuster_features.py` — split `DatasetFeatures` into hierarchy
- All notebooks constructing `DatasetFeatures` — pick the right subclass
- All extraction (`text_pipeline.py`, `pdf_pipeline.py`, etc.) — update return types
- `groundtruth_eval.py` — may benefit but `compare_models()` already handles mixed fields
- Tests — update model construction

Estimate: medium effort, mechanical but wide-reaching. Best done as a standalone initiative, not bolted onto a feature task.
