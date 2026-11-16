"""Tests for relevance_eval: rule route, direct route, scores."""

import json

import numpy as np
import pandas as pd

from llm_metadata.relevance_eval import _rule_inputs, _scores, predictions, score, targets


def test_rule_inputs_maps_enum_underscores():
    feats = _rule_inputs({"data_type": ["genetic_analysis", "presence-only"], "temp_range_i": 2000, "temp_range_f": 2001})
    assert feats["data_type"] == "genetic analysis, presence-only"
    assert feats["temp_range_i"] == 2000


def test_scores_perfect_and_binary():
    y = np.array(["H", "M", "L", "X"], dtype=object)
    s = _scores(y, y.copy())
    assert s["acc4"] == 1 and s["f1"] == 1 and s["kappa4"] == 1
    s = _scores(y, np.array(["M", "H", "X", "L"], dtype=object))
    assert s["acc4"] == 0 and s["acc2"] == 1  # all swaps stay inside the binary classes


def test_direct_route_against_released_labels(tmp_path):
    t = targets()
    dev = pd.read_csv("data/manifests/dev_subset_data_paper.csv")["gt_record_id"].tolist()[:5]
    recs = [{"gt_record_id": g, "status": "success", "output": {"relevance": t.loc[g, "rule"]}} for g in dev]
    recs.append({"gt_record_id": dev[0] + 100000, "status": "success", "output": {"relevance": "H"}})  # not dev: ignored
    path = tmp_path / "run.json"
    path.write_text(json.dumps({"name": "x", "records": recs}))
    df = predictions(path, "dev")
    assert len(df) == 5 and set(df["route"]) == {"direct"}
    assert score(df, "rule", n_boot=50)["scores"]["acc4"][0] == 1.0


def test_failed_record_counts_as_wrong(tmp_path):
    dev = pd.read_csv("data/manifests/dev_subset_data_paper.csv")["gt_record_id"].tolist()[:2]
    t = targets()
    recs = [
        {"gt_record_id": dev[0], "status": "success", "output": {"relevance": t.loc[dev[0], "rule"]}},
        {"gt_record_id": dev[1], "status": "error", "output": None},
    ]
    path = tmp_path / "run.json"
    path.write_text(json.dumps({"name": "x", "records": recs}))
    assert score(predictions(path), "rule", n_boot=50)["scores"]["acc4"][0] == 0.5


def test_ebv_genetic_flag_lifts_genetic_data_to_high():
    from llm_metadata.relevance_rules import dataset_type_class

    plain = _rule_inputs({"data_type": ["genetic_analysis"]})
    ebv = _rule_inputs({"data_type": ["genetic_analysis"], "ebv_genetic": True})
    assert dataset_type_class(plain["data_type"]) == "L"
    assert dataset_type_class(ebv["data_type"]) == "H"
