"""GBIF Species Match API wrapper for taxon key resolution."""

import json
import os
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlencode

import requests
from joblib import Memory

from llm_metadata.logging_utils import logger
from llm_metadata.species_parsing import (
    ParsedTaxon,
    normalize_group_label,
    strip_unbalanced_parens,
    normalize_vernacular,
    scientific_name_candidates,
    singularize_phrase,
    uninomial_candidates,
    vernacular_candidates,
)

# Setup joblib cache for deterministic re-runs
memory = Memory("./cache", verbose=0)

GBIF_MATCH_URL = "https://api.gbif.org/v1/species/match"
REQUEST_TIMEOUT = 15  # seconds
_POLITE_DELAY = 0.3   # seconds between requests (no documented rate limit)
_last_request_time: float = 0.0


# ---------------------------------------------------------------------------
# Core types
# ---------------------------------------------------------------------------

@dataclass
class GBIFMatch:
    """Structured result from a GBIF Species Match API call.

    Attributes:
        gbif_key: GBIF backbone taxon key (usageKey).
        scientific_name: Full scientific name with authorship.
        canonical_name: Name without authorship (e.g. "Tamias striatus").
        rank: Taxonomic rank (SPECIES, GENUS, FAMILY, …).
        confidence: Match confidence 0–100.
        match_type: EXACT, FUZZY, HIGHERRANK, or NONE.
        kingdom: Kingdom name, if available.
    """
    gbif_key: int
    scientific_name: str
    canonical_name: str
    rank: str
    confidence: int
    match_type: str
    kingdom: Optional[str]
    phylum: Optional[str] = None
    class_name: Optional[str] = None
    order: Optional[str] = None
    family: Optional[str] = None
    genus: Optional[str] = None


@dataclass
class ResolvedTaxon:
    """Container pairing a raw input string with its parse and GBIF resolution.

    Attributes:
        original: The raw input string before parsing.
        parsed: Structured `ParsedTaxon` representation.
        gbif_match: Resolved GBIF match, or None if resolution failed.
    """
    original: str
    parsed: ParsedTaxon
    gbif_match: Optional[GBIFMatch]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _polite_get(url: str, params: dict) -> requests.Response:
    """Make a GET request with a small polite delay between calls.

    Args:
        url: Request URL.
        params: Query parameters dict.

    Returns:
        HTTP response object.
    """
    global _last_request_time
    elapsed = time.time() - _last_request_time
    if elapsed < _POLITE_DELAY:
        time.sleep(_POLITE_DELAY - elapsed)
    _last_request_time = time.time()
    return requests.get(url, params=params, timeout=REQUEST_TIMEOUT)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@memory.cache
def match_species(
    name: str,
    kingdom: Optional[str] = None,
    strict: bool = False,
) -> Optional[GBIFMatch]:
    """Look up a species name against the GBIF backbone taxonomy.

    Calls ``GET https://api.gbif.org/v1/species/match`` and returns a
    structured `GBIFMatch` if a result is found above the confidence
    threshold, or ``None`` for no-match / low-confidence results.

    Results are cached via joblib for reproducible re-runs without
    repeated network calls.

    Args:
        name: Species name to look up (scientific or vernacular).
        kingdom: Optional kingdom hint to reduce ambiguity (e.g. "Animalia").
        strict: If True, only accept EXACT match type; reject FUZZY/HIGHERRANK.

    Returns:
        `GBIFMatch` on success, or ``None`` if not found / confidence too low.

    Example:
        >>> m = match_species("Tamias striatus")
        >>> if m:
        ...     print(m.gbif_key, m.canonical_name)
    """
    if not name or not name.strip():
        return None

    params: dict = {"name": name.strip(), "verbose": "true"}
    if kingdom:
        params["kingdom"] = kingdom

    try:
        response = _polite_get(GBIF_MATCH_URL, params)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as exc:
        logger.warning("GBIF API request failed for {!r}: {}", name, exc)
        return None

    match_type = data.get("matchType", "NONE")

    if match_type == "NONE":
        logger.debug("No GBIF match for {!r}", name)
        return None

    if strict and match_type not in ("EXACT",):
        logger.debug("Strict mode: skipping {} match for {!r}", match_type, name)
        return None

    usage_key = data.get("usageKey")
    if not usage_key:
        return None

    return GBIFMatch(
        gbif_key=int(usage_key),
        scientific_name=data.get("scientificName", ""),
        canonical_name=data.get("canonicalName", ""),
        rank=data.get("rank", ""),
        confidence=int(data.get("confidence", 0)),
        match_type=match_type,
        kingdom=data.get("kingdom"),
        phylum=data.get("phylum"),
        class_name=data.get("class"),
        order=data.get("order"),
        family=data.get("family"),
        genus=data.get("genus"),
    )


