"""doi_utils — shared DOI normalization and matching utilities.

All DOI handling in llm_metadata should route through these functions to ensure
consistent normalization across ingestion, manifest building, PDF lookup, and
evaluation subsystems.
"""

from __future__ import annotations

import re
from urllib.parse import quote, unquote

# Common prefixes stripped during normalization
_DOI_PREFIXES = (
    "https://doi.org/",
    "http://doi.org/",
    "doi:",
    "DOI:",
)


def strip_doi_prefix(doi: str) -> str:
    """Strip https://doi.org/, http://doi.org/, or doi: prefix from *doi*.

    Returns the bare DOI path (e.g. ``10.1371/journal.pone.0128238``).
    The string is stripped of leading/trailing whitespace.
    """
    if not doi:
        return ""
    doi = doi.strip()
    for prefix in _DOI_PREFIXES:
        if doi.lower().startswith(prefix.lower()):
            doi = doi[len(prefix):]
            break
    return doi.strip()


def normalize_doi(doi: str) -> str:
    """Return a canonical lowercase bare DOI string.

    Strips URL prefixes, trims whitespace, and lowercases for reliable
    equality comparison.  The DOI registrant path itself is case-insensitive
    per the DOI specification.
    """
    return strip_doi_prefix(doi).lower()


def doi_equal(a: str | None, b: str | None) -> bool:
    """Return True if *a* and *b* resolve to the same DOI after normalization.

    None values are never equal to anything (including each other).
    """
    if a is None or b is None:
        return False
    return normalize_doi(a) == normalize_doi(b)


def doi_filename_stem(doi: str) -> str:
    """Convert a DOI to the filename stem used for local PDFs.

    Convention: strip URL prefix, replace ``/`` with ``_``.
    Example: ``10.1371/journal.pone.0128238`` → ``10.1371_journal.pone.0128238``

    This is the naming convention used throughout the fuster PDF download pipeline.
    """
    bare = strip_doi_prefix(doi)
    return bare.replace("/", "_")


def doi_candidate_variants(doi: str) -> list[str]:
    """Return candidate DOI string variants for fuzzy matching / lookup.

    Returns lowercase bare DOI, full https URL, and any percent-encoded /
    decoded variants that may appear in data sources.
    """
    bare = normalize_doi(doi)
    if not bare:
        return []

    candidates: list[str] = [bare]

    # Add https URL form
    candidates.append(f"https://doi.org/{bare}")

    # Add doi: prefix form
    candidates.append(f"doi:{bare}")

    # Percent-decode if encoded (e.g. %28 → (, %29 → ))
    decoded = unquote(bare)
    if decoded != bare:
        candidates.append(decoded)
    # Also add re-encoded form for reverse lookup
    encoded = quote(bare, safe="10./:-_")
    if encoded != bare:
        candidates.append(encoded)

    # Deduplicate while preserving order
    seen: set[str] = set()
    result: list[str] = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            result.append(c)
    return result


def extract_doi_from_url(url: str | None) -> str | None:
    """Extract a bare DOI from a URL or DOI string.

    Returns None if *url* is empty, None, or does not appear to contain a DOI.
    Does not validate the DOI against any registry — purely string-based.
    """
    if not url:
        return None
    url = str(url).strip()
    if not url:
        return None

    bare = strip_doi_prefix(url)

    # Bare DOIs start with 10. per the registration agency specification
    if re.match(r"^10\.\d{4,}", bare):
        return bare

    return None
