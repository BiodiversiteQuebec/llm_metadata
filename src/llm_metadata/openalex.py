"""
OpenAlex API integration for retrieving scientific papers.

This module provides functions to search for works (papers) in OpenAlex,
with support for filtering by institution, publication year, topics, and
open access status. Designed for ecology paper retrieval from Quebec researchers.
"""

import os
import requests
from typing import Optional, List, Dict, Any

BASE_URL = "https://api.openalex.org"
OPENALEX_EMAIL = os.getenv('OPENALEX_EMAIL')  # Optional for polite pool


def _build_params(mailto: bool = True) -> dict:
    """Build base parameters for API requests."""
    params = {}
    if mailto and OPENALEX_EMAIL:
        params['mailto'] = OPENALEX_EMAIL
    return params


def search_topics(query: str, per_page: int = 50) -> list:
    """
    Search OpenAlex topics by keyword.

    Useful for discovering topic IDs for ecology/biodiversity filtering.

    Args:
        query: Search term (e.g., "ecology", "biodiversity")
        per_page: Results per page (default: 50)

    Returns:
        List of topic dictionaries with id, display_name, description

    Example:
        >>> topics = search_topics("ecology")
        >>> print(topics[0]['display_name'])
    """
    endpoint = f"{BASE_URL}/topics"
    params = _build_params()
    params.update({
        'search': query,
        'per_page': per_page
    })

    response = requests.get(endpoint, params=params)
    response.raise_for_status()

    data = response.json()
    return data.get('results', [])


def search_works(
    ror_id: Optional[str] = None,
    publication_year: Optional[int] = None,
    topics: Optional[List[str]] = None,
    keywords: Optional[str] = None,
    is_oa: Optional[bool] = None,
    work_type: Optional[str] = None,
    per_page: int = 200,
    cursor: str = "*"
) -> dict:
    """
    Search OpenAlex works with filters.

    Args:
        ror_id: Institution ROR ID (e.g., "https://ror.org/00kybxq39")
        publication_year: Filter by year (e.g., 2025)
        topics: List of topic IDs to filter by
        keywords: Search string for title/abstract
        is_oa: Open access filter (True for OA only)
        work_type: Filter by type ("article", "preprint", etc.)
        per_page: Results per page (max 200, default: 200)
        cursor: Pagination cursor (default: "*" for first page)

    Returns:
        API response dict with 'results' and 'meta' keys

    Example:
        >>> response = search_works(
        ...     ror_id="https://ror.org/00kybxq39",
        ...     publication_year=2025,
        ...     keywords="ecology",
        ...     is_oa=True
        ... )
        >>> print(f"Found {len(response['results'])} works")
    """
    endpoint = f"{BASE_URL}/works"
    params = _build_params()

    # Build filter string
    filters = []
    if ror_id:
        filters.append(f"institutions.ror:{ror_id}")
    if publication_year:
        filters.append(f"publication_year:{publication_year}")
    if topics:
        # Multiple topics as OR
        topic_filter = "|".join(topics)
        filters.append(f"topics.id:{topic_filter}")
    if is_oa is not None:
        filters.append(f"is_oa:{str(is_oa).lower()}")
    if work_type:
        filters.append(f"type:{work_type}")

    if filters:
        params['filter'] = ",".join(filters)

    # Add search parameter for keyword search
    if keywords:
        params['search'] = keywords

    # Pagination
    params['per_page'] = per_page
    params['cursor'] = cursor

    response = requests.get(endpoint, params=params)
    response.raise_for_status()

    return response.json()


def get_works_by_filters_all(
    ror_id: Optional[str] = None,
    publication_year: Optional[int] = None,
    topics: Optional[List[str]] = None,
    keywords: Optional[str] = None,
    is_oa: Optional[bool] = None,
    work_type: Optional[str] = None,
    max_results: Optional[int] = None
) -> list:
    """
    Retrieve all works matching filters using cursor pagination.

    This function handles pagination automatically and returns all results.

    Args:
        Same as search_works, plus:
        max_results: Maximum number of results to retrieve (None = all)

    Returns:
        List of all work dictionaries

    Example:
        >>> works = get_works_by_filters_all(
        ...     ror_id="https://ror.org/00kybxq39",
        ...     publication_year=2025,
        ...     keywords="ecology",
        ...     is_oa=True,
        ...     max_results=100
        ... )
        >>> print(f"Retrieved {len(works)} works")
    """
    all_works = []
    cursor = "*"

    while True:
        response = search_works(
            ror_id=ror_id,
            publication_year=publication_year,
            topics=topics,
            keywords=keywords,
            is_oa=is_oa,
            work_type=work_type,
            cursor=cursor
        )

        works = response.get('results', [])
        all_works.extend(works)

        # Check if we've hit max_results
        if max_results and len(all_works) >= max_results:
            return all_works[:max_results]

        # Check if there's a next cursor
        meta = response.get('meta', {})
        next_cursor = meta.get('next_cursor')

        if not next_cursor or len(works) == 0:
            break

        cursor = next_cursor

    return all_works


