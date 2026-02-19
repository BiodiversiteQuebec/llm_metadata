"""
Tests for SS-3.2 functions added to article_retrieval.py:
  - get_cited_articles_for_dataset()
  - generate_cited_articles_csv()

All external API calls are mocked.
"""

import sys
import os
import unittest
import tempfile
from unittest.mock import patch, MagicMock
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
import config  # noqa: F401 – loads .env and configures environment

from llm_metadata.article_retrieval import (
    get_cited_articles_for_dataset,
    generate_cited_articles_csv,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_DATASET_PAPER = {
    "paperId": "dataset001",
    "title": "Camera trap dataset for mammals",
    "abstract": "A biodiversity dataset.",
    "year": 2022,
    "externalIds": {"DOI": "10.5061/dryad.abc123"},
}

SAMPLE_CITING_PAPER_1 = {
    "paperId": "cite001",
    "title": "Mammal diversity in North America",
    "abstract": "Uses camera trap data.",
    "year": 2023,
    "externalIds": {"DOI": "10.1234/mammals.2023"},
}

SAMPLE_CITING_PAPER_2 = {
    "paperId": "cite002",
    "title": "Biodiversity trends across biomes",
    "abstract": None,
    "year": 2024,
    "externalIds": {},
}

SAMPLE_CITATIONS_RESPONSE_WRAPPED = [
    SAMPLE_CITING_PAPER_1,
    SAMPLE_CITING_PAPER_2,
]


def _make_minimal_xlsx(tmp_dir: str) -> str:
    """Create a minimal validated Excel file for CSV generation tests."""
    data = {
        "id": [1, 2, 3],
        "valid_yn": ["yes", "yes", "no"],
        "title": ["Dataset A", "Dataset B", "Dataset C"],
        "source": ["dryad", "semantic_scholar", "zenodo"],
        "source_url": [
            "https://doi.org/10.5061/dryad.aaa",
            "https://www.semanticscholar.org/paper/abc",
            None,
        ],
        "url": [
            "https://doi.org/10.5061/dryad.aaa",
            "https://www.semanticscholar.org/paper/abc",
            None,
        ],
        "cited_article_doi": [None, None, None],
    }
    path = os.path.join(tmp_dir, "test_validated.xlsx")
    pd.DataFrame(data).to_excel(path, index=False)
    return path


# ---------------------------------------------------------------------------
# Tests: get_cited_articles_for_dataset
# ---------------------------------------------------------------------------


class TestGetCitedArticlesForDataset(unittest.TestCase):
    """Tests for the get_cited_articles_for_dataset function."""

    @patch("llm_metadata.article_retrieval.get_paper_citations")
    @patch("llm_metadata.article_retrieval.get_paper_by_doi")
    def test_returns_citing_articles_via_doi(self, mock_by_doi, mock_citations):
        mock_by_doi.__wrapped__ = mock_by_doi  # bypass joblib cache stub
        mock_by_doi.return_value = SAMPLE_DATASET_PAPER
        mock_citations.__wrapped__ = mock_citations
        mock_citations.return_value = SAMPLE_CITATIONS_RESPONSE_WRAPPED

        results = get_cited_articles_for_dataset(
            dataset_title="Camera trap dataset for mammals",
            dataset_doi="10.5061/dryad.abc123",
        )

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["citing_paper_id"], "cite001")
        self.assertEqual(results[0]["citing_paper_doi"], "10.1234/mammals.2023")
        self.assertEqual(results[0]["retrieval_method"], "by_doi")
        self.assertIsNone(results[1]["citing_paper_doi"])
        mock_by_doi.assert_called_once_with("10.5061/dryad.abc123")

    @patch("llm_metadata.article_retrieval.get_paper_citations")
    @patch("llm_metadata.article_retrieval.get_paper_by_title")
    @patch("llm_metadata.article_retrieval.get_paper_by_doi")
    def test_falls_back_to_title_search_when_doi_not_found(
        self, mock_by_doi, mock_by_title, mock_citations
    ):
        mock_by_doi.return_value = None
        mock_by_title.__wrapped__ = mock_by_title
        mock_by_title.return_value = SAMPLE_DATASET_PAPER
        mock_citations.__wrapped__ = mock_citations
        mock_citations.return_value = [SAMPLE_CITING_PAPER_1]

        results = get_cited_articles_for_dataset(
            dataset_title="Camera trap dataset for mammals",
            dataset_doi="10.5061/dryad.abc123",
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["retrieval_method"], "by_title")
        mock_by_title.assert_called_once_with("Camera trap dataset for mammals")

    @patch("llm_metadata.article_retrieval.get_paper_by_title")
    def test_returns_empty_list_when_not_found_in_ss(self, mock_by_title):
        mock_by_title.return_value = None

        results = get_cited_articles_for_dataset(
            dataset_title="Completely unknown dataset",
            dataset_doi=None,
        )

        self.assertEqual(results, [])

    @patch("llm_metadata.article_retrieval.get_paper_citations")
    @patch("llm_metadata.article_retrieval.get_paper_by_doi")
    def test_returns_empty_list_when_no_citations(self, mock_by_doi, mock_citations):
        mock_by_doi.return_value = SAMPLE_DATASET_PAPER
        mock_citations.return_value = []

        results = get_cited_articles_for_dataset(
            dataset_title="Camera trap dataset",
            dataset_doi="10.5061/dryad.abc123",
        )

        self.assertEqual(results, [])

    @patch("llm_metadata.article_retrieval.get_paper_by_doi")
    def test_doi_lookup_exception_falls_back_to_title(self, mock_by_doi):
        mock_by_doi.side_effect = Exception("Network error")

        with patch("llm_metadata.article_retrieval.get_paper_by_title") as mock_by_title:
            mock_by_title.return_value = None
            results = get_cited_articles_for_dataset(
                dataset_title="Some dataset",
                dataset_doi="10.1234/test",
            )

        self.assertEqual(results, [])

    @patch("llm_metadata.article_retrieval.get_paper_citations")
    @patch("llm_metadata.article_retrieval.get_paper_by_doi")
    def test_citing_paper_fields_populated(self, mock_by_doi, mock_citations):
        mock_by_doi.return_value = SAMPLE_DATASET_PAPER
        mock_citations.return_value = [SAMPLE_CITING_PAPER_1]

        results = get_cited_articles_for_dataset(
            dataset_title="Dataset",
            dataset_doi="10.5061/dryad.abc123",
        )

        self.assertEqual(len(results), 1)
        r = results[0]
        self.assertIn("citing_paper_id", r)
        self.assertIn("citing_paper_doi", r)
        self.assertIn("citing_paper_title", r)
        self.assertIn("citing_paper_abstract", r)
        self.assertIn("citing_paper_year", r)
        self.assertIn("retrieval_method", r)
        self.assertEqual(r["citing_paper_year"], 2023)
        self.assertEqual(r["citing_paper_title"], "Mammal diversity in North America")

    @patch("llm_metadata.article_retrieval.get_paper_citations")
    @patch("llm_metadata.article_retrieval.get_paper_by_doi")
    def test_citation_api_exception_returns_empty_list(self, mock_by_doi, mock_citations):
        mock_by_doi.return_value = SAMPLE_DATASET_PAPER
        mock_citations.side_effect = Exception("API error")

        results = get_cited_articles_for_dataset(
            dataset_title="Dataset",
            dataset_doi="10.5061/dryad.abc123",
        )

        self.assertEqual(results, [])

    @patch("llm_metadata.article_retrieval.get_paper_by_title")
    def test_title_only_mode_no_doi(self, mock_by_title):
        mock_by_title.return_value = None

        results = get_cited_articles_for_dataset(dataset_title="My Dataset")

        self.assertEqual(results, [])
        mock_by_title.assert_called_once_with("My Dataset")


