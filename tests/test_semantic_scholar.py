"""
Unit tests for the Semantic Scholar API client module.

All tests use mocked HTTP responses to avoid real API calls.
"""

import pytest
import requests
from unittest.mock import patch, MagicMock

from llm_metadata.semantic_scholar import (
    get_paper_by_doi,
    get_paper_by_title,
    get_paper_citations,
    get_paper_references,
    get_open_access_pdf_url,
    _clean_doi,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_PAPER_RESPONSE = {
    "paperId": "abc123def456",
    "title": "Evaluating the feasibility of automating dataset retrieval for biodiversity monitoring",
    "abstract": "This paper evaluates automated dataset retrieval using LLMs.",
    "year": 2025,
    "authors": [
        {"authorId": "1", "name": "Fuster-Calvo A"},
        {"authorId": "2", "name": "Valentin S"},
    ],
    "openAccessPdf": {
        "url": "https://peerj.com/articles/18853.pdf",
        "status": "HYBRID",
    },
    "externalIds": {
        "DOI": "10.7717/peerj.18853",
        "PubMed": "12345678",
    },
}

SAMPLE_PAPER_NO_OA = {
    "paperId": "zzz999",
    "title": "A closed access paper",
    "abstract": "Abstract text.",
    "year": 2020,
    "authors": [{"authorId": "3", "name": "Author C"}],
    "openAccessPdf": None,
    "externalIds": {"DOI": "10.9999/closed.paper"},
}

SAMPLE_SEARCH_RESPONSE = {
    "total": 1,
    "offset": 0,
    "next": None,
    "data": [
        {
            "paperId": "abc123def456",
            "title": "Evaluating the feasibility of automating dataset retrieval for biodiversity monitoring",
            "abstract": "This paper evaluates automated dataset retrieval using LLMs.",
            "year": 2025,
            "authors": [{"authorId": "1", "name": "Fuster-Calvo A"}],
        }
    ],
}

SAMPLE_EMPTY_SEARCH_RESPONSE = {
    "total": 0,
    "offset": 0,
    "next": None,
    "data": [],
}

SAMPLE_CITATIONS_RESPONSE = {
    "offset": 0,
    "next": None,
    "data": [
        {
            "citingPaper": {
                "paperId": "cite001",
                "title": "A citing paper",
                "abstract": "Cites the original work.",
            }
        },
        {
            "citingPaper": {
                "paperId": "cite002",
                "title": "Another citing paper",
                "abstract": None,
            }
        },
    ],
}

SAMPLE_REFERENCES_RESPONSE = {
    "offset": 0,
    "next": None,
    "data": [
        {
            "citedPaper": {
                "paperId": "ref001",
                "title": "A referenced paper",
                "abstract": "This is referenced.",
            }
        },
    ],
}


def _make_mock_response(status_code: int, json_data=None):
    """Helper: create a mock requests.Response object."""
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    if json_data is not None:
        mock_resp.json.return_value = json_data
    if status_code >= 400:
        mock_resp.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
    else:
        mock_resp.raise_for_status.return_value = None
    return mock_resp


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestCleanDoi:
    """Test the internal DOI cleaning helper."""

    def test_strips_https_prefix(self):
        assert _clean_doi("https://doi.org/10.1234/foo") == "10.1234/foo"

    def test_strips_http_prefix(self):
        assert _clean_doi("http://doi.org/10.1234/foo") == "10.1234/foo"

    def test_strips_doi_colon_prefix(self):
        assert _clean_doi("doi:10.1234/foo") == "10.1234/foo"

    def test_already_clean_doi(self):
        assert _clean_doi("10.1234/foo") == "10.1234/foo"

    def test_strips_whitespace(self):
        assert _clean_doi("  10.1234/foo  ") == "10.1234/foo"


class TestGetPaperByDoi:
    """Tests for get_paper_by_doi."""

    @patch("llm_metadata.semantic_scholar.requests.get")
    def test_returns_paper_on_200(self, mock_get):
        mock_get.return_value = _make_mock_response(200, SAMPLE_PAPER_RESPONSE)

        from llm_metadata.semantic_scholar import get_paper_by_doi as _fn
        result = _fn.__wrapped__("10.7717/peerj.18853")

        assert result is not None
        assert result["paperId"] == "abc123def456"
        assert result["title"] == SAMPLE_PAPER_RESPONSE["title"]

    @patch("llm_metadata.semantic_scholar.requests.get")
    def test_returns_none_on_404(self, mock_get):
        mock_404 = MagicMock()
        mock_404.status_code = 404
        mock_404.raise_for_status.return_value = None
        mock_get.return_value = mock_404

        from llm_metadata.semantic_scholar import get_paper_by_doi as _fn
        result = _fn.__wrapped__("10.9999/nonexistent")

        assert result is None

    @patch("llm_metadata.semantic_scholar.requests.get")
    def test_doi_with_https_prefix_is_cleaned(self, mock_get):
        mock_get.return_value = _make_mock_response(200, SAMPLE_PAPER_RESPONSE)

        from llm_metadata.semantic_scholar import get_paper_by_doi as _fn
        result = _fn.__wrapped__("https://doi.org/10.7717/peerj.18853")

        assert result is not None
        # Verify the call used the DOI: prefix format
        call_args = mock_get.call_args
        called_url = call_args[0][0]
        assert "DOI:10.7717/peerj.18853" in called_url

    @patch("llm_metadata.semantic_scholar.requests.get")
    def test_raises_on_server_error(self, mock_get):
        mock_500 = MagicMock()
        mock_500.status_code = 500
        mock_500.raise_for_status.side_effect = Exception("HTTP 500")
        mock_get.return_value = mock_500

        from llm_metadata.semantic_scholar import get_paper_by_doi as _fn
        with pytest.raises(Exception):
            _fn.__wrapped__("10.1234/server-error")


class TestGetPaperByTitle:
    """Tests for get_paper_by_title."""

    @patch("llm_metadata.semantic_scholar.requests.get")
    def test_returns_first_hit_on_success(self, mock_get):
        mock_get.return_value = _make_mock_response(200, SAMPLE_SEARCH_RESPONSE)

        from llm_metadata.semantic_scholar import get_paper_by_title as _fn
        result = _fn.__wrapped__("biodiversity monitoring")

        assert result is not None
        assert result["paperId"] == "abc123def456"

    @patch("llm_metadata.semantic_scholar.requests.get")
    def test_returns_none_when_no_results(self, mock_get):
        mock_get.return_value = _make_mock_response(200, SAMPLE_EMPTY_SEARCH_RESPONSE)

        from llm_metadata.semantic_scholar import get_paper_by_title as _fn
        result = _fn.__wrapped__("zzzzz unlikely title zzzzz")

        assert result is None

    @patch("llm_metadata.semantic_scholar.requests.get")
    def test_returns_none_on_404(self, mock_get):
        mock_404 = MagicMock()
        mock_404.status_code = 404
        mock_404.raise_for_status.return_value = None
        mock_get.return_value = mock_404

        from llm_metadata.semantic_scholar import get_paper_by_title as _fn
        result = _fn.__wrapped__("some title")

        assert result is None


class TestGetPaperCitations:
    """Tests for get_paper_citations."""

    @patch("llm_metadata.semantic_scholar.requests.get")
    def test_returns_list_of_citing_papers(self, mock_get):
        mock_get.return_value = _make_mock_response(200, SAMPLE_CITATIONS_RESPONSE)

        from llm_metadata.semantic_scholar import get_paper_citations as _fn
        results = _fn.__wrapped__("abc123def456", limit=100)

        assert isinstance(results, list)
        assert len(results) == 2
        assert results[0]["paperId"] == "cite001"
        assert results[1]["paperId"] == "cite002"

    @patch("llm_metadata.semantic_scholar.requests.get")
    def test_returns_empty_list_on_404(self, mock_get):
        mock_404 = MagicMock()
        mock_404.status_code = 404
        mock_404.raise_for_status.return_value = None
        mock_get.return_value = mock_404

        from llm_metadata.semantic_scholar import get_paper_citations as _fn
        results = _fn.__wrapped__("nonexistent_id", limit=100)

        assert results == []

    @patch("llm_metadata.semantic_scholar.requests.get")
    def test_returns_empty_list_when_no_data(self, mock_get):
        mock_get.return_value = _make_mock_response(200, {"data": []})

        from llm_metadata.semantic_scholar import get_paper_citations as _fn
        results = _fn.__wrapped__("abc123def456", limit=100)

        assert results == []


class TestGetPaperReferences:
    """Tests for get_paper_references."""

    @patch("llm_metadata.semantic_scholar.requests.get")
    def test_returns_list_of_referenced_papers(self, mock_get):
        mock_get.return_value = _make_mock_response(200, SAMPLE_REFERENCES_RESPONSE)

        from llm_metadata.semantic_scholar import get_paper_references as _fn
        results = _fn.__wrapped__("abc123def456", limit=100)

        assert isinstance(results, list)
        assert len(results) == 1
        assert results[0]["paperId"] == "ref001"

    @patch("llm_metadata.semantic_scholar.requests.get")
    def test_returns_empty_list_on_404(self, mock_get):
        mock_404 = MagicMock()
        mock_404.status_code = 404
        mock_404.raise_for_status.return_value = None
        mock_get.return_value = mock_404

        from llm_metadata.semantic_scholar import get_paper_references as _fn
        results = _fn.__wrapped__("nonexistent_id", limit=100)

        assert results == []


class TestGetOpenAccessPdfUrl:
    """Tests for get_open_access_pdf_url."""

    @patch("llm_metadata.semantic_scholar.requests.get")
    def test_returns_pdf_url_for_oa_paper(self, mock_get):
        mock_get.return_value = _make_mock_response(200, SAMPLE_PAPER_RESPONSE)

        from llm_metadata.semantic_scholar import get_open_access_pdf_url as _fn
        url = _fn.__wrapped__("10.7717/peerj.18853")

        assert url is not None
        assert url == "https://peerj.com/articles/18853.pdf"

    @patch("llm_metadata.semantic_scholar.requests.get")
    def test_returns_none_for_non_oa_paper(self, mock_get):
        mock_get.return_value = _make_mock_response(200, SAMPLE_PAPER_NO_OA)

        from llm_metadata.semantic_scholar import get_open_access_pdf_url as _fn
        url = _fn.__wrapped__("10.9999/closed.paper")

        assert url is None

    @patch("llm_metadata.semantic_scholar.requests.get")
    def test_returns_none_when_paper_not_found(self, mock_get):
        mock_404 = MagicMock()
        mock_404.status_code = 404
        mock_404.raise_for_status.return_value = None
        mock_get.return_value = mock_404

        from llm_metadata.semantic_scholar import get_open_access_pdf_url as _fn
        url = _fn.__wrapped__("10.9999/nonexistent")

        assert url is None


class TestNetworkErrorHandling:
    """Tests for network error scenarios."""

    @patch("llm_metadata.semantic_scholar.requests.get")
    def test_get_paper_by_doi_raises_on_connection_error(self, mock_get):
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection refused")

        from llm_metadata.semantic_scholar import get_paper_by_doi as _fn
        with pytest.raises(requests.exceptions.ConnectionError):
            _fn.__wrapped__("10.1234/test")

    @patch("llm_metadata.semantic_scholar.requests.get")
    def test_get_paper_by_doi_raises_on_timeout(self, mock_get):
        mock_get.side_effect = requests.exceptions.Timeout("Request timed out")

        from llm_metadata.semantic_scholar import get_paper_by_doi as _fn
        with pytest.raises(requests.exceptions.Timeout):
            _fn.__wrapped__("10.1234/test")
