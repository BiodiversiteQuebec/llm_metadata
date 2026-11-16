"""Contribution scores on a synthetic Atlas whose numbers are easy to check by hand."""

import json
import math

import pandas as pd
import pytest

from llm_metadata.atlas_contribution import (
    DatasetDescription,
    Thresholds,
    case_study,
    compare_with_fuster,
    corpus_ids,
    coverage_north_south,
    describe_extraction,
    group_effort,
    group_gap,
    score_all,
    score_dataset,
    sensitivity,
    spatial_novelty,
    spearman,
    taxonomic_novelty,
    temporal_gain,
)
from llm_metadata.atlas_match import (
    NORTH_REF,
    PROVINCE_REF,
    SOUTH_REF,
    AtlasReference,
    PlaceMatch,
    TaxonMatch,
)
from llm_metadata.schemas.atlas_contribution import AtlasContributionExtraction


def _atlas():
    """Two groups. South: 400 000 km², north: 1 200 000 km².

    INSECTS: south 1 000 obs in the 2010s and 10 in the 1990s; north 10 in the 2010s.
    BIRDS: south 100 000 (2010s), north 50 000 (2010s).
    Species: one beetle with 99 south records and 0 north; one bird.
    """
    g = []
    for reg, ins90, ins10, birds in (("sud_49", 10, 1000, 100_000), ("nord_49", 0, 10, 50_000)):
        g += [
            dict(region_type="admin_nord_sud", region_name=reg, taxon_group="INSECTS", period="1990s", n_observations=ins90, n_species=1, n_datasets=1),
            dict(region_type="admin_nord_sud", region_name=reg, taxon_group="INSECTS", period="2010s", n_observations=ins10, n_species=1, n_datasets=1),
            dict(region_type="admin_nord_sud", region_name=reg, taxon_group="BIRDS", period="2010s", n_observations=birds, n_species=1, n_datasets=1),
        ]
    areas = pd.DataFrame([dict(region_type="admin_nord_sud", region_name="nord_49", area_km2=1_200_000),
                          dict(region_type="admin_nord_sud", region_name="sud_49", area_km2=400_000)])
    sp = pd.DataFrame([
        dict(region_type="admin_nord_sud", region_name="sud_49", id_taxa_ref_species=1, species="Carabus a", genus="Carabus",
             family="Carabidae", taxon_order="Coleoptera", taxon_class="Insecta", phylum="Arthropoda", kingdom="Animalia",
             taxon_group="INSECTS", period="2010s", n_observations=99, n_datasets=1),
        dict(region_type="admin_nord_sud", region_name="sud_49", id_taxa_ref_species=2, species="Turdus b", genus="Turdus",
             family="Turdidae", taxon_order="Passeriformes", taxon_class="Aves", phylum="Chordata", kingdom="Animalia",
             taxon_group="BIRDS", period="2010s", n_observations=100_000, n_datasets=1),
    ])
    return AtlasReference(pd.DataFrame(g), areas, sp)


BEETLE = TaxonMatch("Carabus a", "matched", "species", "Carabus a", ("INSECTS",))
BIRD = TaxonMatch("Turdus b", "matched", "species", "Turdus b", ("BIRDS",))
ABSENT = TaxonMatch("Carabus z", "absent", "species", "Carabus z", ("INSECTS",))
INSECTS = TaxonMatch("insects", "group", "group", None, ("INSECTS",))


def _desc(taxa, region, periods=(), rid="1"):
    level = "unknown" if region == "unknown" else "north_south"
    ref = PROVINCE_REF if region == "unknown" else region
    return DatasetDescription(rid, list(taxa), [PlaceMatch(str(region), level, ref)], list(periods))