def resolve_species_list(
    species: list[str],
    confidence_threshold: int = 80,
    accept_higherrank: bool = True,
) -> list[ResolvedTaxon]:
    """Resolve a list of raw species strings to GBIF taxon keys.

    For each string:
    1. Parse with `ParsedTaxon` to extract scientific and vernacular components.
    2. Query GBIF with the scientific name (preferred) then vernacular (fallback).
    3. Filter by confidence threshold.
    4. Optionally skip HIGHERRANK matches (broad groups like "Mammalia").

    Args:
        species: List of raw species strings from LLM extraction or ground truth.
        confidence_threshold: Minimum confidence score (0–100) to accept a match.
        accept_higherrank: If False, skip matches with ``matchType == "HIGHERRANK"``.

    Returns:
        List of `ResolvedTaxon` objects (one per input string). Items that did
        not resolve will have ``gbif_match=None``.
    """
    results: list[ResolvedTaxon] = []

    for raw in species:
        parsed = ParsedTaxon.model_validate(raw)
        gbif_match: Optional[GBIFMatch] = None

        # Determine names to try, in priority order
        candidates: list[str] = []
        if parsed.scientific:
            candidates.append(parsed.scientific)
        if parsed.vernacular:
            candidates.append(parsed.vernacular)
        # If neither was extracted (e.g. ambiguous parenthetical), try original
        if not candidates and parsed.original:
            candidates.append(parsed.original)

        for name in candidates:
            match = match_species(name)
            if match is None:
                continue
            if match.confidence < confidence_threshold:
                logger.debug("Skipping low-confidence match ({}) for {!r}", match.confidence, name)
                continue
            if not accept_higherrank and match.match_type == "HIGHERRANK":
                logger.debug("Skipping HIGHERRANK match for {!r}", name)
                continue
            gbif_match = match
            break  # First acceptable match wins

        results.append(ResolvedTaxon(original=raw, parsed=parsed, gbif_match=gbif_match))

    return results


def resolve_model_species(
    model: "CoreFeatureModel",  # type: ignore[name-defined]  # avoid circular import
    confidence_threshold: int = 80,
    accept_higherrank: bool = True,
) -> list[ResolvedTaxon]:
    """Resolve the `species` field on a feature model to GBIF payloads.

    Args:
        model: A feature model instance with a ``species`` field.
        confidence_threshold: Minimum GBIF confidence score to accept a match.
        accept_higherrank: Whether to accept HIGHERRANK (broader taxon) matches.

    Returns:
        A list of resolved GBIF payloads. Empty when no species were present.
    """
    if not model.species:
        return []
    return resolve_species_list(
        model.species,
        confidence_threshold=confidence_threshold,
        accept_higherrank=accept_higherrank,
    )


# ===========================================================================
# Taxon resolution with classification (multi-rank evaluation, Atlas matching)
# ===========================================================================
#
# `resolve_taxon(name)` turns one free-text taxon string into a `TaxonRecord`:
# the GBIF backbone key, the classification (kingdom to species, names and
# keys) and a broad taxonomic group. It handles scientific names (with or
# without authorship, "sp."/"spp."), names embedded in decorated strings
# ("Atlantic salmon (Salmo salar)"), vernacular names in any language GBIF
# knows (GBIF vernacular search), and broad-group labels ("birds", "benthic
# macroinvertebrates") through a small curated vocabulary.
#
# GBIF responses are cached in a JSON file (see `GBIFCache`) so evaluations
# are reproducible and re-runs make no network calls.

GBIF_API_BASE = os.getenv("GBIF_API_BASE", "https://api.gbif.org/v1").rstrip("/")
GBIF_BACKBONE_DATASET_KEY = "d7dddbf4-2cf0-4f39-9b2a-bb099caae36c"
DEFAULT_TAXA_CACHE_PATH = Path(
    os.getenv(
        "GBIF_TAXA_CACHE",
        str(Path(__file__).resolve().parents[2] / "data" / "gbif" / "name_resolution_cache.json"),
    )
)

#: Broad taxonomic groups used for group-level scoring and for Atlas matching.
BROAD_GROUPS: tuple[str, ...] = (
    "birds",
    "mammals",
    "fish",
    "amphibians",
    "reptiles",
    "insects",
    "other arthropods",
    "molluscs",
    "other invertebrates",
    "vascular plants",
    "bryophytes",
    "algae",
    "fungi and lichens",
    "other",
)
_VERTEBRATE_GROUPS = ("birds", "mammals", "fish", "amphibians", "reptiles")
_INVERTEBRATE_GROUPS = ("insects", "other arthropods", "molluscs", "other invertebrates")
_PLANT_GROUPS = ("vascular plants", "bryophytes", "algae")

_REPTILE_CLASSES = {"REPTILIA", "TESTUDINES", "SQUAMATA", "CROCODYLIA", "RHYNCHOCEPHALIA", "SPHENODONTIA"}
_FISH_CLASSES = {
    "ACTINOPTERYGII", "ELASMOBRANCHII", "HOLOCEPHALI", "SARCOPTERYGII", "MYXINI",
    "PETROMYZONTI", "CEPHALASPIDOMORPHI", "CHONDRICHTHYES", "TELEOSTEI",
}
_TUNICATE_CLASSES = {"ASCIDIACEA", "THALIACEA", "APPENDICULARIA", "LEPTOCARDII"}
_BRYOPHYTE_PHYLA = {"BRYOPHYTA", "MARCHANTIOPHYTA", "ANTHOCEROTOPHYTA"}
_ALGAE_PHYLA = {"CHLOROPHYTA", "RHODOPHYTA", "CHAROPHYTA", "GLAUCOPHYTA", "OCHROPHYTA", "HAPTOPHYTA", "CRYPTOPHYTA"}

