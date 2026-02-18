"""
Semantic Scholar API integration for retrieving scientific paper metadata.

This module provides functions to search for papers, retrieve metadata,
citations, references, and open access PDF URLs from the Semantic Scholar
Graph API. Designed as a supplementary paper discovery source for the
LLM metadata pipeline.

API Documentation: https://api.semanticscholar.org/graph/v1
"""

import os
import time
import logging
import requests
from typing import Optional, List, Dict, Any
from joblib import Memory

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Setup cache
memory = Memory("./cache", verbose=0)

REQUEST_TIMEOUT = 30  # seconds
_RETRY_DELAYS = [2, 4, 8]  # seconds, for 429 backoff
_AUTHENTICATED_RPS = 1.0   # introductory API key rate limit

BASE_URL = os.getenv("SEMANTIC_SCHOLAR_API_BASE", "https://api.semanticscholar.org/graph/v1").rstrip("/")

SEMANTIC_SCHOLAR_API_KEY = os.getenv("SEMANTIC_SCHOLAR_API_KEY")
_last_request_time: float = 0.0

# Default fields to retrieve for paper lookups
DEFAULT_PAPER_FIELDS = "paperId,title,abstract,year,authors,openAccessPdf,externalIds"
DEFAULT_SEARCH_FIELDS = "paperId,title,abstract,year,authors"
DEFAULT_CITATION_FIELDS = "paperId,title,abstract"
DEFAULT_REFERENCE_FIELDS = "paperId,title,abstract"


def _build_headers() -> Dict[str, str]:
    """Build request headers, including optional API key.

    Unauthenticated: uses the shared public pool (1000 req/sec across all users).
    Authenticated: sends x-api-key header for a dedicated higher rate limit.
    """
    headers = {}
    if SEMANTIC_SCHOLAR_API_KEY:
        headers["x-api-key"] = SEMANTIC_SCHOLAR_API_KEY
    return headers


def _get(url: str, params: Dict[str, Any]) -> requests.Response:
    """Make a GET request, respecting rate limits with 429 retry backoff.

    When an API key is set, enforces 1 RPS proactively (introductory limit).
    Unauthenticated requests use the shared public pool (no per-client throttle).
    """
    global _last_request_time
    rate_limit = _AUTHENTICATED_RPS
    if rate_limit > 0:
        elapsed = time.time() - _last_request_time
        if elapsed < rate_limit:
            time.sleep(rate_limit - elapsed)
        _last_request_time = time.time()

    headers = _build_headers()
    for attempt, wait in enumerate([0] + _RETRY_DELAYS):
        if wait:
            logger.warning("Rate limited (429), retrying in %ss...", wait)
            time.sleep(wait)
        response = requests.get(url, params=params, headers=headers, timeout=REQUEST_TIMEOUT)
        if response.status_code != 429:
            return response
    response.raise_for_status()
    return response


def _clean_doi(doi: str) -> str:
    """Strip any URL prefix from a DOI string.

    Args:
        doi: Raw DOI string, possibly prefixed with https://doi.org/ or doi:

    Returns:
        Clean DOI without prefix
    """
    doi = doi.strip()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if doi.lower().startswith(prefix):
            doi = doi[len(prefix):]
            break
    return doi


@memory.cache
def get_paper_by_doi(doi: str) -> Optional[Dict[str, Any]]:
    """Retrieve paper metadata from Semantic Scholar by DOI.

    Args:
        doi: DOI string (with or without https://doi.org/ prefix)

    Returns:
        Paper metadata dict or None if not found

    Example:
        >>> paper = get_paper_by_doi("10.1371/journal.pone.0128238")
        >>> if paper:
        ...     print(paper['title'])
    """
    clean = _clean_doi(doi)
    paper_id = f"DOI:{clean}"
    endpoint = f"{BASE_URL}/paper/{paper_id}"
    params = {"fields": DEFAULT_PAPER_FIELDS}
    response = _get(endpoint, params)

    if response.status_code == 404:
        logger.debug("Paper not found in Semantic Scholar for DOI: %s", doi)
        return None

    response.raise_for_status()
    return response.json()


@memory.cache
def get_paper_by_title(title: str) -> Optional[Dict[str, Any]]:
    """Search for a paper by title in Semantic Scholar.

    Performs a title search and returns the best matching result (first hit).

    Args:
        title: Paper title to search for

    Returns:
        Best matching paper metadata dict or None if not found

    Example:
        >>> paper = get_paper_by_title("Deep learning for ecology")
        >>> if paper:
        ...     print(paper['paperId'])
    """
    endpoint = f"{BASE_URL}/paper/search"
    params = {
        "query": title,
        "fields": DEFAULT_SEARCH_FIELDS,
        "limit": 1,
    }
    response = _get(endpoint, params)

    if response.status_code == 404:
        logger.debug("No papers found for title: %s", title)
        return None

    response.raise_for_status()
    data = response.json()
    papers = data.get("data", [])
    if not papers:
        return None

    return papers[0]


