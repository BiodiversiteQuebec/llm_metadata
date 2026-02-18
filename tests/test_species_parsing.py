"""
Unit tests for species_parsing module.
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(__file__))
import config  # noqa: F401

from llm_metadata.species_parsing import ParsedTaxon, parse_species_string, looks_scientific


class TestLooksScientific(unittest.TestCase):

    def test_binomial_scientific(self):
        self.assertTrue(looks_scientific("Tamias striatus"))

    def test_trinomial_scientific(self):
        self.assertTrue(looks_scientific("Rangifer tarandus caribou"))

    def test_single_word_not_scientific(self):
        self.assertFalse(looks_scientific("caribou"))

    def test_all_lowercase_not_scientific(self):
        self.assertFalse(looks_scientific("wood turtle"))

    def test_empty_not_scientific(self):
        self.assertFalse(looks_scientific(""))

    def test_one_word_capitalized_not_scientific(self):
        self.assertFalse(looks_scientific("Mammalia"))


class TestParseSpeciesString(unittest.TestCase):

    def test_scientific_binomial(self):
        result = parse_species_string("Tamias striatus")
        self.assertEqual(result["scientific"], "Tamias striatus")
        self.assertIsNone(result["vernacular"])
        self.assertIsNone(result["count"])
        self.assertFalse(result["is_group_description"])

    def test_vernacular_single_word(self):
        result = parse_species_string("caribou")
        self.assertIsNone(result["scientific"])
        self.assertEqual(result["vernacular"], "caribou")
        self.assertFalse(result["is_group_description"])

    def test_vernacular_multi_word(self):
        result = parse_species_string("ground-dwelling beetles")
        self.assertIsNone(result["scientific"])
        self.assertIsNotNone(result["vernacular"])

    def test_parenthetical_vernacular_first(self):
        result = parse_species_string("wood turtle (Glyptemys insculpta)")
        self.assertEqual(result["scientific"], "Glyptemys insculpta")
        self.assertEqual(result["vernacular"], "wood turtle")

    def test_parenthetical_scientific_first(self):
        result = parse_species_string("Glyptemys insculpta (wood turtle)")
        self.assertEqual(result["scientific"], "Glyptemys insculpta")
        self.assertEqual(result["vernacular"], "wood turtle")

    def test_count_and_group(self):
        result = parse_species_string("41 fish mock species")
        self.assertEqual(result["count"], 41)
        self.assertTrue(result["is_group_description"])

    def test_count_without_group_term(self):
        result = parse_species_string("3 Tamias striatus")
        self.assertEqual(result["count"], 3)
        self.assertTrue(result["is_group_description"])  # count present → group

    def test_original_preserved(self):
        raw = "Ursus americanus"
        result = parse_species_string(raw)
        self.assertEqual(result["original"], raw)

    def test_empty_string(self):
        result = parse_species_string("")
        self.assertEqual(result["original"], "")
        self.assertIsNone(result["scientific"])
        self.assertIsNone(result["vernacular"])
        self.assertFalse(result["is_group_description"])

    def test_none_input(self):
        result = parse_species_string(None)
        self.assertIsNone(result["scientific"])
        self.assertIsNone(result["vernacular"])

    def test_strips_species_suffix(self):
        result = parse_species_string("41 bird species")
        self.assertEqual(result["count"], 41)
        self.assertTrue(result["is_group_description"])

    def test_group_term_is_group(self):
        result = parse_species_string("beetles")
        self.assertTrue(result["is_group_description"])


class TestParsedTaxon(unittest.TestCase):

    def test_construct_from_string_scientific(self):
        pt = ParsedTaxon.model_validate("Tamias striatus")
        self.assertEqual(pt.original, "Tamias striatus")
        self.assertEqual(pt.scientific, "Tamias striatus")
        self.assertIsNone(pt.vernacular)
        self.assertFalse(pt.is_group_description)

    def test_construct_from_string_vernacular(self):
        pt = ParsedTaxon.model_validate("caribou")
        self.assertIsNone(pt.scientific)
        self.assertEqual(pt.vernacular, "caribou")

    def test_construct_from_string_parenthetical(self):
        pt = ParsedTaxon.model_validate("wood turtle (Glyptemys insculpta)")
        self.assertEqual(pt.scientific, "Glyptemys insculpta")
        self.assertEqual(pt.vernacular, "wood turtle")

    def test_construct_from_string_count_group(self):
        pt = ParsedTaxon.model_validate("41 fish mock species")
        self.assertEqual(pt.count, 41)
        self.assertTrue(pt.is_group_description)

    def test_construct_from_dict(self):
        pt = ParsedTaxon(
            original="Ursus americanus",
            scientific="Ursus americanus",
            vernacular=None,
            count=None,
            is_group_description=False,
        )
        self.assertEqual(pt.scientific, "Ursus americanus")

    def test_empty_string(self):
        pt = ParsedTaxon.model_validate("")
        self.assertEqual(pt.original, "")
        self.assertIsNone(pt.scientific)
        self.assertIsNone(pt.vernacular)

    def test_scientific_reversed_parenthetical(self):
        pt = ParsedTaxon.model_validate("Glyptemys insculpta (wood turtle)")
        self.assertEqual(pt.scientific, "Glyptemys insculpta")
        self.assertEqual(pt.vernacular, "wood turtle")


if __name__ == "__main__":
    unittest.main()
