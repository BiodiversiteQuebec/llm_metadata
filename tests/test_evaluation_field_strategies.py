"""Tests for FieldEvalStrategy, DEFAULT_FIELD_STRATEGIES, and field_strategies dispatch in compare_models."""

import pytest

from llm_metadata.groundtruth_eval import (
    DEFAULT_FIELD_STRATEGIES,
    EvaluationConfig,
    FieldEvalStrategy,
    FuzzyMatchConfig,
    compare_models,
    evaluate_indexed,
)
from llm_metadata.schemas.fuster_features import DatasetFeatures


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_model(**kwargs) -> DatasetFeatures:
    return DatasetFeatures.model_validate(kwargs)


# ---------------------------------------------------------------------------
# WU-EH3: FieldEvalStrategy defaults
# ---------------------------------------------------------------------------

class TestFieldEvalStrategy:
    def test_default_match_is_exact(self):
        s = FieldEvalStrategy()
        assert s.match == "exact"

    def test_default_threshold_is_80(self):
        s = FieldEvalStrategy()
        assert s.threshold == 80

    def test_custom_values(self):
        s = FieldEvalStrategy(match="fuzzy", threshold=60)
        assert s.match == "fuzzy"
        assert s.threshold == 60

    def test_is_frozen(self):
        s = FieldEvalStrategy()
        with pytest.raises((AttributeError, TypeError)):
            s.match = "fuzzy"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# WU-EH3: DEFAULT_FIELD_STRATEGIES content
# ---------------------------------------------------------------------------

class TestDefaultFieldStrategies:
    def test_exactly_12_fields(self):
        assert len(DEFAULT_FIELD_STRATEGIES) == 12

    def test_excludes_temporal_range(self):
        assert "temporal_range" not in DEFAULT_FIELD_STRATEGIES

    def test_excludes_referred_dataset(self):
        assert "referred_dataset" not in DEFAULT_FIELD_STRATEGIES

    def test_contains_all_expected_fields(self):
        expected = {
            "temp_range_i", "temp_range_f", "spatial_range_km2",
            "data_type", "geospatial_info_dataset",
            "species",
            "time_series", "multispecies", "threatened_species",
            "new_species_science", "new_species_region", "bias_north_south",
        }
        assert set(DEFAULT_FIELD_STRATEGIES.keys()) == expected

    def test_species_uses_enhanced_species(self):
        assert DEFAULT_FIELD_STRATEGIES["species"].match == "enhanced_species"
        assert DEFAULT_FIELD_STRATEGIES["species"].threshold == 70

    def test_boolean_fields_use_exact(self):
        for field in ("time_series", "multispecies", "threatened_species",
                      "new_species_science", "new_species_region", "bias_north_south"):
            assert DEFAULT_FIELD_STRATEGIES[field].match == "exact", (
                f"Expected 'exact' for {field}, got {DEFAULT_FIELD_STRATEGIES[field].match}"
            )

    def test_numeric_fields_use_exact(self):
        for field in ("temp_range_i", "temp_range_f", "spatial_range_km2"):
            assert DEFAULT_FIELD_STRATEGIES[field].match == "exact"

    def test_vocab_fields_use_exact(self):
        assert DEFAULT_FIELD_STRATEGIES["data_type"].match == "exact"
        assert DEFAULT_FIELD_STRATEGIES["geospatial_info_dataset"].match == "exact"


# ---------------------------------------------------------------------------
# WU-EH3: compare_models with field_strategies populated
# ---------------------------------------------------------------------------

