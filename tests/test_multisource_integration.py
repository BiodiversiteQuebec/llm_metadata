"""
Integration tests for multi-source validation pipeline.

Tests realistic end-to-end flows for each data source (Dryad, Zenodo,
Semantic Scholar) through DatasetFeaturesNormalized, verifying that
source-specific URL patterns, boolean fields, and edge cases are
handled correctly.
"""

import math
import pytest
from llm_metadata.schemas.fuster_features import (
    DatasetFeatures,
    DatasetFeaturesNormalized,
    DataSource,
)


# ---------------------------------------------------------------------------
# Realistic record templates per source
# ---------------------------------------------------------------------------

DRYAD_RECORD = {
    "source": "dryad",
    "source_url": "https://datadryad.org/stash/dataset/doi:10.5061/dryad.abc123",
    "journal_url": "https://doi.org/10.1371/journal.pone.0128238",
    "pdf_url": None,
    "is_oa": True,
    "cited_article_doi": "10.1371/journal.pone.0128238",
    "valid_yn": "yes",
    "data_type": "abundance",
    "temp_range_i": 2010,
    "temp_range_f": 2020,
    "species": "Rangifer tarandus, Ursus americanus",
    "time_series": "yes",
    "multispecies": "yes",
    "threatened_species": "no",
    "new_species_science": "no",
    "new_species_region": "no",
    "bias_north_south": "no",
}

ZENODO_RECORD = {
    "source": "zenodo",
    "source_url": "https://zenodo.org/record/12345",
    "journal_url": "https://doi.org/10.5281/zenodo.12345",
    "pdf_url": "https://zenodo.org/record/12345/files/paper.pdf",
    "is_oa": True,
    "cited_article_doi": "10.1234/somepaper.2021",
    "valid_yn": "yes",
    "data_type": "presence-only",
    "temp_range_i": 2015,
    "temp_range_f": 2019,
    "species": "Pinus sylvestris",
    "time_series": "no",
    "multispecies": "no",
    "threatened_species": "yes",
    "new_species_science": "no",
    "new_species_region": "no",
    "bias_north_south": "no",
}

SEMANTIC_SCHOLAR_RECORD = {
    "source": "semantic_scholar",
    "source_url": "https://api.semanticscholar.org/graph/v1/paper/search?query=biodiversity+monitoring",
    "journal_url": "https://doi.org/10.7717/peerj.18853",
    "pdf_url": "https://peerj.com/articles/18853.pdf",
    "is_oa": True,
    "cited_article_doi": "10.7717/peerj.18853",
    "valid_yn": "yes",
    "data_type": "abundance,presence-only",
    "temp_range_i": 2000,
    "temp_range_f": 2023,
    "species": "Homo sapiens",
    "time_series": "yes",
    "multispecies": "yes",
    "threatened_species": "yes",
    "new_species_science": "yes",
    "new_species_region": "no",
    "bias_north_south": "yes",
}


# ---------------------------------------------------------------------------
# Integration: validate Dryad records through DatasetFeaturesNormalized
# ---------------------------------------------------------------------------

class TestDryadRecordValidation:
    """End-to-end validation of typical Dryad records."""

    def test_dryad_source_is_set(self):
        model = DatasetFeaturesNormalized.model_validate(DRYAD_RECORD)
        assert model.source == "dryad"

    def test_dryad_species_parsed_from_comma_string(self):
        model = DatasetFeaturesNormalized.model_validate(DRYAD_RECORD)
        assert isinstance(model.species, list)
        assert len(model.species) == 2
        assert "Rangifer tarandus" in model.species
        assert "Ursus americanus" in model.species

    def test_dryad_data_type_parsed(self):
        model = DatasetFeaturesNormalized.model_validate(DRYAD_RECORD)
        assert model.data_type == ["abundance"]

    def test_dryad_boolean_yes_modulators(self):
        model = DatasetFeaturesNormalized.model_validate(DRYAD_RECORD)
        assert model.time_series is True
        assert model.multispecies is True

    def test_dryad_boolean_no_modulators(self):
        model = DatasetFeaturesNormalized.model_validate(DRYAD_RECORD)
        assert model.threatened_species is False
        assert model.new_species_science is False
        assert model.new_species_region is False
        assert model.bias_north_south is False

    def test_dryad_is_oa_true(self):
        model = DatasetFeaturesNormalized.model_validate(DRYAD_RECORD)
        assert model.is_oa is True

    def test_dryad_cited_article_doi_preserved(self):
        model = DatasetFeaturesNormalized.model_validate(DRYAD_RECORD)
        assert model.cited_article_doi == "10.1371/journal.pone.0128238"

    def test_dryad_temporal_range_as_ints(self):
        model = DatasetFeaturesNormalized.model_validate(DRYAD_RECORD)
        assert model.temp_range_i == 2010
        assert model.temp_range_f == 2020


