"""Prompt-eval entrypoint built on the unified extraction engine."""

from __future__ import annotations

import ast
import contextlib
import json
import shlex
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from llm_metadata.groundtruth_eval import (
    DEFAULT_FIELD_STRATEGIES,
    EvaluationConfig,
    EvaluationReport,
    evaluate_indexed,
)
from llm_metadata.extraction import ExtractionConfig, ExtractionMode, run_manifest_extraction
from llm_metadata.schemas.data_paper import DataPaperManifest, RunArtifact
from llm_metadata.schemas.fuster_features import DatasetFeatures, DatasetFeaturesNormalized


_LIST_COLS = ["data_type", "geospatial_info_dataset", "species"]
_OUTPUT_DIR = Path("artifacts/runs")


def _parse_excel_val(val):
    if val is None:
        return None
    try:
        import pandas as pd  # type: ignore

        if isinstance(val, float) and pd.isna(val):
            return None
    except ImportError:
        pass
    if isinstance(val, list):
        return val
    if isinstance(val, str):
        stripped = val.strip()
        if stripped.startswith("["):
            try:
                return ast.literal_eval(stripped)
            except Exception:
                return val
    return val


def _load_ground_truth(gt_path: str) -> "pd.DataFrame":  # type: ignore[name-defined]
    try:
        import pandas as pd  # type: ignore
    except ImportError as exc:
        raise ImportError("pandas is required for prompt_eval; install with `pip install pandas openpyxl`.") from exc

    df = pd.read_excel(gt_path)
    for col in _LIST_COLS:
        if col in df.columns:
            df[col] = df[col].map(_parse_excel_val)
    return df


def _build_true_by_id(
    df: "pd.DataFrame",  # type: ignore[name-defined]
    allowed_ids: set[int],
) -> dict[str, DatasetFeaturesNormalized]:
    annotation_cols = [
        "data_type",
        "geospatial_info_dataset",
        "spatial_range_km2",
        "temporal_range",
        "temp_range_i",
        "temp_range_f",
        "species",
        "referred_dataset",
        "time_series",
        "multispecies",
        "threatened_species",
        "new_species_science",
        "new_species_region",
        "bias_north_south",
        "valid_yn",
        "reason_not_valid",
        "source",
        "source_url",
        "journal_url",
        "pdf_url",
        "is_oa",
        "cited_article_doi",
    ]
    available_cols = [col for col in annotation_cols if col in df.columns]
    true_by_id: dict[str, DatasetFeaturesNormalized] = {}
    for _, row in df.iterrows():
        record_id = int(row["id"])
        if record_id not in allowed_ids:
            continue
        row_dict = {col: row[col] for col in available_cols if col in row.index}
        true_by_id[str(record_id)] = DatasetFeaturesNormalized.model_validate(row_dict)
    return true_by_id


def _evaluation_payload(report: EvaluationReport) -> dict:
    return {
        "config": report.config.to_dict(),
        "field_metrics": {name: metrics.to_dict() for name, metrics in report.field_metrics.items()},
        "field_results": [result.to_dict() for result in report.field_results],
    }


def run_eval(
    *,
    mode: ExtractionMode | str,
    manifest_path: str,
    prompt_module: Optional[str] = None,
    config: Optional[EvaluationConfig] = None,
    config_path: Optional[str] = None,
    fields: Optional[list[str]] = None,
    model: str = "gpt-5-mini",
    gt_path: str = "data/dataset_092624_validated.xlsx",
    name: Optional[str] = None,
    output_path: Optional[str | Path] = None,
    skip_cache: bool = False,
) -> EvaluationReport:
    """Run extraction + evaluation for one explicit mode over one manifest."""

    manifest = DataPaperManifest.load_csv(manifest_path)
    eval_config = config or (
        EvaluationConfig.from_json(config_path)
        if config_path is not None
        else EvaluationConfig(field_strategies=DEFAULT_FIELD_STRATEGIES)
    )
    run_config = ExtractionConfig(model=model, text_format=DatasetFeatures)
    run_artifact = run_manifest_extraction(
        manifest,
        mode=mode,
        prompt_module=prompt_module,
        config=run_config,
        manifest_path=manifest_path,
        name=name,
        skip_cache=skip_cache,
    )

    gt_df = _load_ground_truth(gt_path)
    true_by_id = _build_true_by_id(gt_df, {record.gt_record_id for record in manifest.records})
    if not true_by_id:
        raise ValueError("No valid GT rows matched the manifest.")

    report = evaluate_indexed(
        true_by_id=true_by_id,
        pred_by_id=run_artifact.predictions_by_id(DatasetFeatures),
        fields=fields,
        config=eval_config,
    )
    report.total_cost_usd = run_artifact.total_cost_usd  # type: ignore[attr-defined]
    report.run_artifact = run_artifact  # type: ignore[attr-defined]

    run_artifact.evaluation = _evaluation_payload(report)
    if output_path is not None:
        run_artifact.save_json(output_path)
        report.saved_path = str(output_path)  # type: ignore[attr-defined]

    return report


