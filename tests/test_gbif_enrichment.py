"""
Unit tests for GBIF enrichment integration.

Tests cover:
- enrich_with_gbif() function behaviour
- gbif_keys field on DatasetFeatures schema
- End-to-end evaluation with gbif_keys using evaluate_indexed
"""

from unittest.mock import patch, MagicMock

from llm_metadata.schemas import DatasetFeatures
from llm_metadata.gbif import GBIFMatch, enrich_with_gbif
from llm_metadata.groundtruth_eval import evaluate_indexed, EvaluationConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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
    """Make a mock ResolvedTaxon with the given gbif_key."""
    from llm_metadata.gbif import ResolvedTaxon
    from llm_metadata.species_parsing import ParsedTaxon
    return ResolvedTaxon(
        original=original,
        parsed=ParsedTaxon(original),
        gbif_match=_make_gbif_match(key),
    )


# ---------------------------------------------------------------------------
# Tests: gbif_keys field on DatasetFeatures
# ---------------------------------------------------------------------------

class TestGbifKeysField:

    def test_gbif_keys_defaults_to_none(self):
        m = DatasetFeatures()
        assert m.gbif_keys is None

    def test_gbif_keys_accepts_list_of_ints(self):
        m = DatasetFeatures(gbif_keys=[5219243, 2435099])
        assert m.gbif_keys == [5219243, 2435099]

    def test_gbif_keys_accepts_none(self):
        m = DatasetFeatures(gbif_keys=None)
        assert m.gbif_keys is None

    def test_gbif_keys_not_set_by_species_field(self):
        """Setting species should not auto-populate gbif_keys."""
        m = DatasetFeatures(species=["Tamias striatus"])
        assert m.gbif_keys is None


# ---------------------------------------------------------------------------
# Tests: enrich_with_gbif()
# ---------------------------------------------------------------------------

class TestEnrichWithGbif:

    def test_enrich_with_known_species_populates_gbif_keys(self):
        model = DatasetFeatures(species=["Tamias striatus"])

        from llm_metadata.gbif import ResolvedTaxon
        from llm_metadata.species_parsing import ParsedTaxon
        resolved = [
            ResolvedTaxon(
                original="Tamias striatus",
                parsed=ParsedTaxon.model_validate("Tamias striatus"),
                gbif_match=_make_gbif_match(5219243),
            )
        ]

        with patch("llm_metadata.gbif.resolve_species_list", return_value=resolved):
            enriched = enrich_with_gbif(model)

        assert enriched.gbif_keys == [5219243]
        # Original unchanged
        assert model.gbif_keys is None

    def test_enrich_with_none_species_gives_none_keys(self):
        model = DatasetFeatures(species=None)
        enriched = enrich_with_gbif(model)
        assert enriched.gbif_keys is None

    def test_enrich_with_empty_species_gives_none_keys(self):
        model = DatasetFeatures(species=[])
        enriched = enrich_with_gbif(model)
        assert enriched.gbif_keys is None

    def test_enrich_with_unmatchable_species_gives_none(self):
        model = DatasetFeatures(species=["xyzzy unknown organism"])

        from llm_metadata.gbif import ResolvedTaxon
        from llm_metadata.species_parsing import ParsedTaxon
        resolved = [
            ResolvedTaxon(
                original="xyzzy unknown organism",
                parsed=ParsedTaxon.model_validate("xyzzy unknown organism"),
                gbif_match=None,
            )
        ]

        with patch("llm_metadata.gbif.resolve_species_list", return_value=resolved):
            enriched = enrich_with_gbif(model)

        assert enriched.gbif_keys is None

    def test_enrich_multiple_species(self):
        model = DatasetFeatures(species=["Tamias striatus", "Rangifer tarandus"])

        from llm_metadata.gbif import ResolvedTaxon
        from llm_metadata.species_parsing import ParsedTaxon
        resolved = [
            ResolvedTaxon(
                original="Tamias striatus",
                parsed=ParsedTaxon.model_validate("Tamias striatus"),
                gbif_match=_make_gbif_match(5219243),
            ),
            ResolvedTaxon(
                original="Rangifer tarandus",
                parsed=ParsedTaxon.model_validate("Rangifer tarandus"),
                gbif_match=_make_gbif_match(2435099),
            ),
        ]

        with patch("llm_metadata.gbif.resolve_species_list", return_value=resolved):
            enriched = enrich_with_gbif(model)

        assert sorted(enriched.gbif_keys) == [2435099, 5219243]

    def test_enrich_partial_match(self):
        """Some species match, some don't — only matched keys are populated."""
        model = DatasetFeatures(species=["Tamias striatus", "xyzzy"])

        from llm_metadata.gbif import ResolvedTaxon
        from llm_metadata.species_parsing import ParsedTaxon
        resolved = [
            ResolvedTaxon(
                original="Tamias striatus",
                parsed=ParsedTaxon.model_validate("Tamias striatus"),
                gbif_match=_make_gbif_match(5219243),
            ),
            ResolvedTaxon(
                original="xyzzy",
                parsed=ParsedTaxon.model_validate("xyzzy"),
                gbif_match=None,
            ),
        ]

        with patch("llm_metadata.gbif.resolve_species_list", return_value=resolved):
            enriched = enrich_with_gbif(model)

        assert enriched.gbif_keys == [5219243]

    def test_enrich_returns_copy_not_mutated(self):
        """enrich_with_gbif must not mutate the original model."""
        model = DatasetFeatures(species=["Tamias striatus"])

        from llm_metadata.gbif import ResolvedTaxon
        from llm_metadata.species_parsing import ParsedTaxon
        resolved = [
            ResolvedTaxon(
                original="Tamias striatus",
                parsed=ParsedTaxon.model_validate("Tamias striatus"),
                gbif_match=_make_gbif_match(5219243),
            )
        ]

        with patch("llm_metadata.gbif.resolve_species_list", return_value=resolved):
            enriched = enrich_with_gbif(model)

        assert model.gbif_keys is None  # original unchanged
        assert enriched.gbif_keys is not None


