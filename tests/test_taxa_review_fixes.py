"""Regression tests for the review of the taxa evaluation (GBIF answers mocked)."""

import pytest

from llm_metadata import gbif
from llm_metadata.gbif import GBIFCache, resolve_taxon
from llm_metadata.species_parsing import split_conjunction
from llm_metadata.taxonomy_eval import evaluate_taxa_lists


def _taxon(key, name, *, rank="SPECIES", kingdom="Animalia", phylum="Chordata", class_="Aves", order="Passeriformes",
           family="Turdidae", genus=None, match_type="EXACT", status="ACCEPTED"):
    data = {"usageKey": key, "canonicalName": name, "scientificName": name, "rank": rank, "status": status,
            "confidence": 98, "matchType": match_type, "kingdom": kingdom, "phylum": phylum, "class": class_,
            "order": order, "family": family, "genus": genus or name.split()[0],
            "kingdomKey": 1 if kingdom == "Animalia" else 6, "phylumKey": 44, "classKey": 212, "orderKey": 729,
            "familyKey": key * 10, "genusKey": key * 100}
    if rank == "SPECIES":
        data["species"] = name
        data["speciesKey"] = key
    return data


BIRDS = {n: _taxon(k, n) for k, n in [(11, "Turdus migratorius"), (12, "Catharus guttatus"), (13, "Hylocichla mustelina")]}
MATCH = {
    **BIRDS,
    "Aves": _taxon(212, "Aves", rank="CLASS", order=None, family=None, genus=None),
    "Salvelinus fontinalis": _taxon(21, "Salvelinus fontinalis", class_=None, order="Salmoniformes", family="Salmonidae"),
    # Homonym genus: GBIF declines to choose between an animal and a plant genus
    "Morus": {"matchType": "NONE", "confidence": 100, "alternatives": [
        _taxon(31, "Morus", rank="GENUS", order="Suliformes", family="Sulidae"),
        _taxon(32, "Morus", rank="GENUS", kingdom="Plantae", phylum="Tracheophyta", class_="Magnoliopsida",
               order="Rosales", family="Moraceae"),
    ]},
    # A binomial unknown to the backbone: GBIF answers with its genus (HIGHERRANK)
    "Typhlodromus herbertae": _taxon(41, "Typhlodromus", rank="GENUS", match_type="HIGHERRANK", phylum="Arthropoda",
                                     class_="Arachnida", order="Mesostigmata", family="Phytoseiidae"),
    "Typhlodromus pyri": _taxon(41, "Typhlodromus", rank="GENUS", match_type="HIGHERRANK", phylum="Arthropoda",
                                class_="Arachnida", order="Mesostigmata", family="Phytoseiidae"),
    "Typhlodromus": _taxon(41, "Typhlodromus", rank="GENUS", phylum="Arthropoda", class_="Arachnida",
                           order="Mesostigmata", family="Phytoseiidae"),
}


@pytest.fixture
def fake(monkeypatch, tmp_path):
    calls = []

    def fake_get(url, params):
        calls.append((url, dict(params)))
        if url.endswith("/species/match"):
            return MATCH.get(params["name"], {"matchType": "NONE", "confidence": 100})
        if url.endswith("/species/search"):
            # A wrong but plausible vernacular hit, which a homonym must never reach
            return {"results": [{"key": 99, "canonicalName": "Gadus morhua", "rank": "SPECIES",
                                 "taxonomicStatus": "ACCEPTED", "kingdom": "Animalia",
                                 "vernacularNames": [{"vernacularName": params["q"]}]}]}
        raise AssertionError(url)

    monkeypatch.setattr(gbif, "_http_get_json", fake_get)
    return GBIFCache(tmp_path / "cache.json"), calls


def test_homonym_genus_stays_unresolved_and_skips_vernacular_search(fake):
    cache, calls = fake
    rec = resolve_taxon("Morus", cache=cache)
    assert rec.status == "ambiguous_homonym"
    assert not any(url.endswith("/species/search") for url, _ in calls)


def test_binomial_not_in_backbone_keeps_its_own_exact_label(fake):
    cache, _ = fake
    a = resolve_taxon("Typhlodromus herbertae", cache=cache)
    b = resolve_taxon("Typhlodromus pyri", cache=cache)
    assert a.status == b.status == "species_not_in_backbone"
    assert a.canonical_name != b.canonical_name  # two unknown species do not merge
    assert a.genus == b.genus == "Typhlodromus"


def test_curated_vernacular_override(fake):
    cache, _ = fake
    rec = resolve_taxon("brook trout", cache=cache)
    assert rec.canonical_name == "Salvelinus fontinalis"


def test_split_on_conjunction_outside_parentheses():
    assert split_conjunction("lemming and rock vole") == ["lemming", "rock vole"]
    assert split_conjunction("beetles (Silphidae and Histeridae)") == ["beetles (Silphidae and Histeridae)"]


def test_count_container_is_capped(fake):
    cache, _ = fake
    true = {"r": ["2 bird species"]}
    pred = {"r": list(BIRDS)}  # three birds listed under "2 bird species"
    capped = evaluate_taxa_lists(true, pred, cache=cache, set_aside="capped")
    uncapped = evaluate_taxa_lists(true, pred, cache=cache, set_aside="uncapped")
    none = evaluate_taxa_lists(true, pred, cache=cache, set_aside="none")
    def fp(ev):  # extracted entries scored but unmatched = false positives
        c = ev.rank_metrics("exact")
        return c.n_pred - c.n_pred_matched

    fp = {"capped": fp(capped), "uncapped": fp(uncapped), "none": fp(none)}
    assert fp["uncapped"] == 0  # old behaviour: all three set aside
    assert fp["capped"] == 1  # one beyond the stated count
    assert fp["none"] == 3  # floor
