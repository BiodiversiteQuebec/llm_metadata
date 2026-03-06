"""Species string parsing utilities for ecological metadata extraction.

This module keeps the raw `species` field untouched, but provides structured
views that downstream notebooks and enrichment steps can use:

- `ParsedTaxon`: scientific/common name parsing with optional count capture
- `TaxonRichnessMention`: count + group parsing for strings like
  "73 weevil species" or "c.132 species of benthic community"

These models support analysis and derived-field evaluation without forcing the
LLM extraction contract itself to change.
"""

import re
from typing import Any, Optional, Sequence

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

_APPROX_PREFIX_RE = re.compile(
    r"^\s*(?P<approx>(?:c(?:irca)?\.?|ca\.?|approx(?:\.|imately)?|about|around))\s*",
    re.IGNORECASE,
)
_LEADING_COUNT_RE = re.compile(r"^(?P<count>\d+)\s+(?P<rest>.*)$")
_PARENS_RE = re.compile(r"\([^()]*\)")
_TRAILING_CONNECTOR_RE = re.compile(r"\b(?:and others?|others?)\b", re.IGNORECASE)
_OF_PREFIX_RE = re.compile(r"^(?:species|taxa|taxon)\s+of\s+", re.IGNORECASE)
_LEADING_ARTICLE_RE = re.compile(r"^(?:the|a|an)\s+", re.IGNORECASE)
_GROUP_STOPWORDS_RE = re.compile(
    r"\b(?:species|taxa|taxon|morphospecies|morphospecies used in analyses|otus?)\b",
    re.IGNORECASE,
)
_WHITESPACE_RE = re.compile(r"\s+")


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


def _singularize_last_token(text: str) -> str:
    """Apply a conservative singularization to the last token only."""
    if not text:
        return text

    words = text.split()
    if not words:
        return text

    last = words[-1]
    lower = last.lower()
    if len(lower) <= 3:
        return text
    if lower.endswith("ies") and len(lower) > 4:
        words[-1] = last[:-3] + "y"
    elif lower.endswith("ses") and len(lower) > 4:
        words[-1] = last[:-2]
    elif lower.endswith("s") and not lower.endswith(("ss", "us", "is")):
        words[-1] = last[:-1]
    return " ".join(words)


def normalize_taxon_group(text: Optional[str]) -> Optional[str]:
    """Normalize a taxonomic group label for comparison-oriented derived fields."""
    if text is None:
        return None

    s = text.strip()
    if not s:
        return None

    s = _PARENS_RE.sub(" ", s)
    s = _TRAILING_CONNECTOR_RE.sub(" ", s)
    s = _OF_PREFIX_RE.sub("", s)
    s = _LEADING_ARTICLE_RE.sub("", s)
    s = _GROUP_STOPWORDS_RE.sub(" ", s)
    s = s.strip(" ,.;:-")
    s = _WHITESPACE_RE.sub(" ", s).strip().lower()
    if not s:
        return None
    return _singularize_last_token(s)


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


def parse_taxon_richness(raw: str) -> dict:
    """Parse a count-bearing taxonomic richness mention from a raw string.

    Typical supported cases:
    - "73 weevil species" -> count=73, group="weevil"
    - "c.132 species of benthic community" -> count=132, group="benthic community"
    - "199 ground-dwelling beetles" -> count=199, group="ground-dwelling beetle"
    """
    if not raw or not isinstance(raw, str):
        return {
            "original": raw or "",
            "count": None,
            "group": None,
            "normalized_group": None,
            "approximate": False,
        }

    original = raw
    s = raw.strip()
    approximate = False

    approx_match = _APPROX_PREFIX_RE.match(s)
    if approx_match:
        approximate = True
        s = s[approx_match.end():].strip()

    count_match = _LEADING_COUNT_RE.match(s)
    if not count_match:
        return {
            "original": original,
            "count": None,
            "group": None,
            "normalized_group": None,
            "approximate": approximate,
        }

    count = int(count_match.group("count"))
    rest = count_match.group("rest").strip()
    group = normalize_taxon_group(rest)

    return {
        "original": original,
        "count": count,
        "group": group,
        "normalized_group": group,
        "approximate": approximate,
    }


def extract_parsed_taxa(species: Optional[Sequence[str]]) -> Optional[list["ParsedTaxon"]]:
    """Parse each raw `species` item into a `ParsedTaxon`."""
    if not species:
        return None
    parsed = [
        ParsedTaxon.model_validate(item)
        for item in species
        if isinstance(item, str) and item.strip()
    ]
    return parsed or None


def extract_taxon_richness_mentions(
    species: Optional[Sequence[str]],
) -> Optional[list["TaxonRichnessMention"]]:
    """Extract only count-bearing taxonomic mentions from a `species` list."""
    if not species:
        return None

    mentions = []
    for item in species:
        mention = TaxonRichnessMention.model_validate(item)
        if mention.count is None:
            continue
        mentions.append(mention)
    return mentions or None


def project_taxon_richness_counts(
    species: Optional[Sequence[str]],
    mentions: Optional[Sequence["TaxonRichnessMention"]] = None,
) -> Optional[list[int]]:
    """Project species strings into comparable richness counts.

    Priority:
    1. Use explicit count-bearing mentions when present.
    2. Otherwise fall back to the length of the parsed `species` list.

    This lets a GT value like "73 weevil species" compare against a prediction
    that enumerates 73 species names even when no count string was emitted.
    """
    if mentions is None:
        mentions = extract_taxon_richness_mentions(species)

    if mentions:
        counts = sorted({mention.count for mention in mentions if mention.count is not None})
        return counts or None

    if not species:
        return None

    cleaned = [item for item in species if isinstance(item, str) and item.strip()]
    return [len(cleaned)] if cleaned else None


def project_taxon_richness_group_keys(
    mentions: Optional[Sequence["TaxonRichnessMention"]],
) -> Optional[list[str]]:
    """Project richness mentions into exact-match comparison keys."""
    if not mentions:
        return None

    keys = sorted(
        {
            mention.comparison_key
            for mention in mentions
            if mention.count is not None and mention.normalized_group
        }
    )
    return keys or None


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

    @property
    def preferred_name(self) -> str:
        """Preferred display/comparison label."""
        return self.scientific or self.vernacular or self.original

    @model_validator(mode='before')
    @classmethod
    def parse_raw_string(cls, data: Any) -> Any:
        """Accept a raw string and parse it into structured fields."""
        if isinstance(data, str):
            return parse_species_string(data)
        return data


class TaxonRichnessMention(BaseModel):
    """Structured count + group mention parsed from a taxonomic string."""

    original: str
    count: Optional[int] = None
    group: Optional[str] = None
    normalized_group: Optional[str] = None
    approximate: bool = False

    @property
    def comparison_key(self) -> str:
        """Stable projection used for exact list/set comparison."""
        if self.count is None:
            return ""
        return f"{self.count}|{self.normalized_group or ''}"

    @model_validator(mode="before")
    @classmethod
    def parse_raw_string(cls, data: Any) -> Any:
        """Accept a raw string and parse it into structured richness fields."""
        if isinstance(data, str):
            return parse_taxon_richness(data)
        return data
