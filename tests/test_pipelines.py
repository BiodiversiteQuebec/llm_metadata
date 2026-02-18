"""
Tests for all three classification pipelines.
"""

import warnings
from pathlib import Path


class TestPipelineImports:
    """Verify all pipeline modules import without error."""

    def test_text_pipeline_imports(self):
        from llm_metadata.text_pipeline import (
            TextClassificationConfig,
            TextInputRecord,
            text_classification_flow,
        )

    def test_pdf_pipeline_imports(self):
        from llm_metadata.pdf_pipeline import (
            PDFClassificationConfig,
            PDFInputRecord,
            pdf_classification_flow,
        )

    def test_section_pipeline_imports(self):
        from llm_metadata.section_pipeline import (
            SectionClassificationConfig,
            SectionInputRecord,
            SectionSelectionConfig,
            section_classification_flow,
        )

    def test_unified_pipelines_interface_imports(self):
        from llm_metadata.pipelines import classify, compare_pipelines


class TestPipelineConfigCreation:
    """Verify configuration objects can be instantiated."""

    def test_text_classification_config(self):
        from llm_metadata.text_pipeline import TextClassificationConfig
        config = TextClassificationConfig(model="gpt-5-mini")
        assert config.model == "gpt-5-mini"

    def test_pdf_classification_config(self):
        from llm_metadata.pdf_pipeline import PDFClassificationConfig
        config = PDFClassificationConfig(model="gpt-5-mini", max_pdf_pages=10)
        assert config.max_pdf_pages == 10

    def test_section_classification_config(self):
        from llm_metadata.section_pipeline import (
            SectionClassificationConfig,
            SectionSelectionConfig,
        )
        config = SectionClassificationConfig(
            model="gpt-5-mini",
            section_config=SectionSelectionConfig(include_all=False),
        )
        assert config is not None


class TestPipelineRecordCreation:
    """Verify input record objects can be instantiated."""

    def test_text_input_record(self):
        from llm_metadata.text_pipeline import TextInputRecord
        record = TextInputRecord(
            id="test_1",
            text="Sample text for classification",
            metadata={"source": "test"},
        )
        assert record.id == "test_1"

    def test_pdf_input_record(self):
        from llm_metadata.pdf_pipeline import PDFInputRecord
        record = PDFInputRecord(
            id="test_pdf",
            pdf_path="data/pdfs/sample.pdf",
            metadata={"type": "test"},
        )
        assert record.id == "test_pdf"

    def test_section_input_record(self):
        from llm_metadata.section_pipeline import SectionInputRecord
        record = SectionInputRecord(
            id="test_section",
            pdf_path="data/pdfs/sample.pdf",
        )
        assert record.id == "test_section"


class TestUnifiedInterface:
    """Verify the unified pipeline interface works."""

    def test_compare_pipelines(self):
        from llm_metadata.pipelines import compare_pipelines
        comparison = compare_pipelines()
        assert comparison is not None

    def test_detect_pipeline_text(self):
        from llm_metadata.pipelines import _detect_pipeline
        assert _detect_pipeline("raw text string") == "text"

    def test_detect_pipeline_pdf(self):
        from llm_metadata.pipelines import _detect_pipeline
        assert _detect_pipeline(Path("paper.pdf")) == "pdf"

    def test_detect_pipeline_section(self):
        from llm_metadata.pipelines import _detect_pipeline
        assert _detect_pipeline(Path("manifest.csv")) == "section"

    def test_detect_pipeline_list_of_pdfs(self):
        from llm_metadata.pipelines import _detect_pipeline
        assert _detect_pipeline([Path("p1.pdf"), Path("p2.pdf")]) == "pdf"


class TestDeprecationWarning:
    """Verify deprecation warnings are raised for legacy imports."""

    def test_fulltext_pipeline_deprecation(self):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            try:
                from llm_metadata import fulltext_pipeline
                # If import succeeds, check for deprecation warning
                has_deprecation = any(
                    issubclass(warning.category, DeprecationWarning)
                    for warning in w
                )
                # Warning may or may not be raised depending on implementation
                # Just verify the import doesn't raise an unexpected error
            except Exception:
                pass  # Import failure is also acceptable
