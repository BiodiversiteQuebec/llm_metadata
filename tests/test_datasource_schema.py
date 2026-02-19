"""
Unit tests for DataSource enum and new multi-source fields in DatasetFeatures.

Tests cover:
- DataSource enum values
- DatasetFeatures with new fields populated
- DatasetFeatures backward compatibility (no new fields)
"""

import unittest

from llm_metadata.schemas.fuster_features import DataSource, DatasetFeatures


class TestDataSourceEnum(unittest.TestCase):
    """Tests for the DataSource enum."""

    def test_datasource_dryad_value(self):
        self.assertEqual(DataSource.DRYAD.value, "dryad")

    def test_datasource_zenodo_value(self):
        self.assertEqual(DataSource.ZENODO.value, "zenodo")

    def test_datasource_semantic_scholar_value(self):
        self.assertEqual(DataSource.SEMANTIC_SCHOLAR.value, "semantic_scholar")

    def test_datasource_all_members(self):
        members = {m.value for m in DataSource}
        self.assertEqual(members, {"dryad", "zenodo", "semantic_scholar", "referenced"})

    def test_datasource_is_string_subclass(self):
        self.assertIsInstance(DataSource.DRYAD, str)
        self.assertEqual(DataSource.DRYAD, "dryad")


class TestDatasetFeaturesBackwardCompatibility(unittest.TestCase):
    """Tests that existing records without new fields still validate."""

    def test_empty_model_is_valid(self):
        """An empty DatasetFeatures should be valid (all fields optional)."""
        model = DatasetFeatures()
        self.assertIsNone(model.source)
        self.assertIsNone(model.source_url)
        self.assertIsNone(model.journal_url)
        self.assertIsNone(model.pdf_url)
        self.assertIsNone(model.is_oa)
        self.assertIsNone(model.cited_article_doi)

    def test_existing_fields_still_work(self):
        """Records created without new fields should still validate correctly."""
        model = DatasetFeatures.model_validate({
            "data_type": ["abundance"],
            "temp_range_i": 2000,
            "temp_range_f": 2020,
            "species": ["Rangifer tarandus"],
        })
        self.assertEqual(model.data_type, ["abundance"])
        self.assertEqual(model.temp_range_i, 2000)
        self.assertEqual(model.temp_range_f, 2020)
        self.assertEqual(model.species, ["Rangifer tarandus"])
        # New fields should default to None
        self.assertIsNone(model.source)
        self.assertIsNone(model.source_url)
        self.assertIsNone(model.journal_url)
        self.assertIsNone(model.pdf_url)
        self.assertIsNone(model.is_oa)
        self.assertIsNone(model.cited_article_doi)

    def test_dict_without_new_fields_validates(self):
        """A dict without new fields should produce a valid DatasetFeatures."""
        data = {
            "valid_yn": "yes",
            "referred_dataset": "Some dataset source",
        }
        model = DatasetFeatures.model_validate(data)
        self.assertIsNone(model.source)
        self.assertIsNone(model.is_oa)


class TestDatasetFeaturesNewFields(unittest.TestCase):
    """Tests for the new multi-source tracking fields in DatasetFeatures."""

    def test_source_field_with_enum_value(self):
        """source field should accept DataSource enum values."""
        model = DatasetFeatures.model_validate({"source": "dryad"})
        self.assertEqual(model.source, "dryad")

    def test_source_field_semantic_scholar(self):
        model = DatasetFeatures.model_validate({"source": "semantic_scholar"})
        self.assertEqual(model.source, "semantic_scholar")

    def test_source_field_zenodo(self):
        model = DatasetFeatures.model_validate({"source": "zenodo"})
        self.assertEqual(model.source, "zenodo")

    def test_source_url_field(self):
        url = "https://api.semanticscholar.org/v1/paper/12345"
        model = DatasetFeatures.model_validate({"source_url": url})
        self.assertEqual(model.source_url, url)

    def test_journal_url_field(self):
        url = "https://doi.org/10.1234/example"
        model = DatasetFeatures.model_validate({"journal_url": url})
        self.assertEqual(model.journal_url, url)

    def test_pdf_url_field(self):
        url = "https://example.com/paper.pdf"
        model = DatasetFeatures.model_validate({"pdf_url": url})
        self.assertEqual(model.pdf_url, url)

    def test_is_oa_true(self):
        model = DatasetFeatures.model_validate({"is_oa": True})
        self.assertTrue(model.is_oa)

    def test_is_oa_false(self):
        model = DatasetFeatures.model_validate({"is_oa": False})
        self.assertFalse(model.is_oa)

    def test_cited_article_doi_field(self):
        doi = "10.1234/peerj.12345"
        model = DatasetFeatures.model_validate({"cited_article_doi": doi})
        self.assertEqual(model.cited_article_doi, doi)

    def test_all_new_fields_populated(self):
        """All new fields can be set together on the same model."""
        data = {
            "source": "semantic_scholar",
            "source_url": "https://api.semanticscholar.org/paper/abc",
            "journal_url": "https://peerj.com/articles/12345",
            "pdf_url": "https://peerj.com/articles/12345.pdf",
            "is_oa": True,
            "cited_article_doi": "10.7717/peerj.18853",
        }
        model = DatasetFeatures.model_validate(data)
        self.assertEqual(model.source, "semantic_scholar")
        self.assertEqual(model.source_url, "https://api.semanticscholar.org/paper/abc")
        self.assertEqual(model.journal_url, "https://peerj.com/articles/12345")
        self.assertEqual(model.pdf_url, "https://peerj.com/articles/12345.pdf")
        self.assertTrue(model.is_oa)
        self.assertEqual(model.cited_article_doi, "10.7717/peerj.18853")

    def test_new_fields_combined_with_existing(self):
        """New fields can coexist with existing fields."""
        data = {
            "data_type": ["abundance", "time_series"],
            "temp_range_i": 2010,
            "temp_range_f": 2023,
            "species": ["Ursus americanus"],
            "source": "dryad",
            "source_url": "https://datadryad.org/stash/dataset/doi:10.5061/dryad.abc",
            "is_oa": False,
            "cited_article_doi": "10.1234/test.doi",
        }
        model = DatasetFeatures.model_validate(data)
        self.assertEqual(model.data_type, ["abundance", "time_series"])
        self.assertEqual(model.temp_range_i, 2010)
        self.assertEqual(model.source, "dryad")
        self.assertFalse(model.is_oa)
        self.assertEqual(model.cited_article_doi, "10.1234/test.doi")

    def test_source_field_none_by_default(self):
        """source field should be None when not specified."""
        model = DatasetFeatures()
        self.assertIsNone(model.source)

    def test_url_fields_accept_non_standard_urls(self):
        """URL fields should accept any string value (no strict URL validation)."""
        model = DatasetFeatures.model_validate({
            "source_url": "not-a-real-url",
            "pdf_url": "ftp://legacy.server/file.pdf",
        })
        self.assertEqual(model.source_url, "not-a-real-url")
        self.assertEqual(model.pdf_url, "ftp://legacy.server/file.pdf")


class TestDataSourceImportFromSchemas(unittest.TestCase):
    """Tests that DataSource is accessible from the schemas package."""

    def test_datasource_importable_from_schemas(self):
        from llm_metadata.schemas import DataSource as DS
        self.assertEqual(DS.DRYAD.value, "dryad")
        self.assertEqual(DS.ZENODO.value, "zenodo")
        self.assertEqual(DS.SEMANTIC_SCHOLAR.value, "semantic_scholar")


if __name__ == "__main__":
    unittest.main()