def test_taxonomic_novelty_follows_the_log_formula():
    atlas = _atlas()
    th = Thresholds(k_taxon=100)
    # 99 records in the south: 1 - log10(100)/log10(101) ≈ 0.002
    assert taxonomic_novelty(_desc([BEETLE], SOUTH_REF), atlas, th) == pytest.approx(1 - 2 / math.log10(101))
    # none in the north: full novelty
    assert taxonomic_novelty(_desc([BEETLE], NORTH_REF), atlas, th) == 1.0


def test_absent_taxa_are_skipped_unless_asked():
    atlas = _atlas()
    assert math.isnan(taxonomic_novelty(_desc([ABSENT], SOUTH_REF), atlas))
    assert taxonomic_novelty(_desc([ABSENT], SOUTH_REF), atlas, Thresholds(absent_policy="novel")) == 1.0
    assert math.isnan(taxonomic_novelty(_desc([INSECTS], SOUTH_REF), atlas))  # group rank: no taxon score


def test_spatial_novelty_compares_density_with_the_province():
    atlas = _atlas()
    # Insects: province 1020 obs / 1.6 M km²; north 10 / 1.2 M km² -> ratio ≈ 0.0131 -> clipped to 1
    assert spatial_novelty(_desc([INSECTS], NORTH_REF), atlas) == 1.0
    assert spatial_novelty(_desc([INSECTS], SOUTH_REF), atlas) == 0.0
    # Birds north: (50 000 / 1.2 M) / (150 000 / 1.6 M) = 0.444 -> log10(2.25) ≈ 0.352
    assert spatial_novelty(_desc([BIRD], NORTH_REF), atlas) == pytest.approx(math.log10(1 / (50_000 / 1.2e6 / (150_000 / 1.6e6))))
    assert math.isnan(spatial_novelty(_desc([BIRD], "unknown"), atlas))


def test_temporal_gain_is_relative_to_the_best_decade():
    atlas = _atlas()
    # Insects south: 1990s hold 10 records vs 1000 in the 2010s -> q = 0.01 -> 1 (k=10)
    assert temporal_gain(_desc([INSECTS], SOUTH_REF, ["1990s"]), atlas) == 1.0
    assert temporal_gain(_desc([INSECTS], SOUTH_REF, ["2010s"]), atlas) == 0.0
    assert temporal_gain(_desc([INSECTS], SOUTH_REF, ["1990s"]), atlas, Thresholds(k_temporal=1000)) == pytest.approx(2 / 3)
    assert math.isnan(temporal_gain(_desc([INSECTS], SOUTH_REF, []), atlas))


def test_group_gap_uses_effort_per_species():
    atlas = _atlas()
    eff = group_effort(atlas).set_index("taxon_group")
    assert eff.loc["INSECTS", "obs_per_species"] == 1020
    # Median of two groups = (1020 + 150 000) / 2; insects get the gap, birds none
    ref = (1020 + 150_000) / 2
    assert group_gap(_desc([INSECTS], SOUTH_REF), atlas) == pytest.approx(min(1, math.log10(ref / 1020)))
    assert group_gap(_desc([BIRD], SOUTH_REF), atlas) == 0.0
    # Mixed dataset: one mention each -> mean of the two
    mixed = group_gap(_desc([INSECTS, BIRD], SOUTH_REF), atlas)
    assert mixed == pytest.approx(min(1, math.log10(ref / 1020)) / 2)


def test_score_dataset_counts_gaps_filled():
    atlas = _atlas()
    # A beetle north of the 49th in the 1990s: no Atlas record of it there, insects sparse
    # in the north, no northern insect record in the 1990s, insects under-sampled.
    s = score_dataset(_desc([BEETLE], NORTH_REF, ["1990s"]), atlas)
    assert (s["taxonomic"], s["spatial"], s["temporal"], s["group_gap"]) == (1.0, 1.0, 1.0, 1.0)
    assert s["n_scores"] == 4 and s["n_gaps"] == 4
    # The bird in the south in its best decade fills no gap
    s = score_dataset(_desc([BIRD], SOUTH_REF, ["2010s"]), atlas)
    assert s["n_gaps"] == 0 and s["taxonomic"] < 0.5


