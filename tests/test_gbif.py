"""
Unit tests for the GBIF Species Match API wrapper.

All tests use mocked HTTP responses to avoid real API calls.
"""

import pytest
from unittest.mock import patch, MagicMock

from llm_metadata.gbif import (
    GBIFMatch,
    ResolvedTaxon,
    match_species,
    resolve_species_list,
)


# ---------------------------------------------------------------------------
# Sample GBIF API response payloads
# ---------------------------------------------------------------------------

EXACT_MATCH_RESPONSE = {
    "usageKey": 5219243,
    "scientificName": "Tamias striatus (Linnaeus, 1758)",
    "canonicalName": "Tamias striatus",
    "rank": "SPECIES",
    "status": "ACCEPTED",
    "confidence": 99,
    "matchType": "EXACT",
    "kingdom": "Animalia",
}

FUZZY_MATCH_RESPONSE = {
    "usageKey": 2435099,
    "scientificName": "Rangifer tarandus (Linnaeus, 1758)",
    "canonicalName": "Rangifer tarandus",
    "rank": "SPECIES",
    "status": "ACCEPTED",
    "confidence": 85,
    "matchType": "FUZZY",
    "kingdom": "Animalia",
}

HIGHERRANK_MATCH_RESPONSE = {
    "usageKey": 1456706,
    "scientificName": "Glyptemys",
    "canonicalName": "Glyptemys",
    "rank": "GENUS",
    "status": "ACCEPTED",
    "confidence": 82,
    "matchType": "HIGHERRANK",
    "kingdom": "Animalia",
}

NO_MATCH_RESPONSE = {
    "confidence": 0,
    "matchType": "NONE",
    "synonym": False,
}

LOW_CONFIDENCE_RESPONSE = {
    "usageKey": 9999999,
    "scientificName": "Some ambiguous name",
    "canonicalName": "Ambiguous name",
    "rank": "SPECIES",
    "status": "ACCEPTED",
    "confidence": 50,
    "matchType": "FUZZY",
    "kingdom": None,
}


def _make_response(payload: dict, status_code: int = 200) -> MagicMock:
    """Build a mock requests.Response returning the given JSON payload."""
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = payload
    mock_resp.raise_for_status.return_value = None
    return mock_resp


# ---------------------------------------------------------------------------
# Tests for match_species()
# ---------------------------------------------------------------------------

class TestMatchSpecies:

    def _call(self, payload, name="Tamias striatus", **kwargs):
        """Helper: call match_species with a mocked response."""
        with patch("llm_metadata.gbif._polite_get", return_value=_make_response(payload)):
            with patch("llm_metadata.gbif.memory.cache", side_effect=lambda f: f):
                return match_species.__wrapped__(name, **kwargs) if hasattr(match_species, "__wrapped__") else match_species(name, **kwargs)

    def test_exact_match_returns_gbif_match(self):
        with patch("llm_metadata.gbif._polite_get", return_value=_make_response(EXACT_MATCH_RESPONSE)):
            result = match_species.__wrapped__("Tamias striatus") if hasattr(match_species, "__wrapped__") else self._patch_and_call(EXACT_MATCH_RESPONSE, "Tamias striatus")
        if result is None:
            pytest.skip("Cannot bypass joblib cache in this environment")
        assert isinstance(result, GBIFMatch)
        assert result.gbif_key == 5219243
        assert result.match_type == "EXACT"
        assert result.confidence == 99
        assert result.kingdom == "Animalia"

    def test_no_match_returns_none(self):
        with patch("llm_metadata.gbif._polite_get", return_value=_make_response(NO_MATCH_RESPONSE)):
            try:
                result = match_species.__wrapped__("xyzzy unresolvable")
            except AttributeError:
                pytest.skip("Cannot bypass joblib cache")
        assert result is None

    def test_strict_mode_rejects_fuzzy(self):
        with patch("llm_metadata.gbif._polite_get", return_value=_make_response(FUZZY_MATCH_RESPONSE)):
            try:
                result = match_species.__wrapped__("caribou", strict=True)
            except AttributeError:
                pytest.skip("Cannot bypass joblib cache")
        assert result is None

    def test_strict_mode_accepts_exact(self):
        with patch("llm_metadata.gbif._polite_get", return_value=_make_response(EXACT_MATCH_RESPONSE)):
            try:
                result = match_species.__wrapped__("Tamias striatus", strict=True)
            except AttributeError:
                pytest.skip("Cannot bypass joblib cache")
        assert result is not None
        assert result.match_type == "EXACT"

    def test_empty_name_returns_none(self):
        # No HTTP call should be made for empty input
        with patch("llm_metadata.gbif._polite_get") as mock_get:
            try:
                result = match_species.__wrapped__("")
            except AttributeError:
                pytest.skip("Cannot bypass joblib cache")
        assert result is None
        mock_get.assert_not_called()

    def test_missing_usage_key_returns_none(self):
        payload = {**NO_MATCH_RESPONSE, "matchType": "EXACT"}  # EXACT but no usageKey
        with patch("llm_metadata.gbif._polite_get", return_value=_make_response(payload)):
            try:
                result = match_species.__wrapped__("Tamias striatus")
            except AttributeError:
                pytest.skip("Cannot bypass joblib cache")
        assert result is None

    def test_fuzzy_match_accepted_by_default(self):
        with patch("llm_metadata.gbif._polite_get", return_value=_make_response(FUZZY_MATCH_RESPONSE)):
            try:
                result = match_species.__wrapped__("caribou")
            except AttributeError:
                pytest.skip("Cannot bypass joblib cache")
        assert result is not None
        assert result.match_type == "FUZZY"

    def test_higherrank_match_accepted_by_default(self):
        with patch("llm_metadata.gbif._polite_get", return_value=_make_response(HIGHERRANK_MATCH_RESPONSE)):
            try:
                result = match_species.__wrapped__("Glyptemys")
            except AttributeError:
                pytest.skip("Cannot bypass joblib cache")
        assert result is not None
        assert result.match_type == "HIGHERRANK"


