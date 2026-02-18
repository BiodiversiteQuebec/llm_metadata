"""
Unit tests for raw PDF extraction functionality.
"""
import pytest

try:
    from llm_metadata.fulltext_pipeline import (
        FulltextPipelineConfig,
        GPTClassifyConfig,
    )
    _import_ok = True
except ImportError:
    _import_ok = False

pytestmark = pytest.mark.skipif(
    not _import_ok,
    reason="llm_metadata.fulltext_pipeline not importable (missing dependencies or API changes)"
)


class TestPipelineConfiguration:
    """Test pipeline configuration for different extraction methods."""

    def test_grobid_extraction_config(self):
        """Test GROBID extraction method configuration."""
        config = FulltextPipelineConfig(
            gpt_config=GPTClassifyConfig(
                model="gpt-5-mini",
                extraction_method="grobid"
            )
        )

        assert config.gpt_config.extraction_method == "grobid"

    def test_raw_pdf_extraction_config(self):
        """Test raw PDF extraction method configuration."""
        config = FulltextPipelineConfig(
            gpt_config=GPTClassifyConfig(
                model="gpt-5-mini",
                extraction_method="raw_pdf",
                max_pdf_pages=10
            )
        )

        assert config.gpt_config.extraction_method == "raw_pdf"
        assert config.gpt_config.max_pdf_pages == 10

    def test_default_max_pdf_pages(self):
        """Test default value for max_pdf_pages."""
        config = FulltextPipelineConfig(
            gpt_config=GPTClassifyConfig(
                model="gpt-5-mini",
                extraction_method="raw_pdf"
            )
        )

        # Check that max_pdf_pages has a default value
        assert config.gpt_config.max_pdf_pages is not None
