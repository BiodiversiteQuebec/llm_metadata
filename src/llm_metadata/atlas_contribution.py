"""What would a dataset add to the Biodiversité Québec Atlas? Four separate scores.

Each score is in [0, 1], 1 meaning "fills a gap", and is computed per dataset from the
taxa, places and years matched by ``llm_metadata.atlas_match``. They are kept apart on
purpose: a dataset can bring a new taxon to a well-sampled region, or an old decade of a
common group, and one number would hide which. See ``docs/atlas_contribution/scores.md``.

* **Taxonomic novelty**: are the dataset's taxa absent or rare in the Atlas for the
  regions it covers? Per taxon matched below the group rank, with ``n`` Atlas
  observations in those regions::

      novelty = 1 - min(1, log10(1 + n) / log10(1 + k_taxon))

  0 observations -> 1; ``k_taxon`` observations or more -> 0 (default 100).
  The dataset score is the mean over its taxa. Taxa absent from the Atlas extract are
  left out by default (``absent_policy="skip"``): the extract has no sensitive species,
  so "absent" often means "at risk", not "new".

* **Spatial novelty**: are the dataset's regions under-sampled for its groups, relative to
  the province? Per group and region, ``ratio`` = (observations per km² of the group in
  the region) / (the same for the whole province)::

      spatial = clip(log10(1 / ratio) / log10(k_spatial), 0, 1)

  At or above the provincial density -> 0; ``k_spatial`` times sparser or worse -> 1
  (default 10). Unknown place -> no score.

* **Temporal gain**: does the dataset cover decades the Atlas lacks for these groups and
  regions? Per group, region and decade covered, ``q`` = Atlas observations in that
  decade / observations in the best-covered decade of the same group and region::

      temporal = clip(log10(1 / q) / log10(k_temporal), 0, 1)

  The best decade -> 0; ``k_temporal`` times fewer records or worse -> 1 (default 10).

* **Group gap**: does the dataset hold groups the Atlas under-represents? Per group,
  ``effort`` = Atlas observations per species the Atlas holds for the group (whole
  province), compared with the median group::

      group_gap = clip(log10(median_effort / effort) / log10(k_group), 0, 1)

  At or above the median effort -> 0; ``k_group`` times less effort or worse -> 1
  (default 10).

Datasets with several groups are averaged with each taxon mention weighing 1, spread
over its groups ("benthic invertebrates" counts a quarter for each invertebrate group).
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any, Callable, Iterable, Optional, Sequence

import numpy as np
import pandas as pd

from llm_metadata.atlas_match import (
    NORTH_REF,
    PERIODS,
    PROVINCE,
    PROVINCE_REF,
    REGION_NORTH,
    AtlasReference,
    PlaceMatch,
    RegionRef,
    TaxonMatch,
    match_place,
    match_taxa,
    periods_for_years,
    places_from_north_flag,
    scope_regions,
)

SCORES: tuple[str, ...] = ("taxonomic", "spatial", "temporal", "group_gap")
SCORE_LABELS = {
    "taxonomic": "Taxonomic novelty",
    "spatial": "Spatial novelty",
    "temporal": "Temporal gain",
    "group_gap": "Group gap",
}

GT_JSON = "data/gt/fuster_gt.json"
RAW_XLSX = "data/dataset_092624.xlsx"
HELDOUT_IDS = "data/manifests/heldout_ids.csv"


@dataclass(frozen=True)
class Thresholds:
    """Every tunable number of the scores, with its default and meaning.

    k_taxon: Atlas observations of a taxon in the dataset's regions at which it counts as
        well covered (novelty 0).
    k_spatial: how many times sparser than the provincial density a region must be, for
        the group, to count as fully under-sampled (spatial 1).
    k_temporal: how many times fewer records a decade must hold than the group's best
        decade in the region to count as fully missing (temporal 1).
    k_group: how many times less sampling effort (observations per species) than the
        median group a group must have to count as fully under-represented (gap 1).
    gap_cut: score from which a dataset is said to "fill" that gap (used only for the
        summary count of gaps filled).
    absent_policy: "skip" leaves taxa absent from the Atlas extract out of taxonomic
        novelty (they may be sensitive species); "novel" scores them 1.
    """

    k_taxon: float = 100.0
    k_spatial: float = 10.0
    k_temporal: float = 10.0
    k_group: float = 10.0
    gap_cut: float = 0.5
    absent_policy: str = "skip"


#: Which score each threshold drives (for the sensitivity check).
THRESHOLD_SCORE = {"k_taxon": "taxonomic", "k_spatial": "spatial", "k_temporal": "temporal", "k_group": "group_gap", "gap_cut": "n_gaps"}


# ---------------------------------------------------------------------------
# Dataset description
# ---------------------------------------------------------------------------


@dataclass
class DatasetDescription:
    """A dataset as seen by the scores: matched taxa, places and decades."""

    record_id: str
    taxa: list[TaxonMatch]
    places: list[PlaceMatch]
    periods: list[str]
    source: str = "annotation"
    title: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def regions(self) -> list[RegionRef]:
        return scope_regions(self.places)

    @property
    def place_known(self) -> bool:
        return any(p.level not in {"unknown", "unmatched", "outside"} for p in self.places)

    @property
    def group_weights(self) -> dict[str, float]:
        """Share of the dataset's usable taxon mentions in each Atlas group (sums to 1)."""
        w: dict[str, float] = {}
        for t in self.taxa:
            if t.status in {"matched", "absent", "group"} and t.groups:
                for g in t.groups:
                    w[g] = w.get(g, 0.0) + 1.0 / len(t.groups)
        total = sum(w.values())
        return {g: v / total for g, v in w.items()} if total else {}


