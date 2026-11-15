"""Tests for class-level scoring, bootstrap intervals, evidence ceiling and run summaries."""

import json
import warnings
from pathlib import Path

import pytest

from llm_metadata.evidence_ceiling import (
    ceiling_recall,
    evidence_table,
    parse_position,
)
from llm_metadata.groundtruth_eval import (
    DERIVED_FIELDS,
    MICRO_KEY,
    EvaluationConfig,
    EvaluationReport,
    FieldEvalStrategy,
    FieldResult,
    aggregate_field_metrics,
    bootstrap_report,
    compare_models,
    evaluate_indexed,
)
from llm_metadata.run_summary import summarize_run
from llm_metadata.schemas.fuster_features import DatasetFeatures, DatasetFeaturesExtraction

ROOT = Path(__file__).resolve().parents[1]


def _model(**kw):
    return DatasetFeatures.model_validate(kw)


# ---- class-level scoring ---------------------------------------------------

CLASS_CONFIG = EvaluationConfig(
    field_strategies={
        "spatial_range_km2": FieldEvalStrategy(),
        "spatial_range_class": FieldEvalStrategy(),
        "temporal_range_class": FieldEvalStrategy(),
    }
)


def _by_field(results):
    return {r.field: r for r in results}


def test_class_match_when_exact_value_differs():
    res = _by_field(compare_models(
        true_model=_model(spatial_range_km2=20000, temp_range_i=2000, temp_range_f=2015),
        pred_model=_model(spatial_range_km2=90000, temp_range_i=2001, temp_range_f=2014),
        record_id=1, config=CLASS_CONFIG,
    ))
    assert res["spatial_range_km2"].match is False  # exact km2 differs
    assert res["spatial_range_class"].match is True  # both H
    assert res["spatial_range_class"].tp == 1
    assert res["temporal_range_class"].match is True  # 16 and 14 years, both H


def test_class_mismatch_and_not_stated():
    res = _by_field(compare_models(
        true_model=_model(spatial_range_km2=20000, temp_range_i=2000, temp_range_f=2015),
        pred_model=_model(spatial_range_km2=100),
        record_id=1, config=CLASS_CONFIG,
    ))
    assert (res["spatial_range_class"].fp, res["spatial_range_class"].fn) == (1, 1)  # H vs L
    assert res["temporal_range_class"].fn == 1  # annotated class, none predicted
    both_empty = _by_field(compare_models(
        true_model=_model(), pred_model=_model(), record_id=2, config=CLASS_CONFIG
    ))
    assert both_empty["spatial_range_class"].tn == 1  # both "not stated"
    assert set(DERIVED_FIELDS) == {"spatial_range_class", "temporal_range_class"}


# ---- the geospatial_info bug -----------------------------------------------

def test_stale_field_name_warns_and_scores_nothing():
    cfg = EvaluationConfig(field_strategies={"geospatial_info": FieldEvalStrategy()})
    with pytest.warns(UserWarning, match="geospatial_info"):
        res = compare_models(
            true_model=_model(geospatial_info_dataset=["site"]),
            pred_model=_model(geospatial_info_dataset=["site"]),
            record_id=1, config=cfg,
        )
    assert res[0].tn == 1 and res[0].tp == 0  # the old silent behaviour: no P/R/F1


def test_checked_in_configs_use_real_field_names():
    names = set(DatasetFeatures.model_fields) | set(DERIVED_FIELDS)
    for path in sorted((ROOT / "configs").glob("eval_*.json")):
        cfg = EvaluationConfig.from_json(path)
        assert set(cfg.field_strategies) <= names, path.name


def test_geospatial_info_dataset_is_scored():
    cfg = EvaluationConfig.from_json(ROOT / "configs/eval_default.json")
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        res = _by_field(compare_models(
            true_model=_model(geospatial_info_dataset=["site", "sample"]),
            pred_model=_model(geospatial_info_dataset=["site"]),
            record_id=1, config=cfg,
        ))
    g = res["geospatial_info_dataset"]
    assert (g.tp, g.fp, g.fn) == (1, 0, 1)


# ---- bootstrap -------------------------------------------------------------

def _report(n=40, hit_rate=0.5):
    results = []
    for i in range(n):
        hit = (i % 2 == 0) if hit_rate == 0.5 else True
        results.append(FieldResult(i, "multispecies", True, True if hit else None, hit,
                                   tp=int(hit), fn=int(not hit)))
        results.append(FieldResult(i, "time_series", None, None, True, tn=1))
    return EvaluationReport(results, aggregate_field_metrics(results), EvaluationConfig())


