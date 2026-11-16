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
_COMMON_DELIMITER_RE = re.compile(r"\s*(?:,|;|/|\||&|\+|\band\b)\s*", re.IGNORECASE)
_NUMERIC_FRAGMENT_RE = re.compile(
    r"\b(?:(?:c(?:irca)?\.?|ca\.?|approx(?:\.|imately)?|about|around)\s*)?\d+(?:\.\d+)?\b",
    re.IGNORECASE,
)


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


def extract_species_richness_mentions(
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


def project_species_richness_counts(
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
        mentions = extract_species_richness_mentions(species)

    if mentions:
        counts = sorted({mention.count for mention in mentions if mention.count is not None})
        return counts or None

    if not species:
        return None

    cleaned = [item for item in species if isinstance(item, str) and item.strip()]
    return [len(cleaned)] if cleaned else None


def project_species_richness_group_keys(
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


def project_species_stripped_richness(
    species: Optional[Sequence[str]],
) -> Optional[list[str]]:
    """Project species strings into taxon labels after dropping count-bearing fragments.

    Pipeline:
    1. Split each raw item on common delimiters such as commas, semicolons, slashes, and "and".
    2. Drop any delimited part that contains a numeric richness/count signal.
    3. Collapse whitespace and drop empty parts.

    Examples:
        ["73 weevil species"] -> None
        ["c.32 ground-dwelling beetles, Acer saccharum"] -> ["Acer saccharum"]
    """
    if not species:
        return None

    out: list[str] = []
    seen: set[str] = set()

    for item in species:
        if not isinstance(item, str) or not item.strip():
            continue
        parts = _COMMON_DELIMITER_RE.split(item.strip())
        for part in parts:
            if _NUMERIC_FRAGMENT_RE.search(part):
                continue
            cleaned = part
            cleaned = _WHITESPACE_RE.sub(" ", cleaned).strip(" ,.;:-")
            if not cleaned or not re.search(r"[A-Za-z]", cleaned):
                continue
            dedupe_key = cleaned.casefold()
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            out.append(cleaned)

    return out or None


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


# ---------------------------------------------------------------------------
# Taxon mentions: splitting decorated strings and finding name candidates
# ---------------------------------------------------------------------------
#
# A raw `species` item can hold one taxon ("Atlantic salmon (Salmo salar)"),
# several taxa ("Histeridae; Silphidae; Nicrophorus sayi"), a count statement
# ("73 weevil species"), a broad-group label ("benthic communities"), or noise
# ("and others)"). The helpers below are pure string processing: they split
# an item into mentions and list the names worth sending to GBIF. Network
# resolution lives in `llm_metadata.gbif`.

_BINOMIAL_RE = re.compile(
    r"\b(?P<genus>[A-Z][a-z]{2,})\s+"
    r"(?P<epithet>[a-z][a-z-]{1,}\.?)"
    r"(?:\s+(?:(?:subsp|ssp|var|f)\.\s+)?(?P<infra>[a-z][a-z-]{2,}))?"
)
_UNINOMIAL_RE = re.compile(r"\b[A-Z][a-z]{3,}\b")
_COUNT_RE = re.compile(
    r"(?<![\w.,])(?P<approx>(?:c(?:irca)?\.?|ca\.?|approx(?:\.|imately)?|about|around|~)\s*)?"
    r"(?P<count>\d{1,5})\s+(?=[A-Za-z(])",
    re.IGNORECASE,
)
_GENUS_ONLY_EPITHETS = {"sp", "sp.", "spp", "spp.", "cf", "cf.", "aff", "aff.", "individuals", "indet", "indet."}
_HYBRID_RE = re.compile(r"\bhybrid|\s×\s|\sx\s(?=[A-Z])", re.IGNORECASE)
_NOISE_RE = re.compile(r"^\s*(?:and\s+)?(?:others?|etc\.?|various|unidentified|unknown)\s*\)?\s*$", re.IGNORECASE)
_GENERIC_LABEL_RE = re.compile(r"\b(?:species|taxa|taxon|individuals|morphospecies|otus?)\b\s*$", re.IGNORECASE)


def strip_unbalanced_parens(text: str) -> str:
    """Drop parentheses that have no partner (e.g. a GT list split inside a parenthesis)."""
    out: list[str] = []
    depth = 0
    for i, ch in enumerate(text):
        if ch == "(":
            if text.find(")", i) == -1:
                out.append(" ")
                continue
            depth += 1
        elif ch == ")":
            if depth == 0:
                out.append(" ")
                continue
            depth -= 1
        out.append(ch)
    return _WHITESPACE_RE.sub(" ", "".join(out)).strip()


def _split_top_level(text: str, separators: str) -> list[str]:
    """Split on separator characters that sit outside parentheses."""
    parts: list[str] = []
    depth = 0
    current: list[str] = []
    for ch in text:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        if ch in separators and depth == 0:
            parts.append("".join(current))
            current = []
            continue
        current.append(ch)
    parts.append("".join(current))
    return [p.strip() for p in parts if p.strip()]


def split_taxon_items(raw: str) -> list[str]:
    """Split one raw `species` item into individual mentions.

    Splits on top-level semicolons, and on a top-level colon followed by a
    comma-separated list ("16 damselfly species (Coenagrionidae): A b, C d").
    Separators inside parentheses are kept, so "weevils (Coleoptera:
    Curculionoidea)" stays whole. Unbalanced parentheses are dropped.

    Examples:
        >>> split_taxon_items("Histeridae; Silphidae")
        ['Histeridae', 'Silphidae']
        >>> split_taxon_items("16 damselfly species: Enallagma boreale, Ischnura posita")
        ['16 damselfly species', 'Enallagma boreale', 'Ischnura posita']
    """
    if not raw or not isinstance(raw, str):
        return []
    text = strip_unbalanced_parens(raw.strip())
    out: list[str] = []
    for part in _split_top_level(text, ";"):
        colon_parts = _split_top_level(part, ":")
        if len(colon_parts) == 2 and len(_split_top_level(colon_parts[1], ",")) >= 2:
            out.append(colon_parts[0])
            out.extend(_split_top_level(colon_parts[1], ","))
        else:
            out.append(part)
    return [p.strip(" ,.") for p in out if p.strip(" ,.")]


def normalize_group_label(text: str) -> str:
    """Lowercase, hyphen-free, stopword-free label used for vocabulary lookups."""
    s = text.replace("-", " ").replace("_", " ")
    s = _PARENS_RE.sub(" ", s)
    s = _GROUP_STOPWORDS_RE.sub(" ", s)
    s = re.sub(r"[^\w\s]", " ", s)
    s = _WHITESPACE_RE.sub(" ", s).strip().lower()
    return s


def scientific_name_candidates(text: str) -> list[str]:
    """List binomial/trinomial and genus-level names embedded in a string.

    Finds names anywhere in the string, including inside parentheses and after
    a vernacular prefix ("migratory caribou Rangifer tarandus caribou").
    "Genus sp." / "Genus spp." yield "Genus spp." so GBIF returns the genus.
    """
    names: list[str] = []
    for m in _BINOMIAL_RE.finditer(text):
        genus, epithet, infra = m.group("genus"), m.group("epithet"), m.group("infra")
        if epithet.lower() in _GENUS_ONLY_EPITHETS:
            name = f"{genus} spp."
        else:
            name = f"{genus} {epithet.rstrip('.')}"
            if infra and infra.lower() not in _GENUS_ONLY_EPITHETS:
                name = f"{name} {infra}"
        if name not in names:
            names.append(name)
    return names


def uninomial_candidates(text: str) -> list[str]:
    """List single capitalised words that may be higher-taxon names.

    Only whole segments count: the text outside parentheses, or a piece of a
    parenthesis split on ":", ";" or ",". So "Histeridae", "Nematoda (adults)"
    and "weevils (Coleoptera: Curculionoidea)" give candidates, while the
    adjective in "Eastern Wolf" does not.
    """
    outside = _WHITESPACE_RE.sub(" ", _PARENS_RE.sub(" ", text)).strip(" ,.;:")
    segments = [outside]
    for inner in _PARENS_RE.findall(text):
        segments.extend(re.split(r"[:;,]", inner.strip("() ")))
    out: list[str] = []
    for segment in segments:
        segment = segment.strip(" ,.;:")
        if _UNINOMIAL_RE.fullmatch(segment) and segment not in out:
            out.append(segment)
    return out


def vernacular_candidates(text: str) -> list[str]:
    """List vernacular phrases to try: text outside and inside parentheses."""
    outside = _WHITESPACE_RE.sub(" ", _PARENS_RE.sub(" ", text)).strip(" ,.;:")
    inside = [m.strip("() ") for m in _PARENS_RE.findall(text)]
    out: list[str] = []
    for phrase in [outside, *inside]:
        phrase = _GROUP_STOPWORDS_RE.sub(" ", phrase)
        phrase = _WHITESPACE_RE.sub(" ", phrase).strip(" ,.;:")
        if phrase and re.search(r"[A-Za-z]", phrase) and phrase not in out:
            out.append(phrase)
    return out


class TaxonMention(BaseModel):
    """One mention found in a `species` item, before any GBIF lookup.

    Attributes:
        original: The mention text as split from the raw item.
        kind: "name" (a taxon or group name to resolve), "count" (a count
            statement such as "73 weevil species"), "hybrid" (hybrid labels),
            or "noise" ("and others").
        count: The stated number of taxa, for count statements.
        approximate: True when the count is prefixed by "c.", "about", etc.
        group_texts: For count statements, the texts that may name the counted
            group, in priority order (after the number, then the whole string).
        generic_label: True for labels that end in "species"/"taxa" and may not
            name any taxon ("shade-tolerant species").
    """

    original: str
    kind: str = "name"
    count: Optional[int] = None
    approximate: bool = False
    group_texts: list[str] = []
    generic_label: bool = False

    @model_validator(mode="before")
    @classmethod
    def parse_raw_string(cls, data: Any) -> Any:
        if isinstance(data, str):
            return parse_taxon_mention(data)
        return data


def parse_taxon_mention(text: str) -> dict:
    """Classify one mention (already split) as a name, count, hybrid or noise."""
    s = (text or "").strip()
    out: dict[str, Any] = {"original": s, "kind": "name", "count": None, "approximate": False,
                           "group_texts": [], "generic_label": False}
    if not s or _NOISE_RE.match(s) or not re.search(r"[A-Za-z]", s):
        out["kind"] = "noise"
        return out
    if _HYBRID_RE.search(s):
        out["kind"] = "hybrid"
        return out
    count_match = None
    for m in _COUNT_RE.finditer(s):
        value = int(m.group("count"))
        if 1700 <= value <= 2100 and len(m.group("count")) == 4:
            continue  # a year, e.g. authorship "(Linnaeus, 1758)"
        count_match = m
        break
    if count_match is not None:
        out["kind"] = "count"
        out["count"] = int(count_match.group("count"))
        out["approximate"] = bool(count_match.group("approx"))
        after = s[count_match.end():]
        before = s[:count_match.start()]
        texts = []
        # Parenthesised scientific names often name the counted group: "(Coenagrionidae)"
        for inner in _PARENS_RE.findall(s):
            inner = inner.strip("() ")
            if uninomial_candidates(inner) or scientific_name_candidates(inner):
                texts.append(inner)
        after_clean = re.split(r"[(:;,]", after)[0].strip()
        for candidate in (after_clean, before.strip(" ,(:;"), _COUNT_RE.sub(" ", s)):
            candidate = strip_unbalanced_parens(_WHITESPACE_RE.sub(" ", candidate)).strip(" ,.;:()")
            if candidate and normalize_group_label(candidate) and candidate not in texts:
                texts.append(candidate)
        out["group_texts"] = texts
        return out
    out["generic_label"] = bool(_GENERIC_LABEL_RE.search(s)) and not scientific_name_candidates(s)
    return out


def normalize_vernacular(text: str) -> str:
    """Accent-, case- and punctuation-insensitive form of a vernacular name."""
    import unicodedata

    s = unicodedata.normalize("NFKD", text)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.lower().replace("-", " ").replace("'", " ").replace("’", " ")
    s = re.sub(r"[^\w\s]", " ", s)
    return _WHITESPACE_RE.sub(" ", s).strip()


def singularize_phrase(text: str) -> str:
    """Singularize the last word of a normalized phrase ("striped skunks" -> "striped skunk")."""
    words = text.split()
    if not words:
        return text
    last = words[-1]
    irregular = {"wolves": "wolf", "mice": "mouse", "geese": "goose", "lice": "louse",
                 "fishes": "fish", "algae": "alga", "fungi": "fungus", "larvae": "larva",
                 "leaves": "leaf", "calves": "calf", "halves": "half", "molluscs": "mollusc",
                 "mollusks": "mollusk"}
    if last in irregular:
        words[-1] = irregular[last]
    elif len(last) > 4 and last.endswith("ies"):
        words[-1] = last[:-3] + "y"
    elif len(last) > 4 and last.endswith(("ches", "shes", "sses", "xes")):
        words[-1] = last[:-2]
    elif len(last) > 3 and last.endswith("s") and not last.endswith(("ss", "us", "is")):
        words[-1] = last[:-1]
    return " ".join(words)


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