def _log_gap(ratio: float, k: float) -> float:
    """clip(log10(1 / ratio) / log10(k), 0, 1); a ratio of 0 is a full gap."""
    if ratio <= 0:
        return 1.0
    return float(min(1.0, max(0.0, math.log10(1.0 / ratio) / math.log10(k))))


def _weighted_mean(pairs: Iterable[tuple[float, float]]) -> float:
    pairs = [(v, w) for v, w in pairs if w > 0 and not math.isnan(v)]
    total = sum(w for _, w in pairs)
    return sum(v * w for v, w in pairs) / total if total else float("nan")


# ---------------------------------------------------------------------------
# The four scores
# ---------------------------------------------------------------------------


def taxonomic_novelty(desc: DatasetDescription, atlas: AtlasReference, th: Thresholds = Thresholds()) -> float:
    vals = []
    for t in desc.taxa:
        if not t.below_group:
            continue
        if t.status == "absent":
            if th.absent_policy == "novel":
                vals.append(1.0)
            continue
        n = sum(atlas.taxon_observations(t.rank, t.name, r) for r in desc.regions)
        vals.append(1.0 - min(1.0, math.log10(1 + n) / math.log10(1 + th.k_taxon)))
    return float(np.mean(vals)) if vals else float("nan")


def spatial_novelty(desc: DatasetDescription, atlas: AtlasReference, th: Thresholds = Thresholds()) -> float:
    weights = desc.group_weights
    if not weights or not desc.place_known:
        return float("nan")
    prov_area = atlas.area(PROVINCE_REF)
    pairs = []
    for g, w in weights.items():
        prov_density = atlas.group_observations(g, PROVINCE_REF) / prov_area
        for r in desc.regions:
            if r.region_type == PROVINCE or prov_density == 0:
                pairs.append((0.0, w))
                continue
            density = atlas.group_observations(g, r) / atlas.area(r)
            pairs.append((_log_gap(density / prov_density, th.k_spatial), w))
    return _weighted_mean(pairs)


def temporal_gain(desc: DatasetDescription, atlas: AtlasReference, th: Thresholds = Thresholds()) -> float:
    weights = desc.group_weights
    periods = [p for p in desc.periods if p in PERIODS]
    if not weights or not periods:
        return float("nan")
    pairs = []
    for g, w in weights.items():
        for r in desc.regions:
            by_decade = {p: atlas.group_observations(g, r, p) for p in PERIODS}
            best = max(by_decade.values())
            for p in periods:
                pairs.append((_log_gap(by_decade[p] / best if best else 0.0, th.k_temporal), w / len(periods)))
    return _weighted_mean(pairs)


