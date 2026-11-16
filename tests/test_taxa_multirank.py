"""Tests for GBIF taxon resolution (`resolve_taxon`) and the multi-rank taxa evaluation.

All GBIF responses are mocked; the JSON cache lives in a temporary folder.
"""

import json

import pytest

from llm_metadata import gbif
from llm_metadata.gbif import GBIFCache, broad_groups_for_classification, resolve_taxon
from llm_metadata.species_parsing import TaxonMention, split_taxon_items
from llm_metadata.taxonomy_eval import evaluate_run_taxa, evaluate_taxa_lists


def _species(key, name, *, kingdom="Animalia", phylum=None, class_=None, order=None, family=None,
             genus=None, rank="SPECIES", match_type="EXACT", status="ACCEPTED", keys=None, **extra):
    data = {
        "usageKey": key, "canonicalName": name, "scientificName": name, "rank": rank, "status": status,
        "confidence": 98, "matchType": match_type, "kingdom": kingdom, "phylum": phylum, "class": class_,
        "order": order, "family": family, "genus": genus,
    }
    if rank in ("SPECIES", "SUBSPECIES", "VARIETY"):
        data["species"] = " ".join(name.split()[:2])
        data["speciesKey"] = (keys or {}).get("species", key)
    data.update({f"{r}Key": v for r, v in (keys or {}).items() if r != "species"})
    data.update(extra)
    return {k: v for k, v in data.items() if v is not None}


SALMONIDAE = dict(phylum="Chordata", order="Salmoniformes", family="Salmonidae", genus="Salmo",
                  keys={"kingdom": 1, "phylum": 44, "order": 1313, "family": 8615, "genus": 2347608})
ERICACEAE = dict(kingdom="Plantae", phylum="Tracheophyta", class_="Magnoliopsida", order="Ericales",
                 family="Ericaceae", genus="Vaccinium",
                 keys={"kingdom": 6, "phylum": 7707728, "class": 220, "order": 1353, "family": 2505, "genus": 2882813})
SILPHIDAE = dict(phylum="Arthropoda", class_="Insecta", order="Coleoptera", family="Silphidae", genus="Nicrophorus",
                 keys={"kingdom": 1, "phylum": 54, "class": 216, "order": 1470, "family": 5464, "genus": 1046})
CERVIDAE = dict(phylum="Chordata", class_="Mammalia", order="Artiodactyla", family="Cervidae", genus="Rangifer",
                keys={"kingdom": 1, "phylum": 44, "class": 359, "order": 731, "family": 5298, "genus": 2440913})

MATCH = {
    "Salmo salar": _species(7595433, "Salmo salar", **SALMONIDAE),
    "Vaccinium spp.": _species(2882813, "Vaccinium", rank="GENUS", match_type="HIGHERRANK", **ERICACEAE),
    "Vaccinium angustifolium": _species(2882849, "Vaccinium angustifolium", **ERICACEAE),
    "Vaccinium myrtilloides": _species(2882834, "Vaccinium myrtilloides", **ERICACEAE),
    "Nicrophorus sayi": _species(1047, "Nicrophorus sayi", **SILPHIDAE),
    "Rangifer tarandus": _species(5220114, "Rangifer tarandus", **CERVIDAE),
    "Rangifer tarandus caribou": _species(5220115, "Rangifer tarandus caribou", rank="SUBSPECIES",
                                          **{**CERVIDAE, "keys": {**CERVIDAE["keys"], "species": 5220114}}),
    "Aves": _species(212, "Aves", rank="CLASS", phylum="Chordata", class_="Aves",
                     keys={"kingdom": 1, "phylum": 44, "class": 212}),
    "Coleoptera": _species(1470, "Coleoptera", rank="ORDER", phylum="Arthropoda", class_="Insecta",
                           order="Coleoptera", keys={"kingdom": 1, "phylum": 54, "class": 216, "order": 1470}),
    "Arachnida": _species(367, "Arachnida", rank="CLASS", phylum="Arthropoda", class_="Arachnida",
                          keys={"kingdom": 1, "phylum": 54, "class": 367}),
    "Setophaga ruticilla": _species(2489, "Setophaga ruticilla", phylum="Chordata", class_="Aves",
                                    order="Passeriformes", family="Parulidae", genus="Setophaga",
                                    keys={"kingdom": 1, "phylum": 44, "class": 212, "order": 729,
                                          "family": 9338, "genus": 2488}),
    # GBIF declines to choose between homonyms; an exact accepted alternative exists
    "Eteone": {"matchType": "HIGHERRANK", "usageKey": 1, "canonicalName": "Animalia", "rank": "KINGDOM",
               "status": "ACCEPTED", "confidence": 92, "kingdom": "Animalia",
               "alternatives": [
                   _species(2311842, "Eteone", rank="GENUS", phylum="Annelida", class_="Polychaeta",
                            order="Phyllodocida", family="Phyllodocidae", genus="Eteone",
                            keys={"kingdom": 1, "phylum": 42, "family": 6973, "genus": 2311842}),
                   _species(3257626, "Eteone", rank="GENUS", status="SYNONYM", acceptedUsageKey=1892909,
                            phylum="Arthropoda", class_="Insecta"),
               ]},
}