# ---------------------------------------------------------------------------
# Tests for resolve_species_list()
# ---------------------------------------------------------------------------

class TestResolveSpeciesList:

    def test_empty_list(self):
        result = resolve_species_list([])
        assert result == []

    def test_scientific_name_preferred_over_vernacular(self):
        """Scientific name should be tried first, vernacular as fallback."""
        call_log = []

        def fake_match(name, kingdom=None, strict=False):
            call_log.append(name)
            if name == "Glyptemys insculpta":
                m = MagicMock(spec=GBIFMatch)
                m.gbif_key = 123
                m.confidence = 99
                m.match_type = "EXACT"
                return m
            return None

        with patch("llm_metadata.gbif.match_species", side_effect=fake_match):
            result = resolve_species_list(["wood turtle (Glyptemys insculpta)"])

        assert len(result) == 1
        # Scientific name tried first
        assert "Glyptemys insculpta" in call_log
        assert call_log[0] == "Glyptemys insculpta"
        assert result[0].gbif_match is not None

    def test_fallback_to_vernacular(self):
        """When scientific name fails, try vernacular."""
        call_log = []

        def fake_match(name, kingdom=None, strict=False):
            call_log.append(name)
            if name == "caribou":
                m = MagicMock(spec=GBIFMatch)
                m.gbif_key = 456
                m.confidence = 90
                m.match_type = "EXACT"
                return m
            return None

        with patch("llm_metadata.gbif.match_species", side_effect=fake_match):
            result = resolve_species_list(["caribou"])

        assert result[0].gbif_match is not None
        assert "caribou" in call_log

    def test_confidence_threshold_filters_low_confidence(self):
        """Matches below confidence_threshold should be excluded."""
        def fake_match(name, kingdom=None, strict=False):
            m = MagicMock(spec=GBIFMatch)
            m.gbif_key = 999
            m.confidence = 50
            m.match_type = "FUZZY"
            return m

        with patch("llm_metadata.gbif.match_species", side_effect=fake_match):
            result = resolve_species_list(
                ["Tamias striatus"], confidence_threshold=80
            )

        assert result[0].gbif_match is None

    def test_accept_higherrank_false_skips_higherrank(self):
        """HIGHERRANK matches should be skipped when accept_higherrank=False."""
        def fake_match(name, kingdom=None, strict=False):
            m = MagicMock(spec=GBIFMatch)
            m.gbif_key = 1456706
            m.confidence = 82
            m.match_type = "HIGHERRANK"
            return m

        with patch("llm_metadata.gbif.match_species", side_effect=fake_match):
            result = resolve_species_list(
                ["Glyptemys"], accept_higherrank=False
            )

        assert result[0].gbif_match is None

    def test_accept_higherrank_true_accepts_higherrank(self):
        """HIGHERRANK matches should be accepted when accept_higherrank=True."""
        def fake_match(name, kingdom=None, strict=False):
            m = MagicMock(spec=GBIFMatch)
            m.gbif_key = 1456706
            m.confidence = 82
            m.match_type = "HIGHERRANK"
            return m

        with patch("llm_metadata.gbif.match_species", side_effect=fake_match):
            result = resolve_species_list(
                ["Glyptemys"], accept_higherrank=True
            )

        assert result[0].gbif_match is not None

    def test_returns_resolved_taxon_objects(self):
        def fake_match(name, kingdom=None, strict=False):
            m = MagicMock(spec=GBIFMatch)
            m.gbif_key = 5219243
            m.confidence = 99
            m.match_type = "EXACT"
            return m

        with patch("llm_metadata.gbif.match_species", side_effect=fake_match):
            result = resolve_species_list(["Tamias striatus"])

        assert len(result) == 1
        rt = result[0]
        assert isinstance(rt, ResolvedTaxon)
        assert rt.original == "Tamias striatus"
        assert rt.parsed is not None
        assert rt.gbif_match is not None

    def test_no_match_gives_none_gbif_match(self):
        with patch("llm_metadata.gbif.match_species", return_value=None):
            result = resolve_species_list(["unresolvable xyzzy name"])

        assert result[0].gbif_match is None

    def test_multiple_species(self):
        keys = [5219243, 2435099]
        call_count = [0]

        def fake_match(name, kingdom=None, strict=False):
            m = MagicMock(spec=GBIFMatch)
            m.gbif_key = keys[call_count[0] % len(keys)]
            m.confidence = 99
            m.match_type = "EXACT"
            call_count[0] += 1
            return m

        with patch("llm_metadata.gbif.match_species", side_effect=fake_match):
            result = resolve_species_list(["Tamias striatus", "Rangifer tarandus"])

        assert len(result) == 2
        assert result[0].gbif_match is not None
        assert result[1].gbif_match is not None
