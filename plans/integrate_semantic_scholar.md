# Semantic Scholar Integration Plan

> **Created:** 2026-02-17  
> **Context:** Expand evaluation coverage from 39% (164/418) to 100% by integrating Semantic Scholar data  
> **Status:** Proposed  
> **Target:** 80% abstract + 80% PDF+OA coverage for 192 valid Semantic Scholar records

---

## Problem Statement

The Fuster et al. annotated dataset contains **254 Semantic Scholar records (61%)** that lack:
- Structured metadata (abstracts, authors, venue, year)
- PDF URLs and open access status
- Integration into evaluation pipeline

Current coverage: **164 Dryad/Zenodo records only (39%)**

**Goal:** Enable full-dataset evaluation by adding Semantic Scholar API integration.

---

## Design Decisions

### API Client Pattern
Follow existing modular pattern (no base class inheritance):
- Create `src/llm_metadata/semanticscholar.py` similar to `openalex.py`
- Use joblib caching with `Memory("./cache")`
- Rate limiting: 100 req/5min (free tier), upgrade with API key if needed
- Map to `OpenAlexWork` schema via adapter function for pipeline compatibility

### Schema Extensions
Extend existing models with optional `source` field:
```python
# OpenAlexWork or new WorkMetadata
source: Literal["openalex", "semantic_scholar", "dryad", "zenodo"] = "openalex"
source_url: Optional[str] = None

# DatasetFeatureExtraction
extraction_source: Literal["abstract", "full_text", "dataset"]
data_repository: Optional[str] = None  # DOI for Semantic Scholar records
```

### PDF Download Strategy
Add Semantic Scholar OA check as **first step** in fallback chain for Semantic Scholar records:
1. Semantic Scholar `openAccessPdf.url`
2. OpenAlex (existing)
3. Unpaywall (existing)
4. EZproxy (existing)
5. Sci-Hub (existing)

Track `download_source` for analytics.

### Validation Pipeline
Two-stage enrichment in notebook:
1. **Semantic Scholar API** → abstracts, OA status, PDF URLs
2. **OpenAlex fallback** → PDF URLs if missing from Semantic Scholar
Output: `data/dataset_092624_validated_all_sources.xlsx`

---

## Implementation Plan

### Phase 1: API Client (Week 1, HIGH priority)
**Blocking:** All downstream work

**Tasks:**
- [ ] Create `src/llm_metadata/semanticscholar.py`
  - `get_paper_by_doi(doi)` with joblib caching
  - `batch_get_papers(dois)` for efficiency
  - Rate limiting with exponential backoff
  - `to_openalex_work()` adapter function
- [ ] Unit tests with mocked API responses
- [ ] Update CLAUDE.md with Semantic Scholar section

**Success criteria:** API client fetches metadata for 10 test DOIs

---

### Phase 2: Validation Pipeline (Week 2, HIGH priority)
**Depends on:** Phase 1

**Tasks:**
- [ ] Extend `notebooks/fuster_annotations_validation.ipynb`
  - Add enrichment cell for Semantic Scholar records
  - Dual-API fallback (Semantic Scholar → OpenAlex)
- [ ] Optional: Create `src/llm_metadata/validate_semantic_scholar.py` utility
- [ ] Generate `data/dataset_092624_validated_all_sources.xlsx`
  - New columns: `abstract_source`, `pdf_url`, `is_oa`, `oa_status`

**Success criteria:** ≥80% abstracts, 100% schema compliance

---

### Phase 3: PDF Download & Coverage (Week 3, MEDIUM priority)
**Depends on:** Phase 2

**Tasks:**
- [ ] Extend `pdf_download.py` with Semantic Scholar OA check
- [ ] Create `notebooks/download_semantic_scholar_pdfs.ipynb`
  - Prefect-based parallel downloads
  - Full fallback chain (Semantic Scholar → OpenAlex → Unpaywall → EZproxy → Sci-Hub)
- [ ] Create `notebooks/semantic_scholar_coverage_analysis.ipynb`
  - Compute abstract/PDF/OA metrics
  - Generate visualizations (Venn diagram, bar charts)
  - Export HTML report