SEARCH = {
    "atlantic salmon": [
        {"key": 7595433, "canonicalName": "Salmo salar", "rank": "SPECIES", "taxonomicStatus": "ACCEPTED",
         "kingdom": "Animalia", "vernacularNames": [{"vernacularName": "Atlantic Salmon"}, {"vernacularName": "saumon atlantique"}]},
        {"key": 99, "canonicalName": "Salmo salar sebago", "rank": "SUBSPECIES", "taxonomicStatus": "ACCEPTED",
         "kingdom": "Animalia", "vernacularNames": [{"vernacularName": "landlocked Atlantic salmon"}]},
    ],
    "caribou": [
        {"key": 2440913, "canonicalName": "Rangifer", "rank": "GENUS", "taxonomicStatus": "ACCEPTED",
         "kingdom": "Animalia", "vernacularNames": [{"vernacularName": "Caribou"}]},
        {"key": 5220114, "canonicalName": "Rangifer tarandus", "rank": "SPECIES", "taxonomicStatus": "ACCEPTED",
         "kingdom": "Animalia", "vernacularNames": [{"vernacularName": "Caribou"}, {"vernacularName": "Reindeer"}]},
    ],
    # A vernacular name given to taxa in many genera is ambiguous
    "water mite": [
        {"key": i, "canonicalName": f"Genus{i} species", "rank": "SPECIES", "taxonomicStatus": "ACCEPTED",
         "kingdom": "Animalia", "vernacularNames": [{"vernacularName": "water mite"}]}
        for i in range(5)
    ],
}


@pytest.fixture
def fake_gbif(monkeypatch, tmp_path):
    calls = []

    def fake_get(url, params):
        calls.append((url, dict(params)))
        if url.endswith("/species/match"):
            return MATCH.get(params["name"], {"matchType": "NONE", "confidence": 100})
        if url.endswith("/species/search"):
            return {"results": SEARCH.get(params["q"], [])}
        raise AssertionError(url)

    monkeypatch.setattr(gbif, "_http_get_json", fake_get)
    cache = GBIFCache(tmp_path / "cache.json")
    return cache, calls


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

