# first line: 94
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
