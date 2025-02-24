import unittest
from llm_metadata.dryad import search_datasets, get_dataset_info

class TestClassify(unittest.TestCase):
    def test_list_datasets_by_keywords(self):
        results = search_datasets("quebec caribou")
        # Assert that the results are a list
        self.assertIsInstance(results, list)

        # Assert that the results are not empty
        self.assertTrue(len(results) > 0)