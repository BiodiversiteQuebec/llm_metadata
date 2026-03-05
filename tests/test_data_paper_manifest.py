"""Tests for llm_metadata.data_paper_manifest."""

import csv
import io
from pathlib import Path

import pytest

from llm_metadata.data_paper_manifest import (
    build_manifest,
    save_manifest_csv,
    load_manifest_csv,
    _resolve_pdf_path,
)
from llm_metadata.schemas.data_paper import DataPaperManifest, DataPaperRecord


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def minimal_gt_xlsx(tmp_path):
    """Create a minimal GT XLSX with 3 records."""
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
def minimal_pdf_manifest(tmp_path):
    """Create a minimal PDF manifest CSV."""
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
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestResolvePdfPath:
    def test_backslash_path(self, tmp_path):
        result = _resolve_pdf_path("fuster\\test.pdf", tmp_path)
        assert result == str(tmp_path / "fuster" / "test.pdf")

    def test_forward_slash_path(self, tmp_path):
        result = _resolve_pdf_path("fuster/test.pdf", tmp_path)
        assert result == str(tmp_path / "fuster" / "test.pdf")

    def test_empty_returns_none(self, tmp_path):
        assert _resolve_pdf_path("", tmp_path) is None
        assert _resolve_pdf_path("nan", tmp_path) is None


class TestBuildManifest:
    def test_full_join(self, minimal_gt_xlsx, minimal_pdf_manifest, tmp_path):
        pytest.importorskip("pandas")
        manifest = build_manifest(
            gt_path=minimal_gt_xlsx,
            pdf_manifest_path=minimal_pdf_manifest,
            pdf_dir=tmp_path,
        )
        assert len(manifest) == 3
        by_id = manifest.by_id()

        # Record 1: has article_doi and pdf_local_path
        r1 = by_id[1]
        assert r1.article_doi == "10.1371/journal.pone.0001"
        assert r1.source_doi == "10.5061/dryad.abc"
        assert r1.pdf_local_path is not None
        assert "10.1371_journal.pone.0001.pdf" in r1.pdf_local_path

        # Record 2: no PDF downloaded
        r2 = by_id[2]
        assert r2.article_doi == "10.1371/journal.pone.0002"
        assert r2.pdf_local_path is None

        # Record 3: no article_doi in GT, no PDF
        r3 = by_id[3]
        assert r3.article_doi is None

    def test_subset_filter(self, minimal_gt_xlsx, minimal_pdf_manifest, tmp_path):
        pytest.importorskip("pandas")
        manifest = build_manifest(
            gt_path=minimal_gt_xlsx,
            pdf_manifest_path=minimal_pdf_manifest,
            pdf_dir=tmp_path,
            subset_ids={1, 2},
        )
        assert len(manifest) == 2
        assert all(r.gt_record_id in {1, 2} for r in manifest)

    def test_subset_path(self, minimal_gt_xlsx, minimal_pdf_manifest, tmp_path):
        pytest.importorskip("pandas")
        import pandas as pd

        subset_csv = tmp_path / "subset.csv"
        pd.DataFrame({"id": [1, 3], "notes": ["", ""]}).to_csv(str(subset_csv), index=False)

        manifest = build_manifest(
            gt_path=minimal_gt_xlsx,
            pdf_manifest_path=minimal_pdf_manifest,
            pdf_dir=tmp_path,
            subset_path=subset_csv,
        )
        assert len(manifest) == 2
        assert {r.gt_record_id for r in manifest} == {1, 3}

    def test_invalid_subset_raises(self, minimal_gt_xlsx, minimal_pdf_manifest, tmp_path):
        pytest.importorskip("pandas")
        with pytest.raises(ValueError, match="not found in GT XLSX"):
            build_manifest(
                gt_path=minimal_gt_xlsx,
                pdf_manifest_path=minimal_pdf_manifest,
                pdf_dir=tmp_path,
                subset_ids={999},
            )

    def test_duplicate_gt_ids_raise(self, minimal_pdf_manifest, tmp_path):
        pytest.importorskip("pandas")
        import pandas as pd

        data = {
            "id": [1, 1],  # duplicate!
            "source": ["dryad", "dryad"],
            "source_url": ["https://doi.org/10.5061/a", "https://doi.org/10.5061/b"],
            "cited_article_doi": [None, None],
            "is_oa": [None, None],
            "pdf_url": [None, None],
            "journal_url": [None, None],
            "title": ["A", "B"],
        }
        bad_gt = tmp_path / "bad_gt.xlsx"
        pd.DataFrame(data).to_excel(str(bad_gt), index=False)

        with pytest.raises(ValueError, match="Duplicate id"):
            build_manifest(
                gt_path=bad_gt,
                pdf_manifest_path=minimal_pdf_manifest,
                pdf_dir=tmp_path,
            )


class TestSaveAndLoadManifestCsv:
    def test_roundtrip(self, tmp_path):
        records = [
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
        manifest = DataPaperManifest(records=records)

        csv_path = tmp_path / "test_manifest.csv"
        save_manifest_csv(manifest, csv_path)
        assert csv_path.exists()

        loaded = load_manifest_csv(csv_path)
        assert len(loaded) == 2
        by_id = loaded.by_id()

        assert by_id[9].source_doi == "10.5061/dryad.qn1cj"
        assert by_id[9].article_doi == "10.1371/journal.pone.0128238"
        assert by_id[9].pdf_local_path == "/some/path.pdf"
        assert by_id[9].is_oa is True
        assert by_id[19].article_doi == "10.1093/jhered/esw073"

    def test_creates_parent_dirs(self, tmp_path):
        records = [DataPaperRecord(gt_record_id=1)]
        manifest = DataPaperManifest(records=records)
        out = tmp_path / "nested" / "dir" / "manifest.csv"
        save_manifest_csv(manifest, out)
        assert out.exists()

    def test_load_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_manifest_csv(tmp_path / "nonexistent.csv")
