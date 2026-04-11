"""Prompt-eval entrypoint built on the unified extraction engine."""

from __future__ import annotations

import contextlib
import json
import os
import shlex
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from pydantic import BaseModel

from llm_metadata.groundtruth_eval import (
    DEFAULT_FIELD_STRATEGIES,
    EvaluationConfig,
    EvaluationReport,
    FieldEvalStrategy,
    evaluate_indexed,
)
from llm_metadata.extraction import ExtractionConfig, ExtractionMode, run_manifest_extraction
from llm_metadata.logging_utils import configure_extraction_logging, logger
from llm_metadata.schemas.data_paper import DataPaperManifest, DataPaperRecord, RunArtifact
from llm_metadata.schemas.fuster_features import (
    DatasetFeaturesExtraction,
    DatasetFeaturesNormalized,
)


_OUTPUT_DIR = Path(os.getenv("PROMPT_EVAL_OUTPUT_DIR", "artifacts/runs"))

def _resolve_output_path(name: Optional[str], output: Optional[str]) -> Path:
    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if output:
        path = Path(output)
        return _OUTPUT_DIR / f"{timestamp}_{path.name}" if path.parent == Path(".") else path
    if name:
        return _OUTPUT_DIR / f"{timestamp}_{name}.json"
    return _OUTPUT_DIR / f"{timestamp}_prompt_eval.json"

def _build_true_by_id_from_gt(
    gt: list[dict],
    allowed_ids: set[int],
    *,
    model_type: type[BaseModel],
) -> dict[str, BaseModel]:
    true_by_id: dict[str, BaseModel] = {}
    for entry in gt:
        entry = dict(entry)  # shallow copy to avoid mutating caller's data
        gt_record_id = int(entry.pop("gt_record_id"))
        if gt_record_id not in allowed_ids:
            continue
        true_by_id[str(gt_record_id)] = model_type.model_validate(entry)
    return true_by_id


def _default_eval_config_for_models(
    *,
    text_format: type[BaseModel],
    gt_model: type[BaseModel],
) -> EvaluationConfig:
    if text_format is DatasetFeaturesExtraction and gt_model is DatasetFeaturesNormalized:
        return EvaluationConfig(field_strategies=DEFAULT_FIELD_STRATEGIES)

    shared_fields = sorted(
        set(text_format.model_fields.keys()) & set(gt_model.model_fields.keys())
    )
    return EvaluationConfig(
        field_strategies={
            field_name: FieldEvalStrategy(match="exact") for field_name in shared_fields
        }
    )


def _evaluation_payload(report: EvaluationReport) -> dict:
    return {
        "config": report.config.to_dict(),
        "field_metrics": {name: metrics.to_dict() for name, metrics in report.field_metrics.items()},
        "field_results": [result.to_dict() for result in report.field_results],
    }


def _save_run_outputs(run_artifact: RunArtifact, output_path: str | Path) -> tuple[Path, Path]:
    json_path = run_artifact.save_json(output_path)
    csv_path = run_artifact.save_extraction_csv(json_path.with_suffix(".csv"))
    return json_path, csv_path