#: Curated broad-group labels: normalized singular label -> (GBIF name or None, broad groups).
#: The GBIF name gives a backbone key so finer taxa can be checked as "inside" the group.
#: Labels with no single backbone taxon (fish, invertebrates, algae) carry only groups.
GROUP_LABELS: dict[str, tuple[Optional[str], tuple[str, ...]]] = {
    # vertebrates
    "vertebrate": (None, _VERTEBRATE_GROUPS),
    "bird": ("Aves", ("birds",)),
    "songbird": ("Passeriformes", ("birds",)),
    "passerine": ("Passeriformes", ("birds",)),
    "waterfowl": ("Anseriformes", ("birds",)),
    "shorebird": ("Charadriiformes", ("birds",)),
    "raptor": (None, ("birds",)),
    "seabird": (None, ("birds",)),
    "mammal": ("Mammalia", ("mammals",)),
    "small mammal": ("Mammalia", ("mammals",)),
    "large mammal": ("Mammalia", ("mammals",)),
    "rodent": ("Rodentia", ("mammals",)),
    "bat": ("Chiroptera", ("mammals",)),
    "carnivore": ("Carnivora", ("mammals",)),
    "ungulate": (None, ("mammals",)),
    "fish": (None, ("fish",)),
    "freshwater fish": (None, ("fish",)),
    "amphibian": ("Amphibia", ("amphibians",)),
    "frog": ("Anura", ("amphibians",)),
    "anuran": ("Anura", ("amphibians",)),
    "salamander": ("Caudata", ("amphibians",)),
    "reptile": (None, ("reptiles",)),
    "turtle": ("Testudines", ("reptiles",)),
    "snake": ("Squamata", ("reptiles",)),
    "herptile": (None, ("amphibians", "reptiles")),
    "herpetofauna": (None, ("amphibians", "reptiles")),
    # insects
    "insect": ("Insecta", ("insects",)),
    "aquatic insect": ("Insecta", ("insects",)),
    "beetle": ("Coleoptera", ("insects",)),
    "weevil": ("Coleoptera", ("insects",)),
    "curculionoidea": ("Coleoptera", ("insects",)),
    "butterfly": ("Lepidoptera", ("insects",)),
    "moth": ("Lepidoptera", ("insects",)),
    "bee": ("Hymenoptera", ("insects",)),
    "wasp": ("Hymenoptera", ("insects",)),
    "ant": ("Hymenoptera", ("insects",)),
    "pollinator": (None, ("insects",)),
    "fly": ("Diptera", ("insects",)),
    "mosquito": ("Diptera", ("insects",)),
    "dragonfly": ("Odonata", ("insects",)),
    "damselfly": ("Odonata", ("insects",)),
    "odonate": ("Odonata", ("insects",)),
    "zygoptera": ("Odonata", ("insects",)),
    "anisoptera": ("Odonata", ("insects",)),
    "stonefly": ("Plecoptera", ("insects",)),
    "mayfly": ("Ephemeroptera", ("insects",)),
    "caddisfly": ("Trichoptera", ("insects",)),
    # other arthropods
    "arthropod": ("Arthropoda", ("insects", "other arthropods")),
    "spider": ("Araneae", ("other arthropods",)),
    "arachnid": ("Arachnida", ("other arthropods",)),
    "mite": ("Arachnida", ("other arthropods",)),
    "acari": ("Arachnida", ("other arthropods",)),
    "hydrachnidia": ("Arachnida", ("other arthropods",)),
    "tick": ("Ixodida", ("other arthropods",)),
    "springtail": ("Collembola", ("other arthropods",)),
    "crustacean": (None, ("other arthropods",)),
    "amphipod": ("Amphipoda", ("other arthropods",)),
    "isopod": ("Isopoda", ("other arthropods",)),
    "copepod": (None, ("other arthropods",)),
    # molluscs and other invertebrates
    "mollusc": ("Mollusca", ("molluscs",)),
    "mollusk": ("Mollusca", ("molluscs",)),
    "snail": ("Gastropoda", ("molluscs",)),
    "gastropod": ("Gastropoda", ("molluscs",)),
    "bivalve": ("Bivalvia", ("molluscs",)),
    "mussel": ("Bivalvia", ("molluscs",)),
    "annelid": ("Annelida", ("other invertebrates",)),
    "polychaete": ("Polychaeta", ("other invertebrates",)),
    "earthworm": ("Clitellata", ("other invertebrates",)),
    "worm": (None, ("other invertebrates",)),
    "nematode": ("Nematoda", ("other invertebrates",)),
    "echinoderm": ("Echinodermata", ("other invertebrates",)),
    "invertebrate": (None, _INVERTEBRATE_GROUPS),
    "macroinvertebrate": (None, _INVERTEBRATE_GROUPS),
    "benthic macroinvertebrate": (None, _INVERTEBRATE_GROUPS),
    "benthic invertebrate": (None, _INVERTEBRATE_GROUPS),
    "aquatic invertebrate": (None, _INVERTEBRATE_GROUPS),
    "benthic community": (None, _INVERTEBRATE_GROUPS),
    "benthic intertidal community": (None, (*_INVERTEBRATE_GROUPS, "algae")),
    "benthos": (None, _INVERTEBRATE_GROUPS),
    "macrobenthos": (None, _INVERTEBRATE_GROUPS),
    "macrofauna": (None, _INVERTEBRATE_GROUPS),
    "benthic macrofauna": (None, _INVERTEBRATE_GROUPS),
    "zooplankton": (None, ("other arthropods", "other invertebrates")),
    # plants, algae, fungi
    "plant": ("Tracheophyta", ("vascular plants",)),
    "vascular plant": ("Tracheophyta", ("vascular plants",)),
    "herbaceous plant": ("Tracheophyta", ("vascular plants",)),
    "understory plant": ("Tracheophyta", ("vascular plants",)),
    "vegetation": ("Tracheophyta", ("vascular plants",)),
    "tree": ("Tracheophyta", ("vascular plants",)),
    "shrub": ("Tracheophyta", ("vascular plants",)),
    "herb": ("Tracheophyta", ("vascular plants",)),
    "forb": ("Tracheophyta", ("vascular plants",)),
    "graminoid": ("Tracheophyta", ("vascular plants",)),
    "grass": ("Tracheophyta", ("vascular plants",)),
    "wildflower": ("Tracheophyta", ("vascular plants",)),
    "fern": ("Polypodiopsida", ("vascular plants",)),
    "conifer": ("Pinopsida", ("vascular plants",)),
    "monocot": ("Liliopsida", ("vascular plants",)),
    "dicot": ("Magnoliopsida", ("vascular plants",)),
    "moss": ("Bryophyta", ("bryophytes",)),
    "bryophyte": (None, ("bryophytes",)),
    "liverwort": ("Marchantiophyta", ("bryophytes",)),
    "alga": (None, ("algae",)),
    "macroalga": (None, ("algae",)),
    "seaweed": (None, ("algae",)),
    "phytoplankton": (None, ("algae",)),
    "diatom": ("Bacillariophyceae", ("algae",)),
    "fungus": ("Fungi", ("fungi and lichens",)),
    "mushroom": ("Fungi", ("fungi and lichens",)),
    "lichen": (None, ("fungi and lichens",)),
    "bacteria": ("Bacteria", ("other",)),
    "bacterium": ("Bacteria", ("other",)),
    "microbe": (None, ("other",)),
}

