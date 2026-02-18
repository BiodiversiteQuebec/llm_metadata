"""
Integration tests for PDF download pipeline with validation.

Tests the full download-and-validate flow:
- validate_pdf correctly rejects HTML, tiny files, missing files
- validate_pdf accepts real PDFs
- Network-dependent tests (download + validate) are skipped when offline
- All existing fuster PDFs pass validation
"""

import pytest
import requests
from pathlib import Path

from llm_metadata.pdf_download import (
    download_pdf_with_fallback,
    download_pdf_from_url,
    validate_pdf,
    guess_publisher_pdf_url,
    InvalidPDFError,
    MIN_PDF_SIZE,
)

# Project root (tests/ is one level below)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Known open-access article with stable PDF URL
OA_DOI = "10.1371/journal.pone.0128238"
OA_PDF_URL = (
    "https://journals.plos.org/plosone/article/file"
    "?id=10.1371/journal.pone.0128238&type=printable"
)


def _has_network() -> bool:
    """Check if external network is reachable."""
    try:
        requests.head("https://journals.plos.org", timeout=5)
        return True
    except Exception:
        return False


class TestValidatePDF:
    """Test the validate_pdf function."""

    @pytest.fixture(autouse=True)
    def setup_temp_dir(self, tmp_path):
        self.temp_dir = tmp_path

    def test_validate_missing_file(self):
        """validate_pdf raises for nonexistent file."""
        with pytest.raises(InvalidPDFError):
            validate_pdf(self.temp_dir / "nonexistent.pdf")

    def test_validate_html_file(self):
        """validate_pdf rejects HTML content saved as .pdf."""
        fake = self.temp_dir / "fake.pdf"
        fake.write_text("<!DOCTYPE html><html><body>Not a PDF</body></html>")
        with pytest.raises(InvalidPDFError, match="not a PDF"):
            validate_pdf(fake)

    def test_validate_small_pdf(self):
        """validate_pdf rejects a file with valid header but too small."""
        tiny = self.temp_dir / "tiny.pdf"
        tiny.write_bytes(b"%PDF-1.4 tiny file")
        with pytest.raises(InvalidPDFError, match="too small"):
            validate_pdf(tiny)

    def test_validate_custom_min_size(self):
        """validate_pdf accepts a small PDF when min_size is lowered."""
        tiny = self.temp_dir / "tiny.pdf"
        tiny.write_bytes(b"%PDF-1.4 tiny file")
        validate_pdf(tiny, min_size=10)

    def test_existing_invalid_pdf_deleted_on_redownload(self):
        """download_pdf_with_fallback deletes existing invalid file instead of returning it."""
        fake = self.temp_dir / "10.9999_fake.pdf"
        fake.write_text("<!DOCTYPE html><html>Not a PDF</html>")
        assert fake.exists()

        result = download_pdf_with_fallback(
            doi="10.9999/fake",
            output_dir=self.temp_dir,
        )
        # Download will fail (no valid source), but the invalid file should be gone
        assert not fake.exists(), "Invalid existing file should have been deleted"


@pytest.mark.skipif(not _has_network(), reason="No network access")
class TestDownloadWithValidation:
    """Integration test: download a real PDF and verify it passes validation."""

    @pytest.fixture(autouse=True)
    def setup_temp_dir(self, tmp_path):
        self.temp_dir = tmp_path

    def test_download_and_validate_oa_pdf(self):
        """Download a known OA PDF and validate it."""
        pdf_path = download_pdf_with_fallback(
            doi=OA_DOI,
            openalex_pdf_url=OA_PDF_URL,
            output_dir=self.temp_dir,
        )
        assert pdf_path is not None, "Download should succeed for OA article"
        assert pdf_path.exists()

        # The downloaded file must pass validation
        validate_pdf(pdf_path)

        # Double-check: file should be a real PDF
        with open(pdf_path, "rb") as f:
            header = f.read(4)
        assert header == b"%PDF"

        # File should be well above the minimum size
        assert pdf_path.stat().st_size > MIN_PDF_SIZE

    def test_download_rejects_html_response(self):
        """download_pdf_from_url rejects an HTML page served as PDF."""
        html_url = "https://doi.org/10.1371/journal.pone.0128238"
        output_path = self.temp_dir / "should_fail.pdf"

        success = download_pdf_from_url(
            pdf_url=html_url,
            output_path=output_path,
            timeout=15,
            max_retries=1,
        )

        # Should fail because the response is HTML, not PDF
        assert not success
        # File should not remain on disk
        assert not output_path.exists()


