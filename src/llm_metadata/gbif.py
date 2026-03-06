"""
GBIF Species Match API wrapper for taxon key resolution.

Resolves species strings (scientific names, vernacular names, or mixed formats)
to GBIF backbone taxon keys via the GBIF Species Match API. Designed as a
preprocessing enrichment step for the LLM metadata pipeline — populates a
`gbif_keys` field on extracted models to enable integer-key-based evaluation
alongside traditional string matching.

API Documentation: https://www.gbif.org/developer/species#searching
Endpoint: GET https://api.gbif.org/v1/species/match

No authentication required; no documented rate limit. A small polite delay is
applied between requests to be considerate of the public API.
"""

import time
from dataclasses import dataclass
from typing import Optional

import requests
from joblib import Memory

from llm_metadata.logging_utils import logger
from llm_metadata.species_parsing import ParsedTaxon

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


def enrich_with_gbif(
    model: "DatasetFeatures",  # type: ignore[name-defined]  # avoid circular import
    confidence_threshold: int = 80,
    accept_higherrank: bool = True,
) -> "DatasetFeatures":
    """Resolve species strings to GBIF keys and return an enriched model copy.

    Reads ``model.species``, resolves each string to a GBIF backbone taxon key,
    and returns a new model instance with ``gbif_keys`` populated. The original
    model is not mutated.

    Args:
        model: A `DatasetFeatures` (or subclass) instance with a ``species`` field.
        confidence_threshold: Minimum GBIF confidence score to accept a match.
        accept_higherrank: Whether to accept HIGHERRANK (broader taxon) matches.

    Returns:
        A copy of `model` with ``gbif_keys`` set to a list of resolved integer
        keys, or ``None`` if no species were present or none resolved.

    Example:
        >>> enriched = enrich_with_gbif(extracted_model)
        >>> enriched.gbif_keys  # [5219243, 2435099, ...]
    """
    if not model.species:
        return model.model_copy(update={"gbif_keys": None})

    resolved = resolve_species_list(
        model.species,
        confidence_threshold=confidence_threshold,
        accept_higherrank=accept_higherrank,
    )
    keys = [r.gbif_match.gbif_key for r in resolved if r.gbif_match is not None]
    return model.model_copy(update={"gbif_keys": keys if keys else None})