_RANK_LEVEL = {
    "KINGDOM": 1, "PHYLUM": 2, "CLASS": 3, "ORDER": 4, "SUPERFAMILY": 4.5,
    "FAMILY": 5, "SUBFAMILY": 5.2, "TRIBE": 5.4, "GENUS": 6, "SUBGENUS": 6.2,
    "SPECIES": 7, "SUBSPECIES": 8, "VARIETY": 8, "FORM": 8, "INFRASPECIFIC_NAME": 8,
}
_FAMILY_LEVEL = _RANK_LEVEL["FAMILY"]


class GBIFCache:
    """JSON file cache for trimmed GBIF responses, keyed by request path and params."""

    def __init__(self, path: Path | str = DEFAULT_TAXA_CACHE_PATH):
        self.path = Path(path)
        self._data: Optional[dict[str, Any]] = None

    def _load(self) -> dict[str, Any]:
        if self._data is None:
            if self.path.exists():
                self._data = json.loads(self.path.read_text(encoding="utf-8"))
            else:
                self._data = {}
        return self._data

    def __contains__(self, key: str) -> bool:
        return key in self._load()

    def get(self, key: str) -> Any:
        return self._load().get(key)

    def set(self, key: str, value: Any) -> None:
        data = self._load()
        data[key] = value
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=0, sort_keys=True, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.path)


_default_cache: Optional[GBIFCache] = None


def get_default_cache() -> GBIFCache:
    """Return the process-wide cache backed by `DEFAULT_TAXA_CACHE_PATH`."""
    global _default_cache
    if _default_cache is None:
        _default_cache = GBIFCache(DEFAULT_TAXA_CACHE_PATH)
    return _default_cache


_MATCH_FIELDS = (
    "usageKey", "acceptedUsageKey", "scientificName", "canonicalName", "rank", "status",
    "confidence", "matchType", "kingdom", "phylum", "class", "order", "family", "genus",
    "species", "kingdomKey", "phylumKey", "classKey", "orderKey", "familyKey", "genusKey",
    "speciesKey",
)


def _trim_match(data: dict) -> dict:
    out = {k: data[k] for k in _MATCH_FIELDS if data.get(k) is not None}
    # Keep exact-name alternatives: they resolve homonyms GBIF refuses to pick
    alternatives = [
        {k: alt[k] for k in _MATCH_FIELDS if alt.get(k) is not None}
        for alt in data.get("alternatives", []) or []
        if alt.get("matchType") == "EXACT"
    ]
    if alternatives:
        out["alternatives"] = alternatives
    return out


