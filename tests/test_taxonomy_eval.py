"""Tests for taxonomy-focused enrichment and evaluation helpers."""

import pytest

from llm_metadata.groundtruth_eval import EvaluationConfig
from llm_metadata.schemas.fuster_features import DatasetFeatures
from llm_metadata.taxonomy_eval import (
    DEFAULT_TAXONOMY_FIELDS,
    build_taxonomy_eval_config,
    enrich_with_taxonomy,
    evaluate_taxonomy_fields,
)


class TestEnrichWithTaxonomy:

    def test_populates_analysis_fields_without_gbif(self):
        model = DatasetFeatures(species=["73 weevil species", "Tamias striatus"])

        enriched = enrich_with_taxonomy(model, include_gbif=False)

        assert enriched.parsed_species is not None
        assert enriched.taxon_richness_mentions is not None
        assert enriched.taxon_richness_counts == [73]
        assert enriched.taxon_richness_group_keys == ["73|weevil"]
        assert enriched.gbif_keys is None

    def test_falls_back_to_species_list_length(self):
        model = DatasetFeatures(species=["Tamias striatus", "Rangifer tarandus"])

        enriched = enrich_with_taxonomy(model, include_gbif=False)

        assert enriched.taxon_richness_mentions is None
        assert enriched.taxon_richness_counts == [2]
        assert enriched.taxon_richness_group_keys is None

    def test_can_delegate_to_gbif_enrichment(self, monkeypatch: pytest.MonkeyPatch):
        model = DatasetFeatures(species=["Tamias striatus"])

        def fake_enrich_with_gbif(model, confidence_threshold=80, accept_higherrank=True):
            return model.model_copy(update={"gbif_keys": [5219243]})

        monkeypatch.setattr("llm_metadata.taxonomy_eval.enrich_with_gbif", fake_enrich_with_gbif)
        enriched = enrich_with_taxonomy(model, include_gbif=True)

        assert enriched.gbif_keys == [5219243]


class TestBuildTaxonomyEvalConfig:

    def test_defaults_to_taxonomy_field_subset(self):
        config = build_taxonomy_eval_config()
        assert isinstance(config, EvaluationConfig)
        assert set(config.field_strategies.keys()) == set(DEFAULT_TAXONOMY_FIELDS)

    def test_can_focus_to_subset(self):
        config = build_taxonomy_eval_config(["taxon_richness_counts"])
        assert list(config.field_strategies.keys()) == ["taxon_richness_counts"]


class TestEvaluateTaxonomyFields:

    def test_count_based_gt_matches_enumerated_prediction(self):
        true_by_id = {
            "1": DatasetFeatures(species=["73 weevil species"]),
        }
        pred_by_id = {
            "1": DatasetFeatures(species=[f"Taxon {i}" for i in range(73)]),
        }

        report = evaluate_taxonomy_fields(
            true_by_id=true_by_id,
            pred_by_id=pred_by_id,
            fields=["taxon_richness_counts"],
            include_gbif=False,
        )

        metrics = report.metrics_for("taxon_richness_counts")
        assert metrics.tp == 1
        assert metrics.fp == 0
        assert metrics.fn == 0

    def test_group_keys_are_evaluated_as_exact_projected_fields(self):
        true_by_id = {
            "1": DatasetFeatures(species=["199 ground-dwelling beetles"]),
        }
        pred_by_id = {
            "1": DatasetFeatures(species=["199 ground-dwelling beetles species"]),
        }

        report = evaluate_taxonomy_fields(
            true_by_id=true_by_id,
            pred_by_id=pred_by_id,
            fields=["taxon_richness_group_keys"],
            include_gbif=False,
        )

        metrics = report.metrics_for("taxon_richness_group_keys")
        assert metrics.tp == 1
        assert metrics.fp == 0
        assert metrics.fn == 0
