"""Build the article's result tables and figures from a set of run artifacts.

    uv run python scripts/build_results_tables.py --runs-json configs/results_runs_dev.json --subset dev --out docs/results/dev_tables
    uv run python scripts/build_results_tables.py --runs-json configs/results_runs_heldout.json --subset heldout --final --out docs/results/heldout_tables

``--runs-json`` maps each condition to a run artifact, e.g.
``{"r1_features_abstract": "artifacts/runs/..json", "r2_combined_pdf_text": "..."}``.
Condition names: ``r1_features_<input>``, ``r2_combined_<input>``, ``r3_scoring_<input>``.

Writes into ``--out``: ``table1_relevance.md`` (both targets, intervals),
``table2_features.md`` (per field and input, intervals, class level, taxa at several
ranks), ``table3_confusion_<condition>.png``, ``s2_cost.md`` and ``tables.json`` with
every number, so each figure in the outline traces back to a run file.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from llm_metadata.groundtruth_eval import MICRO_KEY, bootstrap_report  # noqa: E402
from llm_metadata.relevance_eval import predictions, score  # noqa: E402
from llm_metadata.relevance_rules import LABELS  # noqa: E402
from llm_metadata.run_summary import rescore_run  # noqa: E402

APPROACH = {"r1": "1. Rules on extracted features", "r2": "2b. Combined (features + category)", "r3": "2. Scoring only"}
INPUT = {"abstract": "Short text (abstract / repository description)", "pdf_text": "Long text (PDF text)",
         "pdf_native": "Long text (native PDF)", "sections": "Long text (sections)"}
FEATURE_FIELDS = ["data_type", "geospatial_info_dataset", "species", "temp_range_i", "temp_range_f",
                  "temporal_range_class", "spatial_range_km2", "spatial_range_class", "time_series"]
MODULATORS = ["multispecies", "threatened_species", "new_species_science", "new_species_region", "bias_north_south"]


def _split(name: str) -> tuple[str, str]:
    approach = name.split("_")[0]
    for inp in INPUT:
        if name.endswith(inp):
            return approach, inp
    raise ValueError(f"Cannot read approach and input from {name!r}")


def _iv(t) -> str:
    v, lo, hi = t
    return "n/a" if v != v else f"{v:.2f} [{lo:.2f}, {hi:.2f}]"


def relevance_table(runs: dict[str, str], subset: str, out: Path) -> dict:
    rows, data = [], {}
    for name, path in runs.items():
        approach, inp = _split(name)
        df = predictions(path, subset)
        entry = {"run": path, "n_records": int(len(df)), "failed": int(df["pred"].isna().sum())}
        for target in ("rule", "human"):
            s = score(df, target)
            entry[target] = {"n": s["n"], **{k: list(map(float, v)) for k, v in s["scores"].items()},
                             "direction": s["direction"], "confusion": s["confusion"].to_dict()}
        data[name] = entry
        r, h = entry["rule"], entry["human"]
        rows.append(f"| {APPROACH[approach]} | {INPUT[inp]} | {r['n']} | {_iv(r['f1'])} | {_iv(r['precision'])} | "
                    f"{_iv(r['recall'])} | {_iv(r['acc4'])} | {_iv(h['f1'])} | {_iv(h['acc4'])} |")
        _confusion_png(df, name, out)
    head = ("| Approach | Input | n | Binary F1 (rule) | Binary P (rule) | Binary R (rule) | Four-class agreement (rule) "
            "| Binary F1 (human) | Four-class agreement (human) |\n|---|---|---|---|---|---|---|---|---|")
    text = "\n".join([head, *rows])
    (out / "table1_relevance.md").write_text(
        "Relevance against the rule label (Fuster rules on the human features, primary) and the human label. "
        "Binary: relevant = high or moderate. Values: estimate [95 % bootstrap interval over records].\n\n" + text + "\n")
    return data


def _confusion_png(df: pd.DataFrame, name: str, out: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(8, 3.6))
    for ax, target in zip(axes, ("rule", "human")):
        d = df[df[target].notna()]
        labels = list(LABELS)
        m = np.zeros((4, 4), int)
        for t, p in zip(d[target], d["pred"].fillna("X")):
            if t in labels and p in labels:
                m[labels.index(t), labels.index(p)] += 1
        ax.imshow(m, cmap="Blues")
        for i in range(4):
            for j in range(4):
                ax.text(j, i, m[i, j], ha="center", va="center", color="white" if m[i, j] > m.max() / 2 else "black")
        ax.set_xticks(range(4), labels)
        ax.set_yticks(range(4), labels)
        ax.set_xlabel("Predicted")
        ax.set_ylabel(f"{target.capitalize()} label")
        ax.set_title(f"vs {target} label (n={len(d)})", fontsize=10)
    fig.suptitle(name.replace("_", " "), fontsize=11)
    fig.tight_layout()
    fig.savefig(out / f"table3_confusion_{name}.png", dpi=150)
    plt.close(fig)


def feature_table(runs: dict[str, str], subset: str, out: Path) -> dict:
    feats = {k: v for k, v in runs.items() if k.startswith("r1_") or k.startswith("r2_")}
    data, cols = {}, []
    for name, path in feats.items():
        report, meta = rescore_run(path, subset=subset)
        ci = bootstrap_report(report)
        data[name] = {"run": path, "n": len(meta["ids"]), "failed": len(meta["failed"]),
                      "fields": {f: {m: [ci[f][m].point, ci[f][m].low, ci[f][m].high] for m in ("precision", "recall", "f1")}
                                 for f in ci}}
        try:
            from llm_metadata.taxonomy_eval import evaluate_run_taxa

            tf = evaluate_run_taxa(path, record_ids=meta["ids"]).metrics_frame()
            data[name]["taxa"] = tf.to_dict(orient="records")
        except Exception as exc:  # GBIF offline: keep the table, note the gap
            data[name]["taxa_error"] = str(exc)
        cols.append(name)

    def cell(name, field):
        f = data[name]["fields"].get(field)
        if not f or f["f1"][0] is None:
            return "n/a"
        p, r, f1 = f["precision"][0], f["recall"][0], f["f1"]
        p = "n/a" if p is None else f"{p:.2f}"
        r = "n/a" if r is None else f"{r:.2f}"
        return f"{p} / {r} / {f1[0]:.2f} [{f1[1]:.2f}, {f1[2]:.2f}]" if f1[1] is not None else f"{p} / {r} / {f1[0]:.2f}"

    lines = ["| Field | " + " | ".join(c.replace("_", " ") for c in cols) + " |", "|---|" + "---|" * len(cols)]
    lines.append("| *n records (failed)* | " + " | ".join(f"{data[c]['n']} ({data[c]['failed']})" for c in cols) + " |")
    for group, fields in (("EBV features", FEATURE_FIELDS), ("Modulators", MODULATORS), ("All fields", [MICRO_KEY])):
        lines.append(f"| **{group}** |" + " |" * len(cols))
        for f in fields:
            lines.append(f"| {'micro average' if f == MICRO_KEY else f} | " + " | ".join(cell(c, f) for c in cols) + " |")
    taxa_lines = []
    for c in cols:
        for row in data[c].get("taxa", []):
            taxa_lines.append(f"| {c.replace('_', ' ')} | {row.get('rank')} | {row.get('precision', float('nan')):.2f} | "
                              f"{row.get('recall', float('nan')):.2f} | {row.get('f1', float('nan')):.2f} |")
    (out / "table2_features.md").write_text(
        "Feature extraction, precision / recall / F1 [95 % interval of F1]. Yes/no fields scored as flags "
        "(not stated = false). Class fields: H/M/L classes of the relevance rules.\n\n" + "\n".join(lines)
        + "\n\n**Taxa at several ranks (GBIF resolution)**\n\n| Condition | Rank | P | R | F1 |\n|---|---|---|---|---|\n"
        + "\n".join(taxa_lines) + "\n")
    return data


def cost_table(runs: dict[str, str], out: Path, harvest: int) -> dict:
    data, lines = {}, ["| Condition | Records | Total USD | USD per record | Input tokens per record | Output tokens per record | "
                       f"USD for {harvest:,} records |", "|---|---|---|---|---|---|---|"]
    for name, path in runs.items():
        run = json.loads(Path(path).read_text())
        recs = [r for r in run["records"] if r.get("usage_cost")]
        tot = sum(r["usage_cost"].get("total_cost") or 0 for r in recs)
        n = max(len(recs), 1)
        it = sum(r["usage_cost"].get("input_tokens") or 0 for r in recs) / n
        ot = sum(r["usage_cost"].get("output_tokens") or 0 for r in recs) / n
        data[name] = {"records": len(recs), "total_usd": tot, "usd_per_record": tot / n, "input_tokens": it, "output_tokens": ot}
        lines.append(f"| {name.replace('_', ' ')} | {len(recs)} | {tot:.4f} | {tot / n:.5f} | {it:,.0f} | {ot:,.0f} | {tot / n * harvest:,.2f} |")
    (out / "s2_cost.md").write_text(
        f"Cost of each condition (model {json.loads(Path(next(iter(runs.values()))).read_text()).get('model')}), "
        "standard API prices, prompt caching on, no batch discount (batch would halve it).\n\n" + "\n".join(lines) + "\n")
    return data


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--runs-json", required=True)
    ap.add_argument("--subset", default="dev", choices=["dev", "heldout", "all"])
    ap.add_argument("--final", action="store_true")
    ap.add_argument("--out", required=True)
    ap.add_argument("--harvest", type=int, default=10_000, help="Records in a full repository harvest, for S2.")
    a = ap.parse_args()
    if a.subset != "dev" and not a.final:
        ap.error("Held-out records are scored once, at the end: add --final.")
    runs = json.loads(Path(a.runs_json).read_text())
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    tables = {"subset": a.subset, "runs": runs,
              "table1": relevance_table(runs, a.subset, out),
              "table2": feature_table(runs, a.subset, out),
              "s2": cost_table(runs, out, a.harvest)}
    (out / "tables.json").write_text(json.dumps(tables, indent=2, default=str) + "\n")
    print(f"Wrote tables to {out}")


if __name__ == "__main__":
    main()