class TestMentionParsing:
    def test_split_semicolons_and_colon_lists_but_not_inside_parentheses(self):
        assert split_taxon_items("Histeridae; Silphidae") == ["Histeridae", "Silphidae"]
        assert split_taxon_items("16 damselfly species (Coenagrionidae): Enallagma boreale, Ischnura posita") == [
            "16 damselfly species (Coenagrionidae)", "Enallagma boreale", "Ischnura posita",
        ]
        assert split_taxon_items("weevils (Coleoptera: Curculionoidea)") == ["weevils (Coleoptera: Curculionoidea)"]

    def test_unbalanced_parenthesis_from_a_split_annotation(self):
        assert split_taxon_items("Benthic intertidal community (c.20 algae") == ["Benthic intertidal community c.20 algae"]

    def test_count_statements(self):
        m = TaxonMention.model_validate("c.30 bird species")
        assert (m.kind, m.count, m.approximate) == ("count", 30, True)
        assert m.group_texts[0] == "bird species"
        assert TaxonMention.model_validate("herbaceous plant species (203 species inventoried)").count == 203

    def test_authorship_year_is_not_a_count(self):
        assert TaxonMention.model_validate("Tamias striatus (Linnaeus, 1758)").kind == "name"

    def test_noise_hybrid_and_generic_labels(self):
        assert TaxonMention.model_validate("and others").kind == "noise"
        assert TaxonMention.model_validate("hybrids").kind == "hybrid"
        assert TaxonMention.model_validate("shade-tolerant species").generic_label


class TestBroadGroups:
    @pytest.mark.parametrize(
        "classification, expected",
        [
            (("Animalia", "Chordata", "Aves", "Passeriformes"), ("birds",)),
            (("Animalia", "Chordata", None, "Salmoniformes"), ("fish",)),  # no class for ray-finned fish
            (("Animalia", "Chordata", "Testudines", None), ("reptiles",)),
            (("Animalia", "Arthropoda", "Insecta", "Coleoptera"), ("insects",)),
            (("Animalia", "Arthropoda", "Arachnida", "Mesostigmata"), ("other arthropods",)),
            (("Animalia", "Annelida", "Polychaeta", None), ("other invertebrates",)),
            (("Plantae", "Tracheophyta", "Pinopsida", None), ("vascular plants",)),
            (("Plantae", "Bryophyta", None, None), ("bryophytes",)),
            (("Chromista", "Ochrophyta", "Phaeophyceae", None), ("algae",)),
            (("Fungi", "Basidiomycota", None, None), ("fungi and lichens",)),
            (("Animalia", "Arthropoda", None, None), ("insects", "other arthropods")),
        ],
    )
    def test_classification_to_group(self, classification, expected):
        assert broad_groups_for_classification(*classification) == expected


# ---------------------------------------------------------------------------
# resolve_taxon
# ---------------------------------------------------------------------------

class TestResolveTaxon:
    def test_decorated_string_uses_embedded_scientific_name(self, fake_gbif):
        cache, _ = fake_gbif
        record = resolve_taxon("Atlantic salmon (Salmo salar)", cache=cache)
        assert record.kind == "taxon"
        assert record.method == "scientific"
        assert record.key == 7595433
        assert record.family == "Salmonidae"
        assert record.broad_groups == ("fish",)
        assert record.query == "Atlantic salmon (Salmo salar)"

    def test_vernacular_name_prefers_species_over_genus(self, fake_gbif):
        cache, _ = fake_gbif
        record = resolve_taxon("Caribou", cache=cache)
        assert record.method == "vernacular"
        assert record.canonical_name == "Rangifer tarandus"
        assert record.key_at("species") == 5220114

    def test_vernacular_exact_name_only(self, fake_gbif):
        cache, _ = fake_gbif
        # "landlocked Atlantic salmon" is not an exact hit for "Atlantic salmon"
        assert resolve_taxon("Atlantic salmon", cache=cache).canonical_name == "Salmo salar"

    def test_genus_level_name(self, fake_gbif):
        cache, _ = fake_gbif
        record = resolve_taxon("Vaccinium spp", cache=cache)
        assert record.rank == "GENUS"
        assert record.key_at("genus") == 2882813
        assert record.key_at("species") is None

    def test_group_labels(self, fake_gbif):
        cache, _ = fake_gbif
        birds = resolve_taxon("resident bird species", cache=cache)
        assert (birds.kind, birds.key, birds.broad_groups) == ("group", 212, ("birds",))
        benthic = resolve_taxon("benthic communities", cache=cache)
        assert benthic.kind == "group" and benthic.key is None
        assert set(benthic.broad_groups) == {"insects", "other arthropods", "molluscs", "other invertebrates"}

    def test_ambiguous_vernacular_falls_back_to_group(self, fake_gbif):
        cache, _ = fake_gbif
        record = resolve_taxon("water mite", cache=cache)
        assert record.kind == "group"
        assert record.broad_groups == ("other arthropods",)

    def test_homonym_resolved_through_exact_alternative(self, fake_gbif):
        cache, _ = fake_gbif
        record = resolve_taxon("Eteone sp.", cache=cache)
        assert record.key == 2311842
        assert record.broad_groups == ("other invertebrates",)
        assert "homonym" in record.note

    def test_unresolved_keeps_raw_string(self, fake_gbif):
        cache, _ = fake_gbif
        record = resolve_taxon("Crable a epis", cache=cache)
        assert record.kind == "unresolved"
        assert record.query == "Crable a epis"

    def test_responses_are_cached_on_disk(self, fake_gbif):
        cache, calls = fake_gbif
        resolve_taxon("Salmo salar", cache=cache)
        n = len(calls)
        resolve_taxon("Salmo salar", cache=GBIFCache(cache.path))  # fresh object, same file
        assert len(calls) == n
        assert json.loads(cache.path.read_text())


