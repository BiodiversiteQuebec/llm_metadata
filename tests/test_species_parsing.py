"""
Unit tests for species_parsing module.
"""

from llm_metadata.species_parsing import (
    ParsedTaxon,
    TaxonRichnessMention,
    extract_taxon_richness_mentions,
    looks_scientific,
    normalize_taxon_group,
    parse_species_string,
    parse_taxon_richness,
    project_taxon_richness_counts,
    project_taxon_richness_group_keys,
)


class TestLooksScientific:

    def test_binomial_scientific(self):
        assert looks_scientific("Tamias striatus")

    def test_trinomial_scientific(self):
        assert looks_scientific("Rangifer tarandus caribou")

    def test_single_word_not_scientific(self):
        assert not looks_scientific("caribou")

    def test_all_lowercase_not_scientific(self):
        assert not looks_scientific("wood turtle")

    def test_empty_not_scientific(self):
        assert not looks_scientific("")

    def test_one_word_capitalized_not_scientific(self):
        assert not looks_scientific("Mammalia")


class TestParseSpeciesString:

    def test_scientific_binomial(self):
        result = parse_species_string("Tamias striatus")
        assert result["scientific"] == "Tamias striatus"
        assert result["vernacular"] is None
        assert result["count"] is None
        assert not result["is_group_description"]

    def test_vernacular_single_word(self):
        result = parse_species_string("caribou")
        assert result["scientific"] is None
        assert result["vernacular"] == "caribou"
        assert not result["is_group_description"]

    def test_vernacular_multi_word(self):
        result = parse_species_string("ground-dwelling beetles")
        assert result["scientific"] is None
        assert result["vernacular"] is not None

    def test_parenthetical_vernacular_first(self):
        result = parse_species_string("wood turtle (Glyptemys insculpta)")
        assert result["scientific"] == "Glyptemys insculpta"
        assert result["vernacular"] == "wood turtle"

    def test_parenthetical_scientific_first(self):
        result = parse_species_string("Glyptemys insculpta (wood turtle)")
        assert result["scientific"] == "Glyptemys insculpta"
        assert result["vernacular"] == "wood turtle"

    def test_count_and_group(self):
        result = parse_species_string("41 fish mock species")
        assert result["count"] == 41
        assert result["is_group_description"]

    def test_count_without_group_term(self):
        result = parse_species_string("3 Tamias striatus")
        assert result["count"] == 3
        assert result["is_group_description"]  # count present → group

    def test_original_preserved(self):
        raw = "Ursus americanus"
        result = parse_species_string(raw)
        assert result["original"] == raw

    def test_empty_string(self):
        result = parse_species_string("")
        assert result["original"] == ""
        assert result["scientific"] is None
        assert result["vernacular"] is None
        assert not result["is_group_description"]

    def test_none_input(self):
        result = parse_species_string(None)
        assert result["scientific"] is None
        assert result["vernacular"] is None

    def test_strips_species_suffix(self):
        result = parse_species_string("41 bird species")
        assert result["count"] == 41
        assert result["is_group_description"]

    def test_group_term_is_group(self):
        result = parse_species_string("beetles")
        assert result["is_group_description"]


class TestParsedTaxon:

    def test_construct_from_string_scientific(self):
        pt = ParsedTaxon.model_validate("Tamias striatus")
        assert pt.original == "Tamias striatus"
        assert pt.scientific == "Tamias striatus"
        assert pt.vernacular is None
        assert not pt.is_group_description

    def test_construct_from_string_vernacular(self):
        pt = ParsedTaxon.model_validate("caribou")
        assert pt.scientific is None
        assert pt.vernacular == "caribou"

    def test_construct_from_string_parenthetical(self):
        pt = ParsedTaxon.model_validate("wood turtle (Glyptemys insculpta)")
        assert pt.scientific == "Glyptemys insculpta"
        assert pt.vernacular == "wood turtle"

    def test_construct_from_string_count_group(self):
        pt = ParsedTaxon.model_validate("41 fish mock species")
        assert pt.count == 41
        assert pt.is_group_description

    def test_construct_from_dict(self):
        pt = ParsedTaxon(
            original="Ursus americanus",
            scientific="Ursus americanus",
            vernacular=None,
            count=None,
            is_group_description=False,
        )
        assert pt.scientific == "Ursus americanus"

    def test_empty_string(self):
        pt = ParsedTaxon.model_validate("")
        assert pt.original == ""
        assert pt.scientific is None
        assert pt.vernacular is None

    def test_scientific_reversed_parenthetical(self):
        pt = ParsedTaxon.model_validate("Glyptemys insculpta (wood turtle)")
        assert pt.scientific == "Glyptemys insculpta"
        assert pt.vernacular == "wood turtle"


class TestNormalizeTaxonGroup:

    def test_strips_species_suffix(self):
        assert normalize_taxon_group("weevil species") == "weevil"

    def test_strips_species_of_prefix(self):
        assert normalize_taxon_group("species of benthic community") == "benthic community"

    def test_singularizes_plural_group(self):
        assert normalize_taxon_group("ground-dwelling beetles") == "ground-dwelling beetle"


class TestParseTaxonRichness:

    def test_simple_group_count(self):
        result = parse_taxon_richness("73 weevil species")
        assert result["count"] == 73
        assert result["normalized_group"] == "weevil"
        assert not result["approximate"]

    def test_approximate_group_count(self):
        result = parse_taxon_richness("c.132 species of benthic community")
        assert result["count"] == 132
        assert result["normalized_group"] == "benthic community"
        assert result["approximate"]

    def test_non_count_string_returns_none_fields(self):
        result = parse_taxon_richness("Tamias striatus")
        assert result["count"] is None
        assert result["normalized_group"] is None


class TestTaxonRichnessMention:

    def test_construct_from_string(self):
        mention = TaxonRichnessMention.model_validate("16 damselfly species")
        assert mention.count == 16
        assert mention.normalized_group == "damselfly"
        assert mention.comparison_key == "16|damselfly"


class TestTaxonRichnessProjection:

    def test_extract_count_bearing_mentions(self):
        mentions = extract_taxon_richness_mentions(
            ["73 weevil species", "Tamias striatus", "240 flying-beetles species"]
        )
        assert mentions is not None
        assert [mention.count for mention in mentions] == [73, 240]

    def test_project_counts_prefers_explicit_counts(self):
        counts = project_taxon_richness_counts(
            ["73 weevil species", "240 flying-beetles species"]
        )
        assert counts == [73, 240]

    def test_project_counts_falls_back_to_species_list_length(self):
        counts = project_taxon_richness_counts(
            ["Tamias striatus", "Rangifer tarandus", "Glyptemys insculpta"]
        )
        assert counts == [3]

    def test_project_group_keys(self):
        mentions = extract_taxon_richness_mentions(
            ["73 weevil species", "240 flying-beetles species"]
        )
        keys = project_taxon_richness_group_keys(mentions)
        assert keys == ["240|flying-beetle", "73|weevil"]