def group_effort(atlas: AtlasReference) -> pd.DataFrame:
    """Observations per species per group, whole province (the basis of the group gap)."""
    rows = []
    for g, n_sp in atlas.group_species_count.items():
        if g == "UNGROUPED" or not n_sp:
            continue
        obs = atlas.group_observations(g, PROVINCE_REF)
        rows.append({"taxon_group": g, "n_observations": obs, "n_species": n_sp, "obs_per_species": obs / n_sp})
    return pd.DataFrame(rows).sort_values("obs_per_species").reset_index(drop=True)


def group_gap_by_group(atlas: AtlasReference, th: Thresholds = Thresholds()) -> dict[str, float]:
    eff = group_effort(atlas)
    ref = float(eff["obs_per_species"].median())
    return {r.taxon_group: _log_gap(r.obs_per_species / ref, th.k_group) for r in eff.itertuples()}


def group_gap(desc: DatasetDescription, atlas: AtlasReference, th: Thresholds = Thresholds(),
              _cache: dict | None = None) -> float:
    weights = desc.group_weights
    if not weights:
        return float("nan")
    gaps = group_gap_by_group(atlas, th) if _cache is None else _cache
    return _weighted_mean((gaps.get(g, float("nan")), w) for g, w in weights.items())


def score_dataset(desc: DatasetDescription, atlas: AtlasReference, th: Thresholds = Thresholds(),
                  _gap_cache: dict | None = None) -> dict[str, Any]:
    """The four scores, the number of gaps filled, and what they rest on."""
    out: dict[str, Any] = {
        "record_id": desc.record_id,
        "taxonomic": taxonomic_novelty(desc, atlas, th),
        "spatial": spatial_novelty(desc, atlas, th),
        "temporal": temporal_gain(desc, atlas, th),
        "group_gap": group_gap(desc, atlas, th, _gap_cache),
    }
    avail = [out[s] for s in SCORES if not math.isnan(out[s])]
    out["n_scores"] = len(avail)
    # No score at all (no usable taxon) is "unknown", not "no gap".
    out["n_gaps"] = sum(v >= th.gap_cut for v in avail) if avail else float("nan")
    out["groups"] = ", ".join(f"{g}" for g, _ in sorted(desc.group_weights.items(), key=lambda kv: -kv[1]))
    out["regions"] = ", ".join(r.label for r in desc.regions) if desc.place_known else "unknown"
    out["periods"] = ", ".join(desc.periods)
    out["n_taxa"] = sum(t.status != "other" for t in desc.taxa)
    out["n_taxa_below_group"] = sum(t.below_group for t in desc.taxa)
    out["n_taxa_absent"] = sum(t.status == "absent" for t in desc.taxa)
    out["n_taxa_unresolved"] = sum(t.status == "unresolved" for t in desc.taxa)
    return out


def score_all(descs: Sequence[DatasetDescription], atlas: AtlasReference, th: Thresholds = Thresholds()) -> pd.DataFrame:
    gaps = group_gap_by_group(atlas, th)
    rows = [score_dataset(d, atlas, th, gaps) for d in descs]
    df = pd.DataFrame(rows).set_index("record_id")
    df["title"] = [d.title for d in descs]
    return df


# ---------------------------------------------------------------------------
# Building descriptions: from human annotations or from an extraction
# ---------------------------------------------------------------------------


def corpus_ids(include_heldout: bool = False, gt_json: str | Path = GT_JSON,
               heldout_csv: str | Path = HELDOUT_IDS) -> list[int]:
    """Valid record ids; the held-out ones only when asked (default: left out)."""
    rows = json.loads(Path(gt_json).read_text(encoding="utf-8"))
    heldout = set(pd.read_csv(heldout_csv)["gt_record_id"].astype(int))
    ids = [int(r["gt_record_id"]) for r in rows if r.get("valid_yn") == "yes"]
    return [i for i in ids if include_heldout or i not in heldout]


