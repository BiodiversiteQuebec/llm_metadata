"""Tests for prompt_eval manifest-first PDF mode (WU-SR3).

These tests verify:
- When manifest_path is provided, pdf_local_path is used directly
- Records with pdf_local_path=None are skipped with a warning
- --manifest CLI flag is accepted and passed through
- Manifest metadata (article_doi, source_doi, pdf_local_path, is_oa) is
  included in the saved report records dict

No real API calls are made; classify_pdf_file is patched throughout.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Fixtures — GT XLSX and manifest CSV built in a tmp dir
# ---------------------------------------------------------------------------


@pytest.fixture
def tiny_gt_xlsx(tmp_path):
    """Create a minimal validated GT XLSX with 3 records."""
    pytest.importorskip("pandas")
    import pandas as pd

    data = {
        "id": [10, 20, 30],
        "source": ["dryad", "dryad", "zenodo"],
        "source_url": [
            "https://doi.org/10.5061/dryad.aaa",
            "https://doi.org/10.5061/dryad.bbb",
            "https://doi.org/10.5281/zenodo.111",
        ],
        "cited_article_doi": [
            "https://doi.org/10.1111/aaa.001",
            "https://doi.org/10.1111/bbb.002",
            "https://doi.org/10.1111/ccc.003",
        ],
        "is_oa": [1.0, 0.0, None],
        "pdf_url": [None, None, None],
        "journal_url": [None, None, None],
        "title": ["Paper A", "Paper B", "Paper C"],
        "abstract": ["Abstract 10", "Abstract 20", "Abstract 30"],
        # Annotation fields expected by DatasetFeaturesNormalized
        "data_type": [None, None, None],
        "geospatial_info_dataset": [None, None, None],
        "spatial_range_km2": [None, None, None],
        "temporal_range": [None, None, None],
        "temp_range_i": [None, None, None],
        "temp_range_f": [None, None, None],
        "species": [None, None, None],
        "referred_dataset": [None, None, None],
        "time_series": [None, None, None],
        "multispecies": [None, None, None],
        "threatened_species": [None, None, None],
        "new_species_science": [None, None, None],
        "new_species_region": [None, None, None],
        "bias_north_south": [None, None, None],
        "valid_yn": ["yes", "yes", "yes"],
        "reason_not_valid": [None, None, None],
    }
    path = tmp_path / "gt_validated.xlsx"
    pd.DataFrame(data).to_excel(str(path), index=False)
    return path


@pytest.fixture
def tiny_manifest_csv(tmp_path):
    """Manifest CSV with 3 records: id=10 has pdf, id=20 has no pdf, id=30 has pdf."""
    rows = [
        {
            "gt_record_id": 10,
            "source": "dryad",
            "source_doi": "10.5061/dryad.aaa",
            "source_url": "https://doi.org/10.5061/dryad.aaa",
            "article_doi": "10.1111/aaa.001",
            "article_url": "",
            "pdf_url": "https://example.com/a.pdf",
            "pdf_local_path": str(tmp_path / "paper_10.pdf"),
            "is_oa": "True",
            "openalex_id": "",
            "semantic_scholar_paper_id": "",
            "article_publisher": "",
        },
        {
            "gt_record_id": 20,
            "source": "dryad",
            "source_doi": "10.5061/dryad.bbb",
            "source_url": "https://doi.org/10.5061/dryad.bbb",
            "article_doi": "10.1111/bbb.002",
            "article_url": "",
            "pdf_url": "",
            "pdf_local_path": "",   # No PDF
            "is_oa": "False",
            "openalex_id": "",
            "semantic_scholar_paper_id": "",
            "article_publisher": "",
        },
        {
            "gt_record_id": 30,
            "source": "zenodo",
            "source_doi": "10.5281/zenodo.111",
            "source_url": "https://doi.org/10.5281/zenodo.111",
            "article_doi": "10.1111/ccc.003",
            "article_url": "",
            "pdf_url": "https://example.com/c.pdf",
            "pdf_local_path": str(tmp_path / "paper_30.pdf"),
            "is_oa": "",
            "openalex_id": "",
            "semantic_scholar_paper_id": "",
            "article_publisher": "",
        },
    ]
    path = tmp_path / "manifest.csv"
    fieldnames = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    # Create fake PDF files on disk so Path(...).exists() is True (optional for
    # these tests since we mock classify_pdf_file, but good for realism)
    (tmp_path / "paper_10.pdf").write_bytes(b"%PDF-1.4 fake")
    (tmp_path / "paper_30.pdf").write_bytes(b"%PDF-1.4 fake")

    return path


@pytest.fixture
def mock_extraction_result():
    """A minimal classify_pdf_file result dict."""
    from llm_metadata.schemas.fuster_features import DatasetFeatures

    features = DatasetFeatures()
    return {
        "output": features,
        "usage_cost": {"input_tokens": 10, "output_tokens": 5, "total_cost": 0.001},
        "extraction_method": "openai_file_api",
        "pdf_path": "fake.pdf",
        "file_id": "file-abc123",
    }


# ---------------------------------------------------------------------------
# Helper: patch target for classify_pdf_file inside prompt_eval
# ---------------------------------------------------------------------------

_PATCH_TARGET = "llm_metadata.gpt_classify.classify_pdf_file"
_PATCH_TARGET_ABSTRACT = "llm_metadata.gpt_classify.classify_abstract"


# ---------------------------------------------------------------------------
# Test: manifest mode uses pdf_local_path directly
# ---------------------------------------------------------------------------


class TestManifestPdfPathUsed:
    def test_pdf_local_path_used_from_manifest(
        self, tiny_gt_xlsx, tiny_manifest_csv, mock_extraction_result, tmp_path
    ):
        """When manifest_path is set, classify_pdf_file is called with
        pdf_local_path from the manifest, not a DOI-derived path."""
        pytest.importorskip("pandas")
        from llm_metadata.prompt_eval import run_eval

        calls: list[Path] = []

        def fake_classify(pdf_path, **kwargs):
            calls.append(Path(pdf_path))
            return mock_extraction_result

        with patch(_PATCH_TARGET, side_effect=fake_classify):
            report = run_eval(
                prompt_module="prompts.pdf_file",
                gt_path=str(tiny_gt_xlsx),
                manifest_path=str(tiny_manifest_csv),
            )

        # Only records 10 and 30 have pdf_local_path — record 20 is skipped
        assert len(calls) == 2
        called_names = {p.name for p in calls}
        assert "paper_10.pdf" in called_names
        assert "paper_30.pdf" in called_names

        # Report should have 2 records that succeeded extraction (extraction_success=True)
        records = getattr(report, "records", {})
        successful = [rid for rid, meta in records.items() if meta.get("extraction_success")]
        assert len(successful) == 2

    def test_records_with_no_pdf_skipped_with_warning(
        self, tiny_gt_xlsx, tiny_manifest_csv, mock_extraction_result, tmp_path, capsys
    ):
        """Records with pdf_local_path=None (or empty) must be skipped, with a warning."""
        pytest.importorskip("pandas")
        from llm_metadata.prompt_eval import run_eval

        def fake_classify(pdf_path, **kwargs):
            return mock_extraction_result

        with patch(_PATCH_TARGET, side_effect=fake_classify):
            run_eval(
                prompt_module="prompts.pdf_file",
                gt_path=str(tiny_gt_xlsx),
                manifest_path=str(tiny_manifest_csv),
            )

        captured = capsys.readouterr()
        # Warning about record 20 (no pdf_local_path)
        assert "id=20" in captured.err or "skipped" in captured.err.lower()

    def test_manifest_metadata_in_records_dict(
        self, tiny_gt_xlsx, tiny_manifest_csv, mock_extraction_result, tmp_path
    ):
        """Manifest-derived fields (article_doi, source_doi, pdf_local_path, is_oa)
        must appear in each record entry of the saved records dict."""
        pytest.importorskip("pandas")
        from llm_metadata.prompt_eval import run_eval

        def fake_classify(pdf_path, **kwargs):
            return mock_extraction_result

        with patch(_PATCH_TARGET, side_effect=fake_classify):
            report = run_eval(
                prompt_module="prompts.pdf_file",
                gt_path=str(tiny_gt_xlsx),
                manifest_path=str(tiny_manifest_csv),
            )

        records = getattr(report, "records", {})

        # Record 10 should have manifest metadata injected
        rec10 = records.get("10")
        assert rec10 is not None, "Record 10 missing from report.records"
        assert rec10.get("article_doi") == "10.1111/aaa.001"
        assert rec10.get("source_doi") == "10.5061/dryad.aaa"
        assert rec10.get("is_oa") is True
        assert rec10.get("pdf_local_path") is not None and "paper_10.pdf" in rec10["pdf_local_path"]

        # Record 30 — is_oa was empty string, should be None (falsy)
        rec30 = records.get("30")
        assert rec30 is not None, "Record 30 missing from report.records"
        assert rec30.get("article_doi") == "10.1111/ccc.003"

    def test_manifest_restricts_records_to_manifest_ids(
        self, tiny_gt_xlsx, tiny_manifest_csv, mock_extraction_result, tmp_path
    ):
        """With manifest_path, only records listed in the manifest are evaluated —
        even if gt_path has more records."""
        pytest.importorskip("pandas")
        from llm_metadata.prompt_eval import run_eval

        def fake_classify(pdf_path, **kwargs):
            return mock_extraction_result

        with patch(_PATCH_TARGET, side_effect=fake_classify):
            report = run_eval(
                prompt_module="prompts.pdf_file",
                gt_path=str(tiny_gt_xlsx),
                manifest_path=str(tiny_manifest_csv),
            )

        # Only 3 IDs in manifest; records dict must not contain any IDs outside them
        records = getattr(report, "records", {})
        assert set(records.keys()).issubset({"10", "20", "30"})


class TestManifestSubsetAbstractMode:
    def test_manifest_filters_ids_without_forcing_pdf_mode(
        self, tiny_gt_xlsx, tiny_manifest_csv, mock_extraction_result
    ):
        """With prompt=abstract + manifest, run_eval must use abstract extraction
        and still restrict records to manifest gt_record_id values."""
        pytest.importorskip("pandas")
        from llm_metadata.prompt_eval import run_eval

        abstract_calls: list[str] = []

        def fake_classify_abstract(abstract, **kwargs):
            abstract_calls.append(str(abstract))
            return mock_extraction_result

        with patch(_PATCH_TARGET_ABSTRACT, side_effect=fake_classify_abstract) as abstract_mock, \
             patch(_PATCH_TARGET) as pdf_mock:
            report = run_eval(
                prompt_module="prompts.abstract",
                gt_path=str(tiny_gt_xlsx),
                manifest_path=str(tiny_manifest_csv),
            )

        assert abstract_mock.call_count == 3
        assert pdf_mock.call_count == 0
        assert set(getattr(report, "records", {}).keys()) == {"10", "20", "30"}


# ---------------------------------------------------------------------------
# Test: _build_recreate_command includes --manifest
# ---------------------------------------------------------------------------


class TestBuildRecreateCommand:
    def test_manifest_in_recreate_command(self):
        """When manifest_path is set, --manifest must appear in the recreate command."""
        from llm_metadata.prompt_eval import _build_recreate_command

        cmd = _build_recreate_command(
            prompt_module="prompts.pdf_file",
            manifest_path="data/manifests/dev_subset_data_paper.csv",
            pdf_dir=None,
            config_path=None,
            fields=None,
            output_path=None,
            name=None,
            model="gpt-5-mini",
            gt_path="data/dataset_092624_validated.xlsx",
            skip_cache=False,
        )
        assert "--manifest" in cmd
        assert "dev_subset_data_paper.csv" in cmd

    def test_no_manifest_omitted_from_command(self):
        """When manifest_path is None, --manifest must not appear in the recreate command."""
        from llm_metadata.prompt_eval import _build_recreate_command

        cmd = _build_recreate_command(
            prompt_module="prompts.abstract",
            manifest_path=None,
            pdf_dir=None,
            config_path=None,
            fields=None,
            output_path=None,
            name=None,
            model="gpt-5-mini",
            gt_path="data/dataset_092624_validated.xlsx",
            skip_cache=False,
        )
        assert "--manifest" not in cmd
        assert "--prompt" in cmd


# ---------------------------------------------------------------------------
# Test: CLI --manifest flag is parsed and passed to run_eval
# ---------------------------------------------------------------------------


class TestCliManifestFlag:
    def test_cli_manifest_flag_accepted(self, tiny_gt_xlsx, tiny_manifest_csv, tmp_path):
        """The CLI must accept --manifest and pass it to run_eval."""
        pytest.importorskip("pandas")

        from llm_metadata.prompt_eval import main

        called_kwargs: dict = {}

        def fake_run_eval(**kwargs):
            called_kwargs.update(kwargs)
            # Return a minimal report-like object
            from llm_metadata.groundtruth_eval import EvaluationReport
            report = MagicMock(spec=EvaluationReport)
            report.field_metrics = {}
            report.total_cost_usd = 0.0
            report.records = {}
            report.system_message = "sys"
            report.manifest_path = kwargs.get("manifest_path")
            report.save = MagicMock()
            return report

        cli_args = [
            "prompt_eval",
            "--prompt", "prompts.pdf_file",
            "--gt", str(tiny_gt_xlsx),
            "--manifest", str(tiny_manifest_csv),
            "--model", "gpt-5-mini",
        ]

        with patch("sys.argv", cli_args), \
             patch("llm_metadata.prompt_eval.run_eval", side_effect=fake_run_eval), \
             patch("llm_metadata.prompt_eval._print_metrics_table"):
            try:
                main()
            except SystemExit:
                pass

        assert called_kwargs.get("manifest_path") == str(tiny_manifest_csv)

    def test_cli_pdf_dir_without_manifest(self, tiny_gt_xlsx, tmp_path):
        """The CLI --pdf-dir (without --manifest) must not set manifest_path."""
        pytest.importorskip("pandas")

        from llm_metadata.prompt_eval import main

        called_kwargs: dict = {}

        def fake_run_eval(**kwargs):
            called_kwargs.update(kwargs)
            from llm_metadata.groundtruth_eval import EvaluationReport
            report = MagicMock(spec=EvaluationReport)
            report.field_metrics = {}
            report.total_cost_usd = 0.0
            report.records = {}
            report.system_message = "sys"
            report.manifest_path = None
            report.save = MagicMock()
            return report

        cli_args = [
            "prompt_eval",
            "--prompt", "prompts.pdf_file",
            "--gt", str(tiny_gt_xlsx),
            "--pdf-dir", str(tmp_path / "pdfs"),
            "--model", "gpt-5-mini",
        ]

        with patch("sys.argv", cli_args), \
             patch("llm_metadata.prompt_eval.run_eval", side_effect=fake_run_eval), \
             patch("llm_metadata.prompt_eval._print_metrics_table"):
            try:
                main()
            except SystemExit:
                pass

        assert called_kwargs.get("manifest_path") is None
        assert called_kwargs.get("pdf_dir") == str(tmp_path / "pdfs")
