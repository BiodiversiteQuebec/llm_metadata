# Plan: Populate source_url, journal_url, pdf_url, is_oa, cited_article_doi

> **Status:** Ready for implementation
> **Created:** 2026-02-17
> **Model:** `sonnet`
> **Deps:** WU-A1 (done), WU-A2 (done)
> **Blocks:** WU-B, WU-C1

## Context

WU-A1 added 5 metadata fields to `DatasetFeatures` (`source_url`, `journal_url`, `pdf_url`, `is_oa`, `cited_article_doi`) but they are always None in the validated xlsx because:
1. The raw xlsx uses different column names (`url`, `cited_articles`) — no mapping to schema field names
2. No enrichment step queries OpenAlex for `journal_url`, `pdf_url`, `is_oa`

This plan populates all 5 fields so the validated xlsx is a complete record for downstream consumers (WU-B extraction, WU-C1 PDF download).

## Data Flow

```
xlsx columns           Schema fields           Source
────────────           ─────────────           ──────
url              →     source_url              Column rename before validation
cited_articles   →     cited_article_doi       Column rename (Dryad/Zenodo); url DOI extraction (SS)
(none)           →     journal_url             OpenAlex best_oa_location.landing_page_url
(none)           →     pdf_url                 OpenAlex best_oa_location.pdf_url (+ SS fallback)
(none)           →     is_oa                   OpenAlex open_access.is_oa
```

Key: For Dryad/Zenodo, `cited_article_doi` comes from xlsx `cited_articles` or `article_retrieval.py` API fallback, then OpenAlex is queried with that DOI. For SS, `url` IS the article DOI directly — no retrieval step needed.

## Steps

### Step 1: Add `enrich_article_metadata()` to `article_retrieval.py`

**File:** `src/llm_metadata/article_retrieval.py`

Add one function (~20 lines). Reuses existing cached functions:
- `openalex.get_work_by_doi()` → `is_oa`, `journal_url`, `pdf_url`
- `semantic_scholar.get_open_access_pdf_url()` → `pdf_url` fallback

```python
def enrich_article_metadata(article_doi: str) -> Dict[str, Optional[str | bool]]:
    """Query OpenAlex (+ SS fallback) for journal_url, pdf_url, is_oa."""
```

### Step 2: Column rename in notebook BEFORE validation

**File:** `notebooks/fuster_annotations_validation.ipynb`

New cell between data loading and validation:
```python
COLUMN_RENAME = {'url': 'source_url', 'cited_articles': 'cited_article_doi'}
raw_df = raw_df.rename(columns=COLUMN_RENAME)
# Drop url.1 (confirmed identical to url for all SS records)
```

Ensures `DataFrameValidator` populates `source_url` and `cited_article_doi` during validation.

### Step 3: Fill `cited_article_doi` for SS records AFTER validation

**File:** `notebooks/fuster_annotations_validation.ipynb`

New cell after filtering to valid records. For SS records, `cited_articles` was empty but `url` IS the article DOI:
```python
ss_mask = (df['source'] == 'semantic_scholar') & df['cited_article_doi'].isna()
df.loc[ss_mask, 'cited_article_doi'] = df.loc[ss_mask, 'source_url'].apply(extract_doi_from_url)
```

For Dryad/Zenodo with missing DOIs, use existing `retrieve_article_doi()` API fallback.

### Step 4: Enrich `journal_url`, `pdf_url`, `is_oa` via OpenAlex

**File:** `notebooks/fuster_annotations_validation.ipynb`

New cell. Loop records with `cited_article_doi`, call `enrich_article_metadata()`, populate fields. Print coverage stats per source.

### Step 5: Update `dataset_article_mapping.csv`

**File:** `notebooks/fuster_annotations_validation.ipynb`

Add `journal_url`, `pdf_url`, `is_oa` columns to existing CSV. Original 6 columns unchanged — additive only. Download notebooks won't break.

### Step 6: Export validated xlsx (update existing cell)

Add coverage summary for 5 new fields.

## Files Modified

| File | Change |
|---|---|
| `src/llm_metadata/article_retrieval.py` | Add `enrich_article_metadata()` (~20 lines) + 2 imports |
| `notebooks/fuster_annotations_validation.ipynb` | 4 new cells + update export cell |

No schema changes — fields already exist in `DatasetFeatures`.

## Design Decisions

- **Column rename before validation** — Pydantic sees correct field names, populates models properly
- **Enrichment after validation** — follows CLAUDE.md enrichment pattern (no API calls in validators)
- **Raw xlsx untouched** — rename is in-memory only; `process_dataset()` CLI still works
- **CSV extended, not replaced** — additive columns; backward compatible
- **Both `get_work_by_doi` and `get_open_access_pdf_url` are joblib-cached** — reruns are free

## Verification

1. `uv run python -m pytest tests/` — no regressions
2. Run notebook end-to-end: all 418 rows validate, ~296 valid exported
3. Validated xlsx has non-null `source_url`, `cited_article_doi`, `is_oa` at expected rates
4. `dataset_article_mapping.csv` has 3 new columns
5. Spot-check: pick a Dryad and SS record, verify URLs resolve
