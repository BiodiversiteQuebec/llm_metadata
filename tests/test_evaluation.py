import unittest

from llm_metadata.schemas import DatasetFeatureExtraction
from llm_metadata.schemas.evaluation import evaluate_pairs, micro_average, macro_f1


class _Rec(DatasetFeatureExtraction):
    record_id: str


class TestEvaluation(unittest.TestCase):
    def test_evaluate_pairs_scalar_and_list_fields(self):
        fields = ["taxons", "temp_range_i", "temp_range_f", "data_type"]

        true = [
            _Rec.model_validate(
                {
                    "record_id": "r1",
                    "taxons": "caribou",
                    "temp_range_i": 1999,
                    "temp_range_f": 2015,
                    "data_type": ["abundance", "time_series"],
                }
            ),
            _Rec.model_validate(
                {
                    "record_id": "r2",
                    "taxons": None,
                    "temp_range_i": 2000,
                    "data_type": ["abundance"],
                }
            ),
        ]

        pred = [
            _Rec.model_validate(
                {
                    "record_id": "r1",
                    "taxons": "Caribou",  # case-insensitive match
                    "temp_range_i": 1999,
                    "temp_range_f": 2014,  # wrong
                    "data_type": ["abundance"],  # partial
                }
            ),
            _Rec.model_validate(
                {
                    "record_id": "r2",
                    "taxons": "",  # becomes None via schema validator
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

        # taxons: r1 matches (tp=1), r2 both None (tn=1)
        self.assertEqual(metrics["taxons"].tp, 1)
        self.assertEqual(metrics["taxons"].tn, 1)
        self.assertEqual(metrics["taxons"].fp, 0)
        self.assertEqual(metrics["taxons"].fn, 0)

        # temp_range_f: r1 wrong (fp=1, fn=1), r2 both None (tn=1)
        self.assertEqual(metrics["temp_range_f"].tp, 0)
        self.assertEqual(metrics["temp_range_f"].tn, 1)
        self.assertEqual(metrics["temp_range_f"].fp, 1)
        self.assertEqual(metrics["temp_range_f"].fn, 1)

        # data_type is treated as set; across records:
        # r1: true {abundance,time_series}, pred {abundance} => tp=1 fn=1
        # r2: true {abundance}, pred {abundance,density} => tp=1 fp=1
        self.assertEqual(metrics["data_type"].tp, 2)
        self.assertEqual(metrics["data_type"].fp, 1)
        self.assertEqual(metrics["data_type"].fn, 1)

        micro = micro_average(metrics.values())
        self.assertGreaterEqual(micro.tp, 1)
        self.assertIsNotNone(macro_f1(metrics.values()))