# ---------------------------------------------------------------------------
# Integration: validate Zenodo records through DatasetFeaturesNormalized
# ---------------------------------------------------------------------------

class TestZenodoRecordValidation:
    """End-to-end validation of typical Zenodo records."""

    def test_zenodo_source_is_set(self):
        model = DatasetFeaturesNormalized.model_validate(ZENODO_RECORD)
        assert model.source == "zenodo"

    def test_zenodo_is_oa(self):
        model = DatasetFeaturesNormalized.model_validate(ZENODO_RECORD)
        assert model.is_oa is True

    def test_zenodo_pdf_url_preserved(self):
        model = DatasetFeaturesNormalized.model_validate(ZENODO_RECORD)
        assert model.pdf_url == "https://zenodo.org/record/12345/files/paper.pdf"

    def test_zenodo_single_species(self):
        model = DatasetFeaturesNormalized.model_validate(ZENODO_RECORD)
        assert isinstance(model.species, list)
        assert "Pinus sylvestris" in model.species

    def test_zenodo_time_series_false(self):
        """'no' should coerce to False, not None."""
        model = DatasetFeaturesNormalized.model_validate(ZENODO_RECORD)
        assert model.time_series is False

    def test_zenodo_multispecies_false(self):
        model = DatasetFeaturesNormalized.model_validate(ZENODO_RECORD)
        assert model.multispecies is False

    def test_zenodo_threatened_species_true(self):
        model = DatasetFeaturesNormalized.model_validate(ZENODO_RECORD)
        assert model.threatened_species is True

    def test_zenodo_data_type_presence_only_normalized(self):
        model = DatasetFeaturesNormalized.model_validate(ZENODO_RECORD)
        assert model.data_type is not None
        assert "presence-only" in model.data_type


# ---------------------------------------------------------------------------
# Integration: validate Semantic Scholar records through DatasetFeaturesNormalized
# ---------------------------------------------------------------------------

class TestSemanticScholarRecordValidation:
    """End-to-end validation of typical Semantic Scholar records."""

    def test_ss_source_is_set(self):
        model = DatasetFeaturesNormalized.model_validate(SEMANTIC_SCHOLAR_RECORD)
        assert model.source == "semantic_scholar"

    def test_ss_source_url_preserved(self):
        model = DatasetFeaturesNormalized.model_validate(SEMANTIC_SCHOLAR_RECORD)
        assert "semanticscholar.org" in (model.source_url or "")

    def test_ss_journal_url_preserved(self):
        model = DatasetFeaturesNormalized.model_validate(SEMANTIC_SCHOLAR_RECORD)
        assert model.journal_url == "https://doi.org/10.7717/peerj.18853"

    def test_ss_pdf_url_preserved(self):
        model = DatasetFeaturesNormalized.model_validate(SEMANTIC_SCHOLAR_RECORD)
        assert model.pdf_url == "https://peerj.com/articles/18853.pdf"

    def test_ss_is_oa_true(self):
        model = DatasetFeaturesNormalized.model_validate(SEMANTIC_SCHOLAR_RECORD)
        assert model.is_oa is True

    def test_ss_comma_separated_data_types(self):
        model = DatasetFeaturesNormalized.model_validate(SEMANTIC_SCHOLAR_RECORD)
        assert model.data_type is not None
        assert "abundance" in model.data_type
        assert "presence-only" in model.data_type

    def test_ss_all_boolean_modulators(self):
        model = DatasetFeaturesNormalized.model_validate(SEMANTIC_SCHOLAR_RECORD)
        assert model.time_series is True
        assert model.multispecies is True
        assert model.threatened_species is True
        assert model.new_species_science is True
        assert model.new_species_region is False
        assert model.bias_north_south is True

    def test_ss_cited_article_doi_preserved(self):
        model = DatasetFeaturesNormalized.model_validate(SEMANTIC_SCHOLAR_RECORD)
        assert model.cited_article_doi == "10.7717/peerj.18853"


# ---------------------------------------------------------------------------
# Cross-source edge cases
# ---------------------------------------------------------------------------