@memory.cache
def get_paper_citations(paper_id: str, limit: int = 100) -> List[Dict[str, Any]]:
    """Get papers that cite the given paper.

    Args:
        paper_id: Semantic Scholar paper ID or DOI (e.g., "DOI:10.1234/example")
        limit: Maximum number of citations to return

    Returns:
        List of citing paper metadata dicts

    Example:
        >>> citations = get_paper_citations("649def34f8be52c8b66281af98ae884c09aef38b")
        >>> print(f"Found {len(citations)} citing papers")
    """
    endpoint = f"{BASE_URL}/paper/{paper_id}/citations"
    params = {
        "limit": limit,
        "fields": DEFAULT_CITATION_FIELDS,
    }
    response = _get(endpoint, params)

    if response.status_code == 404:
        logger.debug("Paper not found for citations lookup: %s", paper_id)
        return []

    response.raise_for_status()
    data = response.json()

    # Citations endpoint wraps each entry under a "citingPaper" key
    citations = []
    for item in data.get("data", []):
        citing_paper = item.get("citingPaper")
        if citing_paper:
            citations.append(citing_paper)

    return citations


@memory.cache
def get_paper_references(paper_id: str, limit: int = 100) -> List[Dict[str, Any]]:
    """Get papers referenced by the given paper.

    Args:
        paper_id: Semantic Scholar paper ID or DOI (e.g., "DOI:10.1234/example")
        limit: Maximum number of references to return

    Returns:
        List of referenced paper metadata dicts

    Example:
        >>> refs = get_paper_references("649def34f8be52c8b66281af98ae884c09aef38b")
        >>> print(f"Found {len(refs)} references")
    """
    endpoint = f"{BASE_URL}/paper/{paper_id}/references"
    params = {
        "limit": limit,
        "fields": DEFAULT_REFERENCE_FIELDS,
    }
    response = _get(endpoint, params)

    if response.status_code == 404:
        logger.debug("Paper not found for references lookup: %s", paper_id)
        return []

    response.raise_for_status()
    data = response.json()

    # References endpoint wraps each entry under a "citedPaper" key
    references = []
    for item in data.get("data", []):
        cited_paper = item.get("citedPaper")
        if cited_paper:
            references.append(cited_paper)

    return references


@memory.cache
def get_open_access_pdf_url(doi: str) -> Optional[str]:
    """Get open access PDF URL from Semantic Scholar.

    Fetches paper metadata by DOI and extracts the open access PDF URL
    if available.

    Args:
        doi: DOI string (with or without https://doi.org/ prefix)

    Returns:
        PDF URL string or None if not available

    Example:
        >>> url = get_open_access_pdf_url("10.1371/journal.pone.0128238")
        >>> if url:
        ...     print(f"PDF available at: {url}")
    """
    paper = get_paper_by_doi(doi)
    if not paper:
        return None

    open_access_pdf = paper.get("openAccessPdf")
    if not open_access_pdf:
        return None

    return open_access_pdf.get("url")


if __name__ == "__main__":
    # Example usage
    print("Testing Semantic Scholar API integration...")

    # Test 1: Get paper by DOI
    print("\n1. Retrieving paper by DOI...")
    doi = "10.1371/journal.pone.0128238"
    paper = get_paper_by_doi(doi)
    if paper:
        print(f"  Title: {paper.get('title', 'N/A')}")
        print(f"  Year: {paper.get('year', 'N/A')}")
        print(f"  Paper ID: {paper.get('paperId', 'N/A')}")
        oa_pdf = paper.get("openAccessPdf")
        if oa_pdf:
            print(f"  OA PDF: {oa_pdf.get('url', 'N/A')}")
    else:
        print("  Paper not found")

    # Test 2: Search by title
    print("\n2. Searching by title...")
    result = get_paper_by_title("biodiversity monitoring LLM automated dataset retrieval")
    if result:
        print(f"  Found: {result.get('title', 'N/A')} ({result.get('year', 'N/A')})")
    else:
        print("  No results found")

    # Test 3: Get open access PDF URL
    print("\n3. Getting open access PDF URL...")
    pdf_url = get_open_access_pdf_url(doi)
    if pdf_url:
        print(f"  PDF URL: {pdf_url}")
    else:
        print("  No open access PDF available")

    print("\nSemantic Scholar API integration test complete!")
