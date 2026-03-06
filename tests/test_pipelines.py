"""Tests for the unified explicit-mode extraction engine."""

import time
from pathlib import Path
from unittest.mock import patch

from llm_metadata.extraction import (
    ExtractionConfig,
    ExtractionMode,
    SectionSelectionConfig,
    run_manifest_extraction,
)
from llm_metadata.schemas.data_paper import DataPaperManifest, DataPaperRecord


class TestPipelineConfigCreation:
    def test_extraction_config(self):
        config = ExtractionConfig(model="gpt-5-mini", max_pdf_pages=10)
        assert config.model == "gpt-5-mini"
        assert config.max_pdf_pages == 10

    def test_section_selection_config(self):
        config = SectionSelectionConfig(include_all=False)
        assert config.include_all is False


class TestUnifiedExtraction:
    def test_abstract_mode_uses_manifest_abstract(self):
        manifest = DataPaperManifest(
            records=[DataPaperRecord(gt_record_id=1, abstract="Sample abstract", title="Paper")]
        )

        with patch("llm_metadata.extraction.extract_from_text") as extract_from_text:
            extract_from_text.return_value = {
                "output": type("X", (), {"model_dump": lambda self, mode=None: {"species": ["lynx"]}})(),
                "usage_cost": {"total_cost": 0.1},
            }
            artifact = run_manifest_extraction(manifest, mode=ExtractionMode.ABSTRACT)

        assert len(artifact.records) == 1
        assert artifact.records[0].status == "success"

    def test_pdf_native_mode_skips_missing_pdf(self):
        manifest = DataPaperManifest(records=[DataPaperRecord(gt_record_id=1)])
        artifact = run_manifest_extraction(manifest, mode=ExtractionMode.PDF_NATIVE)
        assert artifact.records[0].status == "skipped"

    def test_pdf_text_mode_calls_pdf_classifier(self, tmp_path):
        pdf_path = tmp_path / "paper.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 fake")
        manifest = DataPaperManifest(
            records=[DataPaperRecord(gt_record_id=1, pdf_local_path=str(pdf_path))]
        )

        with patch("llm_metadata.extraction.extract_from_pdf_text") as extract_from_pdf_text:
            extract_from_pdf_text.return_value = {
                "output": type("X", (), {"model_dump": lambda self, mode=None: {"species": ["lynx"]}})(),
                "usage_cost": {"total_cost": 0.2},
                "extraction_method": "pdf_text",
                "text": "Extracted text",
            }
            artifact = run_manifest_extraction(manifest, mode=ExtractionMode.PDF_TEXT)

        assert artifact.records[0].status == "success"
        assert artifact.records[0].extraction_method == "pdf_text"

    def test_artifact_can_be_saved(self, tmp_path):
        manifest = DataPaperManifest(records=[DataPaperRecord(gt_record_id=1, abstract="Text")])
        with patch("llm_metadata.extraction.extract_from_text") as extract_from_text:
            extract_from_text.return_value = {
                "output": type("X", (), {"model_dump": lambda self, mode=None: {}})(),
                "usage_cost": {"total_cost": 0.0},
            }
            output = tmp_path / "run.json"
            artifact = run_manifest_extraction(
                manifest,
                mode=ExtractionMode.ABSTRACT,
                output_path=output,
                manifest_path="data/manifests/dev_subset_data_paper.csv",
            )
        assert output.exists()
        assert output.with_suffix(".csv").exists()
        assert artifact.manifest_path == "data/manifests/dev_subset_data_paper.csv"

    def test_parallelism_preserves_manifest_order(self):
        manifest = DataPaperManifest(
            records=[
                DataPaperRecord(gt_record_id=1, abstract="slow"),
                DataPaperRecord(gt_record_id=2, abstract="fast"),
            ]
        )

        def fake_extract(text, **kwargs):
            if text == "slow":
                time.sleep(0.05)
            return {
                "output": type("X", (), {"model_dump": lambda self, mode=None: {"abstract": text}})(),
                "usage_cost": {"total_cost": 0.1},
            }

        with patch("llm_metadata.extraction.extract_from_text", side_effect=fake_extract):
            artifact = run_manifest_extraction(manifest, mode=ExtractionMode.ABSTRACT, parallelism=2)

        assert [record.gt_record_id for record in artifact.records] == [1, 2]

    def test_parallelism_must_be_positive(self):
        manifest = DataPaperManifest(records=[DataPaperRecord(gt_record_id=1, abstract="Text")])

        with patch("llm_metadata.extraction.extract_from_text"):
            try:
                run_manifest_extraction(manifest, mode=ExtractionMode.ABSTRACT, parallelism=0)
            except ValueError as exc:
                assert "parallelism" in str(exc)
            else:
                raise AssertionError("Expected ValueError for non-positive parallelism")
