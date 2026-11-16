"""Match a dataset's taxa, places and years against the Biodiversité Québec Atlas holdings.

What the Atlas holds is read from two tables built from the staging database
(see ``docs/atlas_contribution/README.md``):

* ``group_region_decade.csv`` (committed): observations, species and datasets per
  broad taxonomic group x region x decade;
* ``species_region_decade.csv`` (git-ignored, under ``artifacts/atlas/``): the same
  counts per species, with genus, family, order and class. Needed to match taxa
  below the group level. Never commit it or a table derived from it per species.

Regions are the 18 administrative regions (``admin``) and the split north / south of
the 49th parallel (``admin_nord_sud``: ``nord_49``, ``sud_49``). The whole province is
the sum of ``nord_49`` and ``sud_49``. Sensitive species are absent from both tables,
so a species "absent from the Atlas" may also be a sensitive species.

Taxa: a free-text name is resolved with ``llm_metadata.gbif.resolve_taxon`` and matched
at the rank the dataset states: species, genus, family, order or class when the name is
a taxon, broad group when it is a label such as "birds". Each item gets a status:

* ``matched``: the Atlas holds records at that rank;
* ``absent``: GBIF resolved the name, but the Atlas holds no record at that rank
  (never observed, or a sensitive species excluded from the extract);
* ``group``: only a broad group is known ("fish", "benthic invertebrates");
* ``unresolved``: GBIF found nothing, or the answer is ambiguous (homonyms);
* ``other``: noise or labels without a taxon ("and others", "hybrids").

Places: matched to an administrative region by name, else to north / south of the
49th parallel, else to the whole province. Unmatched places are kept as a result.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path
from typing import Any, Callable, Iterable, Optional, Sequence

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
GROUP_TABLE = REPO_ROOT / "docs" / "atlas_contribution" / "group_region_decade.csv"
AREA_TABLE = REPO_ROOT / "docs" / "atlas_contribution" / "region_area.csv"
SPECIES_TABLE = REPO_ROOT / "artifacts" / "atlas" / "species_region_decade.csv"

ADMIN = "admin"
NORTH_SOUTH = "admin_nord_sud"
PROVINCE = "province"
NORTH, SOUTH = "nord_49", "sud_49"

#: Atlas decade bins, oldest first.
PERIODS: tuple[str, ...] = (
    "before_1950", "1950s", "1960s", "1970s", "1980s", "1990s", "2000s", "2010s", "2020s",
)

#: GBIF broad groups (``llm_metadata.gbif.BROAD_GROUPS``) -> Atlas taxon groups.
BROAD_TO_ATLAS: dict[str, Optional[str]] = {
    "birds": "BIRDS",
    "mammals": "MAMMALS",
    "fish": "FISH",
    "amphibians": "AMPHIBIANS",
    "reptiles": "REPTILES",
    "insects": "INSECTS",
    "other arthropods": "OTHER_ARTHROPODS",
    "molluscs": "MOLLUSKS",
    "other invertebrates": "OTHER_INVERTEBRATES",
    "vascular plants": "VASCULAR_PLANTS",
    "bryophytes": "NON_VASCULAR_PLANTS",
    "algae": "ALGAE",
    "fungi and lichens": "FUNGI",
    "other": None,
}
_GROUP_CLASSES = {"Insecta", "Aves", "Mammalia", "Amphibia"}
_MICROBE_KINGDOMS = {"BACTERIA", "ARCHAEA", "PROTOZOA", "VIRUSES"}

#: Which side of the 49th parallel each administrative region lies on.
#: None: the region straddles the parallel (Saguenay–Lac-Saint-Jean).
REGION_NORTH: dict[str, Optional[bool]] = {
    "Abitibi-Témiscamingue": False,
    "Bas-Saint-Laurent": False,
    "Capitale-Nationale": False,
    "Centre-du-Québec": False,
    "Chaudière-Appalaches": False,
    "Côte-Nord": True,
    "Estrie": False,
    "Gaspésie–Îles-de-la-Madeleine": False,
    "Lanaudière": False,
    "Laurentides": False,
    "Laval": False,
    "Mauricie": False,
    "Montérégie": False,
    "Montréal": False,
    "Nord-du-Québec": True,
    "Outaouais": False,
    "Saguenay–Lac-Saint-Jean": None,
}

#: Place-name aliases (normalized, see `normalize_place`) -> administrative region.
#: Region names themselves are added automatically. Kept short and well known:
#: a place outside this list falls back to north / south of the 49th parallel.
REGION_ALIASES: dict[str, str] = {
    "abitibi": "Abitibi-Témiscamingue",
    "temiscamingue": "Abitibi-Témiscamingue",
    "rouyn noranda": "Abitibi-Témiscamingue",
    "val d or": "Abitibi-Témiscamingue",
    "bas st laurent": "Bas-Saint-Laurent",
    "lower st lawrence": "Bas-Saint-Laurent",
    "rimouski": "Bas-Saint-Laurent",
    "kamouraska": "Bas-Saint-Laurent",
    "temiscouata": "Bas-Saint-Laurent",
    "quebec city": "Capitale-Nationale",
    "ville de quebec": "Capitale-Nationale",
    "charlevoix": "Capitale-Nationale",
    "portneuf": "Capitale-Nationale",
    "ile d orleans": "Capitale-Nationale",
    "jacques cartier": "Capitale-Nationale",
    "montmorency forest": "Capitale-Nationale",
    "foret montmorency": "Capitale-Nationale",
    "laurentides wildlife reserve": "Capitale-Nationale",
    "drummondville": "Centre-du-Quebec",
    "victoriaville": "Centre-du-Quebec",
    "lac saint pierre": "Centre-du-Quebec",
    "lake saint pierre": "Centre-du-Quebec",
    "beauce": "Chaudiere-Appalaches",
    "levis": "Chaudiere-Appalaches",
    "anticosti": "Cote-Nord",
    "north shore": "Cote-Nord",
    "sept iles": "Cote-Nord",
    "baie comeau": "Cote-Nord",
    "schefferville": "Cote-Nord",
    "minganie": "Cote-Nord",
    "mingan": "Cote-Nord",
    "tadoussac": "Cote-Nord",
    "manicouagan": "Cote-Nord",
    "eastern townships": "Estrie",
    "cantons de l est": "Estrie",
    "sherbrooke": "Estrie",
    "mont megantic": "Estrie",
    "mount megantic": "Estrie",
    "gaspesie": "Gaspesie-Iles-de-la-Madeleine",
    "gaspe": "Gaspesie-Iles-de-la-Madeleine",
    "gaspe peninsula": "Gaspesie-Iles-de-la-Madeleine",
    "magdalen islands": "Gaspesie-Iles-de-la-Madeleine",
    "iles de la madeleine": "Gaspesie-Iles-de-la-Madeleine",
    "forillon": "Gaspesie-Iles-de-la-Madeleine",
    "bonaventure island": "Gaspesie-Iles-de-la-Madeleine",
    "chic chocs": "Gaspesie-Iles-de-la-Madeleine",
    "joliette": "Lanaudiere",
    "laurentians": "Laurentides",
    "mont tremblant": "Laurentides",
    "trois rivieres": "Mauricie",
    "la mauricie": "Mauricie",
    "shawinigan": "Mauricie",
    "st maurice": "Mauricie",
    "monteregie": "Monteregie",
    "mont saint hilaire": "Monteregie",
    "gault nature reserve": "Monteregie",
    "richelieu": "Monteregie",
    "montreal island": "Montreal",
    "island of montreal": "Montreal",
    "nunavik": "Nord-du-Quebec",
    "james bay": "Nord-du-Quebec",
    "eeyou istchee": "Nord-du-Quebec",
    "baie james": "Nord-du-Quebec",
    "ungava": "Nord-du-Quebec",
    "kuujjuaq": "Nord-du-Quebec",
    "kuujjuarapik": "Nord-du-Quebec",
    "whapmagoostui": "Nord-du-Quebec",
    "radisson": "Nord-du-Quebec",
    "chibougamau": "Nord-du-Quebec",
    "bylot": "Nord-du-Quebec",
    "hudson bay": "Nord-du-Quebec",
    "gatineau": "Outaouais",
    "saguenay": "Saguenay-Lac-Saint-Jean",
    "lac saint jean": "Saguenay-Lac-Saint-Jean",
    "lake saint jean": "Saguenay-Lac-Saint-Jean",
    "chicoutimi": "Saguenay-Lac-Saint-Jean",
}
_PROVINCE_NAMES = ("quebec", "province of quebec", "province de quebec", "whole province")
_NORTH_NAMES = ("northern quebec", "north of the 49th parallel", "nord du 49e parallele")
_SOUTH_NAMES = ("southern quebec", "south of the 49th parallel", "st lawrence lowlands", "st lawrence valley")


def normalize_place(text: str) -> str:
    """Lowercase, accent-free, punctuation-free form used to look up place names.

    "Saint" and "Sainte" become "st" so that "Lac-Saint-Jean" and "Lac St-Jean" agree.
    """
    s = unicodedata.normalize("NFKD", text or "")
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = re.sub(r"[^\w\s]", " ", s.replace("_", " "))
    s = re.sub(r"\b(sainte|saint|ste)\b", "st", s)
    s = re.sub(r"\b(the|of|de|du|des|la|le|les|region|area|administrative)\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()


@dataclass(frozen=True)
class RegionRef:
    """One Atlas region: an administrative region, nord_49 / sud_49, or the province."""

    region_type: str
    region_name: str

    @property
    def label(self) -> str:
        return "Quebec (whole province)" if self.region_type == PROVINCE else self.region_name


PROVINCE_REF = RegionRef(PROVINCE, "Quebec")
NORTH_REF = RegionRef(NORTH_SOUTH, NORTH)
SOUTH_REF = RegionRef(NORTH_SOUTH, SOUTH)


def _alias_index() -> dict[str, str]:
    by_norm = {normalize_place(name): name for name in REGION_NORTH}
    index = dict(by_norm)
    for alias, region in REGION_ALIASES.items():
        index[normalize_place(alias)] = by_norm[normalize_place(region)]
    return index


_ALIASES = _alias_index()
_NORM_PROVINCE = {normalize_place(x) for x in _PROVINCE_NAMES}
_NORM_NORTH = {normalize_place(x) for x in _NORTH_NAMES}
_NORM_SOUTH = {normalize_place(x) for x in _SOUTH_NAMES}


@dataclass
class PlaceMatch:
    """A place name matched to an Atlas region.

    level: "region" (administrative region), "north_south", "province",
    "outside" (not in Quebec), "unmatched", or "unknown" (no place information at all).
    """

    name: str
    level: str
    region: Optional[RegionRef] = None
    note: Optional[str] = None


def match_place(
    name: str,
    *,
    in_quebec: Optional[bool] = None,
    north_of_49: Optional[bool] = None,
) -> PlaceMatch:
    """Match one place to the Atlas region model, finest level first.

    1. A known administrative region or alias found in the name ("Gaspé Peninsula",
       "Nunavik"). When several regions are named, the first one in the text wins and
       the others are noted.
    2. North / south of the 49th parallel, from the name ("northern Quebec") or the
       extraction's ``north_of_49`` flag.
    3. The whole province, when the place is Quebec or in Quebec without more detail.
    A place stated as outside Quebec is "outside"; anything else is "unmatched".
    """
    norm = normalize_place(name)
    if in_quebec is False:
        return PlaceMatch(name, "outside")
    padded = f" {norm} "
    hits = sorted(
        (padded.find(f" {alias} "), -len(alias), region)
        for alias, region in _ALIASES.items()
        if f" {alias} " in padded
    )
    if hits:
        region = hits[0][2]
        others = sorted({r for _, _, r in hits[1:]} - {region})
        return PlaceMatch(name, "region", RegionRef(ADMIN, region), note=f"also names {', '.join(others)}" if others else None)
    if norm in _NORM_NORTH or north_of_49 is True:
        return PlaceMatch(name, "north_south", NORTH_REF)
    if norm in _NORM_SOUTH or north_of_49 is False:
        return PlaceMatch(name, "north_south", SOUTH_REF)
    if norm in _NORM_PROVINCE or in_quebec is True:
        return PlaceMatch(name, "province", PROVINCE_REF)
    return PlaceMatch(name, "unmatched")


def places_from_north_flag(bias_north_south: Any) -> list[PlaceMatch]:
    """Place information from the human annotation, which holds no place names.

    The only spatial clue is ``bias_north_south``: True -> north of the 49th parallel,
    False -> south, missing -> unknown (scored over the whole province where a region
    is needed, and no spatial novelty).
    """
    if bias_north_south is True or str(bias_north_south).strip().lower() in {"true", "yes", "1"}:
        return [PlaceMatch("annotation: north", "north_south", NORTH_REF)]
    if bias_north_south is False or str(bias_north_south).strip().lower() in {"false", "no", "0"}:
        return [PlaceMatch("annotation: south", "north_south", SOUTH_REF)]
    return [PlaceMatch("annotation: no place information", "unknown", PROVINCE_REF)]


def scope_regions(places: Sequence[PlaceMatch]) -> list[RegionRef]:
    """Regions a dataset covers, for scoring: matched regions, else the province.

    When places mix levels (an administrative region and "northern Quebec"), all are
    kept; a province-level place is dropped when a finer one exists.
    """
    refs = [p.region for p in places if p.region is not None]
    fine = [r for r in refs if r.region_type != PROVINCE]
    out = fine or refs or [PROVINCE_REF]
    seen: list[RegionRef] = []
    for r in out:
        if r not in seen:
            seen.append(r)
    return seen


# ---------------------------------------------------------------------------
# Years
# ---------------------------------------------------------------------------


def _to_year(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    m = re.search(r"(1[6-9]\d\d|20\d\d)", str(value))
    return int(m.group(1)) if m else None


def year_to_period(year: int) -> str:
    return "before_1950" if year < 1950 else f"{(year // 10) * 10}s"


def periods_for_years(start: Any, end: Any, *, max_year: int = 2029) -> list[str]:
    """Atlas decade bins covered by a year range; one year alone is a one-year range."""
    y0, y1 = _to_year(start), _to_year(end)
    if y0 is None and y1 is None:
        return []
    y0 = y0 if y0 is not None else y1
    y1 = y1 if y1 is not None else y0
    y0, y1 = min(y0, y1), min(max(y0, y1), max_year)
    out: list[str] = []
    for y in range(y0, y1 + 1):
        p = year_to_period(y)
        if p not in out:
            out.append(p)
    return out


# ---------------------------------------------------------------------------
# Atlas reference tables
# ---------------------------------------------------------------------------

_RANK_COLUMNS = {"species": "species", "genus": "genus", "family": "family", "order": "taxon_order", "class": "taxon_class"}


class AtlasReference:
    """What the Atlas holds, ready for lookups.

    Args:
        groups: the group x region x decade table.
        areas: region areas in km².
        species: the per-species table, or None (then taxa match at group rank only).
    """

    def __init__(self, groups: pd.DataFrame, areas: pd.DataFrame, species: Optional[pd.DataFrame] = None):
        self.groups = groups.copy()
        self.areas = areas.copy()
        self.species = species.copy() if species is not None else None
        self._area = {RegionRef(r.region_type, r.region_name): float(r.area_km2) for r in self.areas.itertuples()}
        self._area[PROVINCE_REF] = self._area.get(NORTH_REF, 0.0) + self._area.get(SOUTH_REF, 0.0)

    @classmethod
    def load(
        cls,
        species_csv: Optional[str | Path] = SPECIES_TABLE,
        groups_csv: str | Path = GROUP_TABLE,
        areas_csv: str | Path = AREA_TABLE,
    ) -> "AtlasReference":
        """Read the reference tables. A missing per-species file is allowed (group rank only)."""
        groups = pd.read_csv(groups_csv)
        areas = pd.read_csv(areas_csv)
        species = None
        if species_csv is not None and Path(species_csv).exists():
            species = pd.read_csv(species_csv)
        return cls(groups, areas, species)

    # -- regions -----------------------------------------------------------

    def area(self, region: RegionRef) -> float:
        return self._area[region]

    @staticmethod
    def _region_mask(df: pd.DataFrame, region: RegionRef) -> pd.Series:
        if region.region_type == PROVINCE:
            return df["region_type"] == NORTH_SOUTH
        return (df["region_type"] == region.region_type) & (df["region_name"] == region.region_name)

    # -- groups ------------------------------------------------------------

    @cached_property
    def _group_index(self) -> dict[tuple[str, RegionRef, str], float]:
        idx: dict[tuple[str, RegionRef, str], float] = {}
        for r in self.groups.itertuples():
            ref = RegionRef(r.region_type, r.region_name)
            idx[(r.taxon_group, ref, r.period)] = idx.get((r.taxon_group, ref, r.period), 0) + float(r.n_observations)
            if r.region_type == NORTH_SOUTH:
                key = (r.taxon_group, PROVINCE_REF, r.period)
                idx[key] = idx.get(key, 0) + float(r.n_observations)
        return idx

    def group_observations(self, group: str, region: RegionRef, period: Optional[str] = None) -> float:
        """Atlas observations of a broad group in a region, for one decade or all."""
        periods = [period] if period else PERIODS
        return sum(self._group_index.get((group, region, p), 0.0) for p in periods)

    @cached_property
    def group_species_count(self) -> dict[str, int]:
        """Distinct (non-sensitive) species the Atlas holds per group, whole province.

        From the per-species table when present; else the largest per-region-decade
        count of the aggregate table (an undercount)."""
        if self.species is not None:
            d = self.species[self.species["region_type"] == NORTH_SOUTH]
            return d.groupby("taxon_group")["id_taxa_ref_species"].nunique().astype(int).to_dict()
        return self.groups.groupby("taxon_group")["n_species"].max().astype(int).to_dict()

    @property
    def group_names(self) -> list[str]:
        return sorted(self.groups["taxon_group"].unique())

    # -- taxa --------------------------------------------------------------

    @cached_property
    def _names(self) -> dict[str, set[str]]:
        if self.species is None:
            return {rank: set() for rank in _RANK_COLUMNS}
        return {rank: set(self.species[col].dropna().unique()) for rank, col in _RANK_COLUMNS.items()}

    @cached_property
    def _taxon_index(self) -> dict[tuple[str, str], pd.DataFrame]:
        """(rank, name) -> rows of the per-species table, built on first use per rank."""
        return {}

    def _taxon_rows(self, rank: str, name: str) -> pd.DataFrame:
        key = (rank, name)
        if key not in self._taxon_index:
            if self.species is None:
                self._taxon_index[key] = pd.DataFrame(columns=["region_type", "region_name", "period", "n_observations", "taxon_group"])
            else:
                col = _RANK_COLUMNS[rank]
                self._taxon_index[key] = self.species[self.species[col] == name]
        return self._taxon_index[key]

    def has_taxon(self, rank: str, name: Optional[str]) -> bool:
        return bool(name) and name in self._names.get(rank, set())

    def taxon_observations(self, rank: str, name: str, region: RegionRef, period: Optional[str] = None) -> float:
        """Atlas observations of a taxon (summed over its species) in a region."""
        rows = self._taxon_rows(rank, name)
        rows = rows[self._region_mask(rows, region)]
        if period:
            rows = rows[rows["period"] == period]
        return float(rows["n_observations"].sum())

    def taxon_groups(self, rank: str, name: str) -> tuple[str, ...]:
        """Atlas groups of a taxon, most observations first."""
        rows = self._taxon_rows(rank, name)
        if rows.empty:
            return ()
        s = rows.groupby("taxon_group")["n_observations"].sum().sort_values(ascending=False)
        return tuple(s.index)

    @cached_property
    def _species_by_epithet(self) -> dict[str, list[tuple[str, str]]]:
        """Specific epithet -> [(Atlas species, group)], to find names the Atlas files under another genus."""
        if self.species is None:
            return {}
        out: dict[str, list[tuple[str, str]]] = {}
        pairs = self.species[["species", "taxon_group"]].drop_duplicates("species")
        for sp, grp in pairs.itertuples(index=False):
            words = str(sp).split()
            if len(words) == 2:
                out.setdefault(words[1], []).append((sp, grp))
        return out

    def same_epithet(self, species: str, groups: Sequence[str]) -> list[str]:
        """Atlas species with the same specific epithet in the same group (synonym candidates)."""
        words = (species or "").split()
        if len(words) < 2:
            return []
        return [sp for sp, grp in self._species_by_epithet.get(words[1], []) if grp in groups and sp != species]


# ---------------------------------------------------------------------------
# Taxa
# ---------------------------------------------------------------------------


@dataclass
class TaxonMatch:
    """One taxon mention matched to the Atlas.

    rank: the rank the match is made at (species, genus, family, order, class, group).
    name: the Atlas name at that rank (None for group-rank matches).
    groups: Atlas taxon groups the item counts toward.
    """

    mention: str
    status: str
    rank: Optional[str] = None
    name: Optional[str] = None
    groups: tuple[str, ...] = ()
    gbif_name: Optional[str] = None
    gbif_rank: Optional[str] = None
    note: Optional[str] = None

    @property
    def below_group(self) -> bool:
        """Named at family rank or finer: precise enough to judge taxonomic novelty.

        Orders and classes ("beetles" -> Coleoptera, "ants" -> Hymenoptera) still give a
        group, but the Atlas is never empty at that rank, so they are not judged."""
        return self.status in {"matched", "absent"} and self.rank in {"species", "genus", "family"}

    def to_dict(self) -> dict[str, Any]:
        return {
            "mention": self.mention, "status": self.status, "rank": self.rank, "name": self.name,
            "groups": ", ".join(self.groups), "gbif_name": self.gbif_name, "gbif_rank": self.gbif_rank,
            "note": self.note,
        }


def atlas_groups_for_record(record: Any) -> tuple[str, ...]:
    """Atlas groups from a GBIF record's broad groups (microbes -> MICROORGANISMS)."""
    out: list[str] = []
    for g in getattr(record, "broad_groups", ()) or ():
        atlas = BROAD_TO_ATLAS.get(g)
        if atlas is None and g == "other" and (getattr(record, "kingdom", "") or "").upper() in _MICROBE_KINGDOMS:
            atlas = "MICROORGANISMS"
        if atlas and atlas not in out:
            out.append(atlas)
    return tuple(out)