# ---------------------------------------------------------------------------
# Multi-rank evaluation
# ---------------------------------------------------------------------------

def _metrics(ev):
    return {row["rank"]: row for row in ev.metrics_frame().to_dict(orient="records")}


class TestEvaluateTaxaLists:
    def test_wording_differences_match_exactly(self, fake_gbif):
        cache, _ = fake_gbif
        ev = evaluate_taxa_lists({"1": ["Atlantic salmon"]}, {"1": ["Salmo salar"]}, cache=cache)
        m = _metrics(ev)
        assert m["exact"]["precision"] == 1.0 and m["exact"]["recall"] == 1.0
        assert m["string_exact"]["recall"] == 0.0

    def test_subspecies_matches_at_species_rank_only(self, fake_gbif):
        cache, _ = fake_gbif
        ev = evaluate_taxa_lists({"1": ["caribou"]}, {"1": ["Rangifer tarandus caribou"]}, cache=cache)
        m = _metrics(ev)
        assert m["exact"]["recall"] == 0.0
        assert m["species"]["recall"] == 1.0
        # The subspecies sits inside the annotated species: not a false positive at the exact rank
        assert m["exact"]["extracted"] == 0
        item = ev.records[0].pred_items[0]
        assert item.status == "within annotation"
        assert item.reason.endswith("same species")
        assert ev.records[0].true_items[0].status == "partial (species)"

    def test_finer_taxa_inside_a_coarser_annotation_are_not_false_positives(self, fake_gbif):
        cache, _ = fake_gbif
        ev = evaluate_taxa_lists(
            {"1": ["Vaccinium spp"]},
            {"1": ["Vaccinium angustifolium", "Vaccinium myrtilloides"]},
            cache=cache,
        )
        m = _metrics(ev)
        assert m["species"]["extracted"] == 0 and m["species"]["extracted_not_scored"] == 2
        assert m["genus"]["precision"] == 1.0 and m["genus"]["recall"] == 1.0
        assert m["exact"]["recall"] == 0.0  # nobody named the genus itself
        assert {i.status for i in ev.records[0].pred_items} == {"within annotation"}

    def test_count_statement_is_never_a_missed_species(self, fake_gbif):
        cache, _ = fake_gbif
        ev = evaluate_taxa_lists(
            {"1": ["c.30 bird species"]},
            {"1": ["Setophaga ruticilla", "Salmo salar"]},
            cache=cache,
        )
        m = _metrics(ev)
        assert m["exact"]["annotated"] == 0  # the count is not an annotated species
        assert m["exact"]["extracted"] == 1  # the bird is inside the group; the fish is an extra
        assert m["broad_group"]["recall"] == 1.0
        assert m["broad_group"]["precision"] == 0.5
        assert m["group_mentioned"]["recall"] == 1.0
        assert m["count_present"]["recall"] == 0.0
        statuses = {i.mention: i.status for i in ev.records[0].pred_items}
        assert statuses == {"Setophaga ruticilla": "within annotation", "Salmo salar": "extra"}

    def test_count_signal_and_values(self, fake_gbif):
        cache, _ = fake_gbif
        ev = evaluate_taxa_lists({"1": ["73 weevil species"]}, {"1": ["73 species in three families"]}, cache=cache)
        assert ev.count_metrics().recall == 1.0
        assert ev.count_value_agreement() == (1, 1)
        assert ev.records[0].true_items[0].record.label == "weevil"

    def test_group_label_matches_named_taxa_inside_it(self, fake_gbif):
        cache, _ = fake_gbif
        ev = evaluate_taxa_lists({"1": ["Nicrophorus sayi"]}, {"1": ["beetles"]}, cache=cache)
        m = _metrics(ev)
        assert m["group_mentioned"]["precision"] == 1.0
        assert m["exact"]["recall"] == 0.0  # a group label does not name the species
        assert m["broad_group"]["f1"] == 1.0

    def test_duplicate_strings_for_one_taxon_count_once(self, fake_gbif):
        cache, _ = fake_gbif
        ev = evaluate_taxa_lists(
            {"1": ["Salmo salar"]}, {"1": ["Atlantic salmon (Salmo salar)", "Salmo salar", "Atlantic salmon"]},
            cache=cache,
        )
        assert _metrics(ev)["exact"]["extracted"] == 1

    def test_unresolved_names_stay_scored_as_labels(self, fake_gbif):
        cache, _ = fake_gbif
        ev = evaluate_taxa_lists({"1": ["Crable a epis"]}, {"1": ["Crable a epis"]}, cache=cache)
        assert _metrics(ev)["exact"]["recall"] == 1.0
        ev = evaluate_taxa_lists({"1": ["Crable a epis"]}, {"1": []}, cache=cache)
        assert ev.records[0].true_items[0].reason == "name not resolved by GBIF"


