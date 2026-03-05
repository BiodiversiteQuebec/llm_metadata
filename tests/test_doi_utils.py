"""Tests for llm_metadata.doi_utils."""

import pytest
from llm_metadata.doi_utils import (
    strip_doi_prefix,
    normalize_doi,
    doi_equal,
    doi_filename_stem,
    doi_candidate_variants,
    extract_doi_from_url,
)


class TestStripDoiPrefix:
    def test_https_prefix(self):
        assert strip_doi_prefix("https://doi.org/10.1371/journal.pone.0128238") == "10.1371/journal.pone.0128238"

    def test_http_prefix(self):
        assert strip_doi_prefix("http://doi.org/10.1371/test") == "10.1371/test"

    def test_doi_colon_prefix(self):
        assert strip_doi_prefix("doi:10.1371/test") == "10.1371/test"

    def test_bare_doi(self):
        assert strip_doi_prefix("10.1371/test") == "10.1371/test"

    def test_whitespace_stripped(self):
        assert strip_doi_prefix("  https://doi.org/10.1371/test  ") == "10.1371/test"

    def test_empty_string(self):
        assert strip_doi_prefix("") == ""


class TestNormalizeDoi:
    def test_lowercases(self):
        assert normalize_doi("10.1371/JOURNAL.PONE.0128238") == "10.1371/journal.pone.0128238"

    def test_strips_prefix_and_lowercases(self):
        assert normalize_doi("https://doi.org/10.1371/Test") == "10.1371/test"

    def test_empty(self):
        assert normalize_doi("") == ""


class TestDoiEqual:
    def test_equal_bare(self):
        assert doi_equal("10.1371/test", "10.1371/test")

    def test_equal_mixed_prefix(self):
        assert doi_equal("https://doi.org/10.1371/test", "10.1371/test")

    def test_equal_case_insensitive(self):
        assert doi_equal("10.1371/TEST", "10.1371/test")

    def test_not_equal(self):
        assert not doi_equal("10.1371/test", "10.1002/other")

    def test_none_never_equal(self):
        assert not doi_equal(None, "10.1371/test")
        assert not doi_equal("10.1371/test", None)
        assert not doi_equal(None, None)


class TestDoiFilenameStem:
    def test_slash_replaced(self):
        assert doi_filename_stem("10.1371/journal.pone.0128238") == "10.1371_journal.pone.0128238"

    def test_strips_prefix(self):
        assert doi_filename_stem("https://doi.org/10.1371/test") == "10.1371_test"

    def test_no_slash(self):
        assert doi_filename_stem("10.12345/simple") == "10.12345_simple"


class TestDoiCandidateVariants:
    def test_includes_bare_and_url(self):
        variants = doi_candidate_variants("10.1371/test")
        assert "10.1371/test" in variants
        assert "https://doi.org/10.1371/test" in variants

    def test_no_duplicates(self):
        variants = doi_candidate_variants("10.1371/test")
        assert len(variants) == len(set(variants))

    def test_empty_returns_empty(self):
        assert doi_candidate_variants("") == []


class TestExtractDoiFromUrl:
    def test_full_url(self):
        result = extract_doi_from_url("https://doi.org/10.1371/journal.pone.0128238")
        assert result == "10.1371/journal.pone.0128238"

    def test_bare_doi(self):
        assert extract_doi_from_url("10.1371/test") == "10.1371/test"

    def test_non_doi_url(self):
        assert extract_doi_from_url("https://example.com/paper") is None

    def test_none(self):
        assert extract_doi_from_url(None) is None

    def test_empty(self):
        assert extract_doi_from_url("") is None
