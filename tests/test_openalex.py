import config
from llm_metadata.openalex import (
    search_topics,
    search_works,
    get_works_by_filters_all,
    get_work_by_doi,
    extract_abstract,
    extract_pdf_url,
    extract_authors,
    is_preprint
)
from llm_metadata.schemas.openalex_work import work_dict_to_model, OpenAlexWork
import unittest

# Sample data for testing
SAMPLE_DOI = "10.1371/journal.pone.0128238"
USHERBROOKE_ROR = "https://ror.org/00kybxq39"


class TestOpenAlexAPI(unittest.TestCase):
    """Test OpenAlex API integration functions."""

    def test_search_topics_ecology(self):
        """Test topic search for ecology keywords."""
        topics = search_topics("ecology", per_page=10)
        self.assertIsInstance(topics, list)
        self.assertGreater(len(topics), 0, "Should return at least one ecology topic")

        # Check structure of first topic
        if topics:
            first_topic = topics[0]
            self.assertIn('id', first_topic)
            self.assertIn('display_name', first_topic)

    def test_get_work_by_doi(self):
        """Test single work retrieval by DOI."""
        work = get_work_by_doi(SAMPLE_DOI)
        self.assertIsNotNone(work, f"Should retrieve work for DOI {SAMPLE_DOI}")
        self.assertIsInstance(work, dict)

        # Check essential fields
        self.assertIn('id', work)
        self.assertIn('title', work)
        self.assertIn('doi', work)

    def test_get_work_by_doi_not_found(self):
        """Test that non-existent DOI returns None."""
        work = get_work_by_doi("10.9999/nonexistent.doi.12345")
        self.assertIsNone(work)

    def test_search_works_basic(self):
        """Test basic work search without filters."""
        response = search_works(keywords="ecology", per_page=5)
        self.assertIsInstance(response, dict)
        self.assertIn('results', response)
        self.assertIn('meta', response)
        self.assertGreater(len(response['results']), 0, "Should return at least one result")

    def test_search_works_with_filters(self):
        """Test work search with institution and year filters."""
        response = search_works(
            ror_id=USHERBROOKE_ROR,
            publication_year=2024,
            keywords="ecology",
            is_oa=True,
            per_page=5
        )
        self.assertIsInstance(response, dict)
        self.assertIn('results', response)
        self.assertIn('meta', response)

        # Meta should contain count
        self.assertIn('count', response['meta'])

    def test_get_works_by_filters_all_with_limit(self):
        """Test batch retrieval with max_results limit."""
        works = get_works_by_filters_all(
            keywords="ecology",
            is_oa=True,
            max_results=10
        )
        self.assertIsInstance(works, list)
        self.assertLessEqual(len(works), 10, "Should respect max_results limit")


class TestMetadataExtraction(unittest.TestCase):
    """Test metadata extraction helper functions."""

    @classmethod
    def setUpClass(cls):
        """Fetch a sample work for testing extraction functions."""
        cls.sample_work = get_work_by_doi(SAMPLE_DOI)

    def test_extract_abstract(self):
        """Test abstract extraction from work dict."""
        if not self.sample_work:
            self.skipTest("Sample work not available")

        abstract = extract_abstract(self.sample_work)

        if self.sample_work.get('abstract_inverted_index'):
            self.assertIsInstance(abstract, str)
            self.assertGreater(len(abstract), 50, "Abstract should be substantial")
        else:
            self.assertIsNone(abstract)

    def test_extract_pdf_url(self):
        """Test PDF URL extraction from OA work."""
        if not self.sample_work:
            self.skipTest("Sample work not available")

        pdf_url = extract_pdf_url(self.sample_work)

        if self.sample_work.get('open_access', {}).get('is_oa'):
            # OA works may or may not have PDF URLs
            if pdf_url:
                self.assertIsInstance(pdf_url, str)
                self.assertTrue(
                    pdf_url.startswith('http'),
                    "PDF URL should be a valid URL"
                )

    def test_extract_authors_with_structure(self):
        """Test author extraction with ORCID and affiliations."""
        if not self.sample_work:
            self.skipTest("Sample work not available")

        authors = extract_authors(self.sample_work)
        self.assertIsInstance(authors, list)
        self.assertGreater(len(authors), 0, "Work should have at least one author")

        # Check structure of first author
        first_author = authors[0]
        self.assertIn('name', first_author)
        self.assertIn('orcid', first_author)
        self.assertIn('institutions', first_author)

        # If ORCID present, should not have URL prefix
        if first_author['orcid']:
            self.assertFalse(
                first_author['orcid'].startswith('https://'),
                "ORCID should not include URL prefix"
            )

    def test_is_preprint(self):
        """Test preprint identification."""
        if not self.sample_work:
            self.skipTest("Sample work not available")

        result = is_preprint(self.sample_work)
        self.assertIsInstance(result, bool)

        # Verify against actual work type
        work_type = self.sample_work.get('type', '').lower()
        if work_type == 'preprint':
            self.assertTrue(result)
        else:
            self.assertFalse(result)


class TestPydanticSchema(unittest.TestCase):
    """Test Pydantic model conversion and validation."""

    @classmethod
    def setUpClass(cls):
        """Fetch a sample work for testing model conversion."""
        cls.sample_work = get_work_by_doi(SAMPLE_DOI)

    def test_work_dict_to_model(self):
        """Test conversion from API dict to Pydantic model."""
        if not self.sample_work:
            self.skipTest("Sample work not available")

        model = work_dict_to_model(self.sample_work)

        # Verify model type
        self.assertIsInstance(model, OpenAlexWork)

        # Verify required fields
        self.assertIsNotNone(model.openalex_id)
        self.assertIsNotNone(model.title)

        # Verify OA fields
        self.assertIsInstance(model.is_oa, bool)

        # Verify preprint flag consistency
        if model.work_type and model.work_type.lower() == 'preprint':
            self.assertTrue(model.is_preprint)

    def test_model_serialization(self):
        """Test that model can be serialized to dict and JSON."""
        if not self.sample_work:
            self.skipTest("Sample work not available")

        model = work_dict_to_model(self.sample_work)

        # Test dict serialization
        model_dict = model.model_dump()
        self.assertIsInstance(model_dict, dict)
        self.assertIn('openalex_id', model_dict)
        self.assertIn('title', model_dict)

        # Test JSON serialization
        model_json = model.model_dump_json()
        self.assertIsInstance(model_json, str)
        self.assertGreater(len(model_json), 0)


if __name__ == '__main__':
    unittest.main()