def _binomial(name: Optional[str]) -> Optional[str]:
    if not name:
        return None
    words = name.split()
    return " ".join(words[:2]) if len(words) >= 2 else None


def _is_ambiguous(record: Any) -> Optional[str]:
    note = (getattr(record, "note", None) or "").lower()
    if "homonym" in note:
        return "ambiguous: GBIF had several names to choose from (homonym)"
    return None


def _pick_groups(atlas_groups: Sequence[str], gbif_groups: Sequence[str]) -> tuple[str, ...]:
    """Atlas groups of the matched rows win (they define the aggregates), except the
    catch-all UNGROUPED, which gives way to the GBIF classification."""
    named = [g for g in atlas_groups if g != "UNGROUPED"]
    if named:
        return tuple(named)
    return tuple(gbif_groups) or tuple(atlas_groups)


_SPECIES_RANKS = {"SPECIES", "SUBSPECIES", "VARIETY", "FORM", "INFRASPECIFIC_NAME"}


def match_record(
    mention: str,
    record: Any,
    atlas: AtlasReference,
    *,
    same_taxon: Optional[Callable[[str, Any], bool]] = None,
) -> TaxonMatch:
    """Match one resolved GBIF record (``llm_metadata.gbif.TaxonRecord``) to the Atlas.

    Args:
        same_taxon: optional check ``(atlas_name, record) -> bool`` used when a species
            is absent under its GBIF name: an Atlas species with the same epithet in the
            same group is accepted if GBIF says it is the same taxon (the Atlas files
            *Notropis hudsonius* as *Hudsonius hudsonius*).
    """
    if record is None or not getattr(record, "resolved", False):
        return TaxonMatch(mention, "unresolved", note="GBIF found no match")
    ambiguous = _is_ambiguous(record)
    if ambiguous:
        return TaxonMatch(mention, "unresolved", gbif_name=record.canonical_name, gbif_rank=record.rank, note=ambiguous)

    gbif_groups = atlas_groups_for_record(record)
    rank = (record.rank or "").upper()
    base = dict(gbif_name=record.accepted_name or record.canonical_name or record.label, gbif_rank=record.rank)

    if record.kind == "taxon":
        if rank in _SPECIES_RANKS:
            candidates = [record.species, _binomial(record.accepted_name), _binomial(record.canonical_name)]
            atlas_rank = "species"
        elif rank in {"GENUS", "SUBGENUS"}:
            candidates, atlas_rank = [record.genus, record.canonical_name], "genus"
        else:  # family, subfamily, tribe: matched at family
            candidates, atlas_rank = [record.family, record.canonical_name], "family"
        candidates = list(dict.fromkeys(c for c in candidates if c))
        for name in candidates:
            if atlas.has_taxon(atlas_rank, name):
                groups = _pick_groups(atlas.taxon_groups(atlas_rank, name), gbif_groups)
                return TaxonMatch(mention, "matched", atlas_rank, name, groups, **base)
        name = candidates[0] if candidates else None
        if atlas_rank == "species" and name and same_taxon is not None:
            for alt in atlas.same_epithet(name, gbif_groups)[:8]:
                if same_taxon(alt, record):
                    groups = _pick_groups(atlas.taxon_groups("species", alt), gbif_groups)
                    return TaxonMatch(mention, "matched", "species", alt, groups, note=f"filed in the Atlas as {alt}", **base)
        parent = "genus" if atlas_rank == "species" else "family" if atlas_rank == "genus" else None
        parent_name = record.genus if parent == "genus" else record.family if parent == "family" else None
        parent_in_atlas = bool(parent) and atlas.has_taxon(parent, parent_name)
        if "vernacular" in (record.method or "") and atlas_rank in {"species", "genus"} and not parent_in_atlas \
                and not atlas.has_taxon("family", record.family):
            # A common name that lands on a family the Atlas never saw is more likely a
            # homonym ("parasites" -> a tongue-worm species) than a novelty.
            return TaxonMatch(
                mention, "unresolved", atlas_rank, name,
                note="ambiguous: common name resolved to a family absent from the Atlas", **base,
            )
        groups = gbif_groups
        if not groups and parent_in_atlas:
            groups = _pick_groups(atlas.taxon_groups(parent, parent_name), ())
        note = "absent from the Atlas extract (never recorded, or a sensitive species)"
        if parent_in_atlas:
            note += f"; its {parent} is in the Atlas"
        if not groups:
            return TaxonMatch(mention, "unresolved", atlas_rank, name, note="no Atlas group for this taxon", **base)
        return TaxonMatch(mention, "absent", atlas_rank, name, groups, note=note, **base)

    # Group: an order or class matches the Atlas column; anything coarser is a group label.
    if rank in {"ORDER", "CLASS"} and record.canonical_name:
        atlas_rank = rank.lower()
        if atlas.has_taxon(atlas_rank, record.canonical_name):
            groups = _pick_groups(atlas.taxon_groups(atlas_rank, record.canonical_name), gbif_groups)
            # A class that is a whole Atlas group (Insecta, Aves) stays at group rank.
            if len(groups) == 1 and record.canonical_name not in _GROUP_CLASSES:
                return TaxonMatch(mention, "matched", atlas_rank, record.canonical_name, groups, **base)
    if not gbif_groups:
        return TaxonMatch(mention, "unresolved", note="broad group not in the Atlas groups", **base)
    return TaxonMatch(mention, "group", "group", None, gbif_groups, **base)