class TestCompareModelsWithFieldStrategies:
    """Only registry fields are evaluated when field_strategies is non-empty."""

    def test_only_registry_fields_evaluated(self):
        """When field_strategies is set, only those fields appear in results."""
        strategies = {
            "temp_range_i": FieldEvalStrategy(match="exact"),
            "data_type":    FieldEvalStrategy(match="exact"),
        }
        config = EvaluationConfig(field_strategies=strategies)

        true_m = _make_model(temp_range_i=2000, data_type=["abundance"], species=["caribou"])
        pred_m = _make_model(temp_range_i=2000, data_type=["abundance"], species=["moose"])

        results = compare_models(
            true_model=true_m, pred_model=pred_m, record_id="r1", config=config
        )
        evaluated_fields = {r.field for r in results}

        # species is NOT in field_strategies — must not appear
        assert "species" not in evaluated_fields
        assert evaluated_fields == {"temp_range_i", "data_type"}

    def test_field_strategies_fields_param_intersection(self):
        """fields= restricts further within registry keys."""
        strategies = {
            "temp_range_i": FieldEvalStrategy(match="exact"),
            "temp_range_f": FieldEvalStrategy(match="exact"),
            "data_type":    FieldEvalStrategy(match="exact"),
        }
        config = EvaluationConfig(field_strategies=strategies)

        true_m = _make_model(temp_range_i=2000, temp_range_f=2010, data_type=["abundance"])
        pred_m = _make_model(temp_range_i=2000, temp_range_f=2010, data_type=["abundance"])

        # Only ask for temp_range_i — intersection with registry: {temp_range_i}
        results = compare_models(
            true_model=true_m, pred_model=pred_m, record_id="r1",
            fields=["temp_range_i"],
            config=config,
        )
        evaluated_fields = {r.field for r in results}
        assert evaluated_fields == {"temp_range_i"}

    def test_fields_param_outside_registry_excluded(self):
        """fields= entries not in field_strategies are silently excluded."""
        strategies = {"temp_range_i": FieldEvalStrategy(match="exact")}
        config = EvaluationConfig(field_strategies=strategies)

        true_m = _make_model(temp_range_i=2000, species=["caribou"])
        pred_m = _make_model(temp_range_i=2001, species=["moose"])

        # species is not in strategies; asking for both — only temp_range_i survives
        results = compare_models(
            true_model=true_m, pred_model=pred_m, record_id="r1",
            fields=["temp_range_i", "species"],
            config=config,
        )
        evaluated_fields = {r.field for r in results}
        assert evaluated_fields == {"temp_range_i"}

    def test_exact_strategy_correct_match(self):
        """exact strategy correctly marks matching and non-matching scalars."""
        strategies = {"temp_range_i": FieldEvalStrategy(match="exact")}
        config = EvaluationConfig(field_strategies=strategies)

        true_m = _make_model(temp_range_i=2000)
        pred_match = _make_model(temp_range_i=2000)
        pred_no_match = _make_model(temp_range_i=2001)

        r_match = compare_models(
            true_model=true_m, pred_model=pred_match, record_id="r1",
            fields=["temp_range_i"], config=config,
        )
        assert r_match[0].match is True
        assert r_match[0].tp == 1

        r_no_match = compare_models(
            true_model=true_m, pred_model=pred_no_match, record_id="r1",
            fields=["temp_range_i"], config=config,
        )
        assert r_no_match[0].match is False

    def test_enhanced_species_strategy_dispatch(self):
        """enhanced_species strategy uses species-aware matching."""
        strategies = {"species": FieldEvalStrategy(match="enhanced_species", threshold=70)}
        config = EvaluationConfig(field_strategies=strategies)

        # True has scientific name; pred has vernacular + scientific — should match
        true_m = _make_model(species=["Glyptemys insculpta"])
        pred_m = _make_model(species=["wood turtle (Glyptemys insculpta)"])

        results = compare_models(
            true_model=true_m, pred_model=pred_m, record_id="r1",
            fields=["species"], config=config,
        )
        # Enhanced matching should find the scientific name inside the pred string
        assert results[0].tp >= 1

    def test_fuzzy_strategy_dispatch_list(self):
        """fuzzy strategy uses fuzzy list matching."""
        strategies = {"species": FieldEvalStrategy(match="fuzzy", threshold=70)}
        config = EvaluationConfig(field_strategies=strategies)

        true_m = _make_model(species=["Tamias striatus"])
        pred_m = _make_model(species=["Tamias striata"])  # slight typo

        results = compare_models(
            true_model=true_m, pred_model=pred_m, record_id="r1",
            fields=["species"], config=config,
        )
        # Fuzzy at 70 should match the typo
        assert results[0].tp == 1

    def test_evaluate_indexed_with_default_strategies(self):
        """evaluate_indexed using DEFAULT_FIELD_STRATEGIES evaluates exactly 12 fields."""
        config = EvaluationConfig(field_strategies=DEFAULT_FIELD_STRATEGIES)

        true_m = _make_model(
            temp_range_i=2000, temp_range_f=2010, data_type=["abundance"],
            time_series=True, multispecies=False,
        )
        pred_m = _make_model(
            temp_range_i=2000, temp_range_f=2010, data_type=["abundance"],
            time_series=True, multispecies=False,
        )

        report = evaluate_indexed(
            true_by_id={"r1": true_m},
            pred_by_id={"r1": pred_m},
            config=config,
        )
        # Must evaluate exactly the 12 registry fields (some may be None/None but still appear)
        assert set(report.field_metrics.keys()) == set(DEFAULT_FIELD_STRATEGIES.keys())


# ---------------------------------------------------------------------------
# WU-EH3: Backward compatibility tests
# ---------------------------------------------------------------------------

class TestBackwardCompat:
    """Legacy parameters work unchanged when field_strategies is empty."""

    def test_empty_field_strategies_fuzzy_match_fields_works(self):
        """Legacy fuzzy_match_fields still activates fuzzy matching when field_strategies={}."""
        config = EvaluationConfig(
            field_strategies={},
            fuzzy_match_fields={"species": FuzzyMatchConfig(threshold=70)},
        )

        true_m = _make_model(species=["Tamias striatus"])
        pred_m = _make_model(species=["Tamias striata"])  # slight typo

        report = evaluate_indexed(
            true_by_id={"r1": true_m},
            pred_by_id={"r1": pred_m},
            fields=["species"],
            config=config,
        )
        # Fuzzy at 70 should match
        assert report.metrics_for("species").tp == 1

    def test_empty_field_strategies_enhanced_species_works(self):
        """Legacy enhanced_species_matching still works when field_strategies={}."""
        config = EvaluationConfig(
            field_strategies={},
            enhanced_species_matching=True,
            enhanced_species_threshold=70,
        )

        true_m = _make_model(species=["Glyptemys insculpta"])
        pred_m = _make_model(species=["wood turtle (Glyptemys insculpta)"])

        report = evaluate_indexed(
            true_by_id={"r1": true_m},
            pred_by_id={"r1": pred_m},
            fields=["species"],
            config=config,
        )
        assert report.metrics_for("species").tp >= 1

    def test_no_field_strategies_uses_model_intersection(self):
        """Without field_strategies, default field list is the model-field intersection."""
        config = EvaluationConfig()  # field_strategies defaults to {}

        true_m = _make_model(temp_range_i=2000, species=["caribou"])
        pred_m = _make_model(temp_range_i=2000, species=["caribou"])

        # No fields= restriction — should evaluate all common fields
        results = compare_models(
            true_model=true_m, pred_model=pred_m, record_id="r1", config=config
        )
        evaluated_fields = {r.field for r in results}
        # species and temp_range_i must both appear (they're in both models)
        assert "species" in evaluated_fields
        assert "temp_range_i" in evaluated_fields
