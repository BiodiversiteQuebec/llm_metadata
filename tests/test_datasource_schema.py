"""Tests for source metadata ownership and feature-model separation."""

import pytest

from llm_metadata.schemas import DataPaperRecord, DataSource
from llm_metadata.schemas.fuster_features import (
    DatasetFeatures,
    DatasetFeaturesEvaluation,
    DatasetFeaturesExtraction,
)


class TestDataSourceEnum:
    def test_datasource_values(self):
        assert DataSource.DRYAD.value == "dryad"
        assert DataSource.ZENODO.value == "zenodo"
        assert DataSource.SEMANTIC_SCHOLAR.value == "semantic_scholar"

    def test_datasource_is_string_subclass(self):
        assert isinstance(DataSource.DRYAD, str)
        assert DataSource.DRYAD == "dryad"


class TestDataPaperRecordOwnsSourceMetadata:
    def test_record_accepts_source_metadata_fields(self):
        record = DataPaperRecord.model_validate(
            {
                "gt_record_id": 1,
                "source": "semantic_scholar",
                "title": "Example paper",
                "source_url": "https://api.semanticscholar.org/paper/abc",
                "article_url": "https://doi.org/10.7717/peerj.18853",
                "pdf_url": "https://peerj.com/articles/18853.pdf",
                "article_doi": "10.7717/peerj.18853",
                "is_oa": True,
            }
        )
        assert record.source == "semantic_scholar"
        assert record.source_url == "https://api.semanticscholar.org/paper/abc"
        assert record.article_url == "https://doi.org/10.7717/peerj.18853"
        assert record.pdf_url == "https://peerj.com/articles/18853.pdf"
        assert record.article_doi == "10.7717/peerj.18853"
        assert record.is_oa is True

    def test_record_normalizes_article_doi(self):
        record = DataPaperRecord(gt_record_id=2, article_doi="https://doi.org/10.1234/ABC")
        assert record.article_doi == "10.1234/abc"


class TestExtractionSchemaIsSemanticOnly:
    def test_existing_semantic_fields_still_validate(self):
        model = DatasetFeatures.model_validate(
            {
                "data_type": ["abundance"],
                "temp_range_i": 2000,
                "temp_range_f": 2020,
                "species": ["Rangifer tarandus"],
            }
        )
        assert model.data_type == ["abundance"]
        assert model.temp_range_i == 2000
        assert model.temp_range_f == 2020
        assert model.species == ["Rangifer tarandus"]

    def test_source_metadata_is_not_on_extraction_model(self):
        schema = DatasetFeaturesExtraction.model_json_schema()
        props = schema["properties"]
        for field_name in ("source", "source_url", "journal_url", "pdf_url", "is_oa", "cited_article_doi"):
            assert field_name not in props

    def test_enrichment_fields_are_not_on_extraction_model(self):
        schema = DatasetFeaturesExtraction.model_json_schema()
        props = schema["properties"]
        for field_name in (
            "parsed_species",
            "taxon_richness_mentions",
            "taxon_richness_counts",
            "taxon_richness_group_keys",
            "taxon_broad_group_labels",
            "species_stripped_richness",
            "gbif_key_stripped_richness",
            "gbif_keys",
        ):
            assert field_name not in props

    def test_alias_points_to_extraction_model(self):
        assert DatasetFeatures is DatasetFeaturesExtraction


class TestEvaluationSchemaAddsDerivedFields:
    def test_evaluation_schema_includes_gbif_keys(self):
        schema = DatasetFeaturesEvaluation.model_json_schema()
        assert "gbif_keys" in schema["properties"]

    def test_extraction_and_evaluation_schemas_differ_intentionally(self):
        extraction_props = DatasetFeaturesExtraction.model_json_schema()["properties"]
        evaluation_props = DatasetFeaturesEvaluation.model_json_schema()["properties"]
        assert "gbif_keys" not in extraction_props
        assert "gbif_keys" in evaluation_props
        assert set(extraction_props).issubset(set(evaluation_props))


class TestDataSourceImportFromSchemas:
    def test_datasource_importable_from_schemas(self):
        from llm_metadata.schemas import DataSource as ImportedDataSource

        assert ImportedDataSource.DRYAD.value == "dryad"
        assert ImportedDataSource.ZENODO.value == "zenodo"
        assert ImportedDataSource.SEMANTIC_SCHOLAR.value == "semantic_scholar"


class TestInvalidSourceValue:
    def test_datasource_invalid_value_raises(self):
        import pydantic

        with pytest.raises(pydantic.ValidationError):
            DataPaperRecord.model_validate({"gt_record_id": 1, "source": "unknown_source_xyz"})
