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
    DERIVED_FIELDS,
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

    run_ids = [int(rec["gt_record_id"]) for rec in run["records"]]
    if len(run_ids) != len(set(run_ids)):
        raise ValueError(f"Duplicate record ids in run file {run_json}")

    # A record whose extraction failed is scored as an empty prediction (every annotated
    # value missed), so that failures lower recall instead of disappearing.
    preds, ids, failed = {}, [], []
    for rec in run["records"]:
        gid = int(rec["gt_record_id"])
        if allowed is not None and gid not in allowed:
            continue
        if rec.get("status") != "success" or rec.get("output") is None:
            preds[str(gid)] = DatasetFeaturesExtraction()
            failed.append(gid)
        else:
            preds[str(gid)] = DatasetFeaturesExtraction.model_validate(rec["output"])
        ids.append(gid)

    trues = {}
    for entry in json.loads(Path(gt).read_text()):
        entry = dict(entry)
        gid = int(entry.pop("gt_record_id"))
        # The ground truth holds one duplicated id (306, not in the open-access corpus):
        # keep the first entry.
        if str(gid) in preds and str(gid) not in trues:
            trues[str(gid)] = DatasetFeaturesNormalized.model_validate(entry)

    report = evaluate_indexed(
        true_by_id=trues, pred_by_id=preds, config=EvaluationConfig.from_json(config)
    )
    meta = {
        "name": run.get("name"), "mode": run.get("mode"), "model": run.get("model"),
        "effort": run.get("reasoning_effort"), "ids": sorted(ids), "subset": subset,
        "failed": sorted(failed),
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
        if field not in ci:
            return "N/A"
        iv = ci[field][metric]
        # "~": the metric was undefined in more than 10 % of replicates (few positives),
        # so the interval is conditional and looks narrower than it is.
        thin = iv.point is not None and iv.n_defined < 0.9 * n_boot
        return iv.format(2) + ("~" if thin else "")

    lines = [
        f"Run: {meta['name']}  model={meta['model']}  effort={meta['effort']}  mode={meta['mode']}",
        f"Records scored: {len(meta['ids'])} ({meta['subset']}), of which failed extractions "
        f"(scored as empty): {len(meta['failed'])}   bootstrap: {n_boot} replicates, seed {seed}, 95 % percentile intervals",
        "Cells: value [low, high]. N/A: undefined (no positive in the denominator). "
        "~: undefined in over 10 % of replicates, interval unreliable.",
        "Micro excludes the class-level fields (they restate the km2 and year fields).",
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


def _count_cube(report: EvaluationReport, rec_ids: list[str], fields: list[str]):
    """counts[record, field, (tp, fp, fn, exact, n)] for the given record and field order."""
    import numpy as np

    r_idx = {rid: i for i, rid in enumerate(rec_ids)}
    f_idx = {f: i for i, f in enumerate(fields)}
    cube = np.zeros((len(rec_ids), len(fields), 5))
    for r in report.field_results:
        rid, f = str(r.record_id), r.field
        if rid in r_idx and f in f_idx:
            cube[r_idx[rid], f_idx[f]] += (r.tp, r.fp, r.fn, 1 if r.match else 0, 1)
    return cube


def compare_runs(
    run_a: str | Path,
    run_b: str | Path,
    gt: str | Path = DEFAULT_GT,
    config: str | Path = DEFAULT_CONFIG,
    subset: str = "dev",
    n_boot: int = 2000,
    seed: int = 0,
) -> tuple[str, dict]:
    """Paired comparison of two runs on the records both scored: B minus A.

    The same bootstrap resample of records is applied to both runs, so record difficulty
    cancels out and the interval of the difference is much narrower than the two separate
    intervals suggest. Reported per field: F1 of A, F1 of B, the difference with its 95 %
    interval, and the share of replicates where B beats A. A change is called a gain or a
    loss only when the interval of the difference excludes 0.

    Returns the text table and ``{field: {...}}`` with the same numbers.
    """
    import numpy as np

    rep_a, meta_a = rescore_run(run_a, gt, config, subset)
    rep_b, meta_b = rescore_run(run_b, gt, config, subset)
    ids_a, ids_b = {str(i) for i in meta_a["ids"]}, {str(i) for i in meta_b["ids"]}
    rec_ids = sorted(ids_a & ids_b)
    only_one = sorted(ids_a ^ ids_b, key=int)
    fields = [f for f in rep_a.fields() if f in set(rep_b.fields())]
    ca, cb = _count_cube(rep_a, rec_ids, fields), _count_cube(rep_b, rec_ids, fields)

    def f1(c):  # last axis: tp, fp, fn, exact, n
        tp, fp, fn = c[..., 0], c[..., 1], c[..., 2]
        den = 2 * tp + fp + fn
        with np.errstate(divide="ignore", invalid="ignore"):
            return np.where(den > 0, 2 * tp / den, np.nan)

    rng = np.random.default_rng(seed)
    picks = rng.integers(0, len(rec_ids), size=(n_boot, len(rec_ids)))
    out: dict[str, dict] = {}
    lines = [
        f"A: {meta_a['name']} ({meta_a['model']}, {meta_a['effort']}, {meta_a['mode']})",
        f"B: {meta_b['name']} ({meta_b['model']}, {meta_b['effort']}, {meta_b['mode']})",
        f"Paired on {len(rec_ids)} records ({subset}); {n_boot} paired bootstrap replicates, seed {seed}. "
        f"Failed extractions (scored as empty): A {len(meta_a['failed'])}, B {len(meta_b['failed'])}.",
        *( [f"WARNING: records in only one run, left out: {', '.join(only_one)}"] if only_one else [] ),
        "Micro excludes the class-level fields. With about 15 fields, one 'gain' or 'loss' at 95 % is"
        " expected by chance: trust a verdict that matches the hypothesis, not a stray one.",
        "",
        f"{'field':<25}{'F1 A':>7}{'F1 B':>7}{'B - A [95 % interval]':>28}{'P(B>A)':>8}  verdict",
        "-" * 88,
    ]
    rows = [(f, ca[:, i, :], cb[:, i, :]) for i, f in enumerate(fields)]
    primary = [i for i, f in enumerate(fields) if f not in DERIVED_FIELDS] or list(range(len(fields)))
    rows.append((MICRO_KEY, ca[:, primary, :].sum(axis=1), cb[:, primary, :].sum(axis=1)))
    for f, a, b in rows:
        name = "micro (all fields)" if f == MICRO_KEY else f
        fa, fb = float(f1(a.sum(axis=0))), float(f1(b.sum(axis=0)))
        d = f1(b[picks].sum(axis=1)) - f1(a[picks].sum(axis=1))
        d = d[~np.isnan(d)]
        if np.isnan(fa) or np.isnan(fb) or len(d) == 0:
            lines.append(f"{name:<25}{'N/A':>7}{'N/A':>7}")
            continue
        lo, hi = np.percentile(d, [2.5, 97.5])
        p_better = float((d > 0).mean())
        if np.all(d == 0):
            verdict = "identical"
        else:
            verdict = "gain" if lo > 0 else ("loss" if hi < 0 else "no clear change")
        out[f] = {"f1_a": fa, "f1_b": fb, "delta": fb - fa, "low": float(lo), "high": float(hi),
                  "p_b_better": p_better, "verdict": verdict}
        lines.append(
            f"{name:<25}{fa:>7.2f}{fb:>7.2f}{fb - fa:>+10.2f} [{lo:+.2f}, {hi:+.2f}]{'':>3}{p_better:>8.2f}  {verdict}"
        )
    return "\n".join(lines), out


def main(argv: Optional[list[str]] = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("run_json")
    ap.add_argument("--compare", default=None, metavar="RUN_B",
                    help="Second run: print a paired comparison (this run = A, RUN_B = B).")
    ap.add_argument("--gt", default=DEFAULT_GT)
    ap.add_argument("--config", default=DEFAULT_CONFIG)
    ap.add_argument("--subset", default="dev", choices=["dev", "heldout", "all"])
    ap.add_argument("--n-boot", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--final", action="store_true",
                    help="Required with --subset heldout or all: the held-out set is scored once, at the end.")
    a = ap.parse_args(argv)
    if a.subset != "dev" and not a.final:
        ap.error("--subset heldout/all scores held-out records: add --final if this is the final pass.")
    if a.compare:
        print(compare_runs(a.run_json, a.compare, a.gt, a.config, a.subset, max(a.n_boot, 2000), a.seed)[0])
        return
    print(summarize_run(a.run_json, a.gt, a.config, a.subset, a.n_boot, a.seed))


if __name__ == "__main__":
    main()