def titles(path: str | Path = RAW_XLSX) -> dict[int, str]:
    raw = pd.read_excel(path, usecols=["id", "title"]).drop_duplicates("id")
    return {int(i): str(t) for i, t in zip(raw["id"], raw["title"])}


def describe_annotation(row: dict, atlas: AtlasReference, *, cache: Any = None,
                        same_taxon: Optional[Callable] = None, south_as_province: bool = False,
                        resolver: Any = None) -> DatasetDescription:
    """A description from one annotated record (``data/gt/fuster_gt.json`` row).

    The annotations hold no place names: ``bias_north_south`` is the only clue
    (True -> north of the 49th parallel, False -> south, missing -> unknown).
    ``south_as_province`` reads False as "anywhere in Quebec" instead (sensitivity).
    """
    places = places_from_north_flag(row.get("bias_north_south"))
    if south_as_province and places[0].region is not None and places[0].region.region_name == "sud_49":
        places = [PlaceMatch("annotation: south read as Quebec-wide", "province", PROVINCE_REF)]
    return DatasetDescription(
        record_id=str(row["gt_record_id"]),
        taxa=match_taxa(row.get("species"), atlas, cache=cache, same_taxon=same_taxon, resolver=resolver),
        places=places,
        periods=periods_for_years(row.get("temp_range_i"), row.get("temp_range_f")),
        source="annotation",
        extra={"bias_north_south": row.get("bias_north_south"), "threatened_species": row.get("threatened_species"),
               "data_type": row.get("data_type")},
    )


def describe_extraction(record_id: str, extraction: Any, atlas: AtlasReference, *, cache: Any = None,
                        same_taxon: Optional[Callable] = None, resolver: Any = None) -> DatasetDescription:
    """A description from an ``AtlasContributionExtraction`` (or its dict)."""
    data = extraction.model_dump() if hasattr(extraction, "model_dump") else dict(extraction)
    names = []
    for t in data.get("focal_taxa") or []:
        name = t.get("scientific_name") or t.get("verbatim_name")
        if name:
            names.append(name)
    places = [match_place(p.get("name", ""), in_quebec=p.get("in_quebec"), north_of_49=p.get("north_of_49"))
              for p in data.get("places") or []]
    if not places:
        places = [PlaceMatch("no place stated", "unknown", PROVINCE_REF)]
    return DatasetDescription(
        record_id=str(record_id),
        taxa=match_taxa(names, atlas, cache=cache, same_taxon=same_taxon, resolver=resolver),
        places=places,
        periods=periods_for_years(data.get("year_start"), data.get("year_end")),
        source="extraction",
        extra={"record_kind": data.get("record_kind"), "occurrence_records_available": data.get("occurrence_records_available")},
    )


def annotation_descriptions(atlas: AtlasReference, *, include_heldout: bool = False, cache: Any = None,
                            same_taxon: Optional[Callable] = None, south_as_province: bool = False,
                            gt_json: str | Path = GT_JSON, raw_xlsx: Optional[str | Path] = RAW_XLSX) -> list[DatasetDescription]:
    """Descriptions of the valid annotated records. Held-out records are read only when
    ``include_heldout=True`` (after the frozen held-out pass)."""
    ids = set(corpus_ids(include_heldout, gt_json))
    rows = [r for r in json.loads(Path(gt_json).read_text(encoding="utf-8")) if int(r["gt_record_id"]) in ids]
    names = titles(raw_xlsx) if raw_xlsx else {}
    out = []
    for r in rows:
        d = describe_annotation(r, atlas, cache=cache, same_taxon=same_taxon, south_as_province=south_as_province)
        d.title = names.get(int(r["gt_record_id"]), "")
        out.append(d)
    return out


# ---------------------------------------------------------------------------
# Sensitivity, comparison with the Fuster relevance, case study
# ---------------------------------------------------------------------------


