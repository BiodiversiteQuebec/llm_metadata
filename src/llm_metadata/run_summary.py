"""One-call summary of a prompt-eval run: scores with intervals, class level, ceiling.

    uv run python -m llm_metadata.run_summary artifacts/runs/<run>.json

Rescoring starts from the extracted values stored in the run file (no API call), against
the ground truth, with ``configs/eval_article.json`` (default fields plus class-level
spatial and temporal range). By default only the 30 dev records are scored; the held-out
records are never touched unless ``subset`` is set to ``heldout`` or ``all`` on purpose.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional

import pandas as pd

from llm_metadata.evidence_ceiling import FIELD_SOURCES, ceiling_recall, evidence_table
from llm_metadata.groundtruth_eval import (
    MICRO_KEY,
    EvaluationConfig,
    EvaluationReport,
    bootstrap_report,
    evaluate_indexed,
)
from llm_metadata.schemas.fuster_features import DatasetFeaturesExtraction, DatasetFeaturesNormalized

DEV_MANIFEST = "data/manifests/dev_subset_data_paper.csv"
HELDOUT_IDS = "data/manifests/heldout_ids.csv"
DEFAULT_GT = "data/gt/fuster_gt.json"
DEFAULT_CONFIG = "configs/eval_article.json"

#: Run mode -> input kind used for the evidence ceiling.
MODE_TO_INPUT = {"abstract": "abstract", "pdf_text": "fulltext", "pdf_native": "pdf", "sections": "fulltext"}
CLASS_FIELDS = ("spatial_range_class", "temporal_range_class")


def rescore_run(
    run_json: str | Path,
    gt: str | Path = DEFAULT_GT,
    config: str | Path = DEFAULT_CONFIG,
    subset: str = "dev",
) -> tuple[EvaluationReport, dict]:
    """Score the extractions stored in a run file against the ground truth.

    ``subset``: ``dev`` (the 30 dev records, default), ``heldout`` or ``all``. Returns the
    report and the run metadata (name, mode, model, record ids used).
    """
    if subset not in ("dev", "heldout", "all"):
        raise ValueError("subset must be 'dev', 'heldout' or 'all'")
    run = json.loads(Path(run_json).read_text())
    dev_ids = set(pd.read_csv(DEV_MANIFEST)["gt_record_id"].astype(int))
    held_ids = set(pd.read_csv(HELDOUT_IDS)["gt_record_id"].astype(int))
    allowed = {"dev": dev_ids, "heldout": held_ids, "all": None}[subset]

    preds, ids = {}, []
    for rec in run["records"]:
        gid = int(rec["gt_record_id"])
        if rec.get("status") != "success" or rec.get("output") is None:
            continue
        if allowed is not None and gid not in allowed:
            continue
        preds[str(gid)] = DatasetFeaturesExtraction.model_validate(rec["output"])
        ids.append(gid)

    trues = {}
    for entry in json.loads(Path(gt).read_text()):
        entry = dict(entry)
        gid = int(entry.pop("gt_record_id"))
        if str(gid) in preds:
            trues[str(gid)] = DatasetFeaturesNormalized.model_validate(entry)

    report = evaluate_indexed(
        true_by_id=trues, pred_by_id=preds, config=EvaluationConfig.from_json(config)
    )
    meta = {
        "name": run.get("name"), "mode": run.get("mode"), "model": run.get("model"),
        "effort": run.get("reasoning_effort"), "ids": sorted(ids), "subset": subset,
    }
    return report, meta


def summarize_run(
    run_json: str | Path,
    gt: str | Path = DEFAULT_GT,
    config: str | Path = DEFAULT_CONFIG,
    subset: str = "dev",
    n_boot: int = 1000,
    seed: int = 0,
) -> str:
    """Text summary: P/R/F1 with 95 % intervals per field, class level, evidence ceiling."""
    report, meta = rescore_run(run_json, gt, config, subset)
    ci = bootstrap_report(report, n_boot=n_boot, seed=seed)
    inp = MODE_TO_INPUT.get(str(meta["mode"]), "abstract")
    table = evidence_table()

    def cell(field, metric):
        return ci[field][metric].format(2) if field in ci else "N/A"

    lines = [
        f"Run: {meta['name']}  model={meta['model']}  effort={meta['effort']}  mode={meta['mode']}",
        f"Records scored: {len(meta['ids'])} ({meta['subset']})   bootstrap: {n_boot} replicates, seed {seed}, 95 % percentile intervals",
        "Cells: value [low, high]. N/A: undefined (no positive in the denominator).",
        "",
    ]
    header = f"{'field':<25}{'precision':<19}{'recall':<19}{'F1':<19}{'exact match':<19}{'ceiling R':>9}"
    lines += [header, "-" * len(header)]
    names = [f for f in report.fields() if f not in CLASS_FIELDS]
    for group, title in ((names, None), ([f for f in CLASS_FIELDS if f in report.field_metrics], "class level (H/M/L, not stated = no class)")):
        if title:
            lines += ["", title]
        for f in group:
            ceil = ""
            if f in FIELD_SOURCES:
                c = ceiling_recall(f, inp, ids=meta["ids"], table=table)
                ceil = "N/A" if c.recall is None else f"{c.recall:.2f}"
            lines.append(
                f"{f:<25}{cell(f,'precision'):<19}{cell(f,'recall'):<19}{cell(f,'f1'):<19}"
                f"{cell(f,'exact_match_rate'):<19}{ceil:>9}"
            )
    lines += ["", f"{'micro (all fields)':<25}{cell(MICRO_KEY,'precision'):<19}{cell(MICRO_KEY,'recall'):<19}{cell(MICRO_KEY,'f1'):<19}{cell(MICRO_KEY,'exact_match_rate'):<19}"]
    lines += [
        "",
        f"Ceiling R = highest recall reachable from the {inp} text on these records, from the annotators'",
        "position columns (value found in abstract/repository text or article). Blank: no position",
        "information for that field. It is a cautious figure: annotators note where they found a value,",
        "not every place it appears, so observed recall can exceed it (see docs/results/evaluation_metrics.md).",
        "Exact match for class fields = class accuracy incl. 'not stated'.",
    ]
    return "\n".join(lines)


def main(argv: Optional[list[str]] = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("run_json")
    ap.add_argument("--gt", default=DEFAULT_GT)
    ap.add_argument("--config", default=DEFAULT_CONFIG)
    ap.add_argument("--subset", default="dev", choices=["dev", "heldout", "all"])
    ap.add_argument("--n-boot", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args(argv)
    print(summarize_run(a.run_json, a.gt, a.config, a.subset, a.n_boot, a.seed))


if __name__ == "__main__":
    main()
