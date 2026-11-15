"""Evidence-availability ceiling: how much of each annotated value can a text hold?

The annotators recorded, for some fields, where they found the value. If it was only
in the dataset files, or was worked out by the annotator (a surface area estimated from a
map), no model reading the abstract can extract it. This module turns those position
columns of ``data/dataset_092624.xlsx`` into a per-record, per-field answer and a ceiling
for recall per field and input.

Raw vocabulary of the position columns (valid records, checked 2026-11-15)
--------------------------------------------------------------------------
Each cell is empty or a comma-separated list of these phrases:

===========================  ===================================================  ==========
Phrase                       Meaning                                              Mapped to
===========================  ===================================================  ==========
``source link abstract``     abstract of the source link (the repository          abstract
                             description, the text the abstract mode reads)
``source link``              the repository page of the dataset                   abstract
``source publication text``  body of the article                                  article
``article``                  same (typo-level variant, spatial column only)       article
``dataset``                  inside the data files                                dataset
``not given``, ``no``        the value is not stated anywhere; the annotator      none
                             derived or estimated it
(empty cell, value present)  the annotator did not record a position              unrecorded
===========================  ===================================================  ==========

``abstract`` therefore means "abstract or repository description text", the same text the
abstract mode sends to the model.

Which fields have positions
---------------------------
* ``temp_range_i``, ``temp_range_f`` (and the class ``temporal_range_class``):
  column ``temporal_range_position``.
* ``spatial_range_km2`` (and ``spatial_range_class``): ``spatial_range_position``.
* ``temporal_duration_y``: ``temporal_duration_position``.
* ``geospatial_info_dataset``: no single position column. The value is "found in the
  repository text" when ``geospatial_info_repo_page_text`` holds a real value (not
  ``no`` or ``not given``), and "found in the article" when
  ``geospatial_info_article_text`` does.
* All other fields (data type, species, the booleans) have no position column: no
  ceiling is computed for them.

For the two class fields the ceiling of the underlying number is a lower bound: a place
name in the text can fix a class without stating the number.

Inputs
------
``abstract`` reaches the ``abstract`` source. ``fulltext`` (and ``pdf``) reach
``abstract`` and ``article``. Neither reaches ``dataset``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd

XLSX_PATH = Path("data/dataset_092624.xlsx")

ABSTRACT = "abstract"
ARTICLE = "article"
DATASET = "dataset"
NONE = "none"
UNRECORDED = "unrecorded"

_PHRASES = {
    "source link abstract": ABSTRACT,
    "source link": ABSTRACT,
    "source publication text": ARTICLE,
    "article": ARTICLE,
    "artcile": ARTICLE,  # typo present in dataset_location
    "dataset": DATASET,
    "not given": NONE,
    "no": NONE,
}

#: Sources each input can read.
INPUT_SOURCES: dict[str, frozenset[str]] = {
    "abstract": frozenset({ABSTRACT}),
    "fulltext": frozenset({ABSTRACT, ARTICLE}),
    "pdf": frozenset({ABSTRACT, ARTICLE}),
}

#: Field -> (position column(s), value column used to know a value exists).
#: Value columns use the spreadsheet; "not given" and "no" count as no value.
FIELD_SOURCES: dict[str, dict] = {
    "temp_range_i": {"position": "temporal_range_position", "value": "temp_range_i"},
    "temp_range_f": {"position": "temporal_range_position", "value": "temp_range_f"},
    "temporal_range_class": {"position": "temporal_range_position", "value": "temp_range_i"},
    "spatial_range_km2": {"position": "spatial_range_position", "value": "spatial_range_km2"},
    "spatial_range_class": {"position": "spatial_range_position", "value": "spatial_range_km2"},
    "temporal_duration_y": {"position": "temporal_duration_position", "value": "temporal_duration_y"},
    "geospatial_info_dataset": {
        "position": None,
        "value": "geospatial_info_dataset",
        "repo": "geospatial_info_repo_page_text",
        "article": "geospatial_info_article_text",
    },
}

_NO_VALUE = {"", "no", "not given", "nan", "none", "n/a", "na", "cant access"}


def _has_value(x) -> bool:
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return False
    return str(x).strip().lower() not in _NO_VALUE


def parse_position(raw) -> frozenset[str]:
    """Sources named in one position cell, as a set of ``abstract``, ``article``,
    ``dataset``, ``none``. An empty cell gives an empty set. An unknown phrase raises
    ``ValueError`` so a new spreadsheet vocabulary is not silently dropped.
    """
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return frozenset()
    out = set()
    for part in str(raw).split(","):
        phrase = part.strip().lower()
        if not phrase:
            continue
        if phrase not in _PHRASES:
            raise ValueError(f"Unknown position phrase {phrase!r} in {raw!r}")
        out.add(_PHRASES[phrase])
    return frozenset(out)


def _geo_sources(repo_cell, article_cell) -> frozenset[str]:
    out = set()
    if _has_value(repo_cell):
        out.add(ABSTRACT)
    if _has_value(article_cell) and str(article_cell).strip().lower() != "cant access":
        out.add(ARTICLE)
    return frozenset(out)


def evidence_table(xlsx: str | Path = XLSX_PATH) -> pd.DataFrame:
    """One row per valid record and field with a ceiling.

    Columns: ``id``, ``field``, ``has_value`` (the annotated value exists),
    ``sources`` (set of where it was found), ``status``: one of ``abstract``,
    ``article``, ``dataset`` (the best, i.e. earliest reachable, source), ``none``
    (stated nowhere, annotator-derived), ``unrecorded`` (value but no position), or
    ``no_value``.
    """
    raw = pd.read_excel(xlsx)
    valid = raw[raw["valid_yn"] == "yes"]
    rows = []
    for _, rec in valid.iterrows():
        for field, spec in FIELD_SOURCES.items():
            has_value = _has_value(rec[spec["value"]])
            if spec["position"] is not None:
                sources = parse_position(rec[spec["position"]])
            else:
                sources = _geo_sources(rec[spec["repo"]], rec[spec["article"]])
            if not has_value:
                status = "no_value"
            elif not sources:
                status = UNRECORDED
            elif sources == {NONE}:
                status = NONE
            else:
                real = sources - {NONE}
                status = (ABSTRACT if ABSTRACT in real else ARTICLE if ARTICLE in real else DATASET)
            rows.append({"id": rec["id"], "field": field, "has_value": has_value,
                         "sources": frozenset(sources - {NONE}), "status": status})
    return pd.DataFrame(rows)


@dataclass(frozen=True)
class Ceiling:
    """Ceiling recall of one field for one input.

    ``n_value``: records with an annotated value. ``n_reachable``: the value is in a text the
    input reads. ``n_unrecorded``: value but no position recorded. ``recall``: the
    ceiling, computed on records with a recorded position (unrecorded left out).
    ``recall_low`` counts unrecorded as unreachable, ``recall_high`` as reachable.
    """

    field: str
    input: str
    n_value: int
    n_reachable: int
    n_unrecorded: int
    recall: Optional[float]
    recall_low: Optional[float]
    recall_high: Optional[float]


def ceiling_recall(
    field: str,
    input: str = "abstract",
    *,
    ids: Optional[Iterable] = None,
    table: Optional[pd.DataFrame] = None,
    xlsx: str | Path = XLSX_PATH,
) -> Ceiling:
    """Highest recall any model could reach on ``field`` reading ``input``.

    ``input`` is ``abstract``, ``fulltext`` or ``pdf``. ``ids`` restricts to some
    records (for example the dev subset); default all valid records. Records where the
    value was not found in any text (annotator-derived) count as unreachable.
    """
    if input not in INPUT_SOURCES:
        raise ValueError(f"input must be one of {sorted(INPUT_SOURCES)}")
    if field not in FIELD_SOURCES:
        raise KeyError(f"No position information for field {field!r}; known: {sorted(FIELD_SOURCES)}")
    t = evidence_table(xlsx) if table is None else table
    t = t[(t["field"] == field) & t["has_value"]]
    if ids is not None:
        t = t[t["id"].isin(set(ids))]
    reach = INPUT_SOURCES[input]
    unrec = t["status"] == UNRECORDED
    recorded = t[~unrec]
    reachable = recorded["sources"].map(lambda s: bool(s & reach))
    n_value, n_unrec, n_rec = len(t), int(unrec.sum()), len(recorded)
    n_reach = int(reachable.sum())
    div = lambda a, b: (a / b) if b else None
    return Ceiling(
        field=field, input=input, n_value=n_value, n_reachable=n_reach, n_unrecorded=n_unrec,
        recall=div(n_reach, n_rec),
        recall_low=div(n_reach, n_value),
        recall_high=div(n_reach + n_unrec, n_value),
    )


def ceilings(
    input: str = "abstract", *, ids: Optional[Iterable] = None, xlsx: str | Path = XLSX_PATH
) -> dict[str, Ceiling]:
    """Ceiling recall for every field that has position information."""
    table = evidence_table(xlsx)
    ids = None if ids is None else list(ids)
    return {f: ceiling_recall(f, input, ids=ids, table=table) for f in FIELD_SOURCES}
