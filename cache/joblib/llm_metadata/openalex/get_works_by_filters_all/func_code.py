# first line: 129
@memory.cache
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
