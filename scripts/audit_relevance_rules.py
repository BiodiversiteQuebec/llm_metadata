"""Audit the Fuster rule scorer and the human-vs-rule agreement.

Prints markdown tables. Held-out records are only ever counted in aggregate:
this script never prints a per-record row for them.

    uv run python scripts/audit_relevance_rules.py
"""

from __future__ import annotations

import pandas as pd
from sklearn.metrics import cohen_kappa_score

from llm_metadata.relevance_rules import (
    LABELS, binarize, classify_features, features_from_row, normalize_human_label,
)

def md(df, index=True):
    """Markdown table without the optional tabulate dependency."""
    d = df.reset_index() if index else df
    head = "| " + " | ".join(str(c) for c in d.columns) + " |"
    sep = "|" + "|".join("---" for _ in d.columns) + "|"
    body = ["| " + " | ".join(str(x) for x in row) + " |" for row in d.itertuples(index=False)]
    return "\n".join([head, sep, *body])


XLSX = "data/dataset_092624.xlsx"
DEV = "data/manifests/dev_subset_data_paper.csv"
HELD = "data/manifests/heldout_ids.csv"
MC_PAIRS = [
    ("MC_dataset_type", "dataset_type"),
    ("MC_temporal_range", "temporal"),
    ("MC_spatial_range", "spatial"),
    ("MC_relevance", "relevance"),
    ("MC_relevance_modifiers", "relevance_modifiers"),
]


def load():
    raw = pd.read_excel(XLSX)
    v = raw[raw["valid_yn"] == "yes"].copy()
    dev = set(pd.read_csv(DEV)["gt_record_id"])
    held = set(pd.read_csv(HELD)["gt_record_id"])
    v["subset"] = v["id"].map(lambda i: "dev" if i in dev else "heldout" if i in held else "other")
    for col, attr in MC_PAIRS:
        v[f"calc_{attr}"] = [
            getattr(classify_features(features_from_row(r)), attr) for _, r in v.iterrows()
        ]
    v["human"] = v["dataset_relevance"].map(normalize_human_label)
    v["rule"] = v["MC_relevance_modifiers"].map(lambda x: x.strip() if isinstance(x, str) and x.strip() in LABELS else None)
    return v


def reproduction(v):
    rows = []
    for col, attr in MC_PAIRS:
        w = v[v[col].isin(LABELS)]
        ok = w[col] == w[f"calc_{attr}"]
        row = {"column": col, "records": len(w), "reproduced": int(ok.sum()), "rate": f"{ok.mean():.1%}"}
        for s in ("dev", "other", "heldout"):
            m = w["subset"] == s
            row[s] = f"{int(ok[m].sum())}/{int(m.sum())}"
        rows.append(row)
    return pd.DataFrame(rows)


def agreement(w, title):
    both = w[w["human"].notna() & w["rule"].notna()]
    n = len(both)
    out = [f"### {title} (n = {n})", ""]
    if n == 0:
        return "\n".join(out + ["No records.", ""])
    ct = pd.crosstab(both["human"], both["rule"]).reindex(index=list(LABELS), columns=list(LABELS), fill_value=0)
    ct.index.name = "human \\ rule"
    ct["total"] = ct.sum(axis=1)
    ct.loc["total"] = ct.sum()
    out += ["Four classes (rows: human `dataset_relevance`, columns: rule `MC_relevance_modifiers`)", "", md(ct), ""]
    agree4 = (both["human"] == both["rule"]).mean()
    k4 = cohen_kappa_score(both["human"], both["rule"])
    hb, rb = both["human"].map(binarize), both["rule"].map(binarize)
    bt = pd.crosstab(hb, rb).reindex(index=["relevant", "not_relevant"], columns=["relevant", "not_relevant"], fill_value=0)
    bt.index.name = "human \\ rule"
    bt["total"] = bt.sum(axis=1)
    bt.loc["total"] = bt.sum()
    agree2 = (hb == rb).mean()
    k2 = cohen_kappa_score(hb, rb) if hb.nunique() > 1 or rb.nunique() > 1 else float("nan")
    out += ["Binary (H and M = relevant; L and X = not relevant)", "", md(bt), ""]
    out += [f"- Four-class agreement: {int((both['human']==both['rule']).sum())}/{n} = {agree4:.1%}, Cohen's kappa {k4:.2f}",
            f"- Binary agreement: {int((hb==rb).sum())}/{n} = {agree2:.1%}, Cohen's kappa {k2:.2f}", ""]
    return "\n".join(out)


if __name__ == "__main__":
    v = load()
    print("## Reproduction of the released MC columns (valid records)\n")
    print(md(reproduction(v), index=False), "\n")
    print("## Non-held-out mismatches\n")
    cols = ["id", "data_type", "temp_range_i", "temp_range_f", "spatial_range_km2"]
    for col, attr in MC_PAIRS:
        w = v[v[col].isin(LABELS) & (v["subset"] != "heldout") & (v[col] != v[f"calc_{attr}"])]
        for _, r in w.iterrows():
            print(f"- {col}: id {r['id']} released {r[col]} computed {r[f'calc_{attr}']}; " + ", ".join(f"{c}={r[c]}" for c in cols[1:]))
    print()
    print(agreement(v, "All valid records with both labels"))
    print(agreement(v[v.subset == "dev"], "Dev subset"))
    print(agreement(v[v.subset == "heldout"], "Held-out (aggregate only)"))
    print(agreement(v[v.subset == "other"], "Valid records outside dev and held-out"))
