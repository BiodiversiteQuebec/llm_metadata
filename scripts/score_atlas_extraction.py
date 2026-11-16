"""Contribution scores from an Atlas-track extraction run, compared with the annotation ceiling.

    uv run python scripts/score_atlas_extraction.py artifacts/runs/<run>.json --out docs/atlas_contribution/extraction_dev.md
    uv run python scripts/score_atlas_extraction.py <run> --include-heldout --out docs/atlas_contribution/extraction_heldout.md

For the records of the run: the four scores computed from the extracted features and from
the human annotations, their rank correlation (Spearman, 95 % bootstrap interval), and the
correlation of the extracted scores with the Fuster rule label. Writes dataset-level
numbers only (no per-species Atlas counts).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from llm_metadata.atlas_contribution import (
    annotation_descriptions,
    compare_with_fuster,
    describe_extraction,
    score_all,
    spearman_ci,
)
from llm_metadata.atlas_match import AtlasReference
from llm_metadata.relevance_eval import targets


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("run_json")
    ap.add_argument("--include-heldout", action="store_true", help="Allowed only after the frozen held-out pass.")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    run = json.loads(Path(a.run_json).read_text())
    atlas = AtlasReference.load()
    ext = [describe_extraction(r["gt_record_id"], r["output"], atlas) for r in run["records"]
           if r.get("status") == "success" and r.get("output")]
    ids = {d.record_id for d in ext}
    ann = [d for d in annotation_descriptions(atlas, include_heldout=a.include_heldout) if d.record_id in ids]
    s_ext = score_all(ext, atlas)
    s_ann = score_all(ann, atlas)
    common = s_ext.index.intersection(s_ann.index)
    score_cols = ["taxonomic", "spatial", "temporal", "group_gap", "n_gaps"]

    lines = [f"# Atlas contribution scores from extraction vs annotation\n",
             f"Run `{Path(a.run_json).name}` ({run.get('model')}, {run.get('mode')}), {len(common)} records "
             f"{'(dev + held-out allowed)' if a.include_heldout else '(non-held-out)'}. Spearman rank correlation "
             "[95 % bootstrap interval], over records where both sides have the score.\n",
             "| Score | Extraction vs annotation | n | Defined from extraction | Defined from annotation |", "|---|---|---|---|---|"]
    out = {}
    for c in score_cols:
        x, y = s_ext.loc[common, c], s_ann.loc[common, c]
        rho, lo, hi, n = spearman_ci(list(x), list(y))
        out[c] = {"rho": rho, "low": lo, "high": hi, "n": n,
                  "defined_extraction": int(x.notna().sum()), "defined_annotation": int(y.notna().sum())}
        fmt = "n/a" if rho != rho else f"{rho:.2f} [{lo:.2f}, {hi:.2f}]"
        lines.append(f"| {c} | {fmt} | {n} | {out[c]['defined_extraction']} | {out[c]['defined_annotation']} |")

    labels = targets()["rule"]
    labels.index = labels.index.astype(str)
    full = compare_with_fuster(s_ext, labels)
    fuster = {"n": full["n"], "spearman_ci": full["spearman_ci"], "crosstab": full["crosstab"].to_string()}
    lines += ["", "**Extracted scores vs the Fuster rule label:**", "", "```", json.dumps({k: v for k, v in fuster.items() if k != "crosstab"}, indent=2, default=str), fuster["crosstab"], "```"]
    kinds = pd.Series([d.extra.get("record_kind") for d in ext]).value_counts().to_dict()
    avail = pd.Series([d.extra.get("occurrence_records_available") for d in ext]).value_counts(dropna=False).to_dict()
    places = pd.Series([p.level for d in ext for p in d.places]).value_counts().to_dict()
    lines += ["", f"Kinds of record: {kinds}", "", f"Occurrence records available: {avail}", "", f"Place match levels: {places}"]
    Path(a.out).write_text("\n".join(lines) + "\n")
    Path(a.out).with_suffix(".json").write_text(json.dumps({"run": a.run_json, "correlations": out, "fuster": fuster,
                                                            "record_kinds": kinds}, indent=2, default=str) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
