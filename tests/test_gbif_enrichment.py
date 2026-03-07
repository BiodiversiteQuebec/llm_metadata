"""Unit tests for GBIF payload resolution and evaluation-model assembly."""

from unittest.mock import patch

from llm_metadata.gbif import GBIFMatch, resolve_model_species
from llm_metadata.groundtruth_eval import evaluate_indexed
from llm_metadata.schemas.fuster_features import DatasetFeaturesEvaluation, DatasetFeaturesExtraction


def _make_gbif_match(key: int, confidence: int = 99, match_type: str = "EXACT") -> GBIFMatch:
    return GBIFMatch(
        gbif_key=key,
        scientific_name=f"Species {key}",
        canonical_name=f"Species {key}",
        rank="SPECIES",
        confidence=confidence,
        match_type=match_type,
        kingdom="Animalia",
    )


def _make_resolved_taxon(key: int, original: str):
    from llm_metadata.gbif import ResolvedTaxon
    from llm_metadata.species_parsing import ParsedTaxon

    return ResolvedTaxon(
        original=original,
        parsed=ParsedTaxon.model_validate(original),
        gbif_match=_make_gbif_match(key),
    )


class TestResolveModelSpecies:
    def test_empty_species_returns_empty_payload(self):
        model = DatasetFeaturesExtraction(species=None)
        assert resolve_model_species(model) == []

    def test_species_are_resolved_to_payloads(self):
        model = DatasetFeaturesExtraction(species=["Tamias striatus"])
        with patch(
            "llm_metadata.gbif.resolve_species_list",
            return_value=[_make_resolved_taxon(5219243, "Tamias striatus")],
        ) as mocked:
            resolved = resolve_model_species(model)
        assert len(resolved) == 1
        assert resolved[0].gbif_match is not None
        assert resolved[0].gbif_match.gbif_key == 5219243
        mocked.assert_called_once()


class TestDatasetFeaturesEvaluationAssembly:
    def test_from_extraction_populates_gbif_keys(self):
        extracted = DatasetFeaturesExtraction(species=["Tamias striatus"])
        enriched = DatasetFeaturesEvaluation.from_extraction(
            extracted,
            gbif=[_make_resolved_taxon(5219243, "Tamias striatus")],
        )
        assert enriched.gbif_keys == [5219243]
        assert enriched.species == ["Tamias striatus"]

    def test_from_extraction_populates_taxonomy_derivatives(self):
        extracted = DatasetFeaturesExtraction(species=["73 weevil species"])
        enriched = DatasetFeaturesEvaluation.from_extraction(extracted)
        assert enriched.parsed_species is not None
        assert enriched.taxon_richness_mentions is not None
        assert enriched.taxon_richness_counts == [73]
        assert enriched.taxon_richness_group_keys == ["73|weevil"]
        assert enriched.species_stripped_richness is None
        assert enriched.gbif_key_stripped_richness is None

    def test_evaluation_model_defaults_to_none_gbif_keys(self):
        model = DatasetFeaturesEvaluation()
        assert model.gbif_keys is None


class TestEvaluateIndexedWithGbifKeys:
    def test_gbif_keys_metrics_exist_in_report(self):
        true_model = DatasetFeaturesEvaluation(species=["Tamias striatus"], gbif_keys=[5219243])
        pred_model = DatasetFeaturesEvaluation(species=["Tamias striatus"], gbif_keys=[5219243])

        report = evaluate_indexed(
            true_by_id={"doi:10.1234/test": true_model},
            pred_by_id={"doi:10.1234/test": pred_model},
            fields=["species", "gbif_keys"],
        )

        assert "gbif_keys" in report.field_metrics

    def test_gbif_keys_partial_match(self):
        true_model = DatasetFeaturesEvaluation(gbif_keys=[5219243, 2435099])
        pred_model = DatasetFeaturesEvaluation(gbif_keys=[5219243, 9999999])

        report = evaluate_indexed(
            true_by_id={"doi1": true_model},
            pred_by_id={"doi1": pred_model},
            fields=["gbif_keys"],
        )

        metrics = report.metrics_for("gbif_keys")
        assert metrics.tp == 1
        assert metrics.fp == 1
        assert metrics.fn == 1
