"""Matching dataset taxa, places and years to the Atlas tables (no network, synthetic Atlas)."""

import pandas as pd
import pytest

from llm_metadata.atlas_match import (
    GROUP_TABLE,
    NORTH_REF,
    PROVINCE_REF,
    SOUTH_REF,
    AtlasReference,
    RegionRef,
    clean_mention,
    match_place,
    match_rates,
    match_record,
    match_taxa,
    periods_for_years,
    places_from_north_flag,
    scope_regions,
)
from llm_metadata.gbif import TaxonRecord
from llm_metadata.taxonomy_eval import TaxonItem


def _species_rows():
    rows = []
    def add(region_type, region, sp, genus, family, order, cls, group, period, n):
        rows.append(dict(region_type=region_type, region_name=region, id_taxa_ref_species=hash(sp) % 10**6, species=sp,
                         genus=genus, family=family, taxon_order=order, taxon_class=cls, phylum="X", kingdom="Animalia",
                         taxon_group=group, period=period, n_observations=n, n_datasets=1))
    for rt, reg in (("admin", "Estrie"), ("admin_nord_sud", "sud_49")):
        add(rt, reg, "Carabus nemoralis", "Carabus", "Carabidae", "Coleoptera", "Insecta", "INSECTS", "2010s", 500)
        add(rt, reg, "Hudsonius hudsonius", "Hudsonius", "Leuciscidae", "Cypriniformes", "Actinopterygii", "FISH", "2000s", 40)
        add(rt, reg, "Odocoileus virginianus", "Odocoileus", "Cervidae", "Artiodactyla", "Mammalia", "MAMMALS", "2010s", 900)
    add("admin_nord_sud", "nord_49", "Carabus nemoralis", "Carabus", "Carabidae", "Coleoptera", "Insecta", "INSECTS", "2010s", 3)
    add("admin", "Nord-du-Québec", "Carabus nemoralis", "Carabus", "Carabidae", "Coleoptera", "Insecta", "INSECTS", "2010s", 3)
    return pd.DataFrame(rows)


def _groups():
    rows = []
    for rt, reg, ins, fish, mam in (("admin", "Estrie", 500, 40, 900), ("admin", "Nord-du-Québec", 3, 0, 0),
                                     ("admin_nord_sud", "sud_49", 500, 40, 900), ("admin_nord_sud", "nord_49", 3, 0, 0)):
        for g, n in (("INSECTS", ins), ("FISH", fish), ("MAMMALS", mam)):
            rows.append(dict(region_type=rt, region_name=reg, taxon_group=g, period="2010s", n_observations=n,
                             n_species=1, n_datasets=1))
    return pd.DataFrame(rows)


def _areas():
    return pd.DataFrame([
        dict(region_type="admin", region_name="Estrie", area_km2=10_000),
        dict(region_type="admin", region_name="Nord-du-Québec", area_km2=800_000),
        dict(region_type="admin_nord_sud", region_name="nord_49", area_km2=1_200_000),
        dict(region_type="admin_nord_sud", region_name="sud_49", area_km2=400_000),
    ])


@pytest.fixture
def atlas():
    return AtlasReference(_groups(), _areas(), _species_rows())


def _taxon(name, rank, **kw):
    level_kind = "group" if rank in {"ORDER", "CLASS", "PHYLUM"} else "taxon"
    rec = TaxonRecord(query=name, kind=kw.pop("kind", level_kind), method=kw.pop("method", "scientific"),
                      canonical_name=name, accepted_name=name, rank=rank, key=kw.pop("key", 1), **kw)
    return rec


# -- places -------------------------------------------------------------------

@pytest.mark.parametrize("name,region", [
    ("Gaspé Peninsula", "Gaspésie–Îles-de-la-Madeleine"),
    ("Nunavik", "Nord-du-Québec"),
    ("Lac-Saint-Jean", "Saguenay–Lac-Saint-Jean"),
    ("Lac St-Jean", "Saguenay–Lac-Saint-Jean"),
    ("Eastern Townships", "Estrie"),
    ("Montréal", "Montréal"),
    ("Côte-Nord region", "Côte-Nord"),
    ("Anticosti Island", "Côte-Nord"),
])
def test_place_names_match_administrative_regions(name, region):
    m = match_place(name)
    assert m.level == "region" and m.region == RegionRef("admin", region)