def spearman(a: Sequence[float], b: Sequence[float]) -> tuple[float, int]:
    """Spearman rank correlation on pairs where both values exist (ties get mean ranks)."""
    s = pd.DataFrame({"a": a, "b": b}).dropna()
    if len(s) < 3 or s["a"].nunique() < 2 or s["b"].nunique() < 2:
        return float("nan"), len(s)
    return float(s["a"].rank().corr(s["b"].rank())), len(s)


def spearman_ci(a: Sequence[float], b: Sequence[float], n_boot: int = 2000, seed: int = 0) -> tuple[float, float, float, int]:
    """Spearman with a 95 % bootstrap interval over records: (rho, low, high, n)."""
    s = pd.DataFrame({"a": list(a), "b": list(b)}).dropna().reset_index(drop=True)
    rho, n = spearman(s["a"], s["b"])
    if math.isnan(rho):
        return rho, float("nan"), float("nan"), n
    rng = np.random.default_rng(seed)
    boots = []
    for _ in range(n_boot):
        i = rng.integers(0, n, n)
        r, _ = spearman(s["a"].to_numpy()[i], s["b"].to_numpy()[i])
        if not math.isnan(r):
            boots.append(r)
    lo, hi = np.percentile(boots, [2.5, 97.5]) if boots else (float("nan"), float("nan"))
    return rho, float(lo), float(hi), n


def share_changed(a: pd.Series, b: pd.Series) -> float:
    """Share of datasets whose score moved (missing on both sides counts as unchanged)."""
    x, y = a.to_numpy(dtype=float), b.reindex(a.index).to_numpy(dtype=float)
    return float(np.mean(~np.isclose(x, y, equal_nan=True))) if len(x) else float("nan")


def sensitivity(descs: Sequence[DatasetDescription], atlas: AtlasReference, base: Thresholds = Thresholds(),
                factors: Sequence[float] = (0.5, 1.5), top: int = 20) -> pd.DataFrame:
    """Vary each threshold by the given factors; report how the ranking of datasets on the
    score it drives moves (Spearman with the baseline, overlap of the top datasets)."""
    ref = score_all(descs, atlas, base)
    rows = []
    for name, score in THRESHOLD_SCORE.items():
        for f in factors:
            th = replace(base, **{name: getattr(base, name) * f})
            new = score_all(descs, atlas, th)
            rho, n = spearman(ref[score], new[score])
            a = ref[score].dropna().sort_values(ascending=False, kind="stable")
            b = new[score].dropna().sort_values(ascending=False, kind="stable")
            k = min(top, len(a))
            overlap = len(set(a.index[:k]) & set(b.index[:k])) / k if k else float("nan")
            changed = share_changed(ref[score], new[score])
            rows.append({"threshold": name, "factor": f, "value": getattr(th, name), "score": score,
                         "spearman": rho, "n": n, f"top{top}_overlap": overlap, "share_changed": changed,
                         "mean_before": ref[score].mean(), "mean_after": new[score].mean()})
    return pd.DataFrame(rows)


FUSTER_ORDER = {"X": 0, "L": 1, "M": 2, "H": 3}


def compare_with_fuster(scores: pd.DataFrame, labels: pd.Series) -> dict[str, Any]:
    """Rank correlation of each score with the Fuster rule label (X < L < M < H), and a
    cross-table of the label against the number of gaps filled."""
    df = scores.join(labels.rename("fuster"), how="left")
    df = df[df["fuster"].notna()].copy()
    df["fuster_rank"] = df["fuster"].map(FUSTER_ORDER)
    corr = {s: spearman(df[s], df["fuster_rank"]) for s in (*SCORES, "n_gaps")}
    ci = {s: spearman_ci(df[s], df["fuster_rank"]) for s in (*SCORES, "n_gaps")}
    table = pd.crosstab(df["fuster"], df["n_gaps"], margins=True).reindex(["H", "M", "L", "X", "All"])
    return {"n": len(df), "spearman": corr, "spearman_ci": ci, "crosstab": table, "frame": df}


