"""Tests for llm_metadata.schemas.data_paper."""

import pytest
from pydantic import ValidationError

from llm_metadata.schemas.data_paper import DataPaperRecord, DataPaperManifest
from llm_metadata.schemas.fuster_features import DataSource


class TestDataPaperRecord:
    def test_minimal_valid(self):
        rec = DataPaperRecord(gt_record_id=9)
        assert rec.gt_record_id == 9
        assert rec.source is None

    def test_doi_normalized_on_construction(self):
        rec = DataPaperRecord(
            gt_record_id=9,
            source_doi="https://doi.org/10.1371/JOURNAL.PONE.0128238",
            article_doi="https://doi.org/10.1371/TEST",
        )
        assert rec.source_doi == "10.1371/journal.pone.0128238"
        assert rec.article_doi == "10.1371/test"

    def test_source_enum(self):
        rec = DataPaperRecord(gt_record_id=9, source="dryad")
        assert rec.source == DataSource.DRYAD

    def test_pdf_path_exists_false_when_unset(self):
        rec = DataPaperRecord(gt_record_id=9)
        assert rec.pdf_path_exists() is False

    def test_pdf_path_exists_false_when_missing_file(self, tmp_path):
        rec = DataPaperRecord(gt_record_id=9, pdf_local_path=str(tmp_path / "nonexistent.pdf"))
        assert rec.pdf_path_exists() is False

    def test_pdf_path_exists_true(self, tmp_path):
        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF")
        rec = DataPaperRecord(gt_record_id=9, pdf_local_path=str(pdf))
        assert rec.pdf_path_exists() is True

    def test_doi_filename_stem(self):
        rec = DataPaperRecord(gt_record_id=9, article_doi="10.1371/journal.pone.0128238")
        assert rec.doi_filename_stem() == "10.1371_journal.pone.0128238"

    def test_doi_filename_stem_falls_back_to_source(self):
        rec = DataPaperRecord(gt_record_id=9, source_doi="10.5061/dryad.qn1cj")
        assert rec.doi_filename_stem() == "10.5061_dryad.qn1cj"

    def test_doi_filename_stem_none_when_no_doi(self):
        rec = DataPaperRecord(gt_record_id=9)
        assert rec.doi_filename_stem() is None


class TestDataPaperManifest:
    def test_empty_manifest(self):
        m = DataPaperManifest()
        assert len(m) == 0

    def test_valid_manifest(self):
        records = [
            DataPaperRecord(gt_record_id=1, source_doi="10.1371/a"),
            DataPaperRecord(gt_record_id=2, source_doi="10.1371/b"),
        ]
        m = DataPaperManifest(records=records)
        assert len(m) == 2

    def test_duplicate_ids_raise(self):
        records = [
            DataPaperRecord(gt_record_id=1),
            DataPaperRecord(gt_record_id=1),
        ]
        with pytest.raises(ValidationError, match="Duplicate gt_record_id"):
            DataPaperManifest(records=records)

    def test_by_id(self):
        records = [
            DataPaperRecord(gt_record_id=9, article_doi="10.1371/a"),
            DataPaperRecord(gt_record_id=19, article_doi="10.1371/b"),
        ]
        m = DataPaperManifest(records=records)
        idx = m.by_id()
        assert 9 in idx
        assert 19 in idx

    def test_with_pdf(self):
        records = [
            DataPaperRecord(gt_record_id=1, pdf_local_path="/some/path.pdf"),
            DataPaperRecord(gt_record_id=2),
        ]
        m = DataPaperManifest(records=records)
        assert len(m.with_pdf()) == 1
        assert m.with_pdf()[0].gt_record_id == 1

    def test_validate_pdf_coverage(self, tmp_path):
        pdf = tmp_path / "a.pdf"
        pdf.write_bytes(b"%PDF")
        records = [
            DataPaperRecord(gt_record_id=1, pdf_local_path=str(pdf)),
            DataPaperRecord(gt_record_id=2, pdf_local_path="/nonexistent/path.pdf"),
            DataPaperRecord(gt_record_id=3),
        ]
        m = DataPaperManifest(records=records)
        cov = m.validate_pdf_coverage()
        assert cov["total"] == 3
        assert cov["with_pdf_local_path"] == 2
        assert cov["pdf_on_disk"] == 1
        assert 2 in cov["missing_from_disk"]
        assert 3 in cov["no_pdf_path"]

    def test_to_csv_rows(self):
        records = [DataPaperRecord(gt_record_id=9, source_doi="10.1371/a")]
        m = DataPaperManifest(records=records)
        rows = m.to_csv_rows()
        assert len(rows) == 1
        assert rows[0]["gt_record_id"] == 9
        assert rows[0]["source_doi"] == "10.1371/a"
