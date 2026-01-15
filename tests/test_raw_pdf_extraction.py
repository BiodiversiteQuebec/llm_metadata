"""
Unit tests for raw PDF extraction functionality.
"""
import unittest
from pathlib import Path
from llm_metadata.fulltext_pipeline import (
    FulltextPipelineConfig,
    GPTClassifyConfig,
)


class TestPipelineConfiguration(unittest.TestCase):
    """Test pipeline configuration for different extraction methods."""

    def test_grobid_extraction_config(self):
        """Test GROBID extraction method configuration."""
        config = FulltextPipelineConfig(
            gpt_config=GPTClassifyConfig(
                model="gpt-5-mini",
                extraction_method="grobid"
            )
        )

        self.assertEqual(config.gpt_config.extraction_method, "grobid")

    def test_raw_pdf_extraction_config(self):
        """Test raw PDF extraction method configuration."""
        config = FulltextPipelineConfig(
            gpt_config=GPTClassifyConfig(
                model="gpt-5-mini",
                extraction_method="raw_pdf",
                max_pdf_pages=10
            )
        )

        self.assertEqual(config.gpt_config.extraction_method, "raw_pdf")
        self.assertEqual(config.gpt_config.max_pdf_pages, 10)

    def test_default_max_pdf_pages(self):
        """Test default value for max_pdf_pages."""
        config = FulltextPipelineConfig(
            gpt_config=GPTClassifyConfig(
                model="gpt-5-mini",
                extraction_method="raw_pdf"
            )
        )

        # Check that max_pdf_pages has a default value
        self.assertIsNotNone(config.gpt_config.max_pdf_pages)


if __name__ == '__main__':
    unittest.main()
