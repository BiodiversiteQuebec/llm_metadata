"""Tests for canonical data-paper contracts."""

import csv

from pathlib import Path

import pytest
from pydantic import ValidationError

from llm_metadata.schemas.data_paper import (
    DataPaperManifest,
    DataPaperRecord,
    ExtractionMode,
    RunArtifact,
    RunRecord,
)
from llm_metadata.schemas.fuster_features import DataSource


class TestDataPaperRecord:
    def test_minimal_valid(self):
        record = DataPaperRecord(gt_record_id=9)
        assert record.gt_record_id == 9
        assert record.source is None

    def test_doi_normalized_on_construction(self):
        record = DataPaperRecord(
            gt_record_id=9,
            source_doi="https://doi.org/10.1371/JOURNAL.PONE.0128238",
            article_doi="https://doi.org/10.1371/TEST",
        )
        assert record.source_doi == "10.1371/journal.pone.0128238"
        assert record.article_doi == "10.1371/test"

    def test_source_enum(self):
        record = DataPaperRecord(gt_record_id=9, source="dryad")
        assert record.source == DataSource.DRYAD

    def test_pdf_path_exists(self, tmp_path):
        pdf_path = tmp_path / "paper.pdf"
        pdf_path.write_bytes(b"%PDF")
        record = DataPaperRecord(gt_record_id=9, pdf_local_path=str(pdf_path))
        assert record.pdf_path_exists() is True

    def test_canonical_id_prefers_article_doi(self):
        record = DataPaperRecord(gt_record_id=9, article_doi="10.1371/journal.pone.0128238")
        assert record.canonical_id() == "10.1371/journal.pone.0128238"


class TestDataPaperManifest:
    def test_duplicate_ids_raise(self):
        with pytest.raises(ValidationError, match="Duplicate gt_record_id"):
            DataPaperManifest(records=[DataPaperRecord(gt_record_id=1), DataPaperRecord(gt_record_id=1)])

    def test_with_pdf_path_returns_new_manifest(self):
        manifest = DataPaperManifest(records=[DataPaperRecord(gt_record_id=1)])
        updated = manifest.with_pdf_path(1, "/tmp/test.pdf")
        assert manifest.by_id()[1].pdf_local_path is None
        assert updated.by_id()[1].pdf_local_path == "/tmp/test.pdf"

    def test_validate_pdf_coverage(self, tmp_path):
        pdf = tmp_path / "a.pdf"
        pdf.write_bytes(b"%PDF")
        manifest = DataPaperManifest(
            records=[
                DataPaperRecord(gt_record_id=1, pdf_local_path=str(pdf)),
                DataPaperRecord(gt_record_id=2, pdf_local_path="/nonexistent/path.pdf"),
                DataPaperRecord(gt_record_id=3),
            ]
        )
        coverage = manifest.validate_pdf_coverage()
        assert coverage["total"] == 3
        assert coverage["pdf_on_disk"] == 1
        assert 2 in coverage["missing_from_disk"]
        assert 3 in coverage["no_pdf_path"]


class TestRunArtifact:
    def test_total_cost_usd(self, tmp_path):
        artifact = RunArtifact(
            name="demo",
            mode=ExtractionMode.ABSTRACT,
            prompt_module="prompts.abstract",
            system_message="system",
            model="gpt-5-mini",
            records=[
                RunRecord(
                    gt_record_id=1,
                    record_id="1",
                    mode=ExtractionMode.ABSTRACT,
                    status="success",
                    usage_cost={"total_cost": 0.1},
                ),
                RunRecord(
                    gt_record_id=2,
                    record_id="2",
                    mode=ExtractionMode.ABSTRACT,
                    status="success",
                    usage_cost={"total_cost": 0.2},
                ),
            ],
        )
        assert artifact.total_cost_usd == 0.3

        output_path = tmp_path / "artifact.json"
        artifact.save_json(output_path)
        loaded = RunArtifact.load_json(output_path)
        assert loaded.name == "demo"
        assert loaded.mode == ExtractionMode.ABSTRACT

    def test_save_extraction_csv(self, tmp_path):
        artifact = RunArtifact(
            name="demo",
            mode=ExtractionMode.ABSTRACT,
            prompt_module="prompts.abstract",
            system_message="system",
            model="gpt-5-mini",
            records=[
                RunRecord(
                    gt_record_id=1,
                    record_id="1",
                    mode=ExtractionMode.ABSTRACT,
                    status="success",
                    title="Paper A",
                    extraction_method="abstract_text",
                    usage_cost={"total_cost": 0.1},
                    output={"species": ["lynx"], "time_series": False},
                )
            ],
        )

        csv_path = tmp_path / "artifact.csv"
        artifact.save_extraction_csv(csv_path)

        with csv_path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))

        assert len(rows) == 1
        assert rows[0]["gt_record_id"] == "1"
        assert rows[0]["species"] == '["lynx"]'
        assert rows[0]["time_series"] == "False"