def test_place_falls_back_to_north_south_then_province():
    assert match_place("northern Quebec").region == NORTH_REF
    assert match_place("Lac Wapizagonke", north_of_49=False).region == SOUTH_REF
    assert match_place("Some bog", in_quebec=True).level == "province"
    assert match_place("Quebec").region == PROVINCE_REF
    assert match_place("Ontario", in_quebec=False).level == "outside"
    assert match_place("A forest somewhere").level == "unmatched"


def test_first_named_region_wins_and_others_are_noted():
    m = match_place("Estrie and Montérégie")
    assert m.region.region_name == "Estrie" and "Montérégie" in m.note


def test_annotation_flag_gives_the_only_place():
    assert places_from_north_flag(True)[0].region == NORTH_REF
    assert places_from_north_flag(False)[0].region == SOUTH_REF
    unknown = places_from_north_flag(None)[0]
    assert unknown.level == "unknown" and unknown.region == PROVINCE_REF


def test_scope_prefers_fine_regions():
    places = [match_place("Quebec"), match_place("Nunavik")]
    assert scope_regions(places) == [RegionRef("admin", "Nord-du-Québec")]
    assert scope_regions([]) == [PROVINCE_REF]


# -- years ----------------------------------------------------------------------

def test_periods_cover_the_year_range():
    assert periods_for_years(1948, 1962) == ["before_1950", "1950s", "1960s"]
    assert periods_for_years("2004", None) == ["2000s"]
    assert periods_for_years(None, None) == []
    assert periods_for_years(2012, 2003) == ["2000s", "2010s"]


# -- taxa -----------------------------------------------------------------------

def test_species_matched_at_species_rank(atlas):
    rec = _taxon("Carabus nemoralis", "SPECIES", species="Carabus nemoralis", genus="Carabus", family="Carabidae",
                 broad_groups=("insects",))
    m = match_record("Carabus nemoralis", rec, atlas)
    assert (m.status, m.rank, m.name, m.groups) == ("matched", "species", "Carabus nemoralis", ("INSECTS",))


def test_subspecies_matched_to_its_species(atlas):
    rec = _taxon("Odocoileus virginianus borealis", "SUBSPECIES", species="Odocoileus virginianus",
                 genus="Odocoileus", family="Cervidae", broad_groups=("mammals",))
    m = match_record("deer", rec, atlas)
    assert m.status == "matched" and m.name == "Odocoileus virginianus"


def test_absent_species_keeps_its_group(atlas):
    rec = _taxon("Carabus auratus", "SPECIES", species="Carabus auratus", genus="Carabus", family="Carabidae",
                 broad_groups=("insects",))
    m = match_record("Carabus auratus", rec, atlas)
    assert m.status == "absent" and m.groups == ("INSECTS",) and "genus is in the Atlas" in m.note
    assert m.below_group


def test_synonym_found_by_epithet_when_gbif_agrees(atlas):
    rec = _taxon("Notropis hudsonius", "SPECIES", species="Notropis hudsonius", genus="Notropis",
                 family="Leuciscidae", broad_groups=("fish",))
    assert match_record("spottail shiner", rec, atlas).status == "absent"
    m = match_record("spottail shiner", rec, atlas, same_taxon=lambda name, r: name == "Hudsonius hudsonius")
    assert m.status == "matched" and m.name == "Hudsonius hudsonius"


def test_order_matches_the_atlas_order_column(atlas):
    rec = _taxon("Coleoptera", "ORDER", broad_groups=("insects",))
    m = match_record("beetles", rec, atlas)
    assert (m.status, m.rank, m.name) == ("matched", "order", "Coleoptera")