def _print_metrics_table(report: EvaluationReport) -> None:
    header = f"{'Field':<25} {'N':>5}  {'P':>6}  {'R':>6}  {'F1':>6}"
    separator = "-" * len(header)
    print(header)
    print(separator)
    for field_name in sorted(report.field_metrics.keys()):
        metrics = report.field_metrics[field_name]
        precision = f"{metrics.precision:.3f}" if metrics.precision is not None else "  N/A"
        recall = f"{metrics.recall:.3f}" if metrics.recall is not None else "  N/A"
        f1 = f"{metrics.f1:.3f}" if metrics.f1 is not None else "  N/A"
        print(f"{field_name:<25} {metrics.n:>5}  {precision:>6}  {recall:>6}  {f1:>6}")
    total_cost = getattr(report, "total_cost_usd", None)
    if total_cost is not None:
        print(f"\nTotal API cost: ${total_cost:.4f}")


class _TeeStream:
    def __init__(self, *streams):
        self._streams = streams

    def write(self, data: str) -> int:
        for stream in self._streams:
            stream.write(data)
        return len(data)

    def flush(self) -> None:
        for stream in self._streams:
            stream.flush()


@contextlib.contextmanager
def _tee_console_to_log(log_path: Path):
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as log_file:
        out = _TeeStream(sys.__stdout__, log_file)
        err = _TeeStream(sys.__stderr__, log_file)
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            print(f"Logging to: {log_path}")
            yield


def _build_recreate_command(
    *,
    mode: ExtractionMode | str,
    manifest_path: str,
    prompt_module: Optional[str],
    config_path: Optional[str],
    fields: Optional[list[str]],
    output_path: Optional[Path],
    name: Optional[str],
    model: str,
    gt_path: str,
    skip_cache: bool,
) -> str:
    command = [
        "uv",
        "run",
        "python",
        "-m",
        "llm_metadata.prompt_eval",
        "--mode",
        str(ExtractionMode(mode).value),
        "--manifest",
        manifest_path,
        "--model",
        model,
        "--gt",
        gt_path,
    ]
    if prompt_module:
        command.extend(["--prompt", prompt_module])
    if config_path:
        command.extend(["--config", config_path])
    if fields:
        command.extend(["--fields", ",".join(fields)])
    if output_path is not None:
        command.extend(["--output", str(output_path)])
    elif name:
        command.extend(["--name", name])
    if skip_cache:
        command.append("--skip-cache")
    return " ".join(shlex.quote(part) for part in command)


def _resolve_output_path(name: Optional[str], output: Optional[str]) -> Path:
    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if output:
        path = Path(output)
        return _OUTPUT_DIR / f"{timestamp}_{path.name}" if path.parent == Path(".") else path
    if name:
        return _OUTPUT_DIR / f"{timestamp}_{name}.json"
    return _OUTPUT_DIR / f"{timestamp}_prompt_eval.json"


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Run extraction + evaluation over a manifest.")
    parser.add_argument("--mode", required=True, choices=[mode.value for mode in ExtractionMode])
    parser.add_argument("--manifest", required=True, help="Path to the canonical DataPaperManifest CSV.")
    parser.add_argument("--prompt", default=None, help="Prompt module path relative to llm_metadata.")
    parser.add_argument("--config", default=None, help="Path to an EvaluationConfig JSON file.")
    parser.add_argument("--fields", default=None, help="Comma-separated field names to evaluate.")
    parser.add_argument("--output", default=None, help="Path to save the run artifact JSON.")
    parser.add_argument("--name", default=None, help="Run name stem for auto-generated output paths.")
    parser.add_argument("--model", default="gpt-5-mini", help="OpenAI model name.")
    parser.add_argument("--gt", default="data/dataset_092624_validated.xlsx", help="Validated GT XLSX path.")
    parser.add_argument("--skip-cache", action="store_true", help="Bypass extraction cache.")
    args = parser.parse_args()

    fields = [field.strip() for field in args.fields.split(",")] if args.fields else None
    output_path = _resolve_output_path(args.name, args.output)
    log_path = output_path.with_suffix(".log")

    with _tee_console_to_log(log_path):
        recreate_cmd = _build_recreate_command(
            mode=args.mode,
            manifest_path=args.manifest,
            prompt_module=args.prompt,
            config_path=args.config,
            fields=fields,
            output_path=Path(args.output) if args.output else None,
            name=args.name if not args.output else None,
            model=args.model,
            gt_path=args.gt,
            skip_cache=args.skip_cache,
        )
        print(f"Recreate command: {recreate_cmd}")

        report = run_eval(
            mode=args.mode,
            manifest_path=args.manifest,
            prompt_module=args.prompt,
            config_path=args.config,
            fields=fields,
            model=args.model,
            gt_path=args.gt,
            name=args.name,
            output_path=output_path,
            skip_cache=args.skip_cache,
        )
        _print_metrics_table(report)
        print(f"\nRun artifact saved to: {output_path}")


if __name__ == "__main__":
    main()
