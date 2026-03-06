"""Tests for prompt_eval on the manifest-first explicit-mode surface."""

from __future__ import annotations

import csv
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def tiny_gt_xlsx(tmp_path):
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
    rows = [
        {
            "gt_record_id": 10,
            "source": "dryad",
            "title": "Paper A",
            "abstract": "Abstract 10",
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
            "title": "Paper B",
            "abstract": "Abstract 20",
            "source_doi": "10.5061/dryad.bbb",
            "source_url": "https://doi.org/10.5061/dryad.bbb",
            "article_doi": "10.1111/bbb.002",
            "article_url": "",
            "pdf_url": "",
            "pdf_local_path": "",
            "is_oa": "False",
            "openalex_id": "",
            "semantic_scholar_paper_id": "",
            "article_publisher": "",
        },
        {
            "gt_record_id": 30,
            "source": "zenodo",
            "title": "Paper C",
            "abstract": "Abstract 30",
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
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    (tmp_path / "paper_10.pdf").write_bytes(b"%PDF-1.4 fake")
    (tmp_path / "paper_30.pdf").write_bytes(b"%PDF-1.4 fake")
    return path


@pytest.fixture
def mock_pdf_result():
    from llm_metadata.schemas.fuster_features import DatasetFeatures

    return {
        "output": DatasetFeatures(),
        "usage_cost": {"input_tokens": 10, "output_tokens": 5, "total_cost": 0.001},
        "extraction_method": "pdf_native",
        "pdf_path": "fake.pdf",
        "file_id": "file-abc123",
    }


@pytest.fixture
def mock_text_result():
    from llm_metadata.schemas.fuster_features import DatasetFeatures

    return {
        "output": DatasetFeatures(),
        "usage_cost": {"input_tokens": 10, "output_tokens": 5, "total_cost": 0.001},
    }


class TestPromptEvalModes:
    def test_pdf_native_uses_manifest_pdf_paths(self, tiny_gt_xlsx, tiny_manifest_csv, mock_pdf_result):
        from llm_metadata.prompt_eval import run_eval

        calls: list[Path] = []

        def fake_extract(pdf_path, **kwargs):
            calls.append(Path(pdf_path))
            return mock_pdf_result

        with patch("llm_metadata.extraction.extract_from_pdf_file", side_effect=fake_extract):
            report = run_eval(
                mode="pdf_native",
                manifest_path=str(tiny_manifest_csv),
                gt_path=str(tiny_gt_xlsx),
            )

        assert {path.name for path in calls} == {"paper_10.pdf", "paper_30.pdf"}
        assert getattr(report, "total_cost_usd") == 0.002

    def test_abstract_mode_uses_manifest_abstracts(self, tiny_gt_xlsx, tiny_manifest_csv, mock_text_result):
        from llm_metadata.prompt_eval import run_eval

        seen_texts: list[str] = []

        def fake_extract(text, **kwargs):
            seen_texts.append(text)
            return mock_text_result

        with patch("llm_metadata.extraction.extract_from_text", side_effect=fake_extract):
            report = run_eval(
                mode="abstract",
                manifest_path=str(tiny_manifest_csv),
                gt_path=str(tiny_gt_xlsx),
            )

        assert seen_texts == ["Abstract 10", "Abstract 20", "Abstract 30"]
        assert len(getattr(report, "run_artifact").records) == 3

    def test_run_eval_saves_run_artifact(self, tiny_gt_xlsx, tiny_manifest_csv, mock_text_result, tmp_path):
        from llm_metadata.prompt_eval import run_eval
        from llm_metadata.schemas.data_paper import RunArtifact

        output_path = tmp_path / "run.json"
        with patch("llm_metadata.extraction.extract_from_text", return_value=mock_text_result):
            report = run_eval(
                mode="abstract",
                manifest_path=str(tiny_manifest_csv),
                gt_path=str(tiny_gt_xlsx),
                output_path=output_path,
            )

        assert output_path.exists()
        assert output_path.with_suffix(".csv").exists()
        loaded = RunArtifact.load_json(output_path)
        assert loaded.mode.value == "abstract"
        assert loaded.evaluation is not None
        assert getattr(report, "saved_path") == str(output_path)
        assert getattr(report, "extraction_csv_path") == str(output_path.with_suffix(".csv"))

    def test_run_eval_forwards_parallelism(self, tiny_gt_xlsx, tiny_manifest_csv):
        from llm_metadata.prompt_eval import run_eval
        from llm_metadata.schemas.data_paper import RunArtifact

        captured: dict = {}

        def fake_run_manifest_extraction(manifest, **kwargs):
            captured.update(kwargs)
            return RunArtifact(
                name="demo",
                mode=kwargs["mode"],
                manifest_path=kwargs.get("manifest_path"),
                prompt_module="prompts.abstract",
                system_message="system",
                model="gpt-5-mini",
                records=[],
            )

        with patch("llm_metadata.prompt_eval.run_manifest_extraction", side_effect=fake_run_manifest_extraction):
            with patch("llm_metadata.prompt_eval.evaluate_indexed") as evaluate_indexed:
                report = MagicMock()
                report.field_metrics = {}
                evaluate_indexed.return_value = report
                run_eval(
                    mode="abstract",
                    manifest_path=str(tiny_manifest_csv),
                    gt_path=str(tiny_gt_xlsx),
                    parallelism=3,
                )

        assert captured["parallelism"] == 3


class TestBuildRecreateCommand:
    def test_recreate_command_contains_mode_and_manifest(self):
        from llm_metadata.prompt_eval import _build_recreate_command

        cmd = _build_recreate_command(
            mode="pdf_native",
            manifest_path="data/manifests/dev_subset_data_paper.csv",
            parallelism=4,
            prompt_module=None,
            config_path=None,
            fields=None,
            output_path=None,
            name=None,
            model="gpt-5-mini",
            gt_path="data/dataset_092624_validated.xlsx",
            skip_cache=False,
        )
        assert "--mode" in cmd
        assert "--manifest" in cmd
        assert "--parallelism 4" in cmd


class TestCliSurface:
    def test_cli_passes_mode_and_manifest(self, tiny_gt_xlsx, tiny_manifest_csv):
        from llm_metadata.prompt_eval import main

        called_kwargs: dict = {}

        def fake_run_eval(**kwargs):
            called_kwargs.update(kwargs)
            report = MagicMock()
            report.field_metrics = {}
            report.total_cost_usd = 0.0
            report.run_artifact = MagicMock()
            return report

        cli_args = [
            "prompt_eval",
            "--mode",
            "pdf_native",
            "--manifest",
            str(tiny_manifest_csv),
            "--parallelism",
            "5",
            "--gt",
            str(tiny_gt_xlsx),
        ]

        with patch("sys.argv", cli_args), patch("llm_metadata.prompt_eval.run_eval", side_effect=fake_run_eval), patch(
            "llm_metadata.prompt_eval._print_metrics_table"
        ):
            try:
                main()
            except SystemExit:
                pass

        assert called_kwargs["mode"] == "pdf_native"
        assert called_kwargs["manifest_path"] == str(tiny_manifest_csv)
        assert called_kwargs["parallelism"] == 5
