"""Helpers for notebook-based taxonomic relevance evaluation."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Collection, Optional

from llm_metadata.gbif import ResolvedTaxon, resolve_species_list
from llm_metadata.groundtruth_eval import (
    EvaluationConfig,
    EvaluationReport,
    FieldEvalStrategy,
    evaluate_indexed,
)
from llm_metadata.schemas.data_paper import RunArtifact
from llm_metadata.schemas.fuster_features import (
    CoreFeatureModel,
    DatasetFeaturesEvaluation,
    DatasetFeaturesExtraction,
    DatasetFeaturesNormalized,
)
from llm_metadata.species_parsing import (
    extract_parsed_taxa,
    extract_taxon_richness_mentions,
    normalize_taxon_group,
    project_species_stripped_richness,
    project_taxon_richness_counts,
    project_taxon_richness_group_keys,
)

_LIST_COLS = ["data_type", "geospatial_info_dataset", "species"]

DEFAULT_TAXONOMY_FIELD_STRATEGIES: dict[str, FieldEvalStrategy] = {
    "species": FieldEvalStrategy(match="enhanced_species", threshold=70),
    "species_stripped_richness": FieldEvalStrategy(
        match="enhanced_species",
        threshold=70,
        applicability="true_present",
    ),
    "gbif_key_stripped_richness": FieldEvalStrategy(match="exact", applicability="both_present"),
    "taxon_richness_counts": FieldEvalStrategy(match="exact"),
    "taxon_richness_group_keys": FieldEvalStrategy(match="exact"),
    "taxon_broad_group_labels": FieldEvalStrategy(match="exact"),
    "gbif_keys": FieldEvalStrategy(match="exact"),
}
DEFAULT_TAXONOMY_FIELDS = list(DEFAULT_TAXONOMY_FIELD_STRATEGIES.keys())

_GBIF_GROUP_LABELS = {
    "class": {
        "AVES": "bird",
        "MAMMALIA": "mammal",
        "ACTINOPTERYGII": "fish",
        "ELASMOBRANCHII": "fish",
    },
    "order": {
        "COLEOPTERA": "beetle",
        "IXODIDA": "tick",
        "TROMBIDIFORMES": "mite",
        "MESOSTIGMATA": "mite",
        "SARCOPTIFORMES": "mite",
    },
    "family": {
        "CURCULIONIDAE": "weevil",
        "BRENTIDAE": "weevil",
        "ANTHRIBIDAE": "weevil",
        "ATTELABIDAE": "weevil",
    },
    "phylum": {
        "ARTHROPODA": "arthropod",
        "MOLLUSCA": "mollusc",
        "ANNELIDA": "annelid",
    },
}


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
    """Load validated GT rows and return normalized feature models keyed by record id."""
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
    model_type: type[DatasetFeaturesExtraction] = DatasetFeaturesExtraction,
) -> dict[str, DatasetFeaturesExtraction]:
    """Load successful predictions from a saved `RunArtifact` JSON."""
    artifact = RunArtifact.load_json(run_artifact_path)
    return artifact.predictions_by_id(model_type)  # type: ignore[return-value]


def project_taxon_broad_group_labels(
    model: CoreFeatureModel,
    *,
    use_gbif: bool = True,
    confidence_threshold: int = 80,
    accept_higherrank: bool = True,
    resolved_taxa: Optional[list[ResolvedTaxon]] = None,
) -> Optional[list[str]]:
    """Project a model into broad comparison-oriented group labels."""
    labels: set[str] = set()

    parsed_species = extract_parsed_taxa(model.species) or []
    richness_mentions = extract_taxon_richness_mentions(model.species) or []

    for mention in richness_mentions:
        if mention.normalized_group:
            labels.add(mention.normalized_group)

    for parsed in parsed_species:
        if parsed.is_group_description and parsed.vernacular:
            group = normalize_taxon_group(parsed.vernacular)
            if group:
                labels.add(group)

    if use_gbif and model.species:
        gbif_payload = resolved_taxa or resolve_species_list(
            list(model.species),
            confidence_threshold=confidence_threshold,
            accept_higherrank=accept_higherrank,
        )
        for resolved in gbif_payload:
            match = resolved.gbif_match
            if match is None:
                continue
            for rank_name, attr_name in (
                ("family", "family"),
                ("order", "order"),
                ("class", "class_name"),
                ("phylum", "phylum"),
            ):
                rank_value = getattr(match, attr_name, None)
                if not rank_value:
                    continue
                mapped = _GBIF_GROUP_LABELS[rank_name].get(str(rank_value).upper())
                if mapped:
                    labels.add(mapped)
                    break

    return sorted(labels) or None


def project_gbif_key_stripped_richness(
    stripped_species: Optional[Collection[str]],
    *,
    confidence_threshold: int = 80,
    accept_higherrank: bool = True,
    resolved_taxa: Optional[list[ResolvedTaxon]] = None,
) -> Optional[list[int]]:
    """Resolve richness-stripped species residue to GBIF backbone keys."""
    if not stripped_species:
        return None

    stripped_list = [item for item in stripped_species if isinstance(item, str) and item.strip()]
    if not stripped_list:
        return None

    payload = resolved_taxa
    if payload is None:
        payload = resolve_species_list(
            stripped_list,
            confidence_threshold=confidence_threshold,
            accept_higherrank=accept_higherrank,
        )

    keys: set[int] = set()
    for resolved in payload:
        match = resolved.gbif_match
        if match is None:
            continue
        keys.add(match.gbif_key)

    return sorted(keys) or None


def enrich_with_taxonomy(
    model: CoreFeatureModel,
    *,
    include_gbif: bool = True,
    gbif_confidence_threshold: int = 80,
    accept_higherrank: bool = True,
) -> DatasetFeaturesEvaluation:
    """Build an evaluation model populated with taxonomy-derived fields."""
    parsed_species = extract_parsed_taxa(model.species)
    richness_mentions = extract_taxon_richness_mentions(model.species)
    stripped_species = project_species_stripped_richness(model.species)
    resolved_taxa: Optional[list[ResolvedTaxon]] = None
    stripped_resolved_taxa: Optional[list[ResolvedTaxon]] = None

    if include_gbif and model.species:
        resolved_taxa = resolve_species_list(
            list(model.species),
            confidence_threshold=gbif_confidence_threshold,
            accept_higherrank=accept_higherrank,
        )
    if include_gbif and stripped_species:
        stripped_resolved_taxa = resolve_species_list(
            list(stripped_species),
            confidence_threshold=gbif_confidence_threshold,
            accept_higherrank=accept_higherrank,
        )

    broad_group_labels = project_taxon_broad_group_labels(
        model,
        use_gbif=include_gbif,
        confidence_threshold=gbif_confidence_threshold,
        accept_higherrank=accept_higherrank,
        resolved_taxa=resolved_taxa,
    )

    return DatasetFeaturesEvaluation.from_extraction(
        model,
        gbif=resolved_taxa,
        parsed_species=parsed_species,
        taxon_richness_mentions=richness_mentions,
        taxon_richness_counts=project_taxon_richness_counts(model.species, richness_mentions),
        taxon_richness_group_keys=project_taxon_richness_group_keys(richness_mentions),
        taxon_broad_group_labels=broad_group_labels,
        species_stripped_richness=stripped_species,
        gbif_key_stripped_richness=project_gbif_key_stripped_richness(
            stripped_species,
            confidence_threshold=gbif_confidence_threshold,
            accept_higherrank=accept_higherrank,
            resolved_taxa=stripped_resolved_taxa,
        )
        if include_gbif
        else None,
    )


def enrich_indexed_models(
    models_by_id: dict[str, CoreFeatureModel],
    *,
    include_gbif: bool = True,
    gbif_confidence_threshold: int = 80,
    accept_higherrank: bool = True,
) -> dict[str, DatasetFeaturesEvaluation]:
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
    true_by_id: dict[str, CoreFeatureModel],
    pred_by_id: dict[str, CoreFeatureModel],
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
