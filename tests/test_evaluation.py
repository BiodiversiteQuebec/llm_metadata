from llm_metadata.schemas import DatasetFeatures
from llm_metadata.groundtruth_eval import evaluate_pairs, micro_average, macro_f1


class _Rec(DatasetFeatures):
    record_id: str


class TestEvaluation:
    def test_evaluate_pairs_scalar_and_list_fields(self):
        fields = ["species", "temp_range_i", "temp_range_f", "data_type"]

        true = [
            _Rec.model_validate(
                {
                    "record_id": "r1",
                    "species": ["caribou"],
                    "temp_range_i": 1999,
                    "temp_range_f": 2015,
                    "data_type": ["abundance", "time_series"],
                }
            ),
            _Rec.model_validate(
                {
                    "record_id": "r2",
                    "species": None,
                    "temp_range_i": 2000,
                    "data_type": ["abundance"],
                }
            ),
        ]

        pred = [
            _Rec.model_validate(
                {
                    "record_id": "r1",
                    "species": ["Caribou"],  # case-insensitive match
                    "temp_range_i": 1999,
                    "temp_range_f": 2014,  # wrong
                    "data_type": ["abundance"],  # partial
                }
            ),
            _Rec.model_validate(
                {
                    "record_id": "r2",
                    "species": None,  # both None
                    "temp_range_i": None,  # missing
                    "data_type": ["abundance", "density"],  # fp density
                }
            ),
        ]

        report = evaluate_pairs(
            true_models=true,
            pred_models=pred,
            key=lambda m: m.record_id,
            fields=fields,
        )

        metrics = report.field_metrics

        # species: r1 matches (tp=1), r2 both None (tn=1)
        assert metrics["species"].tp == 1
        assert metrics["species"].tn == 1
        assert metrics["species"].fp == 0
        assert metrics["species"].fn == 0

        # temp_range_f: r1 wrong (fp=1, fn=1), r2 both None (tn=1)
        assert metrics["temp_range_f"].tp == 0
        assert metrics["temp_range_f"].tn == 1
        assert metrics["temp_range_f"].fp == 1
        assert metrics["temp_range_f"].fn == 1

        # data_type is treated as set; across records:
        # r1: true {abundance,time_series}, pred {abundance} => tp=1 fn=1
        # r2: true {abundance}, pred {abundance,density} => tp=1 fp=1
        assert metrics["data_type"].tp == 2
        assert metrics["data_type"].fp == 1
        assert metrics["data_type"].fn == 1

        micro = micro_average(metrics.values())
        assert micro.tp >= 1
        assert macro_f1(metrics.values()) is not None
