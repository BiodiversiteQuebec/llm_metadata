"""Tests for the Fuster rule scorer (llm_metadata.relevance_rules)."""

from pathlib import Path

import pandas as pd
import pytest

from llm_metadata.relevance_rules import (
    LABELS,
    apply_modulators,
    binarize,
    classify_features,
    dataset_type_class,
    features_from_row,
    majority_vote,
    normalize_human_label,
    spatial_range_class,
    temporal_range_class,
)

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("abundance", "H"),
        ("density", "H"),
        ("EBV genetic analysis", "H"),
        ("distribution", "M"),
        ("presence-absence", "M"),
        ("presence only", "L"),
        ("presence", "L"),
        ("genetic analysis", "L"),  # plain genetic analysis counts as non-EBV
        ("species richness", "L"),
        ("relative abundance", "L"),
        ("other", "X"),
        ("unknown", "X"),
        (None, "X"),
        (float("nan"), "X"),
        ("presence only, EBV genetic analysis", "H"),  # best phrase wins
        ("density, species richness", "H"),
        ("EBV genetic analysis, other", "H"),
        (["presence-only", "abundance"], "H"),
        (["presence-only"], "L"),
    ],
)
def test_dataset_type_class(raw, expected):
    assert dataset_type_class(raw) == expected


def test_dataset_type_falls_back_to_normalized_primary():
    assert dataset_type_class(None, "abundance") == "H"
    assert dataset_type_class("", "genetic_analysis") == "L"


@pytest.mark.parametrize(
    "start, end, expected",
    [
        (2000, 2000, "L"),  # 1 year
        (2000, 2001, "L"),  # 2 years
        (2000, 2002, "M"),  # 3 years, lower edge of M
        (2000, 2010, "M"),  # 11 years, upper edge of M
        (2000, 2011, "H"),  # 12 years, lower edge of H
        (1690, 2004, "H"),
        (None, 2004, "X"),
        (2000, float("nan"), "X"),
        ("2000", "2012", "H"),
        ("n/a", 2012, "X"),
    ],
)
def test_temporal_range_class(start, end, expected):
    assert temporal_range_class(start, end) == expected


@pytest.mark.parametrize(
    "km2, expected",
    [
        (15001, "H"),
        (15000, "M"),
        (5000, "M"),
        (4999.9, "L"),
        (0.5, "L"),
        (None, "X"),
        (float("nan"), "X"),
        ("not given", "X"),
        ("20000", "H"),
    ],
)
def test_spatial_range_class(km2, expected):
    assert spatial_range_class(km2) == expected


@pytest.mark.parametrize(
    "dt, temporal, spatial, expected",
    [
        ("H", "H", "L", "H"),  # two agree
        ("L", "L", "L", "L"),
        ("X", "H", "X", "X"),
        ("H", "M", "L", "M"),  # all differ: min(dt, max(t, s)) = min(H, M)
        ("M", "H", "L", "M"),
        ("L", "H", "M", "L"),
        ("H", "X", "L", "L"),  # special case: H with an X
        ("H", "L", "X", "L"),
        ("M", "X", "L", "L"),  # general rule: min(M, max(X, L)) = L
    ],
)
def test_majority_vote(dt, temporal, spatial, expected):
    assert majority_vote(dt, temporal, spatial) == expected


def test_modulators_upgrade_one_level_only():
    on = {"multispecies": True, "threatened_species": True, "bias_north_south": True}
    assert apply_modulators("L", on) == "M"
    assert apply_modulators("M", on) == "H"
    assert apply_modulators("H", on) == "H"
    assert apply_modulators("X", on) == "L"  # observed in the released labels
    for name in ("multispecies", "threatened_species", "new_species_science",
                 "new_species_region", "bias_north_south"):
        assert apply_modulators("L", {name: True}) == "M"
    assert apply_modulators("L", {"multispecies": False, "threatened_species": None}) == "L"
    assert apply_modulators("L", {"multispecies": "yes"}) == "M"


def test_classify_features_end_to_end():
    res = classify_features(
        {"data_type": "abundance", "temp_range_i": 2000, "temp_range_f": 2015,
         "spatial_range_km2": 100, "multispecies": True}
    )
    assert (res.dataset_type, res.temporal, res.spatial) == ("H", "H", "L")
    assert res.relevance == "H"
    assert res.relevance_modifiers == "H"
    assert res.as_mc_columns()["MC_relevance"] == "H"
    empty = classify_features({})
    assert empty.relevance_modifiers == "X"


def test_binarize_and_human_labels():
    assert [binarize(x) for x in "HMLX"] == ["relevant", "relevant", "not_relevant", "not_relevant"]
    assert binarize("No dataset") is None
    assert normalize_human_label(" X") == "X"
    assert normalize_human_label("No dataset") is None
    assert normalize_human_label("cant access") is None
    assert normalize_human_label(float("nan")) is None


MC_COLUMNS = {
    "MC_dataset_type": "dataset_type",
    "MC_temporal_range": "temporal",
    "MC_spatial_range": "spatial",
    "MC_relevance": "relevance",
    "MC_relevance_modifiers": "relevance_modifiers",
}


def test_reproduces_released_mc_columns_on_dev_records():
    raw = pd.read_excel(ROOT / "data/dataset_092624.xlsx")
    dev_ids = set(pd.read_csv(ROOT / "data/manifests/dev_subset_data_paper.csv")["gt_record_id"])
    dev = raw[raw["id"].isin(dev_ids)]
    assert len(dev) == 30
    for _, row in dev.iterrows():
        res = classify_features(features_from_row(row))
        for column, attr in MC_COLUMNS.items():
            assert row[column] in LABELS
            assert getattr(res, attr) == row[column], f"record {row['id']} {column}"