class TestGuessPublisherPdfUrl:
    """Test publisher PDF URL guessing from DOI prefixes."""

    def test_wiley_doi(self):
        url = guess_publisher_pdf_url("10.1111/mec.14361")
        assert url == "https://onlinelibrary.wiley.com/doi/pdfdirect/10.1111/mec.14361"

    def test_wiley_ece_doi(self):
        url = guess_publisher_pdf_url("10.1002/ece3.3947")
        assert url == "https://onlinelibrary.wiley.com/doi/pdfdirect/10.1002/ece3.3947"

    def test_springer_doi(self):
        url = guess_publisher_pdf_url("10.1007/s10592-019-01170-8")
        assert url == "https://link.springer.com/content/pdf/10.1007/s10592-019-01170-8.pdf"

    def test_nature_doi(self):
        url = guess_publisher_pdf_url("10.1038/s41477-020-0647-x")
        assert url == "https://www.nature.com/articles/s41477-020-0647-x.pdf"

    def test_unknown_publisher_returns_none(self):
        url = guess_publisher_pdf_url("10.9999/unknown")
        assert url is None


def _has_ezproxy_session() -> bool:
    """Check if a valid EZproxy session exists."""
    try:
        from llm_metadata.ezproxy import extract_cookies_from_browser, verify_session_active
        cookies = extract_cookies_from_browser()
        if not cookies:
            return False
        return verify_session_active(cookies)
    except Exception:
        return False


@pytest.mark.skipif(not _has_network(), reason="No network access")
@pytest.mark.skipif(not _has_ezproxy_session(), reason="No active EZproxy session")
class TestEZproxyDownload:
    """Integration test: download a closed-access PDF via EZproxy."""

    # Closed-access Wiley article (Molecular Ecology)
    CLOSED_DOI = "10.1111/mec.14361"

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        self.temp_dir = tmp_path
        from llm_metadata.ezproxy import extract_cookies_from_browser
        self.cookies = extract_cookies_from_browser()

    def test_download_closed_access_via_ezproxy(self):
        """Download a closed-access Wiley article using EZproxy proxied URL."""
        pdf_path = download_pdf_with_fallback(
            doi=self.CLOSED_DOI,
            output_dir=self.temp_dir,
            use_unpaywall=False,  # Skip OA strategies to test EZproxy directly
            ezproxy_cookies=self.cookies,
        )
        assert pdf_path is not None, f"EZproxy download should succeed for {self.CLOSED_DOI}"
        assert pdf_path.exists()
        validate_pdf(pdf_path)


class TestExistingFusterPDFs:
    """Validate all existing PDFs in data/pdfs/fuster/ are real PDFs."""

    FUSTER_DIR = PROJECT_ROOT / "data" / "pdfs" / "fuster"

    def test_all_fuster_pdfs_valid(self):
        """Every .pdf file in the fuster directory must be a valid PDF."""
        if not self.FUSTER_DIR.exists():
            pytest.skip(f"{self.FUSTER_DIR} does not exist")

        pdf_files = list(self.FUSTER_DIR.glob("*.pdf"))
        if not pdf_files:
            pytest.skip("No PDF files found in data/pdfs/fuster/")

        invalid = []
        for pdf_path in pdf_files:
            try:
                validate_pdf(pdf_path)
            except InvalidPDFError as e:
                invalid.append(str(e))

        assert invalid == [], \
            f"Found {len(invalid)} invalid PDF(s):\n" + "\n".join(invalid)