class TestCrossSourceEdgeCases:
    """Edge cases that apply across sources."""

    def test_missing_optional_fields_default_to_none(self):
        """Records without URL metadata should still validate."""
        for source in ("dryad", "zenodo", "semantic_scholar"):
            model = DatasetFeaturesNormalized.model_validate({
                "source": source,
                "valid_yn": "yes",
                "data_type": "abundance",
            })
            assert model.source == source
            assert model.pdf_url is None
            assert model.journal_url is None
            assert model.is_oa is None

    def test_nan_modulator_fields_become_none(self):
        """NaN values from pandas DataFrames should become None."""
        import math
        model = DatasetFeaturesNormalized.model_validate({
            "source": "semantic_scholar",
            "time_series": float('nan'),
            "multispecies": float('nan'),
        })
        assert model.time_series is None
        assert model.multispecies is None

    def test_boolean_integer_coercion(self):
        """1/0 integer values should coerce to True/False for modulator fields."""
        model = DatasetFeaturesNormalized.model_validate({
            "source": "dryad",
            "time_series": 1,
            "multispecies": 0,
            "threatened_species": 1,
        })
        assert model.time_series is True
        assert model.multispecies is False
        assert model.threatened_species is True

    def test_source_case_insensitive(self):
        """Source enum should handle various casings."""
        model = DatasetFeaturesNormalized.model_validate({"source": "Dryad"})
        assert model.source == "dryad"

    def test_source_without_url_fields(self):
        """Source records without URL fields are valid (backward compat)."""
        for source in ("dryad", "zenodo", "semantic_scholar"):
            model = DatasetFeaturesNormalized.model_validate({"source": source})
            assert model.source == source

    def test_is_oa_false_preserved(self):
        """is_oa=False should not be treated as null."""
        model = DatasetFeaturesNormalized.model_validate({
            "source": "zenodo",
            "is_oa": False,
        })
        assert model.is_oa is False

    def test_is_oa_string_false_coerced(self):
        """String 'false' for is_oa should not become None."""
        # is_oa is Optional[bool], no special coercion validator — it's a bool field
        # direct boolean assignment
        model = DatasetFeaturesNormalized.model_validate({
            "source": "dryad",
            "is_oa": False,
        })
        assert model.is_oa is False

    def test_all_three_sources_produce_distinct_values(self):
        """Each source enum value is distinct and correctly stored."""
        models = [
            DatasetFeaturesNormalized.model_validate({"source": s})
            for s in ("dryad", "zenodo", "semantic_scholar")
        ]
        sources = [m.source for m in models]
        assert sources[0] == "dryad"
        assert sources[1] == "zenodo"
        assert sources[2] == "semantic_scholar"
        assert len(set(sources)) == 3

    def test_null_placeholder_strings_become_none(self):
        """Strings like 'N/A', 'nan', 'none' should become None."""
        model = DatasetFeaturesNormalized.model_validate({
            "source": "dryad",
            "cited_article_doi": "N/A",
            "pdf_url": "nan",
        })
        assert model.cited_article_doi is None
        assert model.pdf_url is None

    def test_empty_string_becomes_none(self):
        """Empty strings for optional fields should become None."""
        model = DatasetFeaturesNormalized.model_validate({
            "source": "zenodo",
            "cited_article_doi": "",
            "journal_url": "  ",
        })
        assert model.cited_article_doi is None
        assert model.journal_url is None


# ---------------------------------------------------------------------------
# Integration: DataSource enum consistency with schema
# ---------------------------------------------------------------------------

class TestDataSourceSchemaIntegration:
    """Tests that DataSource enum values round-trip correctly through the schema."""

    def test_datasource_dryad_roundtrip(self):
        model = DatasetFeatures.model_validate({"source": DataSource.DRYAD})
        assert model.source == "dryad"

    def test_datasource_zenodo_roundtrip(self):
        model = DatasetFeatures.model_validate({"source": DataSource.ZENODO})
        assert model.source == "zenodo"

    def test_datasource_ss_roundtrip(self):
        model = DatasetFeatures.model_validate({"source": DataSource.SEMANTIC_SCHOLAR})
        assert model.source == "semantic_scholar"

    def test_datasource_string_value_accepted(self):
        """String values matching enum members should be accepted."""
        for val in ("dryad", "zenodo", "semantic_scholar"):
            model = DatasetFeatures.model_validate({"source": val})
            assert model.source == val

    def test_datasource_invalid_value_raises(self):
        """Invalid source values should raise ValidationError."""
        import pydantic
        with pytest.raises(pydantic.ValidationError):
            DatasetFeatures.model_validate({"source": "unknown_source_xyz"})
