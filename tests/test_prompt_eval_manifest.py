"""Tests for prompt_eval on the manifest-first explicit-mode surface."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel

from llm_metadata.schemas.data_paper import DataPaperManifest


class TinyEvalExtraction(BaseModel):
    relevance: str
    notes: str | None = None


class TinyEvalGT(BaseModel):
    relevance: str
    human_relevance: str | None = None


@pytest.fixture
def tiny_gt_json(tmp_path):
    gt = [
        {"gt_record_id": 10},
        {"gt_record_id": 20},
        {"gt_record_id": 30},
    ]
    path = tmp_path / "gt.json"
    path.write_text(json.dumps(gt), encoding="utf-8")
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
    def test_pdf_native_uses_manifest_pdf_paths(self, tiny_gt_json, tiny_manifest_csv, mock_pdf_result):
        from llm_metadata.prompt_eval import run_eval

        calls: list[Path] = []

        def fake_extract(pdf_path, **kwargs):
            calls.append(Path(pdf_path))
            return mock_pdf_result

        manifest_records = DataPaperManifest.load_csv(str(tiny_manifest_csv)).records
        gt_data = json.loads(tiny_gt_json.read_text())

        with patch("llm_metadata.extraction.extract_from_pdf_file", side_effect=fake_extract):
            report = run_eval(
                mode="pdf_native",
                manifest=manifest_records,
                gt=gt_data,
            )

        assert {path.name for path in calls} == {"paper_10.pdf", "paper_30.pdf"}
        assert getattr(report, "total_cost_usd") == 0.002

    def test_abstract_mode_uses_manifest_abstracts(self, tiny_gt_json, tiny_manifest_csv, mock_text_result):
        from llm_metadata.prompt_eval import run_eval

        seen_texts: list[str] = []

        def fake_extract(text, **kwargs):
            seen_texts.append(text)
            return mock_text_result

        manifest_records = DataPaperManifest.load_csv(str(tiny_manifest_csv)).records
        gt_data = json.loads(tiny_gt_json.read_text())

        with patch("llm_metadata.extraction.extract_from_text", side_effect=fake_extract):
            report = run_eval(
                mode="abstract",
                manifest=manifest_records,
                gt=gt_data,
            )

        assert seen_texts == ["Abstract 10", "Abstract 20", "Abstract 30"]
        assert len(getattr(report, "run_artifact").records) == 3

    def test_run_eval_saves_run_artifact(self, tiny_gt_json, tiny_manifest_csv, mock_text_result, tmp_path):
        from llm_metadata.prompt_eval import run_eval
        from llm_metadata.schemas.data_paper import RunArtifact

        output_path = tmp_path / "run.json"
        manifest_records = DataPaperManifest.load_csv(str(tiny_manifest_csv)).records
        gt_data = json.loads(tiny_gt_json.read_text())

        with patch("llm_metadata.extraction.extract_from_text", return_value=mock_text_result):
            report = run_eval(
                mode="abstract",
                manifest=manifest_records,
                gt=gt_data,
                reasoning_effort="medium",
                description="Artifact persistence test",
                output_path=output_path,
            )

        assert output_path.exists()
        assert output_path.with_suffix(".csv").exists()
        loaded = RunArtifact.load_json(output_path)
        assert loaded.mode.value == "abstract"
        assert loaded.description == "Artifact persistence test"
        assert loaded.reasoning_effort == "medium"
        assert loaded.evaluation is not None
        assert getattr(report, "saved_path") == str(output_path)
        assert getattr(report, "extraction_csv_path") == str(output_path.with_suffix(".csv"))

    def test_run_eval_forwards_parallelism(self, tiny_gt_json, tiny_manifest_csv):
        from llm_metadata.prompt_eval import run_eval
        from llm_metadata.schemas.data_paper import RunArtifact

        captured: dict = {}

        def fake_run_manifest_extraction(manifest, **kwargs):
            captured.update(kwargs)
            return RunArtifact(
                name="demo",
                mode=kwargs["mode"],
                system_message="system",
                model="gpt-5-mini",
                records=[],
            )

        manifest_records = DataPaperManifest.load_csv(str(tiny_manifest_csv)).records
        gt_data = json.loads(tiny_gt_json.read_text())

        with patch("llm_metadata.prompt_eval.run_manifest_extraction", side_effect=fake_run_manifest_extraction):
            with patch("llm_metadata.prompt_eval.evaluate_indexed") as evaluate_indexed:
                report = MagicMock()
                report.field_metrics = {}
                evaluate_indexed.return_value = report
                run_eval(
                    mode="abstract",
                    manifest=manifest_records,
                    gt=gt_data,
                    parallelism=3,
                    reasoning_effort="medium",
                    description="Medium-effort run",
                )

        assert captured["parallelism"] == 3
        assert captured["description"] == "Medium-effort run"
        assert captured["config"].reasoning == {"effort": "medium"}

    def test_run_eval_accepts_custom_models(self, tiny_manifest_csv):
        from llm_metadata.prompt_eval import run_eval

        manifest_records = DataPaperManifest.load_csv(str(tiny_manifest_csv)).records
        gt_data = [
            {"gt_record_id": 10, "relevance": "H", "human_relevance": "M"},
            {"gt_record_id": 20, "relevance": "L", "human_relevance": "L"},
            {"gt_record_id": 30, "relevance": "M", "human_relevance": "M"},
        ]

        def fake_extract(text, **kwargs):
            mapping = {
                "Abstract 10": TinyEvalExtraction(relevance="H", notes="first"),
                "Abstract 20": TinyEvalExtraction(relevance="L", notes="second"),
                "Abstract 30": TinyEvalExtraction(relevance="M", notes="third"),
            }
            return {
                "output": mapping[text],
                "usage_cost": {"input_tokens": 10, "output_tokens": 5, "total_cost": 0.001},
            }

        with patch("llm_metadata.extraction.extract_from_text", side_effect=fake_extract):
            report = run_eval(
                mode="abstract",
                manifest=manifest_records,
                gt=gt_data,
                text_format=TinyEvalExtraction,
                gt_model=TinyEvalGT,
            )

        assert set(report.field_metrics.keys()) == {"relevance"}
        assert report.field_metrics["relevance"].f1 == pytest.approx(1.0)


class TestBuildRecreateCommand:
    def test_recreate_command_contains_mode_and_manifest(self):
        from llm_metadata.prompt_eval import _build_recreate_command

        cmd = _build_recreate_command(
            mode="pdf_native",
            parallelism=4,
            config_path=None,
            fields=None,
            output_path=None,
            name=None,
            model="gpt-5-mini",
            reasoning_effort="medium",
            description="Medium-effort rerun",
            skip_cache=False,
        )
        assert "--mode" in cmd
        assert "--parallelism 4" in cmd
        assert "--reasoning-effort medium" in cmd
        assert "--description 'Medium-effort rerun'" in cmd


class TestCliSurface:
    def test_cli_passes_mode_and_manifest(self, tiny_gt_json, tiny_manifest_csv):
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
            "--reasoning-effort",
            "medium",
            "--description",
            "Viewer smoke test",
            "--gt-manifest",
            str(tiny_gt_json),
        ]

        with patch("sys.argv", cli_args), patch("llm_metadata.prompt_eval.run_eval", side_effect=fake_run_eval), patch(
            "llm_metadata.prompt_eval._print_metrics_table"
        ):
            try:
                main()
            except SystemExit:
                pass

        assert called_kwargs["mode"] == "pdf_native"
        assert called_kwargs["manifest"] is not None
        assert called_kwargs["gt"] is not None
        assert called_kwargs["parallelism"] == 5
        assert called_kwargs["reasoning_effort"] == "medium"
        assert called_kwargs["description"] == "Viewer smoke test"
