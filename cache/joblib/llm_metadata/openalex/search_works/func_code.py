# first line: 59
@memory.cache
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
