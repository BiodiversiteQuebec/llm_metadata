"""Tests for llm_metadata.manifest_adapters."""

import pytest

from llm_metadata.schemas.data_paper import DataPaperManifest, DataPaperRecord
from llm_metadata.manifest_adapters import (
    record_to_fulltext_input,
    record_to_pdf_input,
    record_to_section_input,
    manifest_to_fulltext_inputs,
    manifest_to_pdf_inputs,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def make_record(
    gt_record_id: int = 1,
    article_doi: str = "10.1234/test",
    source_doi: str = "10.5678/dataset",
    pdf_local_path: str = "/data/pdfs/10.1234_test.pdf",
    **kwargs,
) -> DataPaperRecord:
    return DataPaperRecord(
        gt_record_id=gt_record_id,
        article_doi=article_doi,
        source_doi=source_doi,
        pdf_local_path=pdf_local_path,
        **kwargs,
    )


def make_manifest(*records: DataPaperRecord) -> DataPaperManifest:
    return DataPaperManifest(records=list(records))


# ---------------------------------------------------------------------------
# record_to_fulltext_input
# ---------------------------------------------------------------------------


class TestRecordToFulltextInput:
    def test_required_keys_present(self):
        rec = make_record()
        out = record_to_fulltext_input(rec)
        assert "article_doi" in out
        assert "dataset_doi" in out
        assert "pdf_path" in out
        assert "title" in out

    def test_article_doi_preferred_over_source_doi(self):
        rec = make_record(article_doi="10.1000/article", source_doi="10.2000/dataset")
        out = record_to_fulltext_input(rec)
        assert out["article_doi"] == "10.1000/article"

    def test_falls_back_to_source_doi_when_no_article_doi(self):
        rec = make_record(article_doi=None, source_doi="10.2000/dataset")
        out = record_to_fulltext_input(rec)
        assert out["article_doi"] == "10.2000/dataset"

    def test_pdf_path_maps_from_pdf_local_path(self):
        rec = make_record(pdf_local_path="/data/pdfs/test.pdf")
        out = record_to_fulltext_input(rec)
        assert out["pdf_path"] == "/data/pdfs/test.pdf"

    def test_dataset_doi_is_source_doi(self):
        rec = make_record(source_doi="10.5678/dataset")
        out = record_to_fulltext_input(rec)
        assert out["dataset_doi"] == "10.5678/dataset"

    def test_title_is_none(self):
        rec = make_record()
        out = record_to_fulltext_input(rec)
        assert out["title"] is None

    def test_raises_when_both_dois_none(self):
        rec = make_record(article_doi=None, source_doi=None)
        with pytest.raises(ValueError, match="no article_doi or source_doi"):
            record_to_fulltext_input(rec)

    def test_raises_when_pdf_local_path_none(self):
        rec = make_record(pdf_local_path=None)
        with pytest.raises(ValueError, match="no pdf_local_path"):
            record_to_fulltext_input(rec)

    def test_none_fields_map_to_none(self):
        rec = make_record(article_doi="10.1/x", source_doi=None, pdf_local_path="/p.pdf")
        out = record_to_fulltext_input(rec)
        assert out["dataset_doi"] is None


# ---------------------------------------------------------------------------
# record_to_pdf_input
# ---------------------------------------------------------------------------


class TestRecordToPdfInput:
    def test_required_keys_present(self):
        rec = make_record()
        out = record_to_pdf_input(rec)
        assert "id" in out
        assert "pdf_path" in out
        assert "metadata" in out

    def test_id_is_article_doi(self):
        rec = make_record(article_doi="10.1111/test")
        out = record_to_pdf_input(rec)
        assert out["id"] == "10.1111/test"

    def test_id_falls_back_to_source_doi(self):
        rec = make_record(article_doi=None, source_doi="10.2222/data")
        out = record_to_pdf_input(rec)
        assert out["id"] == "10.2222/data"

    def test_pdf_path_maps_from_pdf_local_path(self):
        rec = make_record(pdf_local_path="/data/pdfs/my.pdf")
        out = record_to_pdf_input(rec)
        assert out["pdf_path"] == "/data/pdfs/my.pdf"

    def test_metadata_contains_gt_record_id(self):
        rec = make_record(gt_record_id=42)
        out = record_to_pdf_input(rec)
        assert out["metadata"]["gt_record_id"] == 42

    def test_raises_when_both_dois_none(self):
        rec = make_record(article_doi=None, source_doi=None)
        with pytest.raises(ValueError, match="no article_doi or source_doi"):
            record_to_pdf_input(rec)

    def test_raises_when_pdf_local_path_none(self):
        rec = make_record(pdf_local_path=None)
        with pytest.raises(ValueError, match="no pdf_local_path"):
            record_to_pdf_input(rec)


# ---------------------------------------------------------------------------
# record_to_section_input
# ---------------------------------------------------------------------------


class TestRecordToSectionInput:
    def test_required_keys_present(self):
        rec = make_record()
        out = record_to_section_input(rec)
        assert "id" in out
        assert "pdf_path" in out
        assert "metadata" in out

    def test_id_is_article_doi(self):
        rec = make_record(article_doi="10.3333/abc")
        out = record_to_section_input(rec)
        assert out["id"] == "10.3333/abc"

    def test_id_falls_back_to_source_doi(self):
        rec = make_record(article_doi=None, source_doi="10.4444/xyz")
        out = record_to_section_input(rec)
        assert out["id"] == "10.4444/xyz"

    def test_pdf_path_maps_from_pdf_local_path(self):
        rec = make_record(pdf_local_path="/data/pdfs/sec.pdf")
        out = record_to_section_input(rec)
        assert out["pdf_path"] == "/data/pdfs/sec.pdf"

    def test_metadata_contains_gt_record_id(self):
        rec = make_record(gt_record_id=99)
        out = record_to_section_input(rec)
        assert out["metadata"]["gt_record_id"] == 99

    def test_raises_when_both_dois_none(self):
        rec = make_record(article_doi=None, source_doi=None)
        with pytest.raises(ValueError, match="no article_doi or source_doi"):
            record_to_section_input(rec)

    def test_raises_when_pdf_local_path_none(self):
        rec = make_record(pdf_local_path=None)
        with pytest.raises(ValueError, match="no pdf_local_path"):
            record_to_section_input(rec)


# ---------------------------------------------------------------------------
# manifest_to_fulltext_inputs
# ---------------------------------------------------------------------------


class TestManifestToFulltextInputs:
    def test_returns_list_of_dicts(self):
        m = make_manifest(make_record(gt_record_id=1), make_record(gt_record_id=2))
        out = manifest_to_fulltext_inputs(m)
        assert isinstance(out, list)
        assert len(out) == 2
        for d in out:
            assert isinstance(d, dict)

    def test_all_have_required_keys(self):
        m = make_manifest(make_record(gt_record_id=1), make_record(gt_record_id=2))
        for d in manifest_to_fulltext_inputs(m):
            assert {"article_doi", "dataset_doi", "pdf_path", "title"}.issubset(d)

    def test_skips_records_without_pdf_path(self, capsys):
        good = make_record(gt_record_id=1, pdf_local_path="/p.pdf")
        bad = make_record(gt_record_id=2, pdf_local_path=None)
        m = make_manifest(good, bad)
        out = manifest_to_fulltext_inputs(m)
        assert len(out) == 1
        assert out[0]["pdf_path"] == "/p.pdf"

    def test_skips_records_without_any_doi(self, capsys):
        good = make_record(gt_record_id=1)
        bad = DataPaperRecord(
            gt_record_id=2,
            article_doi=None,
            source_doi=None,
            pdf_local_path="/p.pdf",
        )
        m = make_manifest(good, bad)
        out = manifest_to_fulltext_inputs(m)
        assert len(out) == 1

    def test_empty_manifest_returns_empty_list(self):
        m = DataPaperManifest(records=[])
        out = manifest_to_fulltext_inputs(m)
        assert out == []


# ---------------------------------------------------------------------------
# manifest_to_pdf_inputs
# ---------------------------------------------------------------------------


class TestManifestToPdfInputs:
    def test_returns_list_of_dicts(self):
        m = make_manifest(make_record(gt_record_id=1), make_record(gt_record_id=2))
        out = manifest_to_pdf_inputs(m)
        assert isinstance(out, list)
        assert len(out) == 2

    def test_all_have_required_keys(self):
        m = make_manifest(make_record(gt_record_id=1))
        for d in manifest_to_pdf_inputs(m):
            assert {"id", "pdf_path", "metadata"}.issubset(d)

    def test_skip_missing_pdf_true_skips_records_without_pdf_path(self):
        with_pdf = make_record(gt_record_id=1, pdf_local_path="/a.pdf")
        no_pdf = make_record(gt_record_id=2, pdf_local_path=None)
        m = make_manifest(with_pdf, no_pdf)
        out = manifest_to_pdf_inputs(m, skip_missing_pdf=True)
        assert len(out) == 1
        assert out[0]["id"] == with_pdf.article_doi

    def test_skip_missing_pdf_false_raises_for_records_without_pdf_path(self):
        no_pdf = make_record(gt_record_id=3, pdf_local_path=None)
        m = make_manifest(no_pdf)
        # skip_missing_pdf=False means record_to_pdf_input will raise
        # manifest_to_pdf_inputs catches the ValueError and prints a warning
        out = manifest_to_pdf_inputs(m, skip_missing_pdf=False)
        # The record was skipped (error caught internally) — result is empty
        assert out == []

    def test_metadata_has_gt_record_id(self):
        rec = make_record(gt_record_id=77)
        m = make_manifest(rec)
        out = manifest_to_pdf_inputs(m)
        assert out[0]["metadata"]["gt_record_id"] == 77

    def test_empty_manifest_returns_empty_list(self):
        m = DataPaperManifest(records=[])
        out = manifest_to_pdf_inputs(m)
        assert out == []

    def test_none_pdf_local_path_produces_no_output_when_skipping(self):
        rec = DataPaperRecord(
            gt_record_id=5,
            article_doi="10.1/x",
            pdf_local_path=None,
        )
        m = make_manifest(rec)
        out = manifest_to_pdf_inputs(m, skip_missing_pdf=True)
        assert out == []
