"""
Tests for PDF classification using OpenAI's File API.

These tests make real API calls to OpenAI and incur costs.
Set RUN_SLOW_TESTS=1 to run expensive API tests.
"""

import os
import pytest
from pathlib import Path

from llm_metadata.gpt_extract import (
    extract_from_pdf_file,
    extract_from_pdf_url,
    upload_pdf_to_openai,
    delete_openai_file,
    PDF_SYSTEM_MESSAGE,
)
from llm_metadata.schemas.fuster_features import DatasetFeatures


# Test data paths
TEST_DATA_DIR = Path(__file__).parent / "data"
SAMPLE_PDF_PATH = TEST_DATA_DIR / "sample_article.pdf"

# Public PDF URL for testing - arXiv paper (always accessible)
TEST_PDF_URL = "https://arxiv.org/pdf/2303.08774.pdf"  # GPT-4 technical report


def has_openai_key() -> bool:
    """Check if OpenAI API key is available."""
    return bool(os.environ.get("OPENAI_API_KEY"))


def run_slow_tests() -> bool:
    """Check if slow/expensive tests should run."""
    return os.environ.get("RUN_SLOW_TESTS", "").lower() in ("1", "true", "yes")


@pytest.mark.skipif(not has_openai_key(), reason="OPENAI_API_KEY not set")
class TestUploadPdfToOpenAI:
    """Tests for PDF file upload to OpenAI."""

    def test_upload_valid_pdf(self):
        """Test uploading a valid PDF file."""
        assert SAMPLE_PDF_PATH.exists(), f"Test PDF not found: {SAMPLE_PDF_PATH}"

        file_id = upload_pdf_to_openai(SAMPLE_PDF_PATH)

        assert isinstance(file_id, str)
        assert file_id.startswith("file-")

        # Cleanup
        delete_openai_file(file_id)

    def test_upload_nonexistent_file_raises(self):
        """Test uploading a non-existent file raises error."""
        with pytest.raises(FileNotFoundError):
            upload_pdf_to_openai(TEST_DATA_DIR / "nonexistent.pdf")


@pytest.mark.skipif(
    not (has_openai_key() and run_slow_tests()),
    reason="Slow test - set RUN_SLOW_TESTS=1"
)
class TestClassifyPdfFile:
    """Tests for extract_from_pdf_file function."""

    def test_extract_from_local_pdf_basic(self):
        """Test basic PDF classification from local file."""
        assert SAMPLE_PDF_PATH.exists(), f"Test PDF not found: {SAMPLE_PDF_PATH}"

        result = extract_from_pdf_file(
            pdf_path=SAMPLE_PDF_PATH,
            system_message=PDF_SYSTEM_MESSAGE,
            model="gpt-5-mini",
            reasoning={"effort": "low"},
            max_output_tokens=4096,
            text_format=DatasetFeatures,
        )

        # Verify result structure
        assert "output" in result
        assert "usage_cost" in result
        assert "extraction_method" in result
        assert "pdf_path" in result
        assert "file_id" in result

        # Verify extraction method
        assert result["extraction_method"] == "pdf_native"

        # Verify output is correct type
        assert isinstance(result["output"], DatasetFeatures)

        # Verify usage cost structure
        usage = result["usage_cost"]
        assert "input_tokens" in usage
        assert "output_tokens" in usage
        assert "total_cost" in usage
        assert usage["input_tokens"] > 0
        assert usage["output_tokens"] > 0

    def test_extract_from_local_pdf_extracts_features(self):
        """Test that PDF classification extracts meaningful features."""
        assert SAMPLE_PDF_PATH.exists()

        result = extract_from_pdf_file(
            pdf_path=SAMPLE_PDF_PATH,
            text_format=DatasetFeatures,
        )

        output = result["output"]

        # The sample PDF should have some extracted fields
        has_data = (
            output.data_type is not None or
            output.species is not None or
            output.temp_range_i is not None or
            output.geospatial_info_dataset is not None
        )
        assert has_data, "Expected at least some features to be extracted"

    def test_extract_from_with_cleanup(self):
        """Test PDF classification with file cleanup."""
        assert SAMPLE_PDF_PATH.exists()

        result = extract_from_pdf_file(
            pdf_path=SAMPLE_PDF_PATH,
            text_format=DatasetFeatures,
            cleanup_file=True,
        )

        # File ID should still be in result even after cleanup
        assert "file_id" in result
        assert result["file_id"] is not None


@pytest.mark.skipif(
    not (has_openai_key() and run_slow_tests()),
    reason="Slow test - set RUN_SLOW_TESTS=1"
)
class TestClassifyPdfUrl:
    """Tests for extract_from_pdf_url function."""

    def test_extract_from_pdffrom_url_basic(self):
        """Test basic PDF classification from URL."""
        result = extract_from_pdf_url(
            pdf_url=TEST_PDF_URL,
            system_message=PDF_SYSTEM_MESSAGE,
            model="gpt-5-mini",
            reasoning={"effort": "low"},
            max_output_tokens=4096,
            text_format=DatasetFeatures,
        )

        # Verify result structure
        assert "output" in result
        assert "usage_cost" in result
        assert "extraction_method" in result
        assert "pdf_url" in result

        # Verify extraction method
        assert result["extraction_method"] == "pdf_url"

        # Verify output is correct type
        assert isinstance(result["output"], DatasetFeatures)

        # Verify URL is stored
        assert result["pdf_url"] == TEST_PDF_URL

    def test_extract_from_pdfurl_returns_valid_output(self):
        """Test that URL-based PDF classification returns valid DatasetFeatures."""
        result = extract_from_pdf_url(
            pdf_url=TEST_PDF_URL,
            text_format=DatasetFeatures,
        )

        output = result["output"]

        # Verify the output is a valid DatasetFeatures instance
        assert isinstance(output, DatasetFeatures)

        # Verify the output can be serialized
        output_dict = output.model_dump()
        assert isinstance(output_dict, dict)


@pytest.mark.skipif(not has_openai_key(), reason="OPENAI_API_KEY not set")
class TestPdfClassifyEdgeCases:
    """Edge case tests for PDF classification."""

    def test_invalid_pdf_file_raises(self):
        """Test that invalid PDF file raises appropriate error."""
        # Create a fake PDF (actually HTML)
        fake_pdf = TEST_DATA_DIR / "fake.pdf"
        fake_pdf.write_text("<!DOCTYPE html><html><body>Not a PDF</body></html>")

        try:
            with pytest.raises(Exception) as exc_info:
                extract_from_pdf_file(
                    pdf_path=fake_pdf,
                    text_format=DatasetFeatures,
                )
            # OpenAI may reject malformed uploads with different invalid-file messages.
            error_msg = str(exc_info.value).lower()
            assert (
                "unsupported" in error_msg
                or "pdf" in error_msg
                or "invalid_file" in error_msg
                or "corrupted" in error_msg
                or "badly formatted" in error_msg
            ), f"Expected malformed-PDF signal in error: {error_msg}"
        finally:
            # Cleanup
            fake_pdf.unlink(missing_ok=True)