def gbif_same_taxon(cache: Any = None) -> Callable[[str, Any], bool]:
    """A ``same_taxon`` check backed by GBIF: both names resolve to the same accepted species."""
    from llm_metadata.gbif import resolve_taxon

    def check(atlas_name: str, record: Any) -> bool:
        other = resolve_taxon(atlas_name, cache=cache, allow_qualifier_drop=False)
        if not other.resolved or other.kind != "taxon":
            return False
        mine = {record.key, record.species_key} - {None}
        theirs = {other.key, other.species_key} - {None}
        return bool(mine & theirs)

    return check


def clean_mention(text: str) -> str:
    """Remove spreadsheet artefacts (``_x000D_`` carriage returns) and extra spaces."""
    return re.sub(r"\s+", " ", (text or "").replace("_x000D_", " ")).strip()


_LOWER_BINOMIAL = re.compile(r"^[a-z]+ [a-z]+$")


def match_taxa(
    names: Optional[Sequence[str]],
    atlas: AtlasReference,
    *,
    cache: Any = None,
    resolver: Any = None,
    same_taxon: Optional[Callable[[str, Any], bool]] = None,
) -> list[TaxonMatch]:
    """Split, resolve and match every taxon mention of a dataset.

    Uses ``taxonomy_eval.resolve_species_items`` (splitting "A; B", count statements
    such as "73 weevil species", noise). ``resolver`` replaces it in tests, and
    ``same_taxon`` the GBIF synonym check (``gbif_same_taxon``; None in tests).
    Lower-case binomials ("salix planifolia") that fail are retried capitalised.
    """
    if resolver is None:
        from llm_metadata.taxonomy_eval import resolve_species_items as resolver  # local: heavy imports
    items = []
    for raw in names or []:
        if not isinstance(raw, str) or not raw.strip():
            continue
        text = clean_mention(raw)
        found = resolver([text], cache=cache)
        if _LOWER_BINOMIAL.match(text) and all(i.kind == "unresolved" for i in found):
            found = resolver([text[0].upper() + text[1:]], cache=cache) or found
        items.extend(found)
    out: list[TaxonMatch] = []
    for item in items:
        if item.kind == "other":
            out.append(TaxonMatch(item.mention, "other", note=item.other_reason))
            continue
        if item.kind == "count" and item.record is None:
            out.append(TaxonMatch(item.mention, "unresolved", note="count statement without a resolvable group"))
            continue
        if item.kind == "count" and (item.record.rank or "").upper() in _SPECIES_RANKS:
            # "c. 90 collembola species" resolved to one collembolan species: a resolver slip.
            out.append(TaxonMatch(item.mention, "unresolved", gbif_name=item.record.canonical_name,
                                  note="ambiguous: count statement resolved to a single species"))
            continue
        m = match_record(item.mention, item.record, atlas, same_taxon=same_taxon)
        if item.kind == "count":
            m.note = (m.note + "; " if m.note else "") + f"count statement ({item.count} taxa)"
        out.append(m)
    return out


def match_rates(matches: Iterable[TaxonMatch]) -> dict[str, Any]:
    """Share of mentions per status and per Atlas rank (the 'other' items excluded)."""
    matches = list(matches)
    items = [m for m in matches if m.status != "other"]
    n = len(items)
    status = Counter(m.status for m in items)
    ranks = Counter(m.rank for m in items if m.status in {"matched", "absent", "group"})
    return {
        "n_mentions": n,
        "n_other": len(matches) - n,
        **{f"share_{k}": (status[k] / n if n else float("nan")) for k in ("matched", "absent", "group", "unresolved")},
        "share_usable": (sum(status[k] for k in ("matched", "absent", "group")) / n) if n else float("nan"),
        "by_rank": dict(ranks),
    }


__all__ = [
    "AtlasReference",
    "BROAD_TO_ATLAS",
    "NORTH_REF",
    "PERIODS",
    "PROVINCE_REF",
    "PlaceMatch",
    "REGION_NORTH",
    "RegionRef",
    "SOUTH_REF",
    "TaxonMatch",
    "match_place",
    "match_rates",
    "match_record",
    "match_taxa",
    "normalize_place",
    "periods_for_years",
    "places_from_north_flag",
    "scope_regions",
]
