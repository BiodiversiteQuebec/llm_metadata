"""Fuster rule scorer: from dataset features to a relevance category.

Pure functions, no I/O. They turn extracted (or annotated) features into the
three intermediate classes ("Main Classifiers") and then into one relevance
category, as in Fuster-Calvo et al. 2025 (PeerJ 18853, the Quebec dataset
relevance study; supplement Tables 2 and S2).

Classes are the letters ``H`` (high), ``M`` (moderate), ``L`` (low) and ``X``
(not stated, or unusable). They match the ``MC_*`` columns of
``data/dataset_092624.xlsx``:

======================  ==============================================
Spreadsheet column      Function here
======================  ==============================================
``MC_dataset_type``     :func:`dataset_type_class`
``MC_spatial_range``    :func:`spatial_range_class`
``MC_temporal_range``   :func:`temporal_range_class`
``MC_relevance``        :func:`majority_vote`
``MC_relevance_modifiers``  :func:`apply_modulators` (final category)
======================  ==============================================

Where a threshold comes from
----------------------------
Two kinds of source, and they are not equally solid:

* **Published**: the prose of the paper (and plan notes taken from it).
* **Reconstructed**: the paper text and the released ``MC_*`` columns
  disagree or are silent, so we chose the rule that reproduces the released
  columns on all valid records. Each reconstructed rule is marked as such in
  its docstring. They were validated in ``notebooks/relevance_mechanistic.ipynb``.

The module moves that notebook's code unchanged in behaviour; the tests check
it against the released columns.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from typing import Any, Mapping, Optional, Sequence

#: Class order, best first.
LABELS: tuple[str, ...] = ("H", "M", "L", "X")
#: Numeric rank used by the tiebreaker (X is the lowest).
RANK: dict[str, int] = {"H": 3, "M": 2, "L": 1, "X": 0}
_FROM_RANK: dict[int, str] = {v: k for k, v in RANK.items()}

#: Spatial thresholds in km2. Reconstructed from the released column; the paper
#: reports the same cut points in its Results ("less than 5,000 km2", "between
#: 5,000 and 15,000 km2", "exceeded 15,000 km2").
SPATIAL_HIGH_ABOVE_KM2 = 15_000  # strictly greater than -> H
SPATIAL_MODERATE_FROM_KM2 = 5_000  # 5,000 to 15,000 inclusive -> M; below -> L

#: Temporal thresholds in calendar years counted inclusively (end - start + 1).
#: RECONSTRUCTED. The paper prose says High is "more than 10 years", Moderate
#: 3 to 10 and Low under 3. The released column behaves like inclusive bins
#: 1-2 = L, 3-11 = M, >= 12 = H, so these are the bins used.
TEMPORAL_HIGH_FROM_YEARS = 12
TEMPORAL_MODERATE_FROM_YEARS = 3

#: Modulators: any one of these being true upgrades the class by one level.
MODULATOR_FIELDS: tuple[str, ...] = (
    "multispecies",
    "threatened_species",
    "new_species_science",
    "new_species_region",
    "bias_north_south",
)

#: Binary reading used in every relevance notebook: H and M are "relevant",
#: L and X are "not relevant".
RELEVANT_LABELS: frozenset[str] = frozenset({"H", "M"})


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    return False


# --------------------------------------------------------------------------
# Main Classifier 1: dataset type
# --------------------------------------------------------------------------

def _single_type_class(dt: str) -> Optional[str]:
    """Class of one data type phrase, or None when no rule matches.

    Enum spellings (``genetic_analysis``, ``species_richness``) are read like the
    annotation text (underscores as spaces).
    """
    dt = dt.replace("_", " ")
    if dt in {"other", "unknown"}:
        return "X"
    if "non-ebv" in dt or ("genetic analysis" in dt and "ebv genetic" not in dt):
        return "L"
    if "relative abundance" in dt or "species richness" in dt or "species_richness" in dt:
        return "L"
    if any(x in dt for x in ("abundance", "density", "ebv genetic")):
        return "H"
    if any(x in dt for x in ("distribution", "presence-absence", "presence_absence")):
        return "M"
    if "presence" in dt:
        return "L"
    return None


def dataset_type_class(
    raw_data_type: Any = None, normalized_primary: Optional[str] = None
) -> str:
    """Class of the EBV data type (``MC_dataset_type``).

    Input is the data type text as annotated (for example
    ``"presence only, EBV genetic analysis"``) or a list of enum values from
    an extraction. The text is split on commas, each phrase is classified with
    the table below (first matching line wins), and the **best** class among
    the phrases is returned (H > M > L > X).

    =====================================================  =====
    Phrase contains                                        Class
    =====================================================  =====
    exactly ``other`` or ``unknown``                       X
    ``non-ebv``, or ``genetic analysis`` without ``ebv genetic``   L
    ``relative abundance``, ``species richness``           L
    ``abundance``, ``density``, ``ebv genetic``            H
    ``distribution``, ``presence-absence``                 M
    ``presence`` (presence only)                           L
    anything else                                          no class
    =====================================================  =====

    Published: the paper's Table 2 ranks abundance, density and EBV genetic
    data highest, distribution and presence-absence in the middle, presence-only
    and non-EBV genetic lowest. Reconstructed: plain ``genetic analysis`` counts
    as non-EBV (L), because that reproduces the released column; and a dataset
    with several types takes the best one. (The earlier notebook matched the
    whole text at once, so ``density, species richness`` came out L; taking the
    best phrase gives H, as released, and changes nothing else.)

    ``normalized_primary`` is only a fallback when the raw text is empty.
    """
    if isinstance(raw_data_type, (list, tuple)):
        raw_data_type = ", ".join(str(x) for x in raw_data_type if x)
    if not _is_missing(raw_data_type):
        raw_text = str(raw_data_type).lower().strip()
        if raw_text not in ("", "nan"):
            matched = [
                c for c in (_single_type_class(part.strip()) for part in raw_text.split(","))
                if c is not None
            ]
            if matched:
                return max(matched, key=RANK.__getitem__)

    dt = None
    if not _is_missing(normalized_primary):
        dt = str(normalized_primary).lower().strip()
    if dt in (None, "", "nan", "unknown", "other"):
        return "X"
    if dt == "genetic_analysis":
        return "L"
    if dt in {"abundance", "density"}:
        return "H"
    if dt in {"distribution", "presence-absence"}:
        return "M"
    if dt in {"presence-only", "species_richness"}:
        return "L"
    return "X"


# --------------------------------------------------------------------------
# Main Classifier 2: temporal range
# --------------------------------------------------------------------------

def temporal_duration_years(temp_range_i: Any, temp_range_f: Any) -> Optional[int]:
    """Inclusive number of calendar years, ``end - start + 1``, or None."""
    try:
        start = float(temp_range_i)
        end = float(temp_range_f)
    except (TypeError, ValueError):
        return None
    if math.isnan(start) or math.isnan(end):
        return None
    return int(end - start) + 1


def temporal_range_class(temp_range_i: Any, temp_range_f: Any) -> str:
    """Class of the temporal extent (``MC_temporal_range``).

    Duration is counted in inclusive calendar years: 2004 to 2010 is 7 years.
    ``>= 12`` is H, ``3 to 11`` is M, ``1 to 2`` is L (and anything shorter,
    including an end before the start, also L). A missing start or end is X.

    Reconstructed, see the module constants: the paper prose says "more than
    10 years" for H.
    """
    years = temporal_duration_years(temp_range_i, temp_range_f)
    if years is None:
        return "X"
    if years >= TEMPORAL_HIGH_FROM_YEARS:
        return "H"
    if years >= TEMPORAL_MODERATE_FROM_YEARS:
        return "M"
    return "L"


# --------------------------------------------------------------------------
# Main Classifier 3: spatial range
# --------------------------------------------------------------------------

def spatial_range_class(spatial_range_km2: Any) -> str:
    """Class of the spatial extent (``MC_spatial_range``).

    More than 15,000 km2 is H, 5,000 to 15,000 is M, below 5,000 is L. A
    missing value is X. Cut points from the paper's Results, boundary handling
    (exactly 15,000 is M, exactly 5,000 is M) reconstructed.
    """
    try:
        km2 = float(spatial_range_km2)
    except (TypeError, ValueError):
        return "X"
    if math.isnan(km2):
        return "X"
    if km2 > SPATIAL_HIGH_ABOVE_KM2:
        return "H"
    if km2 >= SPATIAL_MODERATE_FROM_KM2:
        return "M"
    return "L"


# --------------------------------------------------------------------------
# Aggregation and modulators
# --------------------------------------------------------------------------

def majority_vote(dataset_type: str, temporal: str, spatial: str) -> str:
    """Combine the three classes into ``MC_relevance``.

    Published (Table S2): when two or three classifiers agree, that class wins.
    When all three differ:

    * dataset type H with an X for time or space gives L (special case);
    * otherwise ``min(dataset type, max(temporal, spatial))`` on the order
      H > M > L > X.
    """
    counts = Counter((dataset_type, temporal, spatial))
    for label, count in counts.items():
        if count >= 2:
            return label
    if dataset_type == "H" and (temporal == "X" or spatial == "X"):
        return "L"
    best_spatiotemporal = _FROM_RANK[max(RANK[temporal], RANK[spatial])]
    return _FROM_RANK[min(RANK[dataset_type], RANK[best_spatiotemporal])]


def is_true(value: Any) -> bool:
    """True for ``True``, ``"true"``, ``"yes"``, ``"1"``; anything else is False."""
    if value is True:
        return True
    if isinstance(value, str) and value.strip().lower() in ("true", "1", "yes"):
        return True
    return False


_UPGRADE = {"X": "L", "L": "M", "M": "H", "H": "H"}


def apply_modulators(base: str, features: Mapping[str, Any]) -> str:
    """Upgrade the class by one level when any modulator is true
    (``MC_relevance_modifiers``).

    The five modulators are in :data:`MODULATOR_FIELDS`. One level at most, no
    matter how many fire. Reconstructed from the released column: the paper
    says only relevant datasets are upgraded and treats multispecies
    specially, but the released labels also upgrade X to L and count
    ``multispecies`` as a modulator like the others.
    """
    if any(is_true(features.get(name)) for name in MODULATOR_FIELDS):
        return _UPGRADE.get(base, base)
    return base


@dataclass(frozen=True)
class RelevanceResult:
    """All intermediate classes and the final category for one record."""

    dataset_type: str
    temporal: str
    spatial: str
    relevance: str  # MC_relevance (majority vote)
    relevance_modifiers: str  # MC_relevance_modifiers (final)

    def as_mc_columns(self) -> dict[str, str]:
        """Same keys as the spreadsheet ``MC_*`` columns."""
        return {
            "MC_dataset_type": self.dataset_type,
            "MC_temporal_range": self.temporal,
            "MC_spatial_range": self.spatial,
            "MC_relevance": self.relevance,
            "MC_relevance_modifiers": self.relevance_modifiers,
        }


def classify_features(features: Mapping[str, Any]) -> RelevanceResult:
    """Run the whole rule chain on one record of normalized features.

    ``features`` is a mapping with ``data_type`` (text or list),
    ``temp_range_i``, ``temp_range_f``, ``spatial_range_km2`` and the five
    modulator booleans. Missing keys count as missing values. For spreadsheet
    rows, clean them first with :func:`features_from_row`.
    """
    dataset_type = dataset_type_class(features.get("data_type"))
    temporal = temporal_range_class(features.get("temp_range_i"), features.get("temp_range_f"))
    spatial = spatial_range_class(features.get("spatial_range_km2"))
    base = majority_vote(dataset_type, temporal, spatial)
    final = apply_modulators(base, features)
    return RelevanceResult(dataset_type, temporal, spatial, base, final)


def features_from_row(row: Mapping[str, Any]) -> dict[str, Any]:
    """Clean one spreadsheet row (or ground-truth dict) into rule inputs.

    Years, ranges and booleans go through ``DatasetFeaturesNormalized``. The
    raw ``data_type`` text is kept as is, because the normalizer maps both
    ``genetic analysis`` and ``EBV genetic analysis`` to the same value and the
    rules need the difference.
    """
    from llm_metadata.schemas.fuster_features import DatasetFeaturesNormalized

    fields = (
        "temp_range_i", "temp_range_f", "spatial_range_km2", *MODULATOR_FIELDS,
    )
    model = DatasetFeaturesNormalized.model_validate(
        {name: row.get(name) for name in fields}
    )
    out: dict[str, Any] = {name: getattr(model, name) for name in fields}
    out["data_type"] = row.get("data_type")
    return out


def binarize(label: Optional[str]) -> Optional[str]:
    """``relevant`` for H or M, ``not_relevant`` for L or X, None otherwise.

    This is the collapse used by every earlier relevance notebook
    (``binary_collapse`` in ``relevance_mechanistic.ipynb``).
    """
    if label in LABELS:
        return "relevant" if label in RELEVANT_LABELS else "not_relevant"
    return None


def normalize_human_label(label: Any) -> Optional[str]:
    """Clean the ``dataset_relevance`` annotation to H, M, L or X.

    Strips the stray space in `` X``. ``No dataset``, ``cant access`` and empty
    cells return None: those records carry no human relevance class. (The
    earlier notebook mapped ``No dataset`` to X and then kept only H/M/L/X, so
    ``No dataset`` rows were never compared; this returns None for them
    explicitly.)
    """
    if _is_missing(label):
        return None
    text = str(label).strip()
    return text if text in LABELS else None
