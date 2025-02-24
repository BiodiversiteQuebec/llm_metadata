import config
from llm_metadata.zenodo import get_record, get_record_by_doi, get_record_by_doi_list
import unittest

SAMPLE_RECORD_ID = '5009453'
SAMPLE_RECORD_DOI = '10.5061/dryad.708b0'
SAMPLE_RECORD_DOIS = [
    "10.5061/dryad.69p8cz916",
    "10.5061/dryad.6q5g3",
    "10.5061/dryad.708b0",
]

class TestZenodo(unittest.TestCase):
    def test_get_record(self):
        response = get_record({'q': 'id:{}'.format(SAMPLE_RECORD_ID)})
        self.assertIsInstance(response, dict)
        self.assertEqual(response['hits']['total'], 1)

    def test_get_record_by_doi(self):
        response = get_record_by_doi(SAMPLE_RECORD_DOI)
        self.assertIsInstance(response, dict)
        self.assertEqual(response['doi'], SAMPLE_RECORD_DOI)

    def test_get_record_by_doi_list(self):
        response = get_record_by_doi_list(SAMPLE_RECORD_DOIS)
        self.assertIsInstance(response, list)

        # Assert all in
        dois = [record['doi'] for record in response]
        self.assertTrue(all(doi in SAMPLE_RECORD_DOIS for doi in dois))