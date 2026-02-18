"""Tests for modulator fields, DataSource enum, and boolean coercion in fuster_features schema."""

import math
import unittest

from llm_metadata.schemas.fuster_features import (
    DatasetFeatures,
    DatasetFeaturesNormalized,
    DataSource,
)


class TestDataSourceEnum(unittest.TestCase):
    """Test DataSource enum values and usage."""

    def test_enum_values(self):
        self.assertEqual(DataSource.DRYAD, "dryad")
        self.assertEqual(DataSource.ZENODO, "zenodo")
        self.assertEqual(DataSource.SEMANTIC_SCHOLAR, "semantic_scholar")
        self.assertEqual(DataSource.REFERENCED, "referenced")

    def test_source_field_on_base_model(self):
        m = DatasetFeatures(source="dryad")
        self.assertEqual(m.source, "dryad")

    def test_source_field_none_default(self):
        m = DatasetFeatures()
        self.assertIsNone(m.source)

    def test_source_field_all_values(self):
        for val in ("dryad", "zenodo", "semantic_scholar", "referenced"):
            m = DatasetFeatures(source=val)
            self.assertEqual(m.source, val)


class TestModulatorFieldsBase(unittest.TestCase):
    """Test modulator boolean fields on the base DatasetFeatures model."""

    MODULATOR_FIELDS = [
        "time_series", "multispecies", "threatened_species",
        "new_species_science", "new_species_region", "bias_north_south",
    ]

    def test_all_none_by_default(self):
        m = DatasetFeatures()
        for field in self.MODULATOR_FIELDS:
            self.assertIsNone(getattr(m, field), f"{field} should default to None")

    def test_set_true(self):
        m = DatasetFeatures(**{f: True for f in self.MODULATOR_FIELDS})
        for field in self.MODULATOR_FIELDS:
            self.assertTrue(getattr(m, field), f"{field} should be True")

    def test_set_false(self):
        m = DatasetFeatures(**{f: False for f in self.MODULATOR_FIELDS})
        for field in self.MODULATOR_FIELDS:
            self.assertFalse(getattr(m, field), f"{field} should be False")

    def test_mixed_values(self):
        m = DatasetFeatures(
            time_series=True,
            multispecies=False,
            threatened_species=None,
        )
        self.assertTrue(m.time_series)
        self.assertFalse(m.multispecies)
        self.assertIsNone(m.threatened_species)

    def test_serialization_roundtrip(self):
        m = DatasetFeatures(
            time_series=True,
            multispecies=False,
            source="zenodo",
        )
        d = m.model_dump()
        self.assertTrue(d["time_series"])
        self.assertFalse(d["multispecies"])
        self.assertEqual(d["source"], "zenodo")

        m2 = DatasetFeatures.model_validate(d)
        self.assertTrue(m2.time_series)
        self.assertFalse(m2.multispecies)
        self.assertEqual(m2.source, "zenodo")


class TestBooleanCoercionValidator(unittest.TestCase):
    """Test boolean coercion in DatasetFeaturesNormalized for ground truth data."""

    def test_string_yes_no(self):
        """time_series in ground truth uses 'yes'/'no' strings."""
        m = DatasetFeaturesNormalized(time_series="yes", multispecies="no")
        self.assertTrue(m.time_series)
        self.assertFalse(m.multispecies)

    def test_string_true_false(self):
        m = DatasetFeaturesNormalized(time_series="true", multispecies="false")
        self.assertTrue(m.time_series)
        self.assertFalse(m.multispecies)

    def test_string_1_0(self):
        m = DatasetFeaturesNormalized(time_series="1", multispecies="0")
        self.assertTrue(m.time_series)
        self.assertFalse(m.multispecies)

    def test_bool_passthrough(self):
        m = DatasetFeaturesNormalized(time_series=True, multispecies=False)
        self.assertTrue(m.time_series)
        self.assertFalse(m.multispecies)

    def test_int_coercion(self):
        m = DatasetFeaturesNormalized(time_series=1, multispecies=0)
        self.assertTrue(m.time_series)
        self.assertFalse(m.multispecies)

    def test_nan_to_none(self):
        m = DatasetFeaturesNormalized(time_series=float("nan"))
        self.assertIsNone(m.time_series)

    def test_empty_string_to_none(self):
        m = DatasetFeaturesNormalized(time_series="")
        self.assertIsNone(m.time_series)

    def test_na_strings_to_none(self):
        for val in ("na", "N/A", "NaN", "none", "NA"):
            m = DatasetFeaturesNormalized(time_series=val)
            self.assertIsNone(m.time_series, f"'{val}' should coerce to None")

    def test_none_passthrough(self):
        m = DatasetFeaturesNormalized(time_series=None)
        self.assertIsNone(m.time_series)

    def test_case_insensitive(self):
        m = DatasetFeaturesNormalized(time_series="YES", multispecies="No")
        self.assertTrue(m.time_series)
        self.assertFalse(m.multispecies)

    def test_whitespace_handling(self):
        m = DatasetFeaturesNormalized(time_series="  yes  ", multispecies="  no  ")
        self.assertTrue(m.time_series)
        self.assertFalse(m.multispecies)

    def test_all_modulator_fields_coerce(self):
        """All 6 modulator fields should go through the boolean coercion validator."""
        m = DatasetFeaturesNormalized(
            time_series="yes",
            multispecies="no",
            threatened_species="true",
            new_species_science="false",
            new_species_region="1",
            bias_north_south="0",
        )
        self.assertTrue(m.time_series)
        self.assertFalse(m.multispecies)
        self.assertTrue(m.threatened_species)
        self.assertFalse(m.new_species_science)
        self.assertTrue(m.new_species_region)
        self.assertFalse(m.bias_north_south)


