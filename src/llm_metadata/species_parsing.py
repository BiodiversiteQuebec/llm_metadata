"""
Species string parsing utilities for ecological metadata extraction.

Provides `ParsedTaxon`, a Pydantic model that parses raw species strings
into structured components (scientific name, vernacular name, count, group flag).
Used as a preprocessing step before GBIF taxon key resolution.

Typical input formats handled:
- "Tamias striatus" → scientific
- "caribou" → vernacular
- "wood turtle (Glyptemys insculpta)" → vernacular + scientific
- "Glyptemys insculpta (wood turtle)" → scientific + vernacular
- "41 fish mock species" → count=41, vernacular="fish", is_group=True
- "ground-dwelling beetles" → vernacular, is_group=True
"""

import re
from typing import Any, Optional

from pydantic import BaseModel, model_validator


# Words that indicate a broad taxonomic group description rather than a specific taxon
_GROUP_TERMS = {
    "species", "spp", "sp", "fish", "birds", "mammals", "insects",
    "plants", "fungi", "bacteria", "invertebrates", "vertebrates",
    "beetles", "flies", "moths", "butterflies", "bees", "wasps", "ants",
    "trees", "shrubs", "grasses", "ferns", "mosses", "lichens",
    "reptiles", "amphibians", "worms", "spiders", "mites", "ticks",
    "algae", "diatoms", "plankton", "zooplankton", "phytoplankton",
    "organisms", "taxa", "taxon",
}

# Trailing noise suffixes to strip (order matters — longest first)
_NOISE_SUFFIXES = [
    "mock species",
    "species",
]


def _strip_count(s: str) -> tuple[str, Optional[int]]:
    """Strip a leading integer count from a species string.

    Returns (remainder, count) where count is None if no leading number.

    Examples:
        "41 fish mock species" → ("fish mock species", 41)
        "Tamias striatus" → ("Tamias striatus", None)
    """
    m = re.match(r'^(\d+)\s+(.*)', s.strip())
    if m:
        return m.group(2).strip(), int(m.group(1))
    return s.strip(), None


def _strip_noise_suffixes(s: str) -> str:
    """Strip trailing noise words (e.g., 'mock species', 'species') from a string."""
    lower = s.lower()
    for suffix in _NOISE_SUFFIXES:
        if lower.endswith(suffix):
            s = s[:len(s) - len(suffix)].strip()
            lower = s.lower()
    return s


def looks_scientific(text: str) -> bool:
    """Heuristic: detect whether a string looks like a scientific name.

    Scientific names typically have a capitalized genus followed by a
    lowercase species epithet (binomial nomenclature).

    Args:
        text: Species name string to check.

    Returns:
        True if the string matches the scientific name pattern.
    """
    words = text.split()
    if len(words) < 2:
        return False
    return words[0][0].isupper() and words[1][0].islower()


def parse_species_string(raw: str) -> dict:
    """Parse a raw species string into structured components.

    Preprocessing pipeline:
    1. Strip leading count (capture as int)
    2. Strip trailing noise words ("mock species", "species")
    3. Parenthetical split for "name (other name)" patterns
    4. Classify scientific vs vernacular via `looks_scientific()`
    5. Set is_group_description when count was present or name is a broad group term

    Args:
        raw: Raw species string from LLM extraction or ground truth.

    Returns:
        Dict suitable for constructing a `ParsedTaxon` instance.
    """
    if not raw or not isinstance(raw, str):
        return {
            "original": raw or "",
            "scientific": None,
            "vernacular": None,
            "count": None,
            "is_group_description": False,
        }

    original = raw
    s = raw.strip()

    # 1. Strip leading count
    s, count = _strip_count(s)

    # 2. Strip trailing noise
    s = _strip_noise_suffixes(s)

    scientific: Optional[str] = None
    vernacular: Optional[str] = None

    # 3. Parenthetical split
    paren_match = re.match(r'^([^()]+)\s*\(([^()]+)\)\s*$', s)
    if paren_match:
        before = paren_match.group(1).strip()
        inside = paren_match.group(2).strip()

        if looks_scientific(before):
            scientific = before
            vernacular = inside
        elif looks_scientific(inside):
            scientific = inside
            vernacular = before
        else:
            # Can't determine — treat the full string as vernacular
            vernacular = s
    else:
        # 4. Classify without parentheses
        if looks_scientific(s):
            scientific = s
        else:
            vernacular = s

    # 5. Determine group description flag
    # It's a group if a count was present, or the core name is a known group term
    core = (scientific or vernacular or "").lower().strip()
    is_group = count is not None or core in _GROUP_TERMS

    return {
        "original": original,
        "scientific": scientific,
        "vernacular": vernacular,
        "count": count,
        "is_group_description": is_group,
    }


class ParsedTaxon(BaseModel):
    """Structured representation of a parsed species/taxon string.

    Accepts a raw string via `model_validator(mode='before')` and
    parses it into scientific name, vernacular name, count, and group flag.

    Usage:
        pt = ParsedTaxon.model_validate("wood turtle (Glyptemys insculpta)")
        # pt.scientific == "Glyptemys insculpta"
        # pt.vernacular == "wood turtle"

        pt2 = ParsedTaxon.model_validate("41 fish mock species")
        # pt2.count == 41
        # pt2.is_group_description == True
    """

    original: str
    scientific: Optional[str] = None
    vernacular: Optional[str] = None
    count: Optional[int] = None
    is_group_description: bool = False

    @model_validator(mode='before')
    @classmethod
    def parse_raw_string(cls, data: Any) -> Any:
        """Accept a raw string and parse it into structured fields."""
        if isinstance(data, str):
            return parse_species_string(data)
        return data
