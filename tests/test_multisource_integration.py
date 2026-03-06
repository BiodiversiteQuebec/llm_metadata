"""Integration tests for multi-source records after schema separation."""

import pytest

from llm_metadata.schemas.data_paper import DataPaperRecord
from llm_metadata.schemas.fuster_features import DatasetFeaturesNormalized


DRYAD_RECORD = {
    "gt_record_id": 1,
    "source": "dryad",
    "source_url": "https://datadryad.org/stash/dataset/doi:10.5061/dryad.abc123",
    "article_url": "https://doi.org/10.1371/journal.pone.0128238",
    "pdf_url": None,
    "is_oa": True,
    "article_doi": "10.1371/journal.pone.0128238",
}

ZENODO_RECORD = {
    "gt_record_id": 2,
    "source": "zenodo",
    "source_url": "https://zenodo.org/record/12345",
    "article_url": "https://doi.org/10.5281/zenodo.12345",
    "pdf_url": "https://zenodo.org/record/12345/files/paper.pdf",
    "is_oa": True,
    "article_doi": "10.1234/somepaper.2021",
}

SEMANTIC_SCHOLAR_RECORD = {
    "gt_record_id": 3,
    "source": "semantic_scholar",
    "source_url": "https://api.semanticscholar.org/graph/v1/paper/search?query=biodiversity+monitoring",
    "article_url": "https://doi.org/10.7717/peerj.18853",
    "pdf_url": "https://peerj.com/articles/18853.pdf",
    "is_oa": True,
    "article_doi": "10.7717/peerj.18853",
}

SEMANTIC_GT = {
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
    "valid_yn": "yes",
}


class TestDataPaperRecordBySource:
    @pytest.mark.parametrize(
        ("payload", "expected_source"),
        [
            (DRYAD_RECORD, "dryad"),
            (ZENODO_RECORD, "zenodo"),
            (SEMANTIC_SCHOLAR_RECORD, "semantic_scholar"),
        ],
    )
    def test_record_source_round_trip(self, payload, expected_source):
        record = DataPaperRecord.model_validate(payload)
        assert record.source == expected_source

    def test_record_preserves_is_oa_false(self):
        record = DataPaperRecord.model_validate(
            {
                **ZENODO_RECORD,
                "gt_record_id": 4,
                "is_oa": False,
            }
        )
        assert record.is_oa is False

    def test_record_normalizes_source_doi_from_url(self):
        record = DataPaperRecord.model_validate(
            {
                **DRYAD_RECORD,
                "gt_record_id": 5,
                "source_doi": "https://doi.org/10.5061/Dryad.abc123",
            }
        )
        assert record.source_doi == "10.5061/dryad.abc123"


class TestGroundTruthNormalization:
    def test_semantic_gt_row_normalizes_boolean_modulators(self):
        model = DatasetFeaturesNormalized.model_validate(SEMANTIC_GT)
        assert model.time_series is True
        assert model.multispecies is True
        assert model.threatened_species is True
        assert model.new_species_science is True
        assert model.new_species_region is False
        assert model.bias_north_south is True

    def test_semantic_gt_row_parses_species_and_data_type(self):
        model = DatasetFeaturesNormalized.model_validate(SEMANTIC_GT)
        assert model.species == ["Homo sapiens"]
        assert model.data_type == ["abundance", "presence-only"]

    def test_source_metadata_is_ignored_by_gt_model(self):
        model = DatasetFeaturesNormalized.model_validate(
            {
                **SEMANTIC_GT,
                "source": "semantic_scholar",
                "source_url": "https://example.com",
                "pdf_url": "https://example.com/paper.pdf",
                "is_oa": True,
            }
        )
        assert model.species == ["Homo sapiens"]
        assert not hasattr(model, "source")
        assert not hasattr(model, "pdf_url")

    def test_null_placeholder_strings_become_none(self):
        model = DatasetFeaturesNormalized.model_validate(
            {
                "data_type": "abundance",
                "species": "N/A",
                "temporal_range": "",
            }
        )
        assert model.species is None
        assert model.temporal_range is None