class TestSourceCoercionValidator(unittest.TestCase):
    """Test source field coercion in DatasetFeaturesNormalized."""

    def test_string_values(self):
        for val in ("dryad", "zenodo", "semantic_scholar", "referenced"):
            m = DatasetFeaturesNormalized(source=val)
            self.assertEqual(m.source, val)

    def test_case_normalization(self):
        m = DatasetFeaturesNormalized(source="Dryad")
        self.assertEqual(m.source, "dryad")

    def test_nan_to_none(self):
        m = DatasetFeaturesNormalized(source=float("nan"))
        self.assertIsNone(m.source)

    def test_empty_string_to_none(self):
        m = DatasetFeaturesNormalized(source="")
        self.assertIsNone(m.source)

    def test_none_passthrough(self):
        m = DatasetFeaturesNormalized(source=None)
        self.assertIsNone(m.source)


class TestNormalizedModelWithModulators(unittest.TestCase):
    """Integration tests: full DatasetFeaturesNormalized with modulator fields and existing fields."""

    def test_full_ground_truth_record(self):
        """Simulate a complete ground truth record from the xlsx."""
        m = DatasetFeaturesNormalized(
            data_type="abundance, presence-absence",
            geospatial_info_dataset="site coordinates",
            spatial_range_km2="1000,5",
            temporal_range="from 2005 to 2015",
            temp_range_i=2005.0,
            temp_range_f=2015.0,
            species="Tamias striatus, Ursus americanus",
            valid_yn="yes",
            source="dryad",
            time_series="yes",
            multispecies=True,
            threatened_species=False,
            new_species_science=False,
            new_species_region=False,
            bias_north_south=False,
        )
        # Existing field normalization
        self.assertIn("abundance", m.data_type)
        self.assertIn("presence-absence", m.data_type)
        self.assertIn("site", m.geospatial_info_dataset)
        self.assertAlmostEqual(m.spatial_range_km2, 1000.5)
        self.assertEqual(m.temp_range_i, 2005)
        self.assertEqual(m.temp_range_f, 2015)
        self.assertEqual(len(m.species), 2)

        # Modulator fields
        self.assertTrue(m.time_series)
        self.assertTrue(m.multispecies)
        self.assertFalse(m.threatened_species)
        self.assertEqual(m.source, "dryad")

    def test_record_with_all_nan_modulators(self):
        """Simulate a record where all modulator fields are NaN (common in xlsx)."""
        m = DatasetFeaturesNormalized(
            data_type="abundance",
            time_series=float("nan"),
            multispecies=float("nan"),
            threatened_species=float("nan"),
            new_species_science=float("nan"),
            new_species_region=float("nan"),
            bias_north_south=float("nan"),
            source=float("nan"),
        )
        self.assertIn("abundance", m.data_type)
        self.assertIsNone(m.time_series)
        self.assertIsNone(m.multispecies)
        self.assertIsNone(m.threatened_species)
        self.assertIsNone(m.new_species_science)
        self.assertIsNone(m.new_species_region)
        self.assertIsNone(m.bias_north_south)
        self.assertIsNone(m.source)


if __name__ == "__main__":
    unittest.main()