**Success criteria:** ≥80% PDF coverage, coverage report ready

---

### Phase 4: Evaluation Integration (Week 4, MEDIUM priority)
**Depends on:** Phase 3

**Tasks:**
- [ ] Extend `notebooks/fuster_test_extraction_evaluation.ipynb`
  - Process all 299 valid records (not just Dryad)
  - Add source-stratified metrics
  - Compare abstract-only vs full-text approaches
- [ ] Add Semantic Scholar tasks to `prefect_pipeline.py`
- [ ] Generate comprehensive evaluation report

**Success criteria:** 100% dataset coverage, source-stratified F1 scores

---

## Technical Implementation Notes

### Semantic Scholar API Client
```python
# src/llm_metadata/semanticscholar.py
from joblib import Memory
from ratelimit import limits, sleep_and_retry

cache = Memory("./cache", verbose=0)

@sleep_and_retry
@limits(calls=100, period=300)  # Free tier
@cache.cache
def get_paper_by_doi(doi: str, api_key: Optional[str] = None):
    clean_doi = doi.replace("https://doi.org/", "")
    url = f"https://api.semanticscholar.org/graph/v1/paper/DOI:{clean_doi}"
    fields = "paperId,title,abstract,authors,year,venue,externalIds,openAccessPdf,isOpenAccess"
    # ... fetch and return SemanticScholarPaper model

def to_openalex_work(paper) -> dict:
    """Adapter for pipeline compatibility"""
    return {
        "openalex_id": f"https://semanticscholar.org/{paper.paper_id}",
        "doi": paper.doi,
        "abstract": paper.abstract,
        "is_oa": paper.is_open_access,
        "pdf_url": paper.pdf_url,
        "source": "semantic_scholar"
    }
```

### Notebook Workflow
```python
# In fuster_annotations_validation.ipynb
import semanticscholar as ss
import openalex

semantic_df = df[df['source'] == 'semantic_scholar'].copy()

for idx, row in semantic_df.iterrows():
    doi = extract_doi(row['url'])
    
    # Primary: Semantic Scholar
    paper = ss.get_paper_by_doi(doi)
    if paper:
        semantic_df.at[idx, 'full_text'] = paper.abstract or row['full_text']
        semantic_df.at[idx, 'pdf_url'] = paper.pdf_url
        semantic_df.at[idx, 'is_oa'] = paper.is_open_access
    
    # Fallback: OpenAlex for PDF
    if not semantic_df.at[idx, 'pdf_url']:
        oa_work = openalex.get_work_by_doi(doi)
        if oa_work and oa_work.get('is_oa'):
            semantic_df.at[idx, 'pdf_url'] = oa_work.get('pdf_url')

# Merge back and save
df_enriched = pd.concat([df[df['source'] != 'semantic_scholar'], semantic_df])
df_enriched.to_excel('data/dataset_092624_validated_all_sources.xlsx')
```

---

## Success Metrics

**Phase 1:** API client fetches 10 test DOIs successfully  
**Phase 2:** ≥80% abstracts (154/192), 100% schema compliance  
**Phase 3:** ≥80% PDFs (154/192), coverage report ready  
**Phase 4:** 100% evaluation coverage (418 records), source-stratified F1

---

## Risks & Mitigation

| Risk | Mitigation |
|------|------------|
| API rate limits | Use caching, batch calls, optional API key upgrade |
| Missing papers | OpenAlex fallback, document coverage gaps |
| OA < 80% target | Full fallback chain including Sci-Hub, adjust target |
| Schema breaks existing code | Optional fields only, backward compatible |

---

## Related Files

- Task: `tasks/integrate_semantic_scholar.md`
- TODO: `TODO.md` (lines 3-6, 50)
- Presentation: `docs/results_presentation_20260219/work_plan.md`
- Architecture: `CLAUDE.md` (Stage 1: Data Ingestion)
- API patterns: `src/llm_metadata/openalex.py`, `src/llm_metadata/zenodo.py`
- Validation: `notebooks/fuster_annotations_validation.ipynb`
- Evaluation: `src/llm_metadata/groundtruth_eval.py`
