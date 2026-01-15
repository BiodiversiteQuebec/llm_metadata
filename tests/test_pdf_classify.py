"""
Tests for PDF classification using OpenAI's File API.

These tests make real API calls to OpenAI and incur costs.
Run with: python -m unittest tests.test_pdf_classify -v

Set RUN_SLOW_TESTS=1 to run expensive API tests.
"""

import os
import unittest
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from llm_metadata.gpt_classify import (
    classify_pdf_file,
    classify_pdf_url,
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


@unittest.skipUnless(has_openai_key(), "OPENAI_API_KEY not set")
class TestUploadPdfToOpenAI(unittest.TestCase):
    """Tests for PDF file upload to OpenAI."""

    def test_upload_valid_pdf(self):
        """Test uploading a valid PDF file."""
        self.assertTrue(SAMPLE_PDF_PATH.exists(), f"Test PDF not found: {SAMPLE_PDF_PATH}")

        file_id = upload_pdf_to_openai(SAMPLE_PDF_PATH)

        self.assertIsInstance(file_id, str)
        self.assertTrue(file_id.startswith("file-"))

        # Cleanup
        delete_openai_file(file_id)

    def test_upload_nonexistent_file_raises(self):
        """Test uploading a non-existent file raises error."""
        with self.assertRaises(FileNotFoundError):
            upload_pdf_to_openai(TEST_DATA_DIR / "nonexistent.pdf")


@unittest.skipUnless(has_openai_key() and run_slow_tests(), "Slow test - set RUN_SLOW_TESTS=1")
class TestClassifyPdfFile(unittest.TestCase):
    """Tests for classify_pdf_file function."""

    def test_classify_local_pdf_basic(self):
        """Test basic PDF classification from local file."""
        self.assertTrue(SAMPLE_PDF_PATH.exists(), f"Test PDF not found: {SAMPLE_PDF_PATH}")

        result = classify_pdf_file(
            pdf_path=SAMPLE_PDF_PATH,
            system_message=PDF_SYSTEM_MESSAGE,
            model="gpt-5-mini",
            reasoning={"effort": "low"},
            max_output_tokens=4096,
            text_format=DatasetFeatures,
        )

        # Verify result structure
        self.assertIn("output", result)
        self.assertIn("usage_cost", result)
        self.assertIn("extraction_method", result)
        self.assertIn("pdf_path", result)
        self.assertIn("file_id", result)

        # Verify extraction method
        self.assertEqual(result["extraction_method"], "openai_file_api")

        # Verify output is correct type
        self.assertIsInstance(result["output"], DatasetFeatures)

        # Verify usage cost structure
        usage = result["usage_cost"]
        self.assertIn("input_tokens", usage)
        self.assertIn("output_tokens", usage)
        self.assertIn("total_cost", usage)
        self.assertGreater(usage["input_tokens"], 0)
        self.assertGreater(usage["output_tokens"], 0)

    def test_classify_local_pdf_extracts_features(self):
        """Test that PDF classification extracts meaningful features."""
        self.assertTrue(SAMPLE_PDF_PATH.exists())

        result = classify_pdf_file(
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
        self.assertTrue(has_data, "Expected at least some features to be extracted")

    def test_classify_with_cleanup(self):
        """Test PDF classification with file cleanup."""
        self.assertTrue(SAMPLE_PDF_PATH.exists())

        result = classify_pdf_file(
            pdf_path=SAMPLE_PDF_PATH,
            text_format=DatasetFeatures,
            cleanup_file=True,
        )

        # File ID should still be in result even after cleanup
        self.assertIn("file_id", result)
        self.assertIsNotNone(result["file_id"])


@unittest.skipUnless(has_openai_key() and run_slow_tests(), "Slow test - set RUN_SLOW_TESTS=1")
class TestClassifyPdfUrl(unittest.TestCase):
    """Tests for classify_pdf_url function."""

    def test_classify_pdf_from_url_basic(self):
        """Test basic PDF classification from URL."""
        result = classify_pdf_url(
            pdf_url=TEST_PDF_URL,
            system_message=PDF_SYSTEM_MESSAGE,
            model="gpt-5-mini",
            reasoning={"effort": "low"},
            max_output_tokens=4096,
            text_format=DatasetFeatures,
        )

        # Verify result structure
        self.assertIn("output", result)
        self.assertIn("usage_cost", result)
        self.assertIn("extraction_method", result)
        self.assertIn("pdf_url", result)

        # Verify extraction method
        self.assertEqual(result["extraction_method"], "openai_url_api")

        # Verify output is correct type
        self.assertIsInstance(result["output"], DatasetFeatures)

        # Verify URL is stored
        self.assertEqual(result["pdf_url"], TEST_PDF_URL)

    def test_classify_pdf_url_returns_valid_output(self):
        """Test that URL-based PDF classification returns valid DatasetFeatures."""
        result = classify_pdf_url(
            pdf_url=TEST_PDF_URL,
            text_format=DatasetFeatures,
        )

        output = result["output"]

        # Verify the output is a valid DatasetFeatures instance
        # The test PDF is a ML paper so may not have biodiversity features
        self.assertIsInstance(output, DatasetFeatures)

        # Verify the output can be serialized
        output_dict = output.model_dump()
        self.assertIsInstance(output_dict, dict)


@unittest.skipUnless(has_openai_key(), "OPENAI_API_KEY not set")
class TestPdfClassifyEdgeCases(unittest.TestCase):
    """Edge case tests for PDF classification."""

    def test_invalid_pdf_file_raises(self):
        """Test that invalid PDF file raises appropriate error."""
        # Create a fake PDF (actually HTML)
        fake_pdf = TEST_DATA_DIR / "fake.pdf"
        fake_pdf.write_text("<!DOCTYPE html><html><body>Not a PDF</body></html>")

        try:
            with self.assertRaises(Exception) as context:
                classify_pdf_file(
                    pdf_path=fake_pdf,
                    text_format=DatasetFeatures,
                )
            # Should fail with unsupported file type error
            error_msg = str(context.exception).lower()
            self.assertTrue(
                "unsupported" in error_msg or "pdf" in error_msg,
                f"Expected 'unsupported' or 'pdf' in error: {error_msg}"
            )
        finally:
            # Cleanup
            fake_pdf.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
