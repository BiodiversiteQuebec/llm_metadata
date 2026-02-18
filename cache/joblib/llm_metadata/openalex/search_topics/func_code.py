# first line: 28
@memory.cache
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