def test_sensitivity_reports_rank_stability():
    atlas = _atlas()
    descs = [_desc([BEETLE], SOUTH_REF, ["1990s"], "a"), _desc([BIRD], NORTH_REF, ["2010s"], "b"),
             _desc([INSECTS, BIRD], NORTH_REF, ["1990s"], "c")]
    out = sensitivity(descs, atlas, top=2)
    assert set(out["threshold"]) == {"k_taxon", "k_spatial", "k_temporal", "k_group", "gap_cut"}
    assert len(out) == 10


def test_compare_with_fuster_and_spearman():
    scores = pd.DataFrame({"taxonomic": [0.1, 0.5, 0.9], "spatial": [0, 0, 1], "temporal": [0.2, 0.4, 0.6],
                           "group_gap": [0, 0.5, 1], "n_gaps": [0, 1, 2]}, index=["1", "2", "3"])
    labels = pd.Series({"1": "L", "2": "M", "3": "H", "4": "X"})
    out = compare_with_fuster(scores, labels)
    assert out["n"] == 3
    assert out["spearman"]["taxonomic"][0] == pytest.approx(1.0)
    assert out["crosstab"].loc["H", 2] == 1
    assert math.isnan(spearman([1, 1, 1], [1, 2, 3])[0])


def test_case_study_puts_northern_insect_datasets_first():
    atlas = _atlas()
    descs = [_desc([BIRD], NORTH_REF, rid="birds"), _desc([BEETLE], SOUTH_REF, ["2010s"], "south"),
             _desc([BEETLE, BIRD], NORTH_REF, ["1990s"], "north")]
    out = case_study(descs, atlas)
    assert list(out["record_id"]) == ["north", "south"]
    assert out.loc[0, "group_share"] == 0.5 and bool(out.loc[0, "north"])


def test_describe_extraction_uses_places_and_years():
    atlas = _atlas()
    ext = AtlasContributionExtraction.model_validate({
        "focal_taxa": [{"verbatim_name": "ground beetle", "scientific_name": "Carabus a", "rank": "species"}],
        "places": [{"name": "Nunavik", "place_type": "natural_region", "in_quebec": True, "north_of_49": True}],
        "year_start": 1995, "year_end": 1996, "record_kind": "occurrence",
    })
    def resolver(names, cache=None):
        from llm_metadata.taxonomy_eval import TaxonItem
        from llm_metadata.gbif import TaxonRecord
        rec = TaxonRecord(query=names[0], kind="taxon", rank="SPECIES", canonical_name="Carabus a", species="Carabus a",
                          key=1, broad_groups=("insects",))
        return [TaxonItem(record_id="", side="", raw=names[0], mention=names[0], kind="taxon", record=rec)]
    d = describe_extraction("x", ext, atlas, resolver=resolver)
    assert d.taxa[0].status == "matched" and d.periods == ["1990s"]
    assert d.regions[0].region_name == "Nord-du-Québec"


def test_coverage_table_from_committed_aggregates():
    cov = coverage_north_south(AtlasReference.load(species_csv=None)).set_index("taxon_group")
    assert cov.loc["INSECTS", "obs_north"] == 51_455
    assert cov.loc["INSECTS", "share_north"] < 0.07


def test_corpus_ids_leave_heldout_out_by_default(tmp_path):
    gt = tmp_path / "gt.json"
    gt.write_text(json.dumps([{"gt_record_id": 1, "valid_yn": "yes"}, {"gt_record_id": 2, "valid_yn": "yes"},
                              {"gt_record_id": 3, "valid_yn": "no"}]))
    held = tmp_path / "held.csv"
    held.write_text("gt_record_id,source\n2,x\n")
    assert corpus_ids(gt_json=gt, heldout_csv=held) == [1]
    assert corpus_ids(True, gt_json=gt, heldout_csv=held) == [1, 2]
