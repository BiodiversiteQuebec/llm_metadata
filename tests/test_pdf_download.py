import pytest
import tempfile
from pathlib import Path
import shutil

from llm_metadata.pdf_download import (
    sanitize_doi,
    download_pdf,
    batch_download_pdfs
)


class TestDOISanitization:
    """Test DOI sanitization for filenames."""

    def test_sanitize_doi_basic(self):
        """Test basic DOI sanitization."""
        doi = "10.1371/journal.pone.0128238"
        sanitized = sanitize_doi(doi)
        assert sanitized == "10.1371_journal.pone.0128238"

    def test_sanitize_doi_with_prefix(self):
        """Test DOI sanitization with URL prefix."""
        doi = "https://doi.org/10.1371/journal.pone.0128238"
        sanitized = sanitize_doi(doi)
        assert sanitized == "10.1371_journal.pone.0128238"

    def test_sanitize_doi_with_doi_prefix(self):
        """Test DOI sanitization with 'doi:' prefix."""
        doi = "doi:10.1371/journal.pone.0128238"
        sanitized = sanitize_doi(doi)
        assert sanitized == "10.1371_journal.pone.0128238"

    def test_sanitize_doi_special_chars(self):
        """Test DOI with various special characters."""
        doi = "10.1234/test:special/chars"
        sanitized = sanitize_doi(doi)
        # Should replace all problematic characters
        assert "/" not in sanitized
        assert ":" not in sanitized
        assert "\\" not in sanitized


class TestPDFDownload:
    """Test PDF download functionality."""

    @pytest.fixture(autouse=True)
    def setup_temp_dir(self, tmp_path):
        """Create temporary directory for test downloads."""
        self.temp_dir = tmp_path

    def test_download_pdf_success(self):
        """Test successful PDF download from PLOS ONE."""
        # Use a known OA article with public PDF
        pdf_url = "https://journals.plos.org/plosone/article/file?id=10.1371/journal.pone.0128238&type=printable"
        doi = "10.1371/journal.pone.0128238"

        pdf_path = download_pdf(
            pdf_url=pdf_url,
            doi=doi,
            output_dir=self.temp_dir,
            timeout=30
        )

        # Verify download
        assert pdf_path is not None, "Download should succeed"
        assert pdf_path.exists(), "PDF file should exist"
        assert pdf_path.stat().st_size > 1000, "PDF should be larger than 1KB"
        assert pdf_path.name.endswith('.pdf'), "File should have .pdf extension"

    def test_download_pdf_with_year_subdirectory(self):
        """Test PDF download with year-based subdirectory."""
        pdf_url = "https://journals.plos.org/plosone/article/file?id=10.1371/journal.pone.0128238&type=printable"
        doi = "10.1371/journal.pone.0128238"
        year = 2025

        pdf_path = download_pdf(
            pdf_url=pdf_url,
            doi=doi,
            output_dir=self.temp_dir,
            year=year
        )

        # Verify year subdirectory created
        assert pdf_path is not None
        assert str(year) in str(pdf_path)

    def test_download_pdf_invalid_url(self):
        """Test that invalid URL returns None."""
        pdf_path = download_pdf(
            pdf_url="https://invalid.url.that.does.not.exist/file.pdf",
            doi="10.1234/test",
            output_dir=self.temp_dir,
            timeout=5,
            max_retries=1
        )

        assert pdf_path is None, "Invalid URL should return None"

    def test_download_pdf_already_exists(self):
        """Test that existing PDF is not re-downloaded."""
        pdf_url = "https://journals.plos.org/plosone/article/file?id=10.1371/journal.pone.0128238&type=printable"
        doi = "10.1371/journal.pone.0128238"

        # First download
        pdf_path1 = download_pdf(
            pdf_url=pdf_url,
            doi=doi,
            output_dir=self.temp_dir
        )

        assert pdf_path1 is not None

        # Get modification time
        mtime1 = pdf_path1.stat().st_mtime

        # Second download (should skip)
        pdf_path2 = download_pdf(
            pdf_url=pdf_url,
            doi=doi,
            output_dir=self.temp_dir
        )

        # Should return same path
        assert pdf_path1 == pdf_path2

        # Modification time should be unchanged (not re-downloaded)
        mtime2 = pdf_path2.stat().st_mtime
        assert mtime1 == mtime2


class TestBatchDownload:
    """Test batch PDF download functionality."""

    @pytest.fixture(autouse=True)
    def setup_temp_dir(self, tmp_path):
        """Create temporary directory for test downloads."""
        self.temp_dir = tmp_path

    def test_batch_download_pdfs(self):
        """Test batch download with mixed valid/invalid URLs."""
        # Create test works
        works = [
            {
                'pdf_url': 'https://journals.plos.org/plosone/article/file?id=10.1371/journal.pone.0128238&type=printable',
                'doi': '10.1371/journal.pone.0128238',
                'publication_year': 2025
            },
            {
                'pdf_url': 'https://invalid.url/nonexistent.pdf',
                'doi': '10.1234/invalid',
                'publication_year': 2025
            }
        ]

        results = batch_download_pdfs(
            works=works,
            output_dir=self.temp_dir,
            timeout=30
        )

        # Verify results structure
        assert 'successful' in results
        assert 'failed' in results

        # At least one should succeed
        assert len(results['successful']) > 0, "Should have at least one successful download"

        # At least one should fail
        assert len(results['failed']) > 0, "Should have at least one failed download"
