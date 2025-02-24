import requests
from typing import Union

BASE_URL = "https://datadryad.org/api/v2/"

def search_datasets(keywords: Union[str, list], per_page=30, auth_token=None):
    endpoint = BASE_URL + "search"
    
    headers = {}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"

    page = 1
    all_results = []

    # Encode the keywords for the URL
    if isinstance(keywords, list):
        keywords = " ".join(keywords)

    while True:
        params = {
            "q": keywords,
            "page": page,
            "per_page": per_page
        }
        
        response = requests.get(endpoint, headers=headers, params=params)

        if response.status_code != 200:
            print("Error:", response.status_code, response.text)
            break

        response = response.json()
        data = response.get("_embedded", {}).get("stash:datasets", [])
        all_results.extend(data)

        # Assuming the response contains a 'total' key that indicates the total number of results
        if len(all_results) >= response.get("total", 0):
            break
        
        page += 1

    return all_results

def get_dataset(doi):
    # urlencoded doi : DOI like doi:10.1000/18238577 that should be escaped (example: doi%3A10.1000%2F18238577 )
    doi = doi.replace(":", "%3A").replace("/", "%2F")
    endpoint = BASE_URL + "datasets/" + doi

    response = requests.get(endpoint)

    # urlencoded doi using package urllib.parse.quote
    # endpoint = BASE_URL + "datasets/" + urllib.parse.quote(doi)

    if response.status_code != 200:
        print("Error:", response.status_code, response.text)
        return None

    return response.json()

if __name__ == "__main__":
    doi = "doi:10.5061/dryad.n726pq6"
    dataset = get_dataset(doi)