"""Helpers for notebook-based taxonomic relevance evaluation.

These utilities enrich `DatasetFeatures` with derived taxonomic comparison
fields while preserving the original raw extraction contract:

- `parsed_species`: structured name parsing for analysis
- `taxon_richness_mentions`: structured count + group mentions
- `taxon_richness_counts`: projected counts for comparison
- `taxon_richness_group_keys`: projected count+group keys for comparison
- `gbif_keys`: GBIF taxon IDs derived from parsed taxa

The intended usage is notebook-first: load an existing `RunArtifact`, enrich
ground truth and predictions, then evaluate only the field subset relevant to
the question being asked.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Collection, Optional

from llm_metadata.gbif import enrich_with_gbif
from llm_metadata.groundtruth_eval import (
    EvaluationConfig,
    EvaluationReport,
    FieldEvalStrategy,
    evaluate_indexed,
)
from llm_metadata.schemas.data_paper import RunArtifact
from llm_metadata.schemas.fuster_features import DatasetFeatures, DatasetFeaturesNormalized
from llm_metadata.species_parsing import (
    extract_parsed_taxa,
    extract_taxon_richness_mentions,
    project_taxon_richness_counts,
    project_taxon_richness_group_keys,
)

_LIST_COLS = ["data_type", "geospatial_info_dataset", "species"]

DEFAULT_TAXONOMY_FIELD_STRATEGIES: dict[str, FieldEvalStrategy] = {
    "species": FieldEvalStrategy(match="enhanced_species", threshold=70),
    "taxon_richness_counts": FieldEvalStrategy(match="exact"),
    "taxon_richness_group_keys": FieldEvalStrategy(match="exact"),
    "gbif_keys": FieldEvalStrategy(match="exact"),
}
DEFAULT_TAXONOMY_FIELDS = list(DEFAULT_TAXONOMY_FIELD_STRATEGIES.keys())


def _parse_excel_val(val):
    if val is None:
        return None
    try:
        import pandas as pd  # type: ignore

        if isinstance(val, float) and pd.isna(val):
            return None
    except ImportError:
        pass
    if isinstance(val, list):
        return val
    if isinstance(val, str):
        stripped = val.strip()
        if stripped.startswith("["):
            try:
                return ast.literal_eval(stripped)
            except Exception:
                return val
    return val


def build_ground_truth_by_id(
    gt_path: str | Path = "data/dataset_092624_validated.xlsx",
    allowed_ids: Optional[Collection[int]] = None,
) -> dict[str, DatasetFeaturesNormalized]:
    """Load validated GT rows and return `DatasetFeaturesNormalized` keyed by record id."""
    try:
        import pandas as pd  # type: ignore
    except ImportError as exc:
        raise ImportError(
            "pandas is required for taxonomy notebook helpers; install with `pip install pandas openpyxl`."
        ) from exc

    df = pd.read_excel(gt_path)
    for col in _LIST_COLS:
        if col in df.columns:
            df[col] = df[col].map(_parse_excel_val)

    allowed = {int(value) for value in allowed_ids} if allowed_ids is not None else None
    out: dict[str, DatasetFeaturesNormalized] = {}
    for _, row in df.iterrows():
        record_id = int(row["id"])
        if allowed is not None and record_id not in allowed:
            continue
        out[str(record_id)] = DatasetFeaturesNormalized.model_validate(row.to_dict())
    return out


def load_predictions_by_id(
    run_artifact_path: str | Path,
    model_type: type[DatasetFeatures] = DatasetFeatures,
) -> dict[str, DatasetFeatures]:
    """Load successful predictions from a saved `RunArtifact` JSON."""
    artifact = RunArtifact.load_json(run_artifact_path)
    return artifact.predictions_by_id(model_type)  # type: ignore[return-value]


def enrich_with_taxonomy(
    model: DatasetFeatures,
    *,
    include_gbif: bool = True,
    gbif_confidence_threshold: int = 80,
    accept_higherrank: bool = True,
) -> DatasetFeatures:
    """Return a copy of `model` with derived taxonomy analysis fields populated."""
    parsed_species = extract_parsed_taxa(model.species)
    richness_mentions = extract_taxon_richness_mentions(model.species)
    richness_counts = project_taxon_richness_counts(model.species, richness_mentions)
    richness_group_keys = project_taxon_richness_group_keys(richness_mentions)

    enriched = model.model_copy(
        update={
            "parsed_species": parsed_species,
            "taxon_richness_mentions": richness_mentions,
            "taxon_richness_counts": richness_counts,
            "taxon_richness_group_keys": richness_group_keys,
        }
    )
    if include_gbif:
        enriched = enrich_with_gbif(
            enriched,
            confidence_threshold=gbif_confidence_threshold,
            accept_higherrank=accept_higherrank,
        )
    return enriched


def enrich_indexed_models(
    models_by_id: dict[str, DatasetFeatures],
    *,
    include_gbif: bool = True,
    gbif_confidence_threshold: int = 80,
    accept_higherrank: bool = True,
) -> dict[str, DatasetFeatures]:
    """Apply `enrich_with_taxonomy` to each record in an indexed model dictionary."""
    return {
        record_id: enrich_with_taxonomy(
            model,
            include_gbif=include_gbif,
            gbif_confidence_threshold=gbif_confidence_threshold,
            accept_higherrank=accept_higherrank,
        )
        for record_id, model in models_by_id.items()
    }


def build_taxonomy_eval_config(
    fields: Optional[Collection[str]] = None,
) -> EvaluationConfig:
    """Build an `EvaluationConfig` focused on taxonomic relevance fields."""
    field_names = list(fields) if fields is not None else DEFAULT_TAXONOMY_FIELDS
    strategies = {
        name: DEFAULT_TAXONOMY_FIELD_STRATEGIES[name]
        for name in field_names
        if name in DEFAULT_TAXONOMY_FIELD_STRATEGIES
    }
    return EvaluationConfig(field_strategies=strategies)


def evaluate_taxonomy_fields(
    *,
    true_by_id: dict[str, DatasetFeatures],
    pred_by_id: dict[str, DatasetFeatures],
    fields: Optional[Collection[str]] = None,
    include_gbif: bool = True,
    gbif_confidence_threshold: int = 80,
    accept_higherrank: bool = True,
    config: Optional[EvaluationConfig] = None,
) -> EvaluationReport:
    """Enrich both sides and evaluate a taxonomy-focused field subset."""
    eval_fields = list(fields) if fields is not None else DEFAULT_TAXONOMY_FIELDS
    eval_config = config or build_taxonomy_eval_config(eval_fields)

    true_enriched = enrich_indexed_models(
        true_by_id,
        include_gbif=include_gbif,
        gbif_confidence_threshold=gbif_confidence_threshold,
        accept_higherrank=accept_higherrank,
    )
    pred_enriched = enrich_indexed_models(
        pred_by_id,
        include_gbif=include_gbif,
        gbif_confidence_threshold=gbif_confidence_threshold,
        accept_higherrank=accept_higherrank,
    )

    return evaluate_indexed(
        true_by_id=true_enriched,
        pred_by_id=pred_enriched,
        fields=eval_fields,
        config=eval_config,
    )