def restrict(desc: DatasetDescription, group: str, regions: Sequence[RegionRef]) -> DatasetDescription:
    """The part of a dataset about one group, scored over the given regions."""
    taxa = [replace(t, groups=(group,)) for t in desc.taxa if group in t.groups]
    places = [PlaceMatch(r.label, "region" if r.region_type == "admin" else "north_south", r) for r in regions]
    return replace(desc, taxa=taxa, places=places)


def is_north(desc: DatasetDescription) -> bool:
    """True if any place is north of the 49th parallel (nord_49 or a northern region)."""
    for r in desc.regions:
        if r == NORTH_REF or (r.region_type == "admin" and REGION_NORTH.get(r.region_name) is True):
            return True
    return False


def case_study(descs: Sequence[DatasetDescription], atlas: AtlasReference, *, group: str = "INSECTS",
               th: Thresholds = Thresholds()) -> pd.DataFrame:
    """Rank datasets for one group north of the 49th parallel.

    The scripts call it with ``absent_policy="novel"``: few insects carry a legal status
    in Québec, so an insect absent from the extract is most likely truly absent.

    Candidates hold at least one taxon of the group. Each is scored on that group alone:
    north of the 49th parallel when the dataset is known to be there, else over its own
    regions (the province when unknown). Spatial novelty and group gap are then the same
    for every northern candidate, so the ranking uses ``query_score``, the mean of
    taxonomic novelty and temporal gain when available.
    Order: datasets known to be north first, then the share of the dataset's taxa in the
    group, then ``query_score``.
    """
    rows = []
    gaps = group_gap_by_group(atlas, th)
    for d in descs:
        share = d.group_weights.get(group, 0.0)
        if share == 0:
            continue
        north = is_north(d)
        sub = restrict(d, group, [NORTH_REF] if north else d.regions)
        if not d.place_known:
            sub.places = [PlaceMatch("unknown", "unknown", PROVINCE_REF)]
        s = score_dataset(sub, atlas, th, gaps)
        query = [s[k] for k in ("taxonomic", "temporal") if not math.isnan(s[k])]
        rows.append({
            "record_id": d.record_id, "title": d.title, "north": north,
            "place": ", ".join(r.label for r in d.regions) if d.place_known else "unknown",
            "group_share": share, **{k: s[k] for k in SCORES},
            "query_score": float(np.mean(query)) if query else float("nan"),
            "periods": ", ".join(d.periods),
            "n_taxa_absent": sum(t.status == "absent" for t in sub.taxa),
            "taxa": "; ".join(t.mention for t in d.taxa if group in t.groups),
        })
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    return df.sort_values(["north", "group_share", "query_score"], ascending=[False, False, False],
                          na_position="last").reset_index(drop=True)


def coverage_north_south(atlas: AtlasReference) -> pd.DataFrame:
    """Observations per 1 000 km² by group, north and south of the 49th parallel (aggregates only)."""
    rows = []
    south = RegionRef("admin_nord_sud", "sud_49")
    for g in atlas.group_names:
        if g == "UNGROUPED":
            continue
        n_n, n_s = atlas.group_observations(g, NORTH_REF), atlas.group_observations(g, south)
        rows.append({
            "taxon_group": g, "obs_north": n_n, "obs_south": n_s,
            "per_1000km2_north": 1000 * n_n / atlas.area(NORTH_REF),
            "per_1000km2_south": 1000 * n_s / atlas.area(south),
            "share_north": n_n / (n_n + n_s) if n_n + n_s else float("nan"),
        })
    df = pd.DataFrame(rows)
    df["south_to_north_ratio"] = df["per_1000km2_south"] / df["per_1000km2_north"]
    return df.sort_values("per_1000km2_south", ascending=False).reset_index(drop=True)


__all__ = [
    "DatasetDescription",
    "SCORES",
    "Thresholds",
    "annotation_descriptions",
    "case_study",
    "compare_with_fuster",
    "corpus_ids",
    "coverage_north_south",
    "describe_annotation",
    "describe_extraction",
    "group_effort",
    "group_gap",
    "score_all",
    "score_dataset",
    "sensitivity",
    "spatial_novelty",
    "spearman",
    "taxonomic_novelty",
    "temporal_gain",
]
