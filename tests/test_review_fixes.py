"""Regression tests for the evaluation review (micro average, failed records, numbers)."""

import json

import numpy as np
import pandas as pd

from llm_metadata.groundtruth_eval import MICRO_KEY, bootstrap_report
from llm_metadata.relevance_eval import _scores
from llm_metadata.run_summary import compare_runs, rescore_run
from llm_metadata.schemas.fuster_features import DatasetFeaturesNormalized

DEV = pd.read_csv("data/manifests/dev_subset_data_paper.csv")["gt_record_id"].tolist()
GT = {int(e["gt_record_id"]): e for e in json.loads(open("data/gt/fuster_gt.json").read())}


def _run(path, outputs):
    recs = [
        {"gt_record_id": g, "status": "error" if out is None else "success", "output": out}
        for g, out in outputs.items()
    ]
    path.write_text(json.dumps({"name": path.stem, "mode": "abstract", "records": recs}))
    return path


def _years(gid):
    return {k: GT[gid].get(k) for k in ("temp_range_i", "temp_range_f")}


def test_failed_record_is_scored_as_empty(tmp_path):
    ok = _run(tmp_path / "ok.json", {g: _years(g) for g in DEV[:4]})
    bad = _run(tmp_path / "bad.json", {**{g: _years(g) for g in DEV[:3]}, DEV[3]: None})
    rep_ok, meta_ok = rescore_run(ok)
    rep_bad, meta_bad = rescore_run(bad)
    assert meta_bad["failed"] == [DEV[3]] and len(meta_bad["ids"]) == 4
    fn_ok = sum(r.fn for r in rep_ok.field_results)
    fn_bad = sum(r.fn for r in rep_bad.field_results)
    assert fn_bad >= fn_ok  # the failure adds misses, it does not vanish


def test_micro_excludes_class_fields(tmp_path):
    run = _run(tmp_path / "r.json", {g: _years(g) for g in DEV[:6]})
    rep, _ = rescore_run(run)
    ci = bootstrap_report(rep, n_boot=50)
    primary = [r for r in rep.field_results if not r.field.endswith("_class")]
    tp = sum(r.tp for r in primary)
    fp = sum(r.fp for r in primary)
    fn = sum(r.fn for r in primary)
    expected = 2 * tp / (2 * tp + fp + fn)
    assert abs(ci[MICRO_KEY]["f1"].point - expected) < 1e-9


def test_compare_runs_identical_verdict(tmp_path):
    run = _run(tmp_path / "r.json", {g: _years(g) for g in DEV[:5]})
    _, out = compare_runs(run, run, n_boot=100)
    assert all(v["verdict"] == "identical" for v in out.values())


def test_binary_failure_counts_as_wrong():
    y = np.array(["L", "X"], dtype=object)
    p = np.array(["none", "X"], dtype=object)
    assert _scores(y, p)["acc2"] == 0.5


def test_comma_numbers():
    assert DatasetFeaturesNormalized.model_validate({"spatial_range_km2": "15,000"}).spatial_range_km2 == 15000
    assert DatasetFeaturesNormalized.model_validate({"spatial_range_km2": "0,5"}).spatial_range_km2 == 0.5


def test_flag_strategy_treats_none_as_false():
    from llm_metadata.groundtruth_eval import EvaluationConfig, FieldEvalStrategy, compare_models
    from llm_metadata.schemas.fuster_features import DatasetFeaturesExtraction

    cfg = EvaluationConfig(field_strategies={"threatened_species": FieldEvalStrategy(match="flag")})

    def one(t, p):
        return compare_models(
            true_model=DatasetFeaturesNormalized(threatened_species=t),
            pred_model=DatasetFeaturesExtraction(threatened_species=p),
            record_id="r", config=cfg,
        )[0]

    r = one(False, None)
    assert r.match and (r.tp, r.fp, r.fn, r.tn) == (0, 0, 0, 1)
    r = one(True, None)
    assert not r.match and r.fn == 1
    r = one(None, True)
    assert r.fp == 1
    r = one(True, True)
    assert r.tp == 1