# ---------------------------------------------------------------------------
# Tests: generate_cited_articles_csv
# ---------------------------------------------------------------------------


class TestGenerateCitedArticlesCsv(unittest.TestCase):
    """Tests for generate_cited_articles_csv."""

    @patch("llm_metadata.article_retrieval.get_cited_articles_for_dataset")
    def test_generates_csv_with_results(self, mock_get_cited):
        mock_get_cited.return_value = [
            {
                "citing_paper_id": "cite001",
                "citing_paper_doi": "10.1234/test",
                "citing_paper_title": "A citing paper",
                "citing_paper_abstract": "Abstract.",
                "citing_paper_year": 2023,
                "retrieval_method": "by_doi",
            }
        ]

        with tempfile.TemporaryDirectory() as tmp_dir:
            xlsx_path = _make_minimal_xlsx(tmp_dir)
            output_csv = os.path.join(tmp_dir, "output.csv")

            result_df = generate_cited_articles_csv(xlsx_path, output_csv)

            self.assertTrue(os.path.exists(output_csv))
            # Two valid records → at least 2 rows (one per citing paper each)
            self.assertGreater(len(result_df), 0)
            self.assertIn("dataset_id", result_df.columns)
            self.assertIn("citing_paper_doi", result_df.columns)

    @patch("llm_metadata.article_retrieval.get_cited_articles_for_dataset")
    def test_skips_invalid_records(self, mock_get_cited):
        mock_get_cited.return_value = []

        with tempfile.TemporaryDirectory() as tmp_dir:
            xlsx_path = _make_minimal_xlsx(tmp_dir)
            output_csv = os.path.join(tmp_dir, "output.csv")

            result_df = generate_cited_articles_csv(xlsx_path, output_csv)

            # Only 2 valid records (valid_yn == "yes"), so 2 calls
            self.assertEqual(mock_get_cited.call_count, 2)
            self.assertTrue(os.path.exists(output_csv))
            self.assertEqual(len(result_df), 0)

    @patch("llm_metadata.article_retrieval.get_cited_articles_for_dataset")
    def test_output_contains_dataset_metadata(self, mock_get_cited):
        mock_get_cited.return_value = [
            {
                "citing_paper_id": "x",
                "citing_paper_doi": "10.1/x",
                "citing_paper_title": "X paper",
                "citing_paper_abstract": None,
                "citing_paper_year": 2021,
                "retrieval_method": "by_doi",
            }
        ]

        with tempfile.TemporaryDirectory() as tmp_dir:
            xlsx_path = _make_minimal_xlsx(tmp_dir)
            output_csv = os.path.join(tmp_dir, "output.csv")

            result_df = generate_cited_articles_csv(xlsx_path, output_csv)

            self.assertIn("dataset_source", result_df.columns)
            self.assertIn("dataset_title", result_df.columns)


if __name__ == "__main__":
    unittest.main()
