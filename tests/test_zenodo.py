from llm_metadata.zenodo import get_record, get_record_by_doi, get_record_by_doi_list

SAMPLE_RECORD_ID = '5009453'
SAMPLE_RECORD_DOI = '10.5061/dryad.708b0'
SAMPLE_RECORD_DOIS = [
    "10.5061/dryad.69p8cz916",
    "10.5061/dryad.6q5g3",
    "10.5061/dryad.708b0",
]


class TestZenodo:
    def test_get_record(self):
        response = get_record({'q': 'id:{}'.format(SAMPLE_RECORD_ID)})
        assert isinstance(response, dict)
        assert response['hits']['total'] == 1

    def test_get_record_by_doi(self):
        response = get_record_by_doi(SAMPLE_RECORD_DOI)
        assert isinstance(response, dict)
        assert response['doi'] == SAMPLE_RECORD_DOI

    def test_get_record_by_doi_list(self):
        response = get_record_by_doi_list(SAMPLE_RECORD_DOIS)
        assert isinstance(response, list)

        # Assert all in
        dois = [record['doi'] for record in response]
        assert all(doi in SAMPLE_RECORD_DOIS for doi in dois)
