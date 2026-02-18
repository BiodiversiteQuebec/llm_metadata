from llm_metadata.dryad import search_datasets, get_dataset


class TestClassify:
    def test_list_datasets_by_keywords(self):
        results = search_datasets("quebec caribou")
        assert isinstance(results, list)
        assert len(results) > 0