def _split_vernacular_entry(name: str) -> list[str]:
    return [p for p in re.split(r"[,;/]", name) if p.strip()]


def _trim_search(data: dict) -> dict:
    results = []
    for r in data.get("results", []):
        names: list[str] = []
        for entry in r.get("vernacularNames", []) or []:
            for part in _split_vernacular_entry(entry.get("vernacularName", "")):
                norm = normalize_vernacular(part)
                if norm and norm not in names:
                    names.append(norm)
        results.append({
            "key": r.get("key"),
            "canonicalName": r.get("canonicalName"),
            "rank": r.get("rank"),
            "taxonomicStatus": r.get("taxonomicStatus"),
            "kingdom": r.get("kingdom"),
            "vernacularNames": names,
        })
    return {"results": results}


def _http_get_json(url: str, params: dict) -> dict:
    """GET with a polite delay and a few retries on rate limits / server errors."""
    last_exc: Optional[Exception] = None
    for attempt in range(3):
        try:
            response = _polite_get(url, params)
            if response.status_code in (429, 500, 502, 503, 504):
                raise requests.HTTPError(f"HTTP {response.status_code}")
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            last_exc = exc
            time.sleep(2 * (attempt + 1))
    raise requests.RequestException(f"GBIF request failed after retries: {last_exc}")


def _gbif_request(path: str, params: dict, cache: Optional[GBIFCache]) -> Optional[dict]:
    """Cached GBIF GET. Failed requests return None and are not cached."""
    cache = cache if cache is not None else get_default_cache()
    key = f"{path}?{urlencode(sorted(params.items()))}"
    if key in cache:
        return cache.get(key)
    try:
        data = _http_get_json(f"{GBIF_API_BASE}{path}", params)
    except requests.RequestException as exc:
        logger.warning("GBIF request {} failed: {}", key, exc)
        return None
    trimmed = _trim_search(data) if path.endswith("/search") else _trim_match(data)
    cache.set(key, trimmed)
    return trimmed


@dataclass
class TaxonRecord:
    """A free-text taxon string resolved against the GBIF backbone.

    Attributes:
        query: The raw string as given.
        kind: "taxon" (family rank or finer), "group" (a broad-group label or a
            taxon above family rank), or "unresolved".
        method: How it resolved: "scientific", "vernacular",
            "vernacular, qualifier dropped", or "group label".
        matched_name: The candidate string that resolved (e.g. "Salmo salar"
            out of "Atlantic salmon (Salmo salar)").
        key: Accepted GBIF backbone key (synonyms point to their accepted taxon).
        usage_key: Key of the name as matched (differs from `key` for synonyms).
        label: Normalized group label for curated group labels ("beetle").
        broad_groups: One broad group, or several for mixed labels such as
            "benthic macroinvertebrates". Empty when undetermined.
        note: Short free-text explanation (synonym, qualifier dropped, ...).
    """

    query: str
    kind: str = "unresolved"
    method: Optional[str] = None
    matched_name: Optional[str] = None
    key: Optional[int] = None
    usage_key: Optional[int] = None
    scientific_name: Optional[str] = None
    canonical_name: Optional[str] = None
    accepted_name: Optional[str] = None
    rank: Optional[str] = None
    taxonomic_status: Optional[str] = None
    match_type: Optional[str] = None
    confidence: Optional[int] = None
    kingdom: Optional[str] = None
    phylum: Optional[str] = None
    class_name: Optional[str] = None
    order: Optional[str] = None
    family: Optional[str] = None
    genus: Optional[str] = None
    species: Optional[str] = None
    kingdom_key: Optional[int] = None
    phylum_key: Optional[int] = None
    class_key: Optional[int] = None
    order_key: Optional[int] = None
    family_key: Optional[int] = None
    genus_key: Optional[int] = None
    species_key: Optional[int] = None
    label: Optional[str] = None
    broad_groups: tuple[str, ...] = ()
    note: Optional[str] = None

    @property
    def resolved(self) -> bool:
        return self.kind != "unresolved"

    @property
    def rank_level(self) -> Optional[float]:
        return _RANK_LEVEL.get((self.rank or "").upper())

    @property
    def broad_group(self) -> Optional[str]:
        """The single broad group, or None when mixed or undetermined."""
        return self.broad_groups[0] if len(self.broad_groups) == 1 else None

    @property
    def lineage_keys(self) -> set[int]:
        """Backbone keys of this taxon and all its parents (for containment checks)."""
        keys = {
            self.key, self.usage_key, self.kingdom_key, self.phylum_key, self.class_key,
            self.order_key, self.family_key, self.genus_key, self.species_key,
        }
        return {k for k in keys if k is not None}

    def key_at(self, rank: str) -> Optional[int]:
        """Backbone key at "exact", "species", "genus" or "family" rank, if this record reaches it."""
        level = self.rank_level
        if self.kind != "taxon" or level is None:
            return None
        if rank == "exact":
            return self.key
        needed = {"species": _RANK_LEVEL["SPECIES"], "genus": _RANK_LEVEL["GENUS"], "family": _FAMILY_LEVEL}[rank]
        if level < needed:
            return None
        return {"species": self.species_key, "genus": self.genus_key, "family": self.family_key}[rank]

    def name_at(self, rank: str) -> Optional[str]:
        """Display name at a rank (accepted names)."""
        if rank == "exact":
            return self.accepted_name or self.canonical_name
        return {"species": self.species, "genus": self.genus, "family": self.family}.get(rank)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["broad_groups"] = list(self.broad_groups)
        return d


def broad_groups_for_classification(
    kingdom: Optional[str],
    phylum: Optional[str] = None,
    class_name: Optional[str] = None,
    order: Optional[str] = None,
) -> tuple[str, ...]:
    """Map a GBIF classification to one broad group (or several when too coarse to tell).

    Ray-finned fishes have no class in the current GBIF backbone, so a
    chordate with an order but no class is counted as fish.
    """
    k = (kingdom or "").upper()
    p = (phylum or "").upper()
    c = (class_name or "").upper()
    if k == "ANIMALIA":
        if not p:
            return (*_VERTEBRATE_GROUPS, *_INVERTEBRATE_GROUPS)
        if p == "CHORDATA":
            if c == "AVES":
                return ("birds",)
            if c == "MAMMALIA":
                return ("mammals",)
            if c == "AMPHIBIA":
                return ("amphibians",)
            if c in _REPTILE_CLASSES:
                return ("reptiles",)
            if c in _FISH_CLASSES or (not c and order):
                return ("fish",)
            if c in _TUNICATE_CLASSES:
                return ("other invertebrates",)
            return _VERTEBRATE_GROUPS if not c else ("other",)
        if p == "ARTHROPODA":
            if not c:
                return ("insects", "other arthropods")
            return ("insects",) if c == "INSECTA" else ("other arthropods",)
        if p == "MOLLUSCA":
            return ("molluscs",)
        return ("other invertebrates",)
    if k == "PLANTAE":
        if p == "TRACHEOPHYTA":
            return ("vascular plants",)
        if p in _BRYOPHYTE_PHYLA:
            return ("bryophytes",)
        if p in _ALGAE_PHYLA:
            return ("algae",)
        return _PLANT_GROUPS if not p else ("other",)
    if k == "CHROMISTA":
        return ("algae",) if p in _ALGAE_PHYLA else ("other",)
    if k == "FUNGI":
        return ("fungi and lichens",)
    if k:
        return ("other",)
    return ()


def _accept_match(query: str, data: Optional[dict]) -> bool:
    """Decide whether a /species/match answer is trustworthy for this query."""
    if not data or not data.get("usageKey"):
        return False
    match_type = data.get("matchType", "NONE")
    status = (data.get("status") or "").upper()
    if match_type == "NONE" or status == "DOUBTFUL":
        return False
    canonical = data.get("canonicalName") or ""
    first_word = query.split()[0] if query.split() else ""
    single_word = len(query.split()) == 1
    if match_type == "EXACT":
        if single_word:
            return canonical == query
        return int(data.get("confidence", 0)) >= 70
    if match_type == "FUZZY":
        # Spelling variants of the epithet only: same genus, high confidence
        return (
            not single_word
            and int(data.get("confidence", 0)) >= 90
            and canonical.split()[0] == first_word
        )
    if match_type == "HIGHERRANK":
        # "Mytilus spp." -> genus Mytilus; never accept a guess on another word.
        # A single word can come back as HIGHERRANK when a kingdom hint is given.
        return canonical == first_word
    return False


def _record_from_match(query: str, matched_name: str, data: dict, method: str) -> TaxonRecord:
    usage_key = int(data["usageKey"])
    accepted_key = int(data.get("acceptedUsageKey") or usage_key)
    status = data.get("status")
    rank = data.get("rank")
    accepted_name = data.get("canonicalName")
    notes = [data["note"]] if data.get("note") else []
    if status == "SYNONYM":
        if rank == "SPECIES" and data.get("species"):
            accepted_name = data["species"]
        notes.append(f"synonym of {accepted_name}" if accepted_name != data.get("canonicalName") else "synonym")
    note = "; ".join(notes) or None
    record = TaxonRecord(
        query=query,
        kind="taxon",
        method=method,
        matched_name=matched_name,
        key=accepted_key,
        usage_key=usage_key,
        scientific_name=data.get("scientificName"),
        canonical_name=data.get("canonicalName"),
        accepted_name=accepted_name,
        rank=rank,
        taxonomic_status=status,
        match_type=data.get("matchType"),
        confidence=data.get("confidence"),
        kingdom=data.get("kingdom"),
        phylum=data.get("phylum"),
        class_name=data.get("class"),
        order=data.get("order"),
        family=data.get("family"),
        genus=data.get("genus"),
        species=data.get("species"),
        kingdom_key=data.get("kingdomKey"),
        phylum_key=data.get("phylumKey"),
        class_key=data.get("classKey"),
        order_key=data.get("orderKey"),
        family_key=data.get("familyKey"),
        genus_key=data.get("genusKey"),
        species_key=data.get("speciesKey"),
        note=note,
    )
    record.broad_groups = broad_groups_for_classification(
        record.kingdom, record.phylum, record.class_name, record.order
    )
    level = record.rank_level
    if level is not None and level < _FAMILY_LEVEL:
        record.kind = "group"
    return record


