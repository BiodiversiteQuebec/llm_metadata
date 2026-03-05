"""Integration tests for manifest-first extraction inputs."""

from __future__ import annotations

import csv
import warnings

import pytest

from llm_metadata.doi_utils import normalize_doi
from llm_metadata.schemas.data_paper import DataPaperManifest, DataPaperRecord


@pytest.fixture
def gt_xlsx_with_dryad_zenodo(tmp_path):
    pytest.importorskip("pandas")
    import pandas as pd

    path = tmp_path / "gt.xlsx"
    pd.DataFrame(
        {
            "id": [1, 2, 3, 4],
            "source": ["dryad", "zenodo", "dryad", "zenodo"],
            "source_url": [
                "https://doi.org/10.5061/dryad.abc",
                "https://doi.org/10.5281/zenodo.12345",
                "https://doi.org/10.5061/dryad.xyz",
                None,
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
    ).to_excel(str(path), index=False)
    return path


@pytest.fixture
def raw_xlsx(tmp_path):
    pytest.importorskip("pandas")
    import pandas as pd

    path = tmp_path / "raw.xlsx"
    pd.DataFrame(
        {
            "id": [1, 2, 3, 4],
            "full_text": ["Abstract 1", "Abstract 2", "Abstract 3", "Abstract 4"],
        }
    ).to_excel(str(path), index=False)
    return path


@pytest.fixture
def pdf_manifest_with_paths(tmp_path):
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
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return path


class TestMixedSourceManifest:
    def test_record_fields_resolve_from_gt_and_pdf_manifest(
        self, gt_xlsx_with_dryad_zenodo, raw_xlsx, pdf_manifest_with_paths, tmp_path
    ):
        manifest = DataPaperManifest.build(
            gt_path=gt_xlsx_with_dryad_zenodo,
            raw_path=raw_xlsx,
            pdf_manifest_path=pdf_manifest_with_paths,
            pdf_dir=tmp_path,
            subset_ids={1, 2, 4},
        )
        by_id = manifest.by_id()
        assert by_id[1].source_doi == "10.5061/dryad.abc"
        assert by_id[1].article_doi == "10.1371/journal.pone.0001"
        assert "10.1371_journal.pone.0001" in by_id[1].pdf_local_path
        assert by_id[2].source_doi == "10.5281/zenodo.12345"
        assert by_id[4].source_doi is None
        assert by_id[1].abstract == "Abstract 1"

    def test_duplicate_gt_id_ok_with_deduplicate_flag(self, pdf_manifest_with_paths, raw_xlsx, tmp_path):
        pytest.importorskip("pandas")
        import pandas as pd

        dup_gt = tmp_path / "dup_gt.xlsx"
        pd.DataFrame(
            {
                "id": [1, 1],
                "source": ["dryad", "dryad"],
                "source_url": ["https://doi.org/10.5061/a", "https://doi.org/10.5061/a"],
                "cited_article_doi": [None, None],
                "is_oa": [None, None],
                "pdf_url": [None, None],
                "journal_url": [None, None],
                "title": ["A", "A"],
            }
        ).to_excel(str(dup_gt), index=False)

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            manifest = DataPaperManifest.build(
                gt_path=dup_gt,
                raw_path=raw_xlsx,
                pdf_manifest_path=pdf_manifest_with_paths,
                pdf_dir=tmp_path,
                deduplicate_gt=True,
            )
        assert len(manifest.records) == 1
        assert any("Duplicate id values" in str(w.message) for w in caught)


class TestDevSubsetManifest:
    DEV_SUBSET_MANIFEST = "data/manifests/dev_subset_data_paper.csv"

    def test_dev_subset_manifest_loads(self):
        manifest = DataPaperManifest.load_csv(self.DEV_SUBSET_MANIFEST)
        assert len(manifest.records) > 0

    def test_dev_subset_manifest_has_unique_ids(self):
        manifest = DataPaperManifest.load_csv(self.DEV_SUBSET_MANIFEST)
        ids = [record.gt_record_id for record in manifest.records]
        assert len(ids) == len(set(ids))

    def test_doi_normalization_on_record_construction(self):
        record = DataPaperRecord(
            gt_record_id=1,
            source_doi="https://doi.org/10.5061/DRYAD.ABC",
            article_doi="https://doi.org/10.1371/JOURNAL.PONE.0001",
        )
        assert record.source_doi == normalize_doi("10.5061/dryad.abc")
        assert record.article_doi == normalize_doi("10.1371/journal.pone.0001")
