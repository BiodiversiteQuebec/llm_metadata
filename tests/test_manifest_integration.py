"""WU-SR7 integration and regression tests for the manifest refactor.

These tests validate the acceptance criteria from plans/data-papers-manifest-refactor.md:
- Manifest-driven PDF eval resolves pdf_local_path without DOI name inference
- Duplicate GT IDs trigger validation error
- dev_subset manifest meets preflight criteria (30/30 coverage)
"""

from __future__ import annotations

import csv
import warnings
from pathlib import Path

import pytest

from llm_metadata.data_paper_manifest import (
    build_manifest,
    load_manifest_csv,
    save_manifest_csv,
)
from llm_metadata.schemas.data_paper import DataPaperManifest, DataPaperRecord
from llm_metadata.doi_utils import doi_equal, normalize_doi


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def gt_xlsx_with_dryad_zenodo(tmp_path):
    """GT XLSX with Dryad and Zenodo sources (mirrors real-world data mix)."""
    pytest.importorskip("pandas")
    import pandas as pd

    data = {
        "id": [1, 2, 3, 4],
        "source": ["dryad", "zenodo", "dryad", "zenodo"],
        "source_url": [
            "https://doi.org/10.5061/dryad.abc",
            "https://doi.org/10.5281/zenodo.12345",
            "https://doi.org/10.5061/dryad.xyz",
            None,  # no source URL
        ],
        "cited_article_doi": [
            "https://doi.org/10.1371/journal.pone.0001",
            "https://doi.org/10.1093/jhered/test123",
            "https://doi.org/10.1002/ece3.0001",
            "https://doi.org/10.1002/ece3.0002",
        ],
        "is_oa": [1.0, 1.0, 0.0, None],
        "pdf_url": [None, None, None, None],
        "journal_url": [None, None, None, None],
        "title": ["Dryad Paper 1", "Zenodo Paper 2", "Dryad Paper 3", "Zenodo Paper 4"],
    }
    path = tmp_path / "gt.xlsx"
    pd.DataFrame(data).to_excel(str(path), index=False)
    return path