def match_scientific(
    name: str,
    *,
    kingdom: Optional[str] = None,
    cache: Optional[GBIFCache] = None,
) -> Optional[dict]:
    """Cached GBIF /species/match call; returns the trimmed answer if acceptable.

    When GBIF declines to choose between homonyms ("Eteone" is both a
    polychaete genus and a butterfly synonym; "Epilobium angustifolium" has
    two synonym usages), an exact-name alternative is used: the single
    accepted one, or else the first synonym in GBIF's order. Several accepted
    homonyms stay unresolved.
    """
    params = {"name": name, "verbose": "true"}
    if kingdom:
        params["kingdom"] = kingdom
    data = _gbif_request("/species/match", params, cache)
    if _accept_match(name, data):
        return data
    words = name.split()
    target = words[0] if len(words) == 2 and words[1].lower() in {"spp.", "spp", "sp.", "sp"} else name
    exact = [a for a in (data or {}).get("alternatives", []) if a.get("canonicalName") == target]
    accepted = [a for a in exact if a.get("status") == "ACCEPTED"]
    if len(accepted) == 1:
        return {**accepted[0], "note": "homonym: the only accepted exact name was taken"}
    if not accepted and exact:
        return {**exact[0], "note": "homonym: first exact synonym in GBIF order was taken"}
    if target != name:
        # "Eteone spp." can come back as kingdom Animalia; retry the bare genus
        return match_scientific(target, kingdom=kingdom, cache=cache)
    return None


_VERNACULAR_RANK_PREFERENCE = {"SPECIES": 0, "SUBSPECIES": 1, "VARIETY": 1, "FORM": 1, "GENUS": 2, "FAMILY": 3}


def search_vernacular(phrase: str, *, cache: Optional[GBIFCache] = None) -> Optional[dict]:
    """Find the backbone taxon whose vernacular name equals `phrase`.

    Uses GBIF full-text search on vernacular names (backbone only, singular and
    plural forms), then keeps only results with a vernacular name equal to the
    phrase after case, accent, hyphen and plural normalization.

    Choice among the exact hits: accepted names first, then species over
    subspecies over genus over family, then the taxon with the most vernacular
    names (a proxy for the common, well-known taxon: Procyon lotor rather than
    a raccoon subspecies).

    A name shared by several genera ("water mite" is given to taxa in more
    than twenty genera and families) is ambiguous and returns None, so the
    caller can fall back to a broad-group label.

    Returns:
        The chosen search result (trimmed dict) or None.
    """
    norm = normalize_vernacular(phrase)
    if not norm:
        return None
    variants = [norm]
    singular = singularize_phrase(norm)
    if singular not in variants:
        variants.append(singular)

    hits_by_key: dict[Any, tuple[int, dict]] = {}
    order = 0
    for query in variants:
        data = _gbif_request(
            "/species/search",
            {"q": query, "qField": "VERNACULAR", "datasetKey": GBIF_BACKBONE_DATASET_KEY, "limit": 50},
            cache,
        )
        for result in (data or {}).get("results", []):
            order += 1
            if not result.get("canonicalName") or result.get("key") in hits_by_key:
                continue
            if any(v in variants or singularize_phrase(v) in variants for v in result.get("vernacularNames", [])):
                hits_by_key[result.get("key")] = (order, result)
    if not hits_by_key:
        return None

    hits = [result for _, result in sorted(hits_by_key.values(), key=lambda item: item[0])]
    accepted = [r for r in hits if r.get("taxonomicStatus") == "ACCEPTED"] or hits
    genera = {
        r["canonicalName"].split()[0]
        for r in accepted
        if _RANK_LEVEL.get(r.get("rank") or "", 0) >= _RANK_LEVEL["GENUS"]
    }
    if len(genera) > 2:
        logger.debug("Ambiguous vernacular name {!r}: {} genera", phrase, len(genera))
        return None

    def sort_key(item: tuple[int, dict]) -> tuple:
        index, r = item
        return (
            _VERNACULAR_RANK_PREFERENCE.get(r.get("rank") or "", 4),
            -len(r.get("vernacularNames", [])),
            index,
        )

    return sorted(enumerate(accepted), key=sort_key)[0][1]


def resolve_vernacular(
    phrase: str,
    *,
    query: Optional[str] = None,
    cache: Optional[GBIFCache] = None,
) -> Optional[TaxonRecord]:
    """Resolve a vernacular name to a `TaxonRecord` (vernacular search, then match)."""
    hit = search_vernacular(phrase, cache=cache)
    if hit is None:
        return None
    data = match_scientific(hit["canonicalName"], kingdom=hit.get("kingdom"), cache=cache)
    if data is None:
        return None
    return _record_from_match(query or phrase, phrase, data, method="vernacular")


