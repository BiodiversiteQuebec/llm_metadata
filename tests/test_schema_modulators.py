"""Tests for modulator fields and boolean coercion in feature schemas."""

import pytest

from llm_metadata.schemas.fuster_features import (
    DatasetFeatures,
    DatasetFeaturesNormalized,
    DataSource,
)


class TestDataSourceEnum:
    """Test DataSource enum values and usage."""

    def test_enum_values(self):
        assert DataSource.DRYAD == "dryad"
        assert DataSource.ZENODO == "zenodo"
        assert DataSource.SEMANTIC_SCHOLAR == "semantic_scholar"
        assert DataSource.REFERENCED == "referenced"


class TestModulatorFieldsBase:
    """Test modulator boolean fields on the base DatasetFeatures model."""

    MODULATOR_FIELDS = [
        "time_series", "multispecies", "threatened_species",
        "new_species_science", "new_species_region", "bias_north_south",
    ]

    def test_all_none_by_default(self):
        m = DatasetFeatures()
        for field in self.MODULATOR_FIELDS:
            assert getattr(m, field) is None, f"{field} should default to None"

    def test_set_true(self):
        m = DatasetFeatures(**{f: True for f in self.MODULATOR_FIELDS})
        for field in self.MODULATOR_FIELDS:
            assert getattr(m, field) is True, f"{field} should be True"

    def test_set_false(self):
        m = DatasetFeatures(**{f: False for f in self.MODULATOR_FIELDS})
        for field in self.MODULATOR_FIELDS:
            assert getattr(m, field) is False, f"{field} should be False"

    def test_mixed_values(self):
        m = DatasetFeatures(
            time_series=True,
            multispecies=False,
            threatened_species=None,
        )
        assert m.time_series is True
        assert m.multispecies is False
        assert m.threatened_species is None

    def test_serialization_roundtrip(self):
        m = DatasetFeatures(
            time_series=True,
            multispecies=False,
        )
        d = m.model_dump()
        assert d["time_series"] is True
        assert d["multispecies"] is False

        m2 = DatasetFeatures.model_validate(d)
        assert m2.time_series is True
        assert m2.multispecies is False


class TestBooleanCoercionValidator:
    """Test boolean coercion in DatasetFeaturesNormalized for ground truth data."""

    def test_string_yes_no(self):
        """time_series in ground truth uses 'yes'/'no' strings."""
        m = DatasetFeaturesNormalized(time_series="yes", multispecies="no")
        assert m.time_series is True
        assert m.multispecies is False

    def test_string_true_false(self):
        m = DatasetFeaturesNormalized(time_series="true", multispecies="false")
        assert m.time_series is True
        assert m.multispecies is False

    def test_string_1_0(self):
        m = DatasetFeaturesNormalized(time_series="1", multispecies="0")
        assert m.time_series is True
        assert m.multispecies is False

    def test_bool_passthrough(self):
        m = DatasetFeaturesNormalized(time_series=True, multispecies=False)
        assert m.time_series is True
        assert m.multispecies is False

    def test_int_coercion(self):
        m = DatasetFeaturesNormalized(time_series=1, multispecies=0)
        assert m.time_series is True
        assert m.multispecies is False

    def test_nan_to_none(self):
        m = DatasetFeaturesNormalized(time_series=float("nan"))
        assert m.time_series is None

    def test_empty_string_to_none(self):
        m = DatasetFeaturesNormalized(time_series="")
        assert m.time_series is None

    def test_na_strings_to_none(self):
        for val in ("na", "N/A", "NaN", "none", "NA"):
            m = DatasetFeaturesNormalized(time_series=val)
            assert m.time_series is None, f"'{val}' should coerce to None"

    def test_none_passthrough(self):
        m = DatasetFeaturesNormalized(time_series=None)
        assert m.time_series is None

    def test_case_insensitive(self):
        m = DatasetFeaturesNormalized(time_series="YES", multispecies="No")
        assert m.time_series is True
        assert m.multispecies is False

    def test_whitespace_handling(self):
        m = DatasetFeaturesNormalized(time_series="  yes  ", multispecies="  no  ")
        assert m.time_series is True
        assert m.multispecies is False

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
        assert m.time_series is True
        assert m.multispecies is False
        assert m.threatened_species is True
        assert m.new_species_science is False
        assert m.new_species_region is True
        assert m.bias_north_south is False


class TestNormalizedModelWithModulators:
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
            time_series="yes",
            multispecies=True,
            threatened_species=False,
            new_species_science=False,
            new_species_region=False,
            bias_north_south=False,
        )
        # Existing field normalization
        assert "abundance" in m.data_type
        assert "presence-absence" in m.data_type
        assert "site" in m.geospatial_info_dataset
        assert abs(m.spatial_range_km2 - 1000.5) < 1e-7
        assert m.temp_range_i == 2005
        assert m.temp_range_f == 2015
        assert len(m.species) == 2

        # Modulator fields
        assert m.time_series is True
        assert m.multispecies is True
        assert m.threatened_species is False

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
        )
        assert "abundance" in m.data_type
        assert m.time_series is None
        assert m.multispecies is None
        assert m.threatened_species is None
        assert m.new_species_science is None
        assert m.new_species_region is None
        assert m.bias_north_south is None
