# first line: 193
@memory.cache
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