# ---------------------------------------------------------------------------
# End-to-end: evaluate_indexed with gbif_keys
# ---------------------------------------------------------------------------

class TestEvaluateIndexedWithGbifKeys:

    def test_gbif_keys_metrics_exist_in_report(self):
        """evaluate_indexed should produce metrics for gbif_keys field."""
        true_model = DatasetFeatures(
            species=["Tamias striatus"],
            gbif_keys=[5219243],
        )
        pred_model = DatasetFeatures(
            species=["Tamias striatus"],
            gbif_keys=[5219243],
        )

        report = evaluate_indexed(
            true_by_id={"doi:10.1234/test": true_model},
            pred_by_id={"doi:10.1234/test": pred_model},
            fields=["species", "gbif_keys"],
        )

        assert "gbif_keys" in report.field_metrics

    def test_gbif_keys_perfect_match(self):
        """Identical gbif_keys should yield perfect precision/recall."""
        true_model = DatasetFeatures(gbif_keys=[5219243, 2435099])
        pred_model = DatasetFeatures(gbif_keys=[5219243, 2435099])

        report = evaluate_indexed(
            true_by_id={"doi1": true_model},
            pred_by_id={"doi1": pred_model},
            fields=["gbif_keys"],
        )

        m = report.metrics_for("gbif_keys")
        assert m.tp == 2
        assert m.fp == 0
        assert m.fn == 0

    def test_gbif_keys_partial_match(self):
        """Partial key overlap should yield non-zero FP and FN."""
        true_model = DatasetFeatures(gbif_keys=[5219243, 2435099])
        pred_model = DatasetFeatures(gbif_keys=[5219243, 9999999])

        report = evaluate_indexed(
            true_by_id={"doi1": true_model},
            pred_by_id={"doi1": pred_model},
            fields=["gbif_keys"],
        )

        m = report.metrics_for("gbif_keys")
        assert m.tp == 1   # 5219243 shared
        assert m.fp == 1   # 9999999 in pred, not in true
        assert m.fn == 1   # 2435099 in true, not in pred

    def test_species_and_gbif_keys_evaluated_independently(self):
        """Both fields evaluated in single run — each has its own metrics entry."""
        true_model = DatasetFeatures(
            species=["Tamias striatus"],
            gbif_keys=[5219243],
        )
        pred_model = DatasetFeatures(
            species=["Tamias striatus"],
            gbif_keys=[5219243],
        )

        report = evaluate_indexed(
            true_by_id={"doi1": true_model},
            pred_by_id={"doi1": pred_model},
            fields=["species", "gbif_keys"],
        )

        assert "species" in report.field_metrics
        assert "gbif_keys" in report.field_metrics