def get_work_by_doi(doi: str) -> Optional[dict]:
    """
    Retrieve single work by DOI.

    Args:
        doi: Work DOI (e.g., "10.1371/journal.pone.0128238")

    Returns:
        Work dictionary or None if not found

    Example:
        >>> work = get_work_by_doi("10.1371/journal.pone.0128238")
        >>> print(work['title'])
    """
    # Ensure DOI is properly formatted
    if not doi.startswith('https://doi.org/'):
        doi = f"https://doi.org/{doi}"

    endpoint = f"{BASE_URL}/works/{doi}"
    params = _build_params()

    response = requests.get(endpoint, params=params)

    if response.status_code == 404:
        return None

    response.raise_for_status()
    return response.json()


def extract_abstract(work: dict) -> Optional[str]:
    """
    Extract abstract text from work object.

    Args:
        work: OpenAlex work dictionary

    Returns:
        Abstract text or None if not available
    """
    abstract_inverted_index = work.get('abstract_inverted_index')

    if not abstract_inverted_index:
        return None

    # OpenAlex stores abstracts as inverted index
    # Reconstruct the abstract text
    word_positions = []
    for word, positions in abstract_inverted_index.items():
        for pos in positions:
            word_positions.append((pos, word))

    # Sort by position and join
    word_positions.sort(key=lambda x: x[0])
    abstract = ' '.join([word for _, word in word_positions])

    return abstract


def extract_pdf_url(work: dict) -> Optional[str]:
    """
    Extract best available PDF URL from work object.

    Args:
        work: OpenAlex work dictionary

    Returns:
        PDF URL or None if not available
    """
    best_oa_location = work.get('best_oa_location')

    if not best_oa_location:
        return None

    return best_oa_location.get('pdf_url')


def extract_authors(work: dict) -> List[Dict[str, Any]]:
    """
    Extract author information with ORCID and affiliations.

    Args:
        work: OpenAlex work dictionary

    Returns:
        List of dicts with keys: name, orcid, institutions (list of ROR IDs)

    Example:
        >>> authors = extract_authors(work)
        >>> print(authors[0]['name'])
        >>> print(authors[0]['orcid'])
    """
    authorships = work.get('authorships', [])
    authors = []

    for authorship in authorships:
        author = authorship.get('author', {})

        # Extract ORCID (remove URL prefix if present)
        orcid = author.get('orcid')
        if orcid and orcid.startswith('https://orcid.org/'):
            orcid = orcid.replace('https://orcid.org/', '')

        # Extract institution ROR IDs
        institutions = []
        for inst in authorship.get('institutions', []):
            ror = inst.get('ror')
            if ror:
                institutions.append(ror)

        authors.append({
            'name': author.get('display_name'),
            'orcid': orcid,
            'institutions': institutions if institutions else None
        })

    return authors


def is_preprint(work: dict) -> bool:
    """
    Determine if work is a preprint vs peer-reviewed article.

    Args:
        work: OpenAlex work dictionary

    Returns:
        True if work is a preprint, False otherwise
    """
    work_type = work.get('type', '').lower()
    return work_type == 'preprint'


if __name__ == "__main__":
    # Example usage
    print("Testing OpenAlex API integration...")

    # Test 1: Search topics
    print("\n1. Searching for ecology topics...")
    topics = search_topics("ecology", per_page=5)
    for topic in topics[:3]:
        print(f"  - {topic['display_name']} ({topic['id']})")

    # Test 2: Get work by DOI
    print("\n2. Retrieving work by DOI...")
    doi = "10.1371/journal.pone.0128238"
    work = get_work_by_doi(doi)
    if work:
        print(f"  Title: {work['title']}")
        print(f"  Open Access: {work['open_access']['is_oa']}")

        # Test metadata extraction
        abstract = extract_abstract(work)
        if abstract:
            print(f"  Abstract: {abstract[:100]}...")

        pdf_url = extract_pdf_url(work)
        if pdf_url:
            print(f"  PDF URL: {pdf_url}")

        authors = extract_authors(work)
        print(f"  Authors: {len(authors)}")
        if authors:
            print(f"    First author: {authors[0]['name']}")
            if authors[0]['orcid']:
                print(f"    ORCID: {authors[0]['orcid']}")

    # Test 3: Search works (small test)
    print("\n3. Searching for Université de Sherbrooke ecology papers...")
    response = search_works(
        ror_id="https://ror.org/00kybxq39",
        publication_year=2024,  # Use 2024 for testing (2025 may have few results)
        keywords="ecology",
        is_oa=True,
        per_page=5
    )
    print(f"  Found {response['meta']['count']} total works")
    print(f"  Retrieved {len(response['results'])} works in this page")

    print("\n✅ OpenAlex API integration test complete!")