def test_group_label_without_backbone_taxon(atlas):
    rec = TaxonRecord(query="fish", kind="group", method="group label", label="fish", broad_groups=("fish",))
    m = match_record("fish", rec, atlas)
    assert (m.status, m.rank, m.groups) == ("group", "group", ("FISH",))


def test_homonyms_and_odd_common_names_are_unresolved(atlas):
    homonym = _taxon("Elymus mollis", "SPECIES", species="Elymus mollis", broad_groups=("vascular plants",),
                     note="homonym: first exact synonym in GBIF order was taken")
    assert match_record("Elymus mollis", homonym, atlas).status == "unresolved"
    odd = _taxon("Raillietiella orientalis", "SPECIES", species="Raillietiella orientalis", genus="Raillietiella",
                 family="Raillietiellidae", broad_groups=("other arthropods",), method="vernacular")
    assert match_record("parasites", odd, atlas).status == "unresolved"
    # Same common-name route, but the family is in the Atlas: kept as absent (caribou is sensitive)
    caribou = _taxon("Rangifer tarandus", "SPECIES", species="Rangifer tarandus", genus="Rangifer",
                     family="Cervidae", broad_groups=("mammals",), method="vernacular")
    assert match_record("caribou", caribou, atlas).status == "absent"


def test_unresolved_record(atlas):
    assert match_record("Basam fir", TaxonRecord(query="Basam fir"), atlas).status == "unresolved"


def _fake_resolver(table):
    def resolver(names, cache=None):
        out = []
        for raw in names:
            kind, rec, count = table.get(raw, ("unresolved", TaxonRecord(query=raw), None))
            out.append(TaxonItem(record_id="", side="", raw=raw, mention=raw, kind=kind, record=rec, count=count,
                                 other_reason="noise" if kind == "other" else None))
        return out
    return resolver


def test_match_taxa_cleans_text_retries_lowercase_and_flags_counts(atlas):
    carabus = _taxon("Carabus nemoralis", "SPECIES", species="Carabus nemoralis", genus="Carabus",
                     family="Carabidae", broad_groups=("insects",))
    folsomia = _taxon("Folsomia candida", "SPECIES", species="Folsomia candida", broad_groups=("other arthropods",))
    table = {
        "Carabus nemoralis": ("taxon", carabus, None),
        "Carabus x": ("taxon", carabus, None),
        "c. 90 collembola species": ("count", folsomia, 90),
        "and others": ("other", None, None),
    }
    out = match_taxa(["carabus nemoralis", "Carabus_x000D_ x", "c. 90 collembola species", "and others", ""],
                     atlas, resolver=_fake_resolver(table))
    assert [m.status for m in out] == ["matched", "matched", "unresolved", "other"]
    rates = match_rates(out)
    assert rates["n_mentions"] == 3 and rates["n_other"] == 1
    assert rates["share_matched"] == pytest.approx(2 / 3)


def test_clean_mention():
    assert clean_mention("Rangifer_x000D_ tarandus ") == "Rangifer tarandus"


# -- reference tables -------------------------------------------------------------

def test_lookups_sum_regions_and_province(atlas):
    assert atlas.taxon_observations("species", "Carabus nemoralis", RegionRef("admin", "Estrie")) == 500
    assert atlas.taxon_observations("genus", "Carabus", PROVINCE_REF) == 503
    assert atlas.group_observations("INSECTS", PROVINCE_REF) == 503
    assert atlas.group_observations("INSECTS", NORTH_REF, "2010s") == 3
    assert atlas.area(PROVINCE_REF) == 1_600_000


def test_committed_aggregates_load_without_the_species_table():
    ref = AtlasReference.load(species_csv=None)
    assert ref.species is None
    insects_north = ref.group_observations("INSECTS", NORTH_REF)
    assert insects_north == 51_455
    assert ref.area(PROVINCE_REF) == pytest.approx(1_680_833)
    assert "INSECTS" in ref.group_names and GROUP_TABLE.exists()
