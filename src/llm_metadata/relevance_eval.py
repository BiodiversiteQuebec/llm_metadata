"""Relevance scoring evaluation, against both targets.

Two targets, reported side by side (see ``docs/results/relevance_targets.md``):

* **rule label**: ``MC_relevance_modifiers``, the Fuster rule output on the human
  features (primary target);
* **human label**: ``dataset_relevance``, the annotator's own judgement.

A run gives a predicted category in one of two ways:

* **rules on extracted features** (approach 1): the run's outputs are feature
  extractions; :func:`llm_metadata.relevance_rules.classify_features` turns each
  into a category;
* **direct** (approach 2, or the combined variant): the run's outputs carry a
  ``relevance`` field (H, M, L or X).

    uv run python -m llm_metadata.relevance_eval artifacts/runs/<run>.json [--subset dev]

Only dev records are scored unless ``--subset heldout`` or ``all`` is given on purpose.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

from llm_metadata.relevance_rules import (
    LABELS,
    RELEVANT_LABELS,
    classify_features,
    features_from_row,
    normalize_human_label,
)

RAW_XLSX = "data/dataset_092624.xlsx"
DEV_MANIFEST = "data/manifests/dev_subset_data_paper.csv"
HELDOUT_IDS = "data/manifests/heldout_ids.csv"
COMPONENTS = ("dataset_type", "temporal", "spatial")
_MC = {"dataset_type": "MC_dataset_type", "temporal": "MC_temporal_range", "spatial": "MC_spatial_range"}


def _clean(label: Any) -> Optional[str]:
    if label is None or (isinstance(label, float) and np.isnan(label)):
        return None
    text = str(label).strip()
    return text if text in LABELS else None


@lru_cache(maxsize=1)
def targets() -> pd.DataFrame:
    """One row per record id: rule label, human label and the released intermediate classes."""
    raw = pd.read_excel(RAW_XLSX)
    out = pd.DataFrame({
        "gt_record_id": raw["id"].astype(int),
        "rule": raw["MC_relevance_modifiers"].map(_clean),
        "human": raw["dataset_relevance"].map(normalize_human_label),
        **{f"true_{c}": raw[col].map(_clean) for c, col in _MC.items()},
    })
    return out.set_index("gt_record_id")


def subset_ids(subset: str) -> Optional[set[int]]:
    if subset == "dev":
        return set(pd.read_csv(DEV_MANIFEST)["gt_record_id"].astype(int))
    if subset == "heldout":
        return set(pd.read_csv(HELDOUT_IDS)["gt_record_id"].astype(int))
    if subset == "all":
        return None
    raise ValueError("subset must be dev, heldout or all")


def _rule_inputs(output: dict) -> dict:
    """Extracted features -> rule inputs. Enum underscores become spaces so that
    ``genetic_analysis`` and ``species_richness`` hit the same rules as the annotation text."""
    data_type = output.get("data_type") or []
    if isinstance(data_type, str):
        data_type = [data_type]
    feats = features_from_row({k: output.get(k) for k in (
        "temp_range_i", "temp_range_f", "spatial_range_km2", "multispecies", "threatened_species",
        "new_species_science", "new_species_region", "bias_north_south")})
    feats["data_type"] = ", ".join(str(d).replace("_", " ") for d in data_type) or None
    return feats


def predictions(run_json: str | Path, subset: str = "dev") -> pd.DataFrame:
    """Predicted category per record of a run, with the predicted intermediate classes
    when the category comes from the rules. Records that failed extraction are kept with
    no prediction (they count as errors, not as missing)."""
    run = json.loads(Path(run_json).read_text())
    allowed = subset_ids(subset)
    rows = []
    for rec in run["records"]:
        gid = int(rec["gt_record_id"])
        if allowed is not None and gid not in allowed:
            continue
        out = rec.get("output") if rec.get("status") == "success" else None
        row: dict[str, Any] = {"gt_record_id": gid, "status": rec.get("status")}
        if out is None:
            row["pred"] = None
        elif out.get("relevance") is not None:
            row["pred"] = _clean(out["relevance"])
            row["route"] = "direct"
        else:
            res = classify_features(_rule_inputs(out))
            row.update(pred=res.relevance_modifiers, route="rules", pred_dataset_type=res.dataset_type,
                       pred_temporal=res.temporal, pred_spatial=res.spatial)
        rows.append(row)
    df = pd.DataFrame(rows).set_index("gt_record_id")
    return df.join(targets(), how="left")


def _kappa(y: np.ndarray, p: np.ndarray) -> float:
    labels = list(LABELS)
    n = len(y)
    if n == 0:
        return float("nan")
    po = float(np.mean(y == p))
    pe = sum((np.sum(y == lab) / n) * (np.sum(p == lab) / n) for lab in labels)
    return float("nan") if pe == 1 else (po - pe) / (1 - pe)


def _scores(y: np.ndarray, p: np.ndarray) -> dict[str, float]:
    """Four-class accuracy and kappa; binary (H+M relevant) precision, recall, F1."""
    yb = np.isin(y, list(RELEVANT_LABELS))
    pb = np.isin(p, list(RELEVANT_LABELS))
    tp, fp, fn = int(np.sum(yb & pb)), int(np.sum(~yb & pb)), int(np.sum(yb & ~pb))
    return {
        "acc4": float(np.mean(y == p)) if len(y) else float("nan"),
        "kappa4": _kappa(y, p),
        "acc2": float(np.mean(yb == pb)) if len(y) else float("nan"),
        "precision": tp / (tp + fp) if tp + fp else float("nan"),
        "recall": tp / (tp + fn) if tp + fn else float("nan"),
        "f1": 2 * tp / (2 * tp + fp + fn) if (2 * tp + fp + fn) else float("nan"),
    }


def score(df: pd.DataFrame, target: str = "rule", n_boot: int = 2000, seed: int = 0) -> dict[str, Any]:
    """Scores against ``target`` ("rule" or "human") with 95 % bootstrap intervals.
    Records without that target label are left out; failed predictions count as wrong
    (predicted ``None``)."""
    d = df[df[target].notna()]
    y = d[target].to_numpy(dtype=object)
    p = d["pred"].fillna("none").to_numpy(dtype=object)
    point = _scores(y, p)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(d), size=(n_boot, len(d))) if len(d) else np.zeros((0, 0), int)
    boots = [_scores(y[i], p[i]) for i in idx]
    ci = {}
    for k, v in point.items():
        vals = np.array([b[k] for b in boots], dtype=float)
        vals = vals[~np.isnan(vals)]
        ci[k] = (v, *(np.percentile(vals, [2.5, 97.5]) if len(vals) else (np.nan, np.nan)))
    conf = pd.crosstab(pd.Series(y, name=f"{target} label"), pd.Series(p, name="predicted"))
    conf = conf.reindex(index=list(LABELS), columns=list(LABELS) + (["none"] if "none" in p else []), fill_value=0)
    direction = Counter(
        "over" if pp in LABELS and LABELS.index(pp) < LABELS.index(yy) else
        "under" if pp in LABELS and LABELS.index(pp) > LABELS.index(yy) else
        "exact" if pp == yy else "failed"
        for yy, pp in zip(y, p)
    )
    return {"n": len(d), "scores": ci, "confusion": conf, "direction": dict(direction)}


def error_attribution(df: pd.DataFrame) -> pd.DataFrame:
    """For rule-based predictions: per intermediate class, how often the extracted class
    differs from the released one, split by whether the final category was right.
    Tells which feature (data type, temporal, spatial, modulators) drives wrong categories."""
    d = df[(df.get("route") == "rules") & df["rule"].notna()].copy()
    if d.empty:
        return pd.DataFrame()
    d["final_right"] = d["pred"] == d["rule"]
    rows = []
    for c in COMPONENTS:
        wrong = d[f"pred_{c}"] != d[f"true_{c}"]
        rows.append({
            "component": c,
            "wrong_component": int(wrong.sum()),
            "wrong_component_and_final_wrong": int((wrong & ~d["final_right"]).sum()),
            "most_common_error": Counter(
                f"{t}->{p}" for t, p in zip(d.loc[wrong, f"true_{c}"], d.loc[wrong, f"pred_{c}"])
            ).most_common(3),
        })
    return pd.DataFrame(rows)


def summarize(run_json: str | Path, subset: str = "dev") -> str:
    df = predictions(run_json, subset)
    run = json.loads(Path(run_json).read_text())
    route = df["route"].dropna().unique().tolist() if "route" in df else []
    lines = [f"Run: {run.get('name')}  model={run.get('model')}  effort={run.get('reasoning_effort')}  "
             f"mode={run.get('mode')}  route={'/'.join(route) or 'n/a'}  subset={subset}", ""]
    for target in ("rule", "human"):
        s = score(df, target)
        lines.append(f"Target: {target} label  (n={s['n']})")
        for k, (v, lo, hi) in s["scores"].items():
            lines.append(f"  {k:<10}{v:6.2f} [{lo:.2f}, {hi:.2f}]")
        lines.append(f"  direction vs target: {s['direction']}")
        lines.append(s["confusion"].to_string())
        lines.append("")
    att = error_attribution(df)
    if not att.empty:
        lines += ["Error attribution (rule label; extracted vs released intermediate class):", att.to_string(index=False)]
    return "\n".join(lines)


def main(argv: Optional[list[str]] = None) -> None:
    ap = argparse.ArgumentParser(description="Relevance scores of a run against the rule and human labels.")
    ap.add_argument("run_json")
    ap.add_argument("--subset", default="dev", choices=["dev", "heldout", "all"])
    a = ap.parse_args(argv)
    print(summarize(a.run_json, a.subset))


if __name__ == "__main__":
    main()