def test_bootstrap_is_reproducible_and_brackets_point():
    rep = _report()
    a = bootstrap_report(rep, n_boot=200, seed=3)
    b = bootstrap_report(rep, n_boot=200, seed=3)
    assert a["multispecies"]["recall"] == b["multispecies"]["recall"]
    r = a["multispecies"]["recall"]
    assert r.point == pytest.approx(0.5)
    assert r.low < 0.5 < r.high
    assert r.low >= 0.3 and r.high <= 0.7  # roughly +-0.15 for n = 40
    assert MICRO_KEY in a
    # nothing positive for time_series: undefined, not zero
    assert a["time_series"]["precision"].point is None
    assert a["time_series"]["exact_match_rate"].point == 1.0


def test_bootstrap_degenerate_has_zero_width():
    r = bootstrap_report(_report(hit_rate=1.0), n_boot=100)["multispecies"]["recall"]
    assert (r.point, r.low, r.high) == (1.0, 1.0, 1.0)


def test_bootstrap_reads_saved_report_and_run_artifact(tmp_path):
    rep = _report(10)
    saved = tmp_path / "report.json"
    rep.save(saved)
    assert bootstrap_report(saved, n_boot=50)["multispecies"]["recall"].point == pytest.approx(0.5)
    doc = json.loads(saved.read_text())
    wrapped = tmp_path / "run.json"
    wrapped.write_text(json.dumps({"name": "x", "evaluation": {
        "config": doc["config"], "field_metrics": doc["field_metrics"], "field_results": doc["field_results"]}}))
    assert bootstrap_report(wrapped, n_boot=50)["multispecies"]["recall"].point == pytest.approx(0.5)


# ---- evidence ceiling ------------------------------------------------------

def test_parse_position_vocabulary():
    assert parse_position("source link abstract, dataset") == {"abstract", "dataset"}
    assert parse_position("source publication text") == {"article"}
    assert parse_position("source link") == {"abstract"}
    assert parse_position("not given") == {"none"}
    assert parse_position("no") == {"none"}
    assert parse_position(float("nan")) == frozenset()
    with pytest.raises(ValueError):
        parse_position("somewhere new")


def test_ceiling_abstract_is_below_fulltext():
    table = evidence_table(ROOT / "data/dataset_092624.xlsx")
    for field in ("temp_range_i", "spatial_range_km2", "geospatial_info_dataset"):
        a = ceiling_recall(field, "abstract", table=table)
        f = ceiling_recall(field, "fulltext", table=table)
        assert a.n_value == f.n_value > 0
        assert a.recall <= f.recall
        assert a.recall_low <= a.recall_high
    sp = ceiling_recall("spatial_range_km2", "abstract", table=table)
    assert sp.recall < 0.2  # most km2 values are annotator estimates or only in the article


def test_ceiling_rejects_unknown_input_and_field():
    with pytest.raises(ValueError):
        ceiling_recall("temp_range_i", "video")
    with pytest.raises(KeyError):
        ceiling_recall("species", "abstract")


# ---- run summary -----------------------------------------------------------

def test_summarize_run_on_synthetic_artifact(tmp_path):
    gt = json.loads((ROOT / "data/gt/fuster_gt.json").read_text())
    import pandas as pd
    dev_ids = list(pd.read_csv(ROOT / "data/manifests/dev_subset_data_paper.csv")["gt_record_id"])
    held_ids = list(pd.read_csv(ROOT / "data/manifests/heldout_ids.csv")["gt_record_id"])
    by_id = {e["gt_record_id"]: e for e in gt}
    records = []
    for gid in dev_ids[:5] + held_ids[:2]:
        out = {k: v for k, v in by_id[gid].items() if k in DatasetFeaturesExtraction.model_fields}
        records.append({"gt_record_id": gid, "status": "success", "output": out})
    run = tmp_path / "run.json"
    run.write_text(json.dumps({"name": "synthetic", "mode": "abstract", "model": "m", "records": records}))
    text = summarize_run(run, n_boot=50)
    assert "Records scored: 5 (dev)" in text  # held-out records in the file are not scored
    assert "geospatial_info_dataset" in text and "spatial_range_class" in text
    assert "ceiling R" in text
