# External Sources Refactor Plan

> **Created:** 2026-02-03
> **Context:** Insights from debugging Sci-Hub integration failures
> **Status:** Proposed

## Summary

The PDF download pipeline has grown organically with multiple external source integrations (OpenAlex, Unpaywall, EZproxy, Sci-Hub). This document captures architectural weaknesses identified during a debugging session and areas for improvement.

---

## Problems Identified

### 1. Fragile External Service Integrations

Sci-Hub changed its page structure from `<iframe>` to `<object>` tags, silently breaking downloads. The integration bug (passing bytes as URL) went unnoticed.

**Issues:**
- Single-pattern matching with no fallbacks
- No integration tests that verify actual service behavior
- Silent failures that don't surface until manual investigation

**Improvement:** Parsers should handle multiple page structures and have tests that catch regressions.

---

### 2. Inconsistent Interfaces Across Sources

Each source module has different return conventions:
- `scihub.py` returns `{'pdf': bytes, 'err': str}`
- `unpaywall.py` returns model or `None`
- `openalex.py` returns dict or `None`

**Issues:**
- Every integration point needs custom error handling
- Easy to introduce bugs when assumptions differ (e.g., bytes vs URL)

**Improvement:** Standardize the interface so all sources return the same structure.

---

### 3. No Structured Failure Tracking

`failed_downloads.log` is append-only with many duplicates. Same DOIs fail repeatedly across runs.

**Issues:**
- Wasted API calls retrying known failures
- No analytics on failure patterns
- Can't answer "which publishers have worst success rate?"

**Improvement:** Track attempts with enough metadata to avoid redundant retries and enable analytics.

---

### 4. Hardcoded Configuration

Configuration is scattered across multiple files:
- Preferred Sci-Hub mirrors in `scihub.py`
- Publisher URL patterns in `pdf_download.py`
- EZproxy domain in `ezproxy.py`
- Timeouts and size thresholds in `pdf_download.py`

**Issues:**
- Updating configuration requires code changes
- Hard to see all settings in one place

**Improvement:** Centralize configuration in dedicated config files.

---

### 5. Missing Documentation in CLAUDE.md

**Gaps identified:**
- No mention of fallback chain order (OpenAlex → Unpaywall → EZproxy → Sci-Hub)
- No debug commands for download failures
- No explanation of which DOI prefixes map to which publishers
- No guidance on known limitations (preprints, books not in Sci-Hub)

**Improvement:** Add a "PDF Download Pipeline" section to CLAUDE.md with:
- Fallback chain explanation
- Debug commands
- Known limitations by DOI prefix

---

### 6. Third-Party Code Integration

`scihub.py` is a forked library with different conventions than the rest of the codebase (returns dict with 'err' key instead of raising exceptions).

**Issues:**
- Inconsistent with project patterns
- Error handling logic leaks into callers

**Improvement:** Either adapt the library to project conventions or wrap it in an adapter layer.

---

### 7. Test Coverage Gaps

Before this session, `scihub.py` had no tests. The existing `test_pdf_download.py` doesn't test the fallback chain integration.

**Issues:**
- Regressions go unnoticed
- Integration bugs (like the bytes-as-URL bug) slip through

**Improvement:** Add tests for:
- Each source's parsing logic (unit tests with mocked responses)
- The fallback chain behavior (integration tests)
- Error handling paths

---

## CLAUDE.md Additions Needed

Add a section covering:

1. **Fallback chain order** and what each source is best for
2. **Debug commands** for investigating download failures
3. **Known limitations** by DOI prefix:
   - Authorea preprints (`10.22541/*`) - not in Sci-Hub
   - Cambridge books (`10.1017/*`) - not in Sci-Hub
   - Zenodo datasets (`10.5281/zenodo.*`) - skip entirely
4. **How to update Sci-Hub mirrors** when they rotate or get blocked

---

## Success Criteria

| Area | Current State | Desired State |
|------|---------------|---------------|
| Download success rate | 95.7% | 98%+ |
| Time to debug failures | ~30 min | < 5 min |
| Test coverage (sources) | ~20% | 80%+ |
| Config changes requiring code | All | Minimal |
| Duplicate retry attempts | Many | None |

---

## Open Questions

1. Should Sci-Hub be disabled by default, requiring explicit opt-in?
2. How long should we wait before retrying a failed source for a given DOI?
3. Should we track which strategy succeeded for each DOI to inform future attempts?
4. Would parallel/async downloads significantly improve batch performance?
