"""Helpers for notebook-based taxonomic relevance evaluation."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Collection, Optional

from llm_metadata.gbif import ResolvedTaxon, resolve_species_list
from llm_metadata.groundtruth_eval import (
    EvaluationConfig,
    EvaluationReport,
    FieldEvalStrategy,
    evaluate_indexed,
)
from llm_metadata.schemas.data_paper import RunArtifact
from llm_metadata.schemas.fuster_features import (
    CoreFeatureModel,
    DatasetFeaturesEvaluation,
    DatasetFeaturesExtraction,
    DatasetFeaturesNormalized,
)
from llm_metadata.species_parsing import (
    extract_parsed_taxa,
    extract_species_richness_mentions,
    normalize_taxon_group,
    project_species_richness_counts,
    project_species_richness_group_keys,
)

_LIST_COLS = ["data_type", "geospatial_info_dataset", "species"]

DEFAULT_TAXONOMY_FIELD_STRATEGIES: dict[str, FieldEvalStrategy] = {
    "species": FieldEvalStrategy(match="enhanced_species", threshold=70),
    "species_richness_counts": FieldEvalStrategy(match="exact"),
    "species_richness_group_keys": FieldEvalStrategy(match="exact"),
    "taxon_broad_group_labels": FieldEvalStrategy(match="exact"),
    "gbif_keys": FieldEvalStrategy(match="exact"),
}
DEFAULT_TAXONOMY_FIELDS = list(DEFAULT_TAXONOMY_FIELD_STRATEGIES.keys())

_GBIF_GROUP_LABELS = {
    "class": {
        "AVES": "bird",
        "MAMMALIA": "mammal",
        "ACTINOPTERYGII": "fish",
        "ELASMOBRANCHII": "fish",
    },
    "order": {
        "COLEOPTERA": "beetle",
        "IXODIDA": "tick",
        "TROMBIDIFORMES": "mite",
        "MESOSTIGMATA": "mite",
        "SARCOPTIFORMES": "mite",
    },
    "family": {
        "CURCULIONIDAE": "weevil",
        "BRENTIDAE": "weevil",
        "ANTHRIBIDAE": "weevil",
        "ATTELABIDAE": "weevil",
    },
    "phylum": {
        "ARTHROPODA": "arthropod",
        "MOLLUSCA": "mollusc",
        "ANNELIDA": "annelid",
    },
}


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


def build_ground_truth_by_id(
    gt_path: str | Path = "data/dataset_092624_validated.xlsx",
    allowed_ids: Optional[Collection[int]] = None,
) -> dict[str, DatasetFeaturesNormalized]:
    """Load validated GT rows and return normalized feature models keyed by record id."""
    try:
        import pandas as pd  # type: ignore
    except ImportError as exc:
        raise ImportError(
            "pandas is required for taxonomy notebook helpers; install with `pip install pandas openpyxl`."
        ) from exc

    df = pd.read_excel(gt_path)
    for col in _LIST_COLS:
        if col in df.columns:
            df[col] = df[col].map(_parse_excel_val)

    allowed = {int(value) for value in allowed_ids} if allowed_ids is not None else None
    out: dict[str, DatasetFeaturesNormalized] = {}
    for _, row in df.iterrows():
        record_id = int(row["id"])
        if allowed is not None and record_id not in allowed:
            continue
        out[str(record_id)] = DatasetFeaturesNormalized.model_validate(row.to_dict())
    return out


def load_predictions_by_id(
    run_artifact_path: str | Path,
    model_type: type[DatasetFeaturesExtraction] = DatasetFeaturesExtraction,
) -> dict[str, DatasetFeaturesExtraction]:
    """Load successful predictions from a saved `RunArtifact` JSON."""
    artifact = RunArtifact.load_json(run_artifact_path)
    return artifact.predictions_by_id(model_type)  # type: ignore[return-value]


def project_taxon_broad_group_labels(
    model: CoreFeatureModel,
    *,
    use_gbif: bool = True,
    confidence_threshold: int = 80,
    accept_higherrank: bool = True,
    resolved_taxa: Optional[list[ResolvedTaxon]] = None,
) -> Optional[list[str]]:
    """Project a model into broad comparison-oriented group labels."""
    labels: set[str] = set()

    parsed_species = extract_parsed_taxa(model.species) or []
    richness_mentions = extract_species_richness_mentions(model.species) or []

    for mention in richness_mentions:
        if mention.normalized_group:
            labels.add(mention.normalized_group)

    for parsed in parsed_species:
        if parsed.is_group_description and parsed.vernacular:
            group = normalize_taxon_group(parsed.vernacular)
            if group:
                labels.add(group)

    if use_gbif and model.species:
        gbif_payload = resolved_taxa or resolve_species_list(
            list(model.species),
            confidence_threshold=confidence_threshold,
            accept_higherrank=accept_higherrank,
        )
        for resolved in gbif_payload:
            match = resolved.gbif_match
            if match is None:
                continue
            for rank_name, attr_name in (
                ("family", "family"),
                ("order", "order"),
                ("class", "class_name"),
                ("phylum", "phylum"),
            ):
                rank_value = getattr(match, attr_name, None)
                if not rank_value:
                    continue
                mapped = _GBIF_GROUP_LABELS[rank_name].get(str(rank_value).upper())
                if mapped:
                    labels.add(mapped)
                    break

    return sorted(labels) or None


def enrich_with_taxonomy(
    model: CoreFeatureModel,
    *,
    include_gbif: bool = True,
    gbif_confidence_threshold: int = 80,
    accept_higherrank: bool = True,
) -> DatasetFeaturesEvaluation:
    """Build an evaluation model populated with taxonomy-derived fields."""
    parsed_species = extract_parsed_taxa(model.species)
    richness_mentions = extract_species_richness_mentions(model.species)
    resolved_taxa: Optional[list[ResolvedTaxon]] = None

    if include_gbif and model.species:
        resolved_taxa = resolve_species_list(
            list(model.species),
            confidence_threshold=gbif_confidence_threshold,
            accept_higherrank=accept_higherrank,
        )

    broad_group_labels = project_taxon_broad_group_labels(
        model,
        use_gbif=include_gbif,
        confidence_threshold=gbif_confidence_threshold,
        accept_higherrank=accept_higherrank,
        resolved_taxa=resolved_taxa,
    )

    return DatasetFeaturesEvaluation.from_extraction(
        model,
        gbif=resolved_taxa,
        parsed_species=parsed_species,
        species_richness_mentions=richness_mentions,
        species_richness_counts=project_species_richness_counts(model.species, richness_mentions),
        species_richness_group_keys=project_species_richness_group_keys(richness_mentions),
        taxon_broad_group_labels=broad_group_labels,
    )


def enrich_indexed_models(
    models_by_id: dict[str, CoreFeatureModel],
    *,
    include_gbif: bool = True,
    gbif_confidence_threshold: int = 80,
    accept_higherrank: bool = True,
) -> dict[str, DatasetFeaturesEvaluation]:
    """Apply `enrich_with_taxonomy` to each record in an indexed model dictionary."""
    return {
        record_id: enrich_with_taxonomy(
            model,
            include_gbif=include_gbif,
            gbif_confidence_threshold=gbif_confidence_threshold,
            accept_higherrank=accept_higherrank,
        )
        for record_id, model in models_by_id.items()
    }


def build_taxonomy_eval_config(
    fields: Optional[Collection[str]] = None,
) -> EvaluationConfig:
    """Build an `EvaluationConfig` focused on taxonomic relevance fields."""
    field_names = list(fields) if fields is not None else DEFAULT_TAXONOMY_FIELDS
    strategies = {
        name: DEFAULT_TAXONOMY_FIELD_STRATEGIES[name]
        for name in field_names
        if name in DEFAULT_TAXONOMY_FIELD_STRATEGIES
    }
    return EvaluationConfig(field_strategies=strategies)


def evaluate_taxonomy_fields(
    *,
    true_by_id: dict[str, CoreFeatureModel],
    pred_by_id: dict[str, CoreFeatureModel],
    fields: Optional[Collection[str]] = None,
    include_gbif: bool = True,
    gbif_confidence_threshold: int = 80,
    accept_higherrank: bool = True,
    config: Optional[EvaluationConfig] = None,
) -> EvaluationReport:
    """Enrich both sides and evaluate a taxonomy-focused field subset."""
    eval_fields = list(fields) if fields is not None else DEFAULT_TAXONOMY_FIELDS
    eval_config = config or build_taxonomy_eval_config(eval_fields)

    true_enriched = enrich_indexed_models(
        true_by_id,
        include_gbif=include_gbif,
        gbif_confidence_threshold=gbif_confidence_threshold,
        accept_higherrank=accept_higherrank,
    )
    pred_enriched = enrich_indexed_models(
        pred_by_id,
        include_gbif=include_gbif,
        gbif_confidence_threshold=gbif_confidence_threshold,
        accept_higherrank=accept_higherrank,
    )

    return evaluate_indexed(
        true_by_id=true_enriched,
        pred_by_id=pred_enriched,
        fields=eval_fields,
        config=eval_config,
    )


# =============================================================================
# Multi-rank taxonomic evaluation of a run artifact
# =============================================================================
#
# Exact name matching penalises good extractions: "Atlantic salmon (Salmo
# salar)" vs "Atlantic salmon", "Rangifer tarandus caribou" vs "caribou",
# 73 weevil species listed by name vs "73 weevil species". The scorer below
# resolves both sides with `llm_metadata.gbif.resolve_taxon` and scores at
# several ranks. Count statements and broad-group labels get their own
# signals instead of being counted as missed species.
#
# Usage:
#     from llm_metadata.taxonomy_eval import evaluate_run_taxa
#     ev = evaluate_run_taxa("artifacts/runs/<run>.json")
#     ev.metrics_frame(); ev.items_frame()
# CLI:
#     uv run python -m llm_metadata.taxonomy_eval artifacts/runs/<run>.json

import json as _json
from dataclasses import dataclass as _dataclass, field as _field
from typing import Any, Iterable, Sequence

from llm_metadata.gbif import GBIFCache, TaxonRecord, resolve_taxon
from llm_metadata.species_parsing import TaxonMention, normalize_vernacular, split_taxon_items

#: Ranks scored, finest first. "exact" compares accepted backbone keys of the
#: named taxa (family rank or finer); "broad_group" compares `gbif.BROAD_GROUPS`.
RANKS: tuple[str, ...] = ("exact", "species", "genus", "family", "broad_group")
_RANK_LABELS = {
    "exact": "same taxon",
    "species": "same species",
    "genus": "same genus",
    "family": "same family",
    "broad_group": "same broad group",
}


@_dataclass
class TaxonItem:
    """One mention from a `species` list, with its resolution.

    kind:
        "taxon"      named taxon at family rank or finer (scored at every rank it reaches)
        "group"      broad-group label or taxon above family (broad-group rank + group signal)
        "count"      count statement; `record` is the counted group, if found
        "unresolved" a name GBIF could not resolve (scored as its own label)
        "other"      hybrid labels, noise ("and others"), labels without a taxon
    """

    record_id: str
    side: str  # "annotation" or "extraction"
    raw: str
    mention: str
    kind: str
    record: Optional[TaxonRecord] = None
    count: Optional[int] = None
    approximate: bool = False
    other_reason: Optional[str] = None
    # filled by scoring
    best_rank: Optional[str] = None
    status: str = ""
    reason: str = ""

    @property
    def name_key(self) -> tuple[str, str]:
        return ("name", normalize_vernacular(self.mention))

    def entry_at(self, rank: str) -> Any:
        """The comparison entry at a rank, or None when the item is not scored there."""
        if self.kind == "unresolved":
            return self.name_key
        if self.record is None or self.kind == "other":
            return None
        if rank == "broad_group":
            groups = self.record.broad_groups
            return frozenset(groups) if groups else None
        if self.kind != "taxon":
            return None
        key = self.record.key_at(rank)
        return ("gbif", key) if key is not None else None

    def display(self) -> str:
        r = self.record
        if r is None or not r.resolved:
            return ""
        name = r.accepted_name or r.canonical_name or (r.label or "")
        rank = (r.rank or "").lower()
        return f"{name} [{rank}]" if rank else name

    def to_row(self) -> dict[str, Any]:
        r = self.record
        return {
            "record_id": self.record_id,
            "side": self.side,
            "raw": self.raw,
            "mention": self.mention,
            "kind": self.kind,
            "resolved_as": self.display(),
            "gbif_key": r.key if r else None,
            "rank": r.rank if r else None,
            "family": r.family if r else None,
            "broad_groups": ", ".join(r.broad_groups) if r else "",
            "method": r.method if r else None,
            "count": self.count,
            "best_rank": self.best_rank,
            "status": self.status,
            "reason": self.reason,
        }


def resolve_species_items(
    species: Optional[Sequence[str]],
    *,
    record_id: str = "",
    side: str = "",
    cache: Optional[GBIFCache] = None,
) -> list[TaxonItem]:
    """Split, classify and resolve every mention in a raw `species` list."""
    items: list[TaxonItem] = []
    for raw in species or []:
        if not isinstance(raw, str) or not raw.strip():
            continue
        for part in split_taxon_items(raw):
            mention = TaxonMention.model_validate(part)
            item = TaxonItem(record_id=record_id, side=side, raw=raw, mention=part, kind="other")
            if mention.kind == "noise":
                item.other_reason = "noise (e.g. 'and others')"
            elif mention.kind == "hybrid":
                item.other_reason = "hybrid label"
            elif mention.kind == "count":
                item.kind = "count"
                item.count = mention.count
                item.approximate = mention.approximate
                for text in mention.group_texts:
                    rec = resolve_taxon(text, cache=cache, allow_qualifier_drop=False)
                    if rec.resolved:
                        item.record = rec
                        break
            else:
                rec = resolve_taxon(part, cache=cache)
                if rec.resolved:
                    item.kind = rec.kind
                    item.record = rec
                elif mention.generic_label:
                    item.other_reason = "label without a taxon (trait or functional group)"
                else:
                    item.kind = "unresolved"
                    item.record = rec
            items.append(item)
    return items


def _entries_match(a: Any, b: Any) -> bool:
    if isinstance(a, frozenset) and isinstance(b, frozenset):
        return bool(a & b)
    return a == b


def _strictly_inside(inner: TaxonItem, outer: TaxonItem) -> bool:
    """True when `inner` is a finer taxon contained in the coarser `outer` item."""
    ri, ro = inner.record, outer.record
    if ri is None or ro is None or not ri.resolved or not ro.resolved:
        return False
    if inner.kind not in ("taxon", "group") or outer.kind not in ("taxon", "group", "count"):
        return False
    if ro.key is not None:
        if ri.key == ro.key:
            return False
        return ro.key in ri.lineage_keys
    # Group without a backbone taxon (fish, invertebrates, algae): use broad groups
    return bool(ri.broad_groups) and set(ri.broad_groups) <= set(ro.broad_groups)


def _overlaps(a: TaxonItem, b: TaxonItem) -> bool:
    """Same, nested, or (for groups without a backbone taxon) same broad group."""
    ra, rb = a.record, b.record
    if ra is None or rb is None or not ra.resolved or not rb.resolved:
        return False
    if ra.key is not None and ra.key in rb.lineage_keys:
        return True
    if rb.key is not None and rb.key in ra.lineage_keys:
        return True
    if ra.key is None or rb.key is None:
        return bool(set(ra.broad_groups) & set(rb.broad_groups))
    return False


@_dataclass
class RankCounts:
    """Counts behind precision/recall at one rank (or for one signal).

    Precision = matched extracted entries / extracted entries scored.
    Recall    = matched annotated entries / annotated entries scored.
    Entries are de-duplicated per record (two strings for the same taxon
    count once).
    """

    rank: str
    n_true: int = 0
    n_true_matched: int = 0
    n_pred: int = 0
    n_pred_matched: int = 0
    n_pred_not_scored: int = 0
    n_records: int = 0

    @property
    def precision(self) -> Optional[float]:
        return self.n_pred_matched / self.n_pred if self.n_pred else None

    @property
    def recall(self) -> Optional[float]:
        return self.n_true_matched / self.n_true if self.n_true else None

    @property
    def f1(self) -> Optional[float]:
        p, r = self.precision, self.recall
        if p is None or r is None or (p + r) == 0:
            return None if p is None or r is None else 0.0
        return 2 * p * r / (p + r)

    def add(self, other: "RankCounts") -> None:
        self.n_true += other.n_true
        self.n_true_matched += other.n_true_matched
        self.n_pred += other.n_pred
        self.n_pred_matched += other.n_pred_matched
        self.n_pred_not_scored += other.n_pred_not_scored
        self.n_records += other.n_records

    def to_row(self) -> dict[str, Any]:
        return {
            "rank": self.rank,
            "precision": None if self.precision is None else round(self.precision, 3),
            "recall": None if self.recall is None else round(self.recall, 3),
            "f1": None if self.f1 is None else round(self.f1, 3),
            "annotated": self.n_true,
            "annotated_matched": self.n_true_matched,
            "extracted": self.n_pred,
            "extracted_matched": self.n_pred_matched,
            "extracted_not_scored": self.n_pred_not_scored,
            "records": self.n_records,
        }


def _score_rank(rank: str, true_items: list[TaxonItem], pred_items: list[TaxonItem]) -> RankCounts:
    true_entries: dict[Any, list[TaxonItem]] = {}
    pred_entries: dict[Any, list[TaxonItem]] = {}
    for item in true_items:
        entry = item.entry_at(rank)
        if entry is not None:
            true_entries.setdefault(entry, []).append(item)
    for item in pred_items:
        entry = item.entry_at(rank)
        if entry is not None:
            pred_entries.setdefault(entry, []).append(item)

    counts = RankCounts(rank=rank, n_records=1 if (true_entries or pred_entries) else 0)
    counts.n_true = len(true_entries)
    counts.n_true_matched = sum(
        1 for t in true_entries if any(_entries_match(t, p) for p in pred_entries)
    )
    for p, items in pred_entries.items():
        if any(_entries_match(t, p) for t in true_entries):
            counts.n_pred += 1
            counts.n_pred_matched += 1
            continue
        # A finer extracted taxon inside a coarser annotation ("Vaccinium spp",
        # "c.30 beetle species") cannot be judged at this rank.
        if any(_strictly_inside(pi, ti) for pi in items for ti in true_items):
            counts.n_pred_not_scored += 1
            continue
        counts.n_pred += 1
    return counts


def _best_rank(item: TaxonItem, others: list[TaxonItem]) -> Optional[str]:
    for rank in RANKS:
        entry = item.entry_at(rank)
        if entry is None:
            continue
        if any(_entries_match(entry, o.entry_at(rank)) for o in others if o.entry_at(rank) is not None):
            return rank
    return None


def _annotate_items(true_items: list[TaxonItem], pred_items: list[TaxonItem]) -> None:
    """Fill best_rank / status / reason on every item of one record."""
    for side_items, others, side in ((true_items, pred_items, "annotation"), (pred_items, true_items, "extraction")):
        for item in side_items:
            item.best_rank = _best_rank(item, others)
            if item.kind == "other":
                item.status = "not scored"
                item.reason = item.other_reason or "not a taxon"
                continue
            if item.kind == "count":
                item.status = "count statement"
                group = item.display() or "no group found"
                matched = any(_overlaps(item, o) for o in others) if item.record else False
                item.reason = f"count {item.count} ({group}); group {'mentioned' if matched else 'not mentioned'} on the other side"
                continue
            if item.kind == "group":
                matched = any(_overlaps(item, o) for o in others)
                item.status = "group label"
                item.reason = f"group {'matched' if matched else 'not matched'} on the other side"
                continue
            if item.best_rank == "exact":
                item.status = "match"
                item.reason = "same taxon" + (" (different wording)" if item.raw.strip().casefold() not in {o.raw.strip().casefold() for o in others} else "")
                continue
            container = None
            if side == "extraction":
                container = next((o for o in others if _strictly_inside(item, o)), None)
            if container is not None:
                # The annotation is coarser ("Vaccinium spp", "c.30 beetle species"):
                # the extracted taxon cannot be judged at the finer ranks.
                item.status = "within annotation"
                item.reason = f"inside the annotated '{container.mention}'"
                if item.best_rank is not None:
                    item.reason += f"; {_RANK_LABELS[item.best_rank]}"
            elif item.best_rank is not None:
                item.status = f"partial ({item.best_rank})"
                item.reason = f"{_RANK_LABELS[item.best_rank]} only"
            elif item.kind == "unresolved":
                item.status = "missed" if side == "annotation" else "extra"
                item.reason = "name not resolved by GBIF"
            else:
                item.status = "missed" if side == "annotation" else "extra"
                item.reason = (
                    "no counterpart at any rank"
                    if side == "annotation"
                    else "not in the annotation (incidental taxon or over-extraction)"
                )


def _count_signal(true_items: list[TaxonItem], pred_items: list[TaxonItem]) -> dict[str, Any]:
    t_counts = [i for i in true_items if i.kind == "count"]
    p_counts = [i for i in pred_items if i.kind == "count"]
    value_match = None
    if t_counts and p_counts:
        value_match = any(
            t.count == p.count
            or ((t.approximate or p.approximate) and abs(t.count - p.count) <= 0.1 * max(t.count, p.count))
            for t in t_counts for p in p_counts
        )
    return {
        "true_has_count": bool(t_counts),
        "pred_has_count": bool(p_counts),
        "true_counts": [i.count for i in t_counts],
        "pred_counts": [i.count for i in p_counts],
        "count_value_match": value_match,
    }


def _group_signal(true_items: list[TaxonItem], pred_items: list[TaxonItem]) -> RankCounts:
    def groups(items: list[TaxonItem]) -> list[TaxonItem]:
        return [i for i in items if i.kind == "group" or (i.kind == "count" and i.record is not None)]

    def scorable(items: list[TaxonItem]) -> list[TaxonItem]:
        return [i for i in items if i.kind in ("taxon", "group") or (i.kind == "count" and i.record is not None)]

    t_groups, p_groups = groups(true_items), groups(pred_items)
    counts = RankCounts(rank="group_mentioned", n_records=1 if (t_groups or p_groups) else 0)
    counts.n_true = len(t_groups)
    counts.n_true_matched = sum(1 for g in t_groups if any(_overlaps(g, o) for o in scorable(pred_items)))
    counts.n_pred = len(p_groups)
    counts.n_pred_matched = sum(1 for g in p_groups if any(_overlaps(g, o) for o in scorable(true_items)))
    return counts


def _string_baselines(true_species: list[str], pred_species: list[str]) -> tuple[RankCounts, RankCounts]:
    from llm_metadata.groundtruth_eval import _enhanced_species_match_lists

    out = []
    t_exact = {s.strip().casefold() for s in true_species if isinstance(s, str) and s.strip()}
    p_exact = {s.strip().casefold() for s in pred_species if isinstance(s, str) and s.strip()}
    t_fuzzy, p_fuzzy = _enhanced_species_match_lists(list(true_species), list(pred_species), 70)
    for name, t, p in (("string_exact", t_exact, p_exact), ("string_fuzzy", t_fuzzy, p_fuzzy)):
        counts = RankCounts(rank=name, n_records=1 if (t or p) else 0)
        counts.n_true, counts.n_pred = len(t), len(p)
        counts.n_true_matched = counts.n_pred_matched = len(t & p)
        out.append(counts)
    return out[0], out[1]


@_dataclass
class RecordTaxaResult:
    record_id: str
    true_species: list[str]
    pred_species: list[str]
    true_items: list[TaxonItem]
    pred_items: list[TaxonItem]
    ranks: dict[str, RankCounts]
    groups: RankCounts
    counts: dict[str, Any]
    baselines: dict[str, RankCounts]


@_dataclass
class TaxaEvaluation:
    """Result of `evaluate_run_taxa`: per-rank metrics plus per-record detail."""

    run_name: str
    records: list[RecordTaxaResult] = _field(default_factory=list)

    def _total(self, getter) -> RankCounts:
        total: Optional[RankCounts] = None
        for rec in self.records:
            part = getter(rec)
            if total is None:
                total = RankCounts(rank=part.rank)
            total.add(part)
        return total or RankCounts(rank="")

    def rank_metrics(self, rank: str) -> RankCounts:
        return self._total(lambda r: r.ranks[rank])

    def group_metrics(self) -> RankCounts:
        return self._total(lambda r: r.groups)

    def count_metrics(self) -> RankCounts:
        """Count statement present: a record-level yes/no signal."""
        out = RankCounts(rank="count_present")
        for rec in self.records:
            c = rec.counts
            if c["true_has_count"] or c["pred_has_count"]:
                out.n_records += 1
            out.n_true += int(c["true_has_count"])
            out.n_pred += int(c["pred_has_count"])
            both = int(c["true_has_count"] and c["pred_has_count"])
            out.n_true_matched += both
            out.n_pred_matched += both
        return out

    def count_value_agreement(self) -> tuple[int, int]:
        """(records where a count value agrees, records where both sides give a count)."""
        both = [r for r in self.records if r.counts["count_value_match"] is not None]
        return sum(1 for r in both if r.counts["count_value_match"]), len(both)

    def metrics_frame(self):
        """Per-rank precision/recall/F1 (micro over records), plus signals and string baselines."""
        import pandas as pd

        rows = [self.rank_metrics(rank).to_row() for rank in RANKS]
        rows.append(self.group_metrics().to_row())
        rows.append(self.count_metrics().to_row())
        rows.append(self._total(lambda r: r.baselines["string_exact"]).to_row())
        rows.append(self._total(lambda r: r.baselines["string_fuzzy"]).to_row())
        return pd.DataFrame(rows)

    def items_frame(self):
        """One row per mention, both sides, with status and reason."""
        import pandas as pd

        rows = [item.to_row() for rec in self.records for item in (*rec.true_items, *rec.pred_items)]
        return pd.DataFrame(rows)

    def records_frame(self):
        """One row per record: matched/total entries at each rank, counts, groups."""
        import pandas as pd

        rows = []
        for rec in self.records:
            row: dict[str, Any] = {"record_id": rec.record_id}
            for rank in RANKS:
                c = rec.ranks[rank]
                row[f"{rank}_recall"] = f"{c.n_true_matched}/{c.n_true}"
                row[f"{rank}_precision"] = f"{c.n_pred_matched}/{c.n_pred}"
            row["groups"] = f"{rec.groups.n_true_matched}/{rec.groups.n_true}"
            row["true_counts"] = rec.counts["true_counts"]
            row["pred_counts"] = rec.counts["pred_counts"]
            rows.append(row)
        return pd.DataFrame(rows)

    def resolution_rate(self, side: str = "annotation") -> tuple[int, int]:
        """(resolved, total) over name mentions (taxa, groups, unresolved) on one side."""
        items = [
            i for rec in self.records
            for i in (rec.true_items if side == "annotation" else rec.pred_items)
            if i.kind in ("taxon", "group", "unresolved")
        ]
        return sum(1 for i in items if i.kind != "unresolved"), len(items)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_name": self.run_name,
            "metrics": self.metrics_frame().to_dict(orient="records"),
            "count_value_agreement": list(self.count_value_agreement()),
            "resolution_rate": {
                side: list(self.resolution_rate(side)) for side in ("annotation", "extraction")
            },
            "items": self.items_frame().to_dict(orient="records"),
        }


def evaluate_taxa_lists(
    true_by_id: dict[str, Optional[Sequence[str]]],
    pred_by_id: dict[str, Optional[Sequence[str]]],
    *,
    run_name: str = "",
    cache: Optional[GBIFCache] = None,
) -> TaxaEvaluation:
    """Multi-rank evaluation of raw `species` lists keyed by record id.

    Records are those present in `true_by_id`; a missing prediction counts as
    an empty list.
    """
    evaluation = TaxaEvaluation(run_name=run_name)
    for record_id in sorted(true_by_id, key=lambda x: (len(str(x)), str(x))):
        true_species = [s for s in (true_by_id.get(record_id) or []) if isinstance(s, str)]
        pred_species = [s for s in (pred_by_id.get(record_id) or []) if isinstance(s, str)]
        true_items = resolve_species_items(true_species, record_id=str(record_id), side="annotation", cache=cache)
        pred_items = resolve_species_items(pred_species, record_id=str(record_id), side="extraction", cache=cache)
        _annotate_items(true_items, pred_items)
        exact_b, fuzzy_b = _string_baselines(true_species, pred_species)
        evaluation.records.append(
            RecordTaxaResult(
                record_id=str(record_id),
                true_species=true_species,
                pred_species=pred_species,
                true_items=true_items,
                pred_items=pred_items,
                ranks={rank: _score_rank(rank, true_items, pred_items) for rank in RANKS},
                groups=_group_signal(true_items, pred_items),
                counts=_count_signal(true_items, pred_items),
                baselines={"string_exact": exact_b, "string_fuzzy": fuzzy_b},
            )
        )
    return evaluation


def load_gt_species(gt_path: str | Path = "data/gt/fuster_gt.json") -> dict[str, Optional[list[str]]]:
    """Annotated `species` lists keyed by gt_record_id (as strings)."""
    data = _json.loads(Path(gt_path).read_text(encoding="utf-8"))
    return {str(row["gt_record_id"]): row.get("species") for row in data}


def evaluate_run_taxa(
    run_path: str | Path,
    *,
    gt_path: str | Path = "data/gt/fuster_gt.json",
    record_ids: Optional[Iterable[int | str]] = None,
    cache: Optional[GBIFCache] = None,
) -> TaxaEvaluation:
    """Multi-rank taxa evaluation of a prompt_eval run artifact, in one call.

    Args:
        run_path: A `RunArtifact` JSON (``artifacts/runs/*.json``).
        gt_path: Ground-truth JSON array with ``gt_record_id`` and ``species``.
        record_ids: Optional subset of gt_record_ids to score (default: every
            record in the run).
        cache: Optional `GBIFCache` (default: the shared JSON cache).

    Returns:
        A `TaxaEvaluation`; use ``.metrics_frame()``, ``.items_frame()``,
        ``.records_frame()``.

    Example:
        >>> ev = evaluate_run_taxa("artifacts/runs/20261115_082643_haiku55_abstract_low.json")
        >>> ev.metrics_frame()
    """
    artifact = RunArtifact.load_json(run_path)
    gt = load_gt_species(gt_path)
    wanted = {str(i) for i in record_ids} if record_ids is not None else None
    true_by_id: dict[str, Optional[list[str]]] = {}
    pred_by_id: dict[str, Optional[list[str]]] = {}
    for rec in artifact.records:
        rid = str(rec.gt_record_id)
        if wanted is not None and rid not in wanted:
            continue
        true_by_id[rid] = gt.get(rid)
        output = rec.output or {}
        pred_by_id[rid] = output.get("species") if rec.status == "success" else None
    return evaluate_taxa_lists(true_by_id, pred_by_id, run_name=artifact.name, cache=cache)


def _format_metrics(ev: TaxaEvaluation) -> str:
    frame = ev.metrics_frame()
    agree, both = ev.count_value_agreement()
    res_t = ev.resolution_rate("annotation")
    res_p = ev.resolution_rate("extraction")
    lines = [
        f"Run: {ev.run_name} ({len(ev.records)} records)",
        frame.to_string(index=False),
        f"Count values agree in {agree}/{both} records where both sides give a count.",
        f"Resolved names: annotation {res_t[0]}/{res_t[1]}, extraction {res_p[0]}/{res_p[1]}.",
    ]
    return "\n".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> None:
    import argparse

    import pandas as pd

    parser = argparse.ArgumentParser(description="Multi-rank taxonomic evaluation of a run artifact.")
    parser.add_argument("run", help="Run artifact JSON (artifacts/runs/*.json)")
    parser.add_argument("--gt", default="data/gt/fuster_gt.json", help="Ground-truth JSON")
    parser.add_argument("--manifest", help="Restrict to gt_record_id values in this manifest CSV")
    parser.add_argument("--items-csv", help="Write the per-mention table to this CSV")
    parser.add_argument("--json", dest="json_path", help="Write metrics and items to this JSON")
    parser.add_argument("--show", choices=["mismatches", "all", "none"], default="mismatches",
                        help="Per-mention rows to print")
    args = parser.parse_args(argv)

    record_ids = None
    if args.manifest:
        record_ids = pd.read_csv(args.manifest)["gt_record_id"].astype(int).tolist()
    ev = evaluate_run_taxa(args.run, gt_path=args.gt, record_ids=record_ids)
    print(_format_metrics(ev))

    items = ev.items_frame()
    if args.show != "none" and not items.empty:
        if args.show == "mismatches":
            items = items[~items["status"].isin(["match"])]
        cols = ["record_id", "side", "mention", "kind", "resolved_as", "status", "reason"]
        with pd.option_context("display.max_rows", None, "display.max_colwidth", 60, "display.width", 250):
            print()
            print(items[cols].to_string(index=False))
    if args.items_csv:
        ev.items_frame().to_csv(args.items_csv, index=False)
    if args.json_path:
        Path(args.json_path).write_text(_json.dumps(ev.to_dict(), indent=2, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
