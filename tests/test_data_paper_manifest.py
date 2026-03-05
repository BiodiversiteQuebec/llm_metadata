"""Tests for DataPaperManifest construction and CSV persistence."""

import csv

import pytest

from llm_metadata.schemas.data_paper import (
    DataPaperManifest,
    DataPaperRecord,
    _resolve_pdf_path,
)


@pytest.fixture
def minimal_gt_xlsx(tmp_path):
    pytest.importorskip("pandas")
    import pandas as pd

    data = {
        "id": [1, 2, 3],
        "source": ["dryad", "zenodo", "dryad"],
        "source_url": [
            "https://doi.org/10.5061/dryad.abc",
            "https://doi.org/10.5061/dryad.xyz",
            "https://doi.org/10.5061/dryad.def",
        ],
        "cited_article_doi": [
            "https://doi.org/10.1371/journal.pone.0001",
            "https://doi.org/10.1371/journal.pone.0002",
            None,
        ],
        "is_oa": [1.0, 0.0, None],
        "pdf_url": [None, None, None],
        "journal_url": [None, None, None],
        "title": ["Paper 1", "Paper 2", "Paper 3"],
    }
    path = tmp_path / "gt.xlsx"
    pd.DataFrame(data).to_excel(str(path), index=False)
    return path


@pytest.fixture
def minimal_raw_xlsx(tmp_path):
    pytest.importorskip("pandas")
    import pandas as pd

    data = {"id": [1, 2, 3], "full_text": ["Abstract 1", "Abstract 2", "Abstract 3"]}
    path = tmp_path / "raw.xlsx"
    pd.DataFrame(data).to_excel(str(path), index=False)
    return path


@pytest.fixture
def minimal_pdf_manifest(tmp_path):
    rows = [
        {
            "article_doi": "https://doi.org/10.1371/journal.pone.0001",
            "record_id": 1,
            "source": "dryad",
            "title": "Paper 1",
            "is_oa": True,
            "pdf_url_xlsx": "https://example.com/paper1.pdf",
            "downloaded_pdf_path": "fuster/10.1371_journal.pone.0001.pdf",
            "status": "downloaded",
            "error": "",
        },
        {
            "article_doi": "https://doi.org/10.1371/journal.pone.0002",
            "record_id": 2,
            "source": "zenodo",
            "title": "Paper 2",
            "is_oa": False,
            "pdf_url_xlsx": "",
            "downloaded_pdf_path": "",
            "status": "failed",
            "error": "All download strategies failed",
        },
    ]
    path = tmp_path / "manifest.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return path


class TestResolvePdfPath:
    def test_normalizes_separators(self, tmp_path):
        assert _resolve_pdf_path("fuster\\test.pdf", tmp_path) == str(tmp_path / "fuster" / "test.pdf")
        assert _resolve_pdf_path("fuster/test.pdf", tmp_path) == str(tmp_path / "fuster" / "test.pdf")

    def test_empty_returns_none(self, tmp_path):
        assert _resolve_pdf_path("", tmp_path) is None
        assert _resolve_pdf_path("nan", tmp_path) is None


class TestBuildManifest:
    def test_builds_from_gt_pdf_manifest_and_raw(
        self, minimal_gt_xlsx, minimal_raw_xlsx, minimal_pdf_manifest, tmp_path
    ):
        manifest = DataPaperManifest.build(
            gt_path=minimal_gt_xlsx,
            raw_path=minimal_raw_xlsx,
            pdf_manifest_path=minimal_pdf_manifest,
            pdf_dir=tmp_path,
        )
        assert len(manifest) == 3
        by_id = manifest.by_id()
        assert by_id[1].abstract == "Abstract 1"
        assert by_id[1].article_doi == "10.1371/journal.pone.0001"
        assert by_id[1].pdf_local_path is not None
        assert by_id[2].pdf_local_path is None
        assert by_id[3].article_doi is None

    def test_subset_filter(self, minimal_gt_xlsx, minimal_raw_xlsx, minimal_pdf_manifest, tmp_path):
        manifest = DataPaperManifest.build(
            gt_path=minimal_gt_xlsx,
            raw_path=minimal_raw_xlsx,
            pdf_manifest_path=minimal_pdf_manifest,
            pdf_dir=tmp_path,
            subset_ids={1, 2},
        )
        assert len(manifest.records) == 2

    def test_duplicate_gt_ids_raise(self, minimal_pdf_manifest, minimal_raw_xlsx, tmp_path):
        pytest.importorskip("pandas")
        import pandas as pd

        bad_gt = tmp_path / "bad_gt.xlsx"
        pd.DataFrame(
            {
                "id": [1, 1],
                "source": ["dryad", "dryad"],
                "source_url": ["https://doi.org/10.5061/a", "https://doi.org/10.5061/b"],
                "cited_article_doi": [None, None],
                "is_oa": [None, None],
                "pdf_url": [None, None],
                "journal_url": [None, None],
                "title": ["A", "B"],
            }
        ).to_excel(str(bad_gt), index=False)

        with pytest.raises(ValueError, match="Duplicate id values found"):
            DataPaperManifest.build(
                gt_path=bad_gt,
                raw_path=minimal_raw_xlsx,
                pdf_manifest_path=minimal_pdf_manifest,
                pdf_dir=tmp_path,
            )


class TestManifestCsvRoundTrip:
    def test_roundtrip(self, tmp_path):
        manifest = DataPaperManifest(
            records=[
                DataPaperRecord(
                    gt_record_id=9,
                    source="dryad",
                    source_doi="10.5061/dryad.qn1cj",
                    article_doi="10.1371/journal.pone.0128238",
                    pdf_local_path="/some/path.pdf",
                    is_oa=True,
                ),
                DataPaperRecord(gt_record_id=19, article_doi="10.1093/jhered/esw073"),
            ]
        )

        csv_path = tmp_path / "nested" / "manifest.csv"
        manifest.save_csv(csv_path)
        loaded = DataPaperManifest.load_csv(csv_path)
        assert loaded.by_id()[9].article_doi == "10.1371/journal.pone.0128238"
        assert loaded.by_id()[19].article_doi == "10.1093/jhered/esw073"