def run_eval(
    *,
    mode: ExtractionMode | str,
    manifest: list[DataPaperRecord],
    gt: list[dict],
    prompt: Optional[str] = None,
    parallelism: int = 1,
    config: Optional[EvaluationConfig] = None,
    config_path: Optional[str] = None,
    fields: Optional[list[str]] = None,
    model: str = "gpt-5-mini",
    reasoning_effort: str = "low",
    name: Optional[str] = None,
    description: Optional[str] = None,
    output_path: Optional[str | Path] = None,
    skip_cache: bool = False,
    text_format: type[BaseModel] = DatasetFeaturesExtraction,
    gt_model: type[BaseModel] = DatasetFeaturesNormalized,
) -> EvaluationReport:
    """Run extraction + evaluation for one explicit mode over one manifest."""

    requested_output_path = Path(output_path) if output_path is not None else None
    resolved_output_path = _resolve_output_path(
        name if requested_output_path is None else None,
        str(requested_output_path) if requested_output_path is not None else None,
    )
    log_path = resolved_output_path.with_suffix(".log")
    recreate_cmd = (
        "Python API run with custom notebook-defined schema; CLI recreation unavailable."
        if text_format is not DatasetFeaturesExtraction or gt_model is not DatasetFeaturesNormalized
        else _build_recreate_command(
            mode=mode,
            parallelism=parallelism,
            config_path=config_path,
            fields=fields,
            output_path=requested_output_path,
            name=name if requested_output_path is None else None,
            model=model,
            reasoning_effort=reasoning_effort,
            description=description,
            skip_cache=skip_cache,
        )
    )

    try:
        with _tee_console_to_log(log_path):
            print(f"Recreate command: {recreate_cmd}")
            configure_extraction_logging()
            manifest_obj = DataPaperManifest(records=manifest)
            logger.info(
                "Starting prompt_eval mode={} records={} parallelism={} model={} reasoning_effort={} description={} skip_cache={}",
                ExtractionMode(mode).value,
                len(manifest_obj.records),
                parallelism,
                model,
                reasoning_effort,
                description or "",
                skip_cache,
            )
            logger.info("Loaded manifest records={}", len(manifest_obj.records))
            eval_config = config or (
                EvaluationConfig.from_json(config_path)
                if config_path is not None
                else _default_eval_config_for_models(
                    text_format=text_format,
                    gt_model=gt_model,
                )
            )
            run_config = ExtractionConfig(
                model=model,
                reasoning={"effort": reasoning_effort},
                text_format=text_format,
            )
            run_artifact = run_manifest_extraction(
                manifest_obj,
                mode=mode,
                parallelism=parallelism,
                prompt=prompt,
                config=run_config,
                name=name,
                description=description,
                skip_cache=skip_cache,
            )

            # Compute provenance digests
            run_artifact.gt_digest = RunArtifact.compute_digest(
                json.dumps(gt, sort_keys=True, default=str)
            )
            run_artifact.manifest_digest = RunArtifact.compute_digest(
                json.dumps([r.model_dump() for r in manifest], sort_keys=True, default=str)
            )

            logger.info("Building ground truth from {} GT records", len(gt))
            allowed_ids = {record.gt_record_id for record in manifest_obj.records}
            true_by_id = _build_true_by_id_from_gt(
                gt,
                allowed_ids,
                model_type=gt_model,
            )
            if not true_by_id:
                raise ValueError("No valid GT rows matched the manifest.")

            logger.info(
                "Evaluating predictions matched_records={} fields={}",
                len(true_by_id),
                ",".join(fields) if fields else "default",
            )
            report = evaluate_indexed(
                true_by_id=true_by_id,
                pred_by_id=run_artifact.predictions_by_id(text_format),
                fields=fields,
                config=eval_config,
            )
            report.total_cost_usd = run_artifact.total_cost_usd  # type: ignore[attr-defined]
            report.run_artifact = run_artifact  # type: ignore[attr-defined]

            run_artifact.evaluation = _evaluation_payload(report)
            saved_json_path, saved_csv_path = _save_run_outputs(run_artifact, resolved_output_path)
            report.saved_path = str(saved_json_path)  # type: ignore[attr-defined]
            report.extraction_csv_path = str(saved_csv_path)  # type: ignore[attr-defined]
            logger.info("Saved prompt_eval artifact to {}", saved_json_path)
            logger.info("Saved extraction results CSV to {}", saved_csv_path)

            logger.info(
                "Completed prompt_eval mode={} records={} total_cost=${:.4f}",
                ExtractionMode(mode).value,
                len(run_artifact.records),
                run_artifact.total_cost_usd,
            )
            _print_metrics_table(report)
            print(f"\nRun artifact saved to: {saved_json_path}")
            return report
    finally:
        configure_extraction_logging()


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
    parallelism: int,
    config_path: Optional[str],
    fields: Optional[list[str]],
    output_path: Optional[Path],
    name: Optional[str],
    model: str,
    reasoning_effort: str,
    description: Optional[str],
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
        "--parallelism",
        str(parallelism),
        "--model",
        model,
        "--reasoning-effort",
        reasoning_effort,
    ]
    if config_path:
        command.extend(["--config", config_path])
    if fields:
        command.extend(["--fields", ",".join(fields)])
    if output_path is not None:
        command.extend(["--output", str(output_path)])
    elif name:
        command.extend(["--name", name])
    if description:
        command.extend(["--description", description])
    if skip_cache:
        command.append("--skip-cache")
    return " ".join(shlex.quote(part) for part in command)



def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Run extraction + evaluation over a manifest.")
    parser.add_argument("--mode", required=True, choices=[mode.value for mode in ExtractionMode])
    parser.add_argument("--manifest", required=True, help="Path to DataPaperManifest CSV.")
    parser.add_argument("--gt-manifest", default="data/gt/fuster_gt.json", help="Path to GT JSON array file.")
    parser.add_argument("--gt", default=None, help="[DEPRECATED] Validated GT XLSX path. Use --gt-manifest instead.")
    parser.add_argument("--prompt", default=None, help="Path to a text file containing the system prompt, or omit for mode default.")
    parser.add_argument("--parallelism", type=int, default=1, help="Number of records to extract concurrently.")
    parser.add_argument("--config", default=None, help="Path to an EvaluationConfig JSON file.")
    parser.add_argument("--fields", default=None, help="Comma-separated field names to evaluate.")
    parser.add_argument("--output", default=None, help="Path to save the run artifact JSON.")
    parser.add_argument("--name", default=None, help="Run name stem for auto-generated output paths.")
    parser.add_argument("--model", default="gpt-5-mini", help="OpenAI model name.")
    parser.add_argument("--reasoning-effort", default="low", help="GPT-5 reasoning effort.")
    parser.add_argument("--description", default=None, help="Short description stored with the run artifact.")
    parser.add_argument("--skip-cache", action="store_true", help="Bypass extraction cache.")
    args = parser.parse_args()

    # Load manifest CSV → list[DataPaperRecord]
    manifest_records = DataPaperManifest.load_csv(args.manifest).records

    # Load GT
    if args.gt is not None:
        import warnings
        warnings.warn(
            "--gt is deprecated. Use --gt-manifest with a JSON file instead. "
            "See `export_gt_json()` in llm_metadata.schemas.data_paper.",
            DeprecationWarning,
            stacklevel=1,
        )
        from llm_metadata.schemas.data_paper import export_gt_json
        import tempfile
        tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        export_gt_json(gt_path=args.gt, output_path=tmp.name)
        gt_data = json.loads(Path(tmp.name).read_text(encoding="utf-8"))
    else:
        gt_path = Path(args.gt_manifest)
        gt_data = json.loads(gt_path.read_text(encoding="utf-8"))

    # Load prompt text from file if provided
    prompt_text = None
    if args.prompt:
        prompt_text = Path(args.prompt).read_text(encoding="utf-8")

    fields = [f.strip() for f in args.fields.split(",")] if args.fields else None

    run_eval(
        mode=args.mode,
        manifest=manifest_records,
        gt=gt_data,
        prompt=prompt_text,
        parallelism=args.parallelism,
        config_path=args.config,
        fields=fields,
        model=args.model,
        reasoning_effort=args.reasoning_effort,
        name=args.name,
        description=args.description,
        output_path=args.output,
        skip_cache=args.skip_cache,
    )


if __name__ == "__main__":
    main()