@pytest.fixture
def pdf_manifest_with_paths(tmp_path):
    """PDF manifest where article_doi doesn't match the source_url naming."""
    rows = [
        {
            "article_doi": "https://doi.org/10.1371/journal.pone.0001",
            "record_id": 1,
            "source": "dryad",
            "title": "Dryad Paper 1",
            "is_oa": True,
            "pdf_url_xlsx": "https://journals.plos.org/file.pdf",
            "downloaded_pdf_path": "fuster/10.1371_journal.pone.0001.pdf",
            "status": "downloaded",
            "error": "",
        },
        {
            "article_doi": "https://doi.org/10.1093/jhered/test123",
            "record_id": 2,
            "source": "zenodo",
            "title": "Zenodo Paper 2",
            "is_oa": True,
            "pdf_url_xlsx": "https://academic.oup.com/file.pdf",
            "downloaded_pdf_path": "fuster/10.1093_jhered_test123.pdf",
            "status": "downloaded",
            "error": "",
        },
        # Records 3 and 4 have no downloaded PDF (source DOI mismatch scenario)
        {
            "article_doi": "https://doi.org/10.1002/ece3.0001",
            "record_id": 3,
            "source": "dryad",
            "title": "Dryad Paper 3",
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
# Integration: manifest builds correctly for mixed Dryad/Zenodo sources
# ---------------------------------------------------------------------------


class TestMixedSourceManifest:
    """Integration: manifest does NOT skip Dryad/Zenodo rows due to source DOI mismatch."""

    def test_dryad_record_gets_article_doi_not_source_doi(
        self, gt_xlsx_with_dryad_zenodo, pdf_manifest_with_paths, tmp_path
    ):
        """Dryad record 1: pdf_local_path resolved via article_doi, not source_url."""
        manifest = build_manifest(
            gt_path=gt_xlsx_with_dryad_zenodo,
            pdf_manifest_path=pdf_manifest_with_paths,
            pdf_dir=tmp_path,
            subset_ids={1},
        )
        r = manifest.by_id()[1]
        # source_doi comes from source_url (dryad DOI)
        assert r.source_doi == "10.5061/dryad.abc"
        # article_doi from cited_article_doi (what the PDF is filed under)
        assert r.article_doi == "10.1371/journal.pone.0001"
        # pdf_local_path resolved from PDF manifest (not from source_doi name)
        assert r.pdf_local_path is not None
        assert "10.1371_journal.pone.0001" in r.pdf_local_path

    def test_zenodo_record_gets_article_doi(
        self, gt_xlsx_with_dryad_zenodo, pdf_manifest_with_paths, tmp_path
    ):
        """Zenodo record 2: article_doi resolved from cited_article_doi."""
        manifest = build_manifest(
            gt_path=gt_xlsx_with_dryad_zenodo,
            pdf_manifest_path=pdf_manifest_with_paths,
            pdf_dir=tmp_path,
            subset_ids={2},
        )
        r = manifest.by_id()[2]
        assert r.source_doi == "10.5281/zenodo.12345"
        assert r.article_doi == "10.1093/jhered/test123"
        assert r.pdf_local_path is not None

    def test_record_with_no_source_url_handled(
        self, gt_xlsx_with_dryad_zenodo, pdf_manifest_with_paths, tmp_path
    ):
        """Record 4 has no source_url — source_doi should be None, no crash."""
        manifest = build_manifest(
            gt_path=gt_xlsx_with_dryad_zenodo,
            pdf_manifest_path=pdf_manifest_with_paths,
            pdf_dir=tmp_path,
            subset_ids={4},
        )
        r = manifest.by_id()[4]
        assert r.source_doi is None
        assert r.article_doi == "10.1002/ece3.0002"


# ---------------------------------------------------------------------------
# Regression: duplicate GT IDs
# ---------------------------------------------------------------------------


class TestDuplicateGtIdRejection:
    def test_duplicate_gt_id_raises_by_default(self, tmp_path, pdf_manifest_with_paths):
        pytest.importorskip("pandas")
        import pandas as pd

        data = {
            "id": [1, 1],
            "source": ["dryad", "dryad"],
            "source_url": ["https://doi.org/10.5061/a", "https://doi.org/10.5061/b"],
            "cited_article_doi": [None, None],
            "is_oa": [None, None],
            "pdf_url": [None, None],
            "journal_url": [None, None],
            "title": ["A", "A"],
        }
        bad_gt = tmp_path / "dup_gt.xlsx"
        pd.DataFrame(data).to_excel(str(bad_gt), index=False)

        with pytest.raises(ValueError, match="Duplicate id values found"):
            build_manifest(
                gt_path=bad_gt,
                pdf_manifest_path=pdf_manifest_with_paths,
                pdf_dir=tmp_path,
            )

    def test_duplicate_gt_id_ok_with_deduplicate_flag(self, tmp_path, pdf_manifest_with_paths):
        pytest.importorskip("pandas")
        import pandas as pd

        data = {
            "id": [1, 1],
            "source": ["dryad", "dryad"],
            "source_url": ["https://doi.org/10.5061/a", "https://doi.org/10.5061/a"],
            "cited_article_doi": [None, None],
            "is_oa": [None, None],
            "pdf_url": [None, None],
            "journal_url": [None, None],
            "title": ["A", "A"],
        }
        dup_gt = tmp_path / "dup_gt.xlsx"
        pd.DataFrame(data).to_excel(str(dup_gt), index=False)

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            manifest = build_manifest(
                gt_path=dup_gt,
                pdf_manifest_path=pdf_manifest_with_paths,
                pdf_dir=tmp_path,
                deduplicate_gt=True,
            )
        assert len(manifest) == 1
        assert any("Duplicate id" in str(warning.message) for warning in w)


# ---------------------------------------------------------------------------
# Acceptance: dev_subset manifest preflight (30/30 coverage)
# ---------------------------------------------------------------------------


class TestDevSubsetManifestPreflight:
    """WU-SR7 acceptance gate: the generated dev subset manifest must pass preflight."""

    DEV_SUBSET_MANIFEST = Path("data/manifests/dev_subset_data_paper.csv")

    def test_manifest_file_exists(self):
        assert self.DEV_SUBSET_MANIFEST.exists(), (
            f"dev_subset manifest not found at {self.DEV_SUBSET_MANIFEST}. "
            "Run: uv run python -m llm_metadata.data_paper_manifest "
            "--subset-ids 9,19,27 --output data/manifests/dev_subset_data_paper.csv"
        )

    def test_row_count_equals_30(self):
        if not self.DEV_SUBSET_MANIFEST.exists():
            pytest.skip("manifest not generated yet")
        m = load_manifest_csv(self.DEV_SUBSET_MANIFEST)
        assert len(m) == 30, f"Expected 30 records, got {len(m)}"

    def test_unique_gt_record_ids(self):
        if not self.DEV_SUBSET_MANIFEST.exists():
            pytest.skip("manifest not generated yet")
        m = load_manifest_csv(self.DEV_SUBSET_MANIFEST)
        assert len(m.by_id()) == 30

    def test_all_records_have_pdf_local_path(self):
        if not self.DEV_SUBSET_MANIFEST.exists():
            pytest.skip("manifest not generated yet")
        m = load_manifest_csv(self.DEV_SUBSET_MANIFEST)
        cov = m.validate_pdf_coverage()
        assert cov["with_pdf_local_path"] == 30, (
            f"Not all records have pdf_local_path: missing {cov['no_pdf_path']}"
        )

    def test_all_pdfs_exist_on_disk(self):
        if not self.DEV_SUBSET_MANIFEST.exists():
            pytest.skip("manifest not generated yet")
        m = load_manifest_csv(self.DEV_SUBSET_MANIFEST)
        cov = m.validate_pdf_coverage()
        assert cov["pdf_on_disk"] == 30, (
            f"PDFs missing from disk: {cov['missing_from_disk']}"
        )

    def test_all_records_have_article_doi(self):
        """Every dev subset record should have a resolvable article_doi for PDF eval."""
        if not self.DEV_SUBSET_MANIFEST.exists():
            pytest.skip("manifest not generated yet")
        m = load_manifest_csv(self.DEV_SUBSET_MANIFEST)
        missing_doi = [r.gt_record_id for r in m if not r.article_doi and not r.source_doi]
        assert not missing_doi, f"Records with no DOI: {missing_doi}"


# ---------------------------------------------------------------------------
# DOI normalization centralization
# ---------------------------------------------------------------------------


class TestDoiNormalizationCentralization:
    """Verify DOI normalization behavior is consistent across the system."""

    def test_normalize_strips_prefix(self):
        assert normalize_doi("https://doi.org/10.1371/test") == "10.1371/test"

    def test_normalize_lowercases(self):
        assert normalize_doi("10.1371/TEST") == "10.1371/test"

    def test_doi_equal_cross_format(self):
        assert doi_equal("https://doi.org/10.1371/test", "10.1371/TEST")

    def test_manifest_stores_normalized_dois(self):
        """DataPaperRecord normalizes DOIs on construction."""
        rec = DataPaperRecord(
            gt_record_id=9,
            source_doi="https://doi.org/10.1371/JOURNAL",
            article_doi="HTTP://DOI.ORG/10.1002/ECE3.1476",
        )
        assert rec.source_doi == "10.1371/journal"
        assert rec.article_doi == "10.1002/ece3.1476"