def resolve_group_label(
    text: str,
    *,
    query: Optional[str] = None,
    cache: Optional[GBIFCache] = None,
) -> Optional[TaxonRecord]:
    """Resolve a broad-group label ("birds", "small mammals", "benthic communities").

    Looks up the whole normalized label, then its last two words, then its last
    word in `GROUP_LABELS`.
    """
    norm = singularize_phrase(normalize_vernacular(normalize_group_label(text)))
    if not norm:
        return None
    words = norm.split()
    for candidate in (norm, " ".join(words[-2:]), words[-1]):
        if candidate not in GROUP_LABELS:
            continue
        gbif_name, groups = GROUP_LABELS[candidate]
        record = TaxonRecord(query=query or text, method="group label", matched_name=text, label=candidate)
        if gbif_name:
            data = match_scientific(gbif_name, cache=cache)
            if data is not None:
                record = _record_from_match(query or text, text, data, method="group label")
                record.label = candidate
        record.kind = "group"
        record.broad_groups = tuple(groups)
        return record
    return None


def resolve_taxon(
    name: str,
    *,
    cache: Optional[GBIFCache] = None,
    allow_qualifier_drop: bool = True,
) -> TaxonRecord:
    """Resolve one free-text taxon string to a GBIF backbone record with its classification.

    Steps, first success wins:

    1. The whole string is a curated broad-group label ("birds", "fish").
    2. Scientific names found in the string, binomials first
       ("wood turtle (Glyptemys insculpta)" -> Glyptemys insculpta;
       "Vaccinium spp" -> genus Vaccinium; authorship is ignored).
    3. Single capitalised words that are higher-taxon names ("Histeridae").
    4. GBIF vernacular search on the text outside, then inside, parentheses
       (any language GBIF knows: "raccoons", "sapin baumier").
    5. Broad-group label from the last words ("resident bird species" -> birds).
    6. Vernacular search after dropping leading qualifiers
       ("boreal caribou" -> "caribou"); flagged in `note`.

    A record above family rank (order, class, ...) gets ``kind="group"``.
    The raw string is always kept in ``query``.

    Args:
        name: Raw taxon string (scientific, vernacular, decorated or a group label).
        cache: Optional `GBIFCache`; defaults to the shared JSON cache.
        allow_qualifier_drop: Whether step 6 may run.

    Returns:
        A `TaxonRecord`; ``kind == "unresolved"`` when nothing matched.
    """
    raw = name or ""
    text = strip_unbalanced_parens(raw.strip())
    if not text:
        return TaxonRecord(query=raw)

    # 1. Whole string is a group label
    label = singularize_phrase(normalize_vernacular(normalize_group_label(text)))
    if label in GROUP_LABELS:
        record = resolve_group_label(text, query=raw, cache=cache)
        if record is not None:
            return record

    # 2. Binomials / genus-level names
    for candidate in scientific_name_candidates(text):
        data = match_scientific(candidate, cache=cache)
        if data is not None:
            return _record_from_match(raw, candidate, data, method="scientific")

    # 3. Uninomials (higher taxa), with curated fallbacks for names absent from the backbone
    for candidate in uninomial_candidates(text):
        data = match_scientific(candidate, cache=cache)
        if data is not None:
            return _record_from_match(raw, candidate, data, method="scientific")
        if candidate.lower() in GROUP_LABELS:
            record = resolve_group_label(candidate, query=raw, cache=cache)
            if record is not None:
                return record

    phrases = vernacular_candidates(text)

    # 4. Vernacular names
    for phrase in phrases:
        record = resolve_vernacular(phrase, query=raw, cache=cache)
        if record is not None:
            return record

    # 5. Group label from the head noun
    for phrase in phrases:
        record = resolve_group_label(phrase, query=raw, cache=cache)
        if record is not None:
            return record

    # 6. Drop leading qualifiers ("Atlantic-Gaspésie caribou" -> "caribou").
    #    Not for strings holding a scientific name that failed ("Eteone sp").
    if allow_qualifier_drop and not scientific_name_candidates(text):
        for phrase in phrases:
            words = normalize_vernacular(phrase).split()
            for start in range(1, len(words)):
                shorter = " ".join(words[start:])
                if len(shorter) < 4:
                    continue
                record = resolve_vernacular(shorter, query=raw, cache=cache)
                if record is not None and (record.rank_level or 0) >= _RANK_LEVEL["GENUS"]:
                    record.method = "vernacular, qualifier dropped"
                    record.note = f"matched on '{shorter}'"
                    return record

    return TaxonRecord(query=raw)


def enrich_with_gbif(
    model: "CoreFeatureModel",  # type: ignore[name-defined]  # avoid circular import
    confidence_threshold: int = 80,
    accept_higherrank: bool = True,
) -> "DatasetFeaturesEvaluation":
    """Backward-compatible convenience wrapper returning an evaluation model."""
    from llm_metadata.schemas.fuster_features import DatasetFeaturesEvaluation

    resolved = resolve_model_species(
        model,
        confidence_threshold=confidence_threshold,
        accept_higherrank=accept_higherrank,
    )
    return DatasetFeaturesEvaluation.from_extraction(model, gbif=resolved)
