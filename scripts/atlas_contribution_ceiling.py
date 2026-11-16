"""Atlas contribution scores from the human annotations (the ceiling), no API cost.

    uv run python scripts/atlas_contribution_ceiling.py \
        --species-csv /path/to/artifacts/atlas/species_region_decade.csv [--include-heldout]

Held-out records are left out unless ``--include-heldout`` is given (only after the
frozen held-out pass). GBIF answers are cached in ``data/gbif/atlas_contribution_cache.json``.

Writes, dataset-level only (committed):
    docs/atlas_contribution/ceiling_scores.csv, ceiling_match_rates.csv,
    ceiling_sensitivity.csv, ceiling_fuster_crosstab.csv, case_insects_north.csv,
    group_effort.csv, coverage_north_south.csv, fig_coverage_north_south.png
and, per taxon (git-ignored, holds per-species Atlas status):
    artifacts/atlas/ceiling_taxon_matches.csv
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

from llm_metadata.atlas_contribution import (  # noqa: E402
    SCORES,
    Thresholds,
    annotation_descriptions,
    case_study,
    compare_with_fuster,
    coverage_north_south,
    group_effort,
    score_all,
    sensitivity,
    share_changed,
    spearman,
)
from llm_metadata.atlas_match import AtlasReference, gbif_same_taxon, match_rates  # noqa: E402
from llm_metadata.gbif import GBIFCache  # noqa: E402
from llm_metadata.relevance_eval import targets  # noqa: E402

OUT = Path("docs/atlas_contribution")
PRIVATE = Path("artifacts/atlas")
CACHE = "data/gbif/atlas_contribution_cache.json"

GROUP_NAMES = {
    "ALGAE": "Algae", "AMPHIBIANS": "Amphibians", "BIRDS": "Birds", "FISH": "Fish", "FUNGI": "Fungi and lichens",
    "INSECTS": "Insects", "MAMMALS": "Mammals", "MICROORGANISMS": "Microorganisms", "MOLLUSKS": "Molluscs",
    "NON_VASCULAR_PLANTS": "Mosses and liverworts", "OTHER_ARTHROPODS": "Other arthropods",
    "OTHER_INVERTEBRATES": "Other invertebrates", "REPTILES": "Reptiles", "VASCULAR_PLANTS": "Vascular plants",
}


def figure(cov: pd.DataFrame, path: Path) -> None:
    """Observations per 1 000 km², north vs south of the 49th parallel, per group (log scale)."""
    d = cov.sort_values("per_1000km2_south", ascending=True)
    y = np.arange(len(d))
    fig, ax = plt.subplots(figsize=(7.5, 5.2))
    south_c, north_c = "#4a6fa5", "#d08c2f"
    for yi, s, n in zip(y, d["per_1000km2_south"], d["per_1000km2_north"]):
        ax.plot([n, s], [yi, yi], color="#c9c9c9", lw=1.5, zorder=1)
    ax.scatter(d["per_1000km2_south"], y, color=south_c, s=36, zorder=2, label="South of the 49th parallel (25 % of the area)")
    ax.scatter(d["per_1000km2_north"], y, color=north_c, s=36, zorder=2, label="North of the 49th parallel (75 % of the area)")
    ax.set_xscale("log")
    ax.set_yticks(y, [GROUP_NAMES.get(g, g) for g in d["taxon_group"]])
    for tick, g in zip(ax.get_yticklabels(), d["taxon_group"]):
        if g == "INSECTS":  # the case study group
            tick.set_fontweight("bold")
    for yi, r in zip(y, d["south_to_north_ratio"]):
        ax.annotate(f"×{r:,.0f}", (d["per_1000km2_south"].iloc[yi], yi), xytext=(6, -3), textcoords="offset points",
                    fontsize=7.5, color="#555555")
    ax.set_xlabel("Atlas observations per 1 000 km² (log scale), all decades")
    ax.set_title("Atlas coverage is far thinner north of the 49th parallel, for every group", fontsize=10.5, loc="left")
    ax.legend(frameon=False, fontsize=8, loc="lower right")
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="x", color="#eeeeee", lw=0.6)
    fig.text(0.01, 0.01, "Source: Biodiversité Québec Atlas (staging, 2026-11-15), sensitive species excluded. "
             "×N: times denser in the south.", fontsize=7, color="#666666")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(path, dpi=200)
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--species-csv", required=True, help="Per-species Atlas table (git-ignored)")
    ap.add_argument("--include-heldout", action="store_true", help="Add the held-out records (after the frozen pass only)")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    PRIVATE.mkdir(parents=True, exist_ok=True)

    atlas = AtlasReference.load(args.species_csv)
    cache = GBIFCache(CACHE)
    same = gbif_same_taxon(cache)
    descs = annotation_descriptions(atlas, include_heldout=args.include_heldout, cache=cache, same_taxon=same)
    suffix = "_with_heldout" if args.include_heldout else ""

    # Match rates (per mention and per dataset); per-taxon detail stays private.
    rows = [{"record_id": d.record_id, **t.to_dict()} for d in descs for t in d.taxa]
    pd.DataFrame(rows).to_csv(PRIVATE / f"ceiling_taxon_matches{suffix}.csv", index=False)
    rates = match_rates([t for d in descs for t in d.taxa])
    with_taxa = [d for d in descs if any(t.status != "other" for t in d.taxa)]
    per_ds = {
        "n_records": len(descs),
        "n_records_with_taxa": len(with_taxa),
        "n_records_any_usable_taxon": sum(any(t.status in {"matched", "absent", "group"} for t in d.taxa) for d in descs),
        "n_records_any_below_group": sum(any(t.status == "matched" and t.rank != "group" for t in d.taxa) for d in descs),
        "n_records_place_north": sum(str(d.extra.get("bias_north_south")) == "True" for d in descs),
        "n_records_place_south": sum(str(d.extra.get("bias_north_south")) == "False" for d in descs),
        "n_records_with_years": sum(bool(d.periods) for d in descs),
    }
    mr = pd.DataFrame([{**{k: v for k, v in rates.items() if k != "by_rank"},
                        **{f"rank_{k}": v for k, v in rates["by_rank"].items()}, **per_ds}]).T
    mr.columns = ["value"]
    mr.to_csv(OUT / f"ceiling_match_rates{suffix}.csv")

    th = Thresholds()
    scores = score_all(descs, atlas, th)
    lab = targets()["rule"]
    lab.index = lab.index.astype(str)
    scores = scores.join(lab.rename("fuster_rule"))
    scores.round(3).to_csv(OUT / f"ceiling_scores{suffix}.csv")

    # Structural variants: absent species scored as new; "south" read as Quebec-wide.
    variants = {}
    variants["absent_novel"] = score_all(descs, atlas, Thresholds(absent_policy="novel"))
    descs_sp = annotation_descriptions(atlas, include_heldout=args.include_heldout, cache=cache, same_taxon=same,
                                       south_as_province=True)
    variants["south_as_province"] = score_all(descs_sp, atlas, th)

    sens = sensitivity(descs, atlas, th)
    struct = []
    for name, v in variants.items():
        for s in (*SCORES, "n_gaps"):
            rho, n = spearman(scores[s], v[s])
            struct.append({"threshold": name, "factor": np.nan, "value": np.nan, "score": s, "spearman": rho, "n": n,
                           "top20_overlap": np.nan,
                           "share_changed": share_changed(scores[s], v[s]),
                           "mean_before": scores[s].mean(), "mean_after": v[s].mean()})
    sens = pd.concat([sens, pd.DataFrame(struct)], ignore_index=True)
    sens.round(3).to_csv(OUT / f"ceiling_sensitivity{suffix}.csv", index=False)

    # Between-score correlations (is a composite justified?)
    corr = pd.DataFrame({a: {b: spearman(scores[a], scores[b])[0] for b in SCORES} for a in SCORES})
    corr.round(2).to_csv(OUT / f"ceiling_score_correlations{suffix}.csv")

    comp = compare_with_fuster(scores.drop(columns=["fuster_rule"]), lab)
    comp["crosstab"].to_csv(OUT / f"ceiling_fuster_crosstab{suffix}.csv")
    fus = {s: {"rho": r, "ci95": [lo, hi], "n": n} for s, (r, lo, hi, n) in comp["spearman_ci"].items()}
    for name, v in variants.items():
        c = compare_with_fuster(v, lab)
        fus[f"n_gaps ({name})"] = {"rho": c["spearman"]["n_gaps"][0], "n": c["spearman"]["n_gaps"][1]}
    # The rule label upgrades a record flagged north (a modulator), which is also our only
    # place clue: compare with the label before modulators too.
    raw = pd.read_excel("data/dataset_092624.xlsx", usecols=["id", "MC_relevance"]).drop_duplicates("id")
    raw = raw[raw["id"].astype(str).isin(scores.index)]
    pre = pd.Series(raw["MC_relevance"].where(raw["MC_relevance"].isin(list("HMLX"))).values,
                    index=raw["id"].astype(str))
    c = compare_with_fuster(scores.drop(columns=["fuster_rule"]), pre)
    for s, (r, lo, hi, n) in c["spearman_ci"].items():
        fus[f"{s} (label before modulators)"] = {"rho": r, "ci95": [lo, hi], "n": n}
    c["crosstab"].to_csv(OUT / f"ceiling_fuster_premodulator_crosstab{suffix}.csv")
    (OUT / f"ceiling_fuster_spearman{suffix}.json").write_text(json.dumps(fus, indent=2))

    # Few insects carry a legal status in Québec: an insect absent from the extract is
    # most likely truly absent, so absent insect species count as new here.
    case = case_study(descs, atlas, group="INSECTS", th=Thresholds(absent_policy="novel"))
    case.round(3).to_csv(OUT / f"case_insects_north{suffix}.csv", index=False)

    group_effort(atlas).round(1).to_csv(OUT / "group_effort.csv", index=False)
    cov = coverage_north_south(atlas)
    cov.round(3).to_csv(OUT / "coverage_north_south.csv", index=False)
    figure(cov, OUT / "fig_coverage_north_south.png")

    print(mr.to_string())
    print(scores[list(SCORES) + ["n_gaps"]].describe().round(2).to_string())
    print("score correlations\n", corr.round(2).to_string())
    print("fuster spearman", json.dumps(fus, indent=1))
    print(comp["crosstab"].to_string())
    print(sens.round(3).to_string())
    print(case.head(15).to_string())


if __name__ == "__main__":
    main()