class TestEvaluateRunTaxa:
    def test_one_call_on_a_run_artifact(self, fake_gbif, tmp_path):
        cache, _ = fake_gbif
        gt = tmp_path / "gt.json"
        gt.write_text(json.dumps([
            {"gt_record_id": 1, "species": ["Atlantic salmon"]},
            {"gt_record_id": 2, "species": ["c.30 bird species"]},
            {"gt_record_id": 3, "species": ["caribou"]},
        ]))
        run = tmp_path / "run.json"
        run.write_text(json.dumps({
            "name": "test_run", "mode": "abstract", "system_message": "x", "model": "m",
            "records": [
                {"gt_record_id": 1, "record_id": "a", "mode": "abstract", "status": "success",
                 "output": {"species": ["Salmo salar"]}},
                {"gt_record_id": 2, "record_id": "b", "mode": "abstract", "status": "success",
                 "output": {"species": ["Setophaga ruticilla"]}},
                {"gt_record_id": 3, "record_id": "c", "mode": "abstract", "status": "error", "output": None},
            ],
        }))
        ev = evaluate_run_taxa(run, gt_path=gt, cache=cache)
        assert ev.run_name == "test_run"
        m = _metrics(ev)
        assert m["exact"]["annotated"] == 2 and m["exact"]["annotated_matched"] == 1
        items = ev.items_frame()
        assert set(items.columns) >= {"record_id", "side", "mention", "status", "reason"}
        assert ev.resolution_rate("annotation") == (2, 2)  # count statements are not names
        only_one = evaluate_run_taxa(run, gt_path=gt, cache=cache, record_ids=[1])
        assert len(only_one.records) == 1
