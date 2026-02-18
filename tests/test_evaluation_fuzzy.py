"""Test fuzzy matching in evaluation module."""

from llm_metadata.groundtruth_eval import (
    EvaluationConfig,
    FuzzyMatchConfig,
    evaluate_indexed,
)
from llm_metadata.schemas.fuster_features import DatasetFeatures, DatasetFeaturesNormalized


class TestEvaluationFuzzy:
    """Test suite for fuzzy matching and vocabulary normalization in evaluation."""

    def test_fuzzy_match_species(self):
        """Test fuzzy matching for species lists."""

        # Create test data with slight variations
        manual = DatasetFeatures(
            species=["Tamias striatus", "Ursus americanus"]
        )
        automated = DatasetFeatures(
            species=["Tamias striata", "Ursus americanus"]  # Slight typo in first species
        )

        # Without fuzzy matching - should have mismatches
        config_strict = EvaluationConfig(treat_lists_as_sets=True)
        report_strict = evaluate_indexed(
            true_by_id={"test": manual},
            pred_by_id={"test": automated},
            fields=["species"],
            config=config_strict
        )

        # With fuzzy matching - should match
        config_fuzzy = EvaluationConfig(
            treat_lists_as_sets=True,
            fuzzy_match_fields={"species": FuzzyMatchConfig(threshold=70)}
        )
        report_fuzzy = evaluate_indexed(
            true_by_id={"test": manual},
            pred_by_id={"test": automated},
            fields=["species"],
            config=config_fuzzy
        )

        # Fuzzy should have better recall
        strict_metrics = report_strict.metrics_for("species")
        fuzzy_metrics = report_fuzzy.metrics_for("species")

        assert fuzzy_metrics.recall >= strict_metrics.recall
        assert fuzzy_metrics.f1 >= strict_metrics.f1

    def test_vocabulary_normalization_in_schema(self):
        """Test that vocabulary normalization happens in DatasetFeaturesNormalized validators."""

        # Test data_type normalization - must use Normalized class
        manual = DatasetFeaturesNormalized(
            data_type=["presence only", "EBV genetic analysis"]
        )

        # Should normalize to enum values
        assert "presence-only" in manual.data_type
        assert "genetic_analysis" in manual.data_type

        # Test geospatial_info_dataset normalization
        manual2 = DatasetFeaturesNormalized(
            geospatial_info_dataset=["site coordinates", "geographic features"]
        )

        assert "site" in manual2.geospatial_info_dataset
        assert "geographic_features" in manual2.geospatial_info_dataset

    def test_evaluation_config_declarative(self):
        """Test declarative evaluation configuration."""

        manual = DatasetFeatures(
            species=["Species one", "Species two"],
            data_type=["abundance"]
        )
        automated = DatasetFeatures(
            species=["species one", "species TWO"],  # Different case
            data_type=["abundance"]
        )

        # Configure fuzzy matching only for species
        config = EvaluationConfig(
            treat_lists_as_sets=True,
            fuzzy_match_fields={"species": FuzzyMatchConfig(threshold=70)}
        )

        report = evaluate_indexed(
            true_by_id={"test": manual},
            pred_by_id={"test": automated},
            fields=["species", "data_type"],
            config=config
        )

        # Species should match via fuzzy
        species_metrics = report.metrics_for("species")
        assert species_metrics.recall == 1.0

        # data_type should match exactly
        data_type_metrics = report.metrics_for("data_type")
        assert data_type_metrics.f1 == 1.0
