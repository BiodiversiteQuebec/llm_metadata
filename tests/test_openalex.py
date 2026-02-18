import pytest

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

# Sample data for testing
SAMPLE_DOI = "10.1371/journal.pone.0128238"
USHERBROOKE_ROR = "https://ror.org/00kybxq39"


class TestOpenAlexAPI:
    """Test OpenAlex API integration functions."""

    def test_search_topics_ecology(self):
        """Test topic search for ecology keywords."""
        topics = search_topics("ecology", per_page=10)
        assert isinstance(topics, list)
        assert len(topics) > 0, "Should return at least one ecology topic"

        # Check structure of first topic
        if topics:
            first_topic = topics[0]
            assert 'id' in first_topic
            assert 'display_name' in first_topic

    def test_get_work_by_doi(self):
        """Test single work retrieval by DOI."""
        work = get_work_by_doi(SAMPLE_DOI)
        assert work is not None, f"Should retrieve work for DOI {SAMPLE_DOI}"
        assert isinstance(work, dict)

        # Check essential fields
        assert 'id' in work
        assert 'title' in work
        assert 'doi' in work

    def test_get_work_by_doi_not_found(self):
        """Test that non-existent DOI returns None."""
        work = get_work_by_doi("10.9999/nonexistent.doi.12345")
        assert work is None

    def test_search_works_basic(self):
        """Test basic work search without filters."""
        response = search_works(keywords="ecology", per_page=5)
        assert isinstance(response, dict)
        assert 'results' in response
        assert 'meta' in response
        assert len(response['results']) > 0, "Should return at least one result"

    def test_search_works_with_filters(self):
        """Test work search with institution and year filters."""
        response = search_works(
            ror_id=USHERBROOKE_ROR,
            publication_year=2024,
            keywords="ecology",
            is_oa=True,
            per_page=5
        )
        assert isinstance(response, dict)
        assert 'results' in response
        assert 'meta' in response

        # Meta should contain count
        assert 'count' in response['meta']

    def test_get_works_by_filters_all_with_limit(self):
        """Test batch retrieval with max_results limit."""
        works = get_works_by_filters_all(
            keywords="ecology",
            is_oa=True,
            max_results=10
        )
        assert isinstance(works, list)
        assert len(works) <= 10, "Should respect max_results limit"


class TestMetadataExtraction:
    """Test metadata extraction helper functions."""

    @pytest.fixture(scope="class", autouse=True)
    def fetch_sample_work(self, request):
        """Fetch a sample work for testing extraction functions."""
        request.cls.sample_work = get_work_by_doi(SAMPLE_DOI)

    def test_extract_abstract(self):
        """Test abstract extraction from work dict."""
        if not self.sample_work:
            pytest.skip("Sample work not available")

        abstract = extract_abstract(self.sample_work)

        if self.sample_work.get('abstract_inverted_index'):
            assert isinstance(abstract, str)
            assert len(abstract) > 50, "Abstract should be substantial"
        else:
            assert abstract is None

    def test_extract_pdf_url(self):
        """Test PDF URL extraction from OA work."""
        if not self.sample_work:
            pytest.skip("Sample work not available")

        pdf_url = extract_pdf_url(self.sample_work)

        if self.sample_work.get('open_access', {}).get('is_oa'):
            # OA works may or may not have PDF URLs
            if pdf_url:
                assert isinstance(pdf_url, str)
                assert pdf_url.startswith('http'), "PDF URL should be a valid URL"

    def test_extract_authors_with_structure(self):
        """Test author extraction with ORCID and affiliations."""
        if not self.sample_work:
            pytest.skip("Sample work not available")

        authors = extract_authors(self.sample_work)
        assert isinstance(authors, list)
        assert len(authors) > 0, "Work should have at least one author"

        # Check structure of first author
        first_author = authors[0]
        assert 'name' in first_author
        assert 'orcid' in first_author
        assert 'institutions' in first_author

        # If ORCID present, should not have URL prefix
        if first_author['orcid']:
            assert not first_author['orcid'].startswith('https://'), \
                "ORCID should not include URL prefix"

    def test_is_preprint(self):
        """Test preprint identification."""
        if not self.sample_work:
            pytest.skip("Sample work not available")

        result = is_preprint(self.sample_work)
        assert isinstance(result, bool)

        # Verify against actual work type
        work_type = self.sample_work.get('type', '').lower()
        if work_type == 'preprint':
            assert result is True
        else:
            assert result is False


class TestPydanticSchema:
    """Test Pydantic model conversion and validation."""

    @pytest.fixture(scope="class", autouse=True)
    def fetch_sample_work(self, request):
        """Fetch a sample work for testing model conversion."""
        request.cls.sample_work = get_work_by_doi(SAMPLE_DOI)

    def test_work_dict_to_model(self):
        """Test conversion from API dict to Pydantic model."""
        if not self.sample_work:
            pytest.skip("Sample work not available")

        model = work_dict_to_model(self.sample_work)

        # Verify model type
        assert isinstance(model, OpenAlexWork)

        # Verify required fields
        assert model.openalex_id is not None
        assert model.title is not None

        # Verify OA fields
        assert isinstance(model.is_oa, bool)

        # Verify preprint flag consistency
        if model.work_type and model.work_type.lower() == 'preprint':
            assert model.is_preprint is True

    def test_model_serialization(self):
        """Test that model can be serialized to dict and JSON."""
        if not self.sample_work:
            pytest.skip("Sample work not available")

        model = work_dict_to_model(self.sample_work)

        # Test dict serialization
        model_dict = model.model_dump()
        assert isinstance(model_dict, dict)
        assert 'openalex_id' in model_dict
        assert 'title' in model_dict

        # Test JSON serialization
        model_json = model.model_dump_json()
        assert isinstance(model_json, str)
        assert len(model_json) > 0
