import os
import requests

ZENODO_HOST = 'https://zenodo.org'
ZENODO_ACCESS_TOKEN = os.getenv('ZENODO_ACCESS_TOKEN')

def check_access_token(func):
    def wrapper(*args, **kwargs):
        if not ZENODO_ACCESS_TOKEN:
            raise ValueError('ZENODO_ACCESS_TOKEN environment variable is not set')
        return func(*args, **kwargs)
    return wrapper

@check_access_token
def get_record(params: dict):
    # Append the host to the params
    params['access_token'] = ZENODO_ACCESS_TOKEN

    # Make the request
    response = requests.get(f'{ZENODO_HOST}/api/records', params=params)

    # Manage the response
    if response.status_code == 200:
        return response.json()
    else:
        # Raise an exception
        response.raise_for_status()

def get_record_by_doi(doi: str):
    response = get_record({'q': f'doi:"{doi}"'})
    if response['hits']['total'] > 0:
        record = response['hits']['hits'][0]
        # Tag the record with its data source
        record["source"] = "zenodo"
        return record
    return None

def get_record_by_doi_list(dois: list):
    response = get_record({'q': ' OR '.join([f'doi:"{doi}"' for doi in dois])})
    records = response['hits']['hits']
    # Tag each record with its data source
    for record in records:
        record["source"] = "zenodo"
    return records