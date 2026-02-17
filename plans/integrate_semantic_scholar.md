# Semantic Scholar Integration Plan

> **Created:** 2026-02-17
> **Context:** Expanding evaluation dataset with Semantic Scholar data (254 of 418 annotated records)
> **Status:** Proposed
> **Goal:** Achieve 80% abstract availability and 80% PDF+OA coverage for Semantic Scholar records

---

## Executive Summary

The current evaluation pipeline processes datasets from Dryad and Zenodo only, covering 164 of 418 records (39%) in the Fuster et al. annotated dataset. The remaining 254 records (61%) were retrieved via Semantic Scholar and lack:

1. **Structured metadata extraction** (abstracts, authors, publication info)
2. **PDF download pipeline integration** (OpenAlex/Unpaywall/EZproxy/Sci-Hub fallback chain)
3. **Open access status tracking** (for filtering evaluation to OA-only papers)
4. **Data coverage analytics** (proportion with abstracts, PDFs, OA licenses)

This plan outlines integration of the Semantic Scholar API to fill these gaps and expand evaluation coverage to 100% of the annotated dataset.

---

## Current State Analysis

### Annotated Dataset Breakdown
- **Total records:** 418
- **Dryad/Zenodo:** 164 (39%) — fully integrated
- **Semantic Scholar:** 254 (61%) — **not integrated**
  - Valid records: 192 (75.6%)
  - Invalid records: 62 (24.4%)

### Key Data Fields in `dataset_092624.xlsx`
```python
# Semantic Scholar records have:
'url'          # DOI links (e.g., https://doi.org/10.1139/CJB-2017-0193)
'source'       # 'semantic_scholar'
'title'        # Dataset/article title
'full_text'    # Abstract text (may be incomplete)
'valid_yn'     # Manual validation status
# Missing:
'cited_articles'  # Empty for all Semantic Scholar records
# No PDF tracking, no OA status, no structured author/journal metadata
```

### Current Pipeline Architecture
The project uses a **modular API client pattern** without base class inheritance:

| Module | Purpose | Key Functions |
|--------|---------|---------------|
| `openalex.py` | Article search, DOI lookup, OA metadata | `get_work_by_doi()`, `search_works()` |
| `dryad.py` | Dataset repository API | `search_datasets()`, `get_dataset()` |
| `zenodo.py` | Dataset repository API | `get_record_by_doi()` |
| `pdf_download.py` | PDF acquisition with fallback chain | `download_pdf_for_doi()` |
| `article_retrieval.py` | DOI matching for dataset→article mapping | `extract_doi_from_cited_articles()` |

**Missing:** `semanticscholar.py` module to retrieve metadata from Semantic Scholar API.

---

## Integration Requirements

### 1. API Module Development
**File:** `src/llm_metadata/semanticscholar.py`

**Objectives:**
- Implement Python client for Semantic Scholar API v1
- Support paper search by DOI, title, or Semantic Scholar paper ID
- Extract metadata: abstract, authors, publication venue, year, citation count
- Retrieve PDF URLs and open access status
- Use joblib caching (consistent with `openalex.py` pattern)

**API Endpoints:**
- Paper lookup: `GET /graph/v1/paper/{paper_id}` (DOI format: `DOI:10.1139/...`)
- Batch lookup: `POST /graph/v1/paper/batch` (up to 500 DOIs)
- Fields: `paperId,title,abstract,authors,year,venue,openAccessPdf,isOpenAccess,externalIds`

**Example Response Schema:**
```json
{
  "paperId": "649def34f8be52c8b66281af98ae884c09aef38b",
  "title": "Forest inventory...",
  "abstract": "We present...",
  "authors": [{"authorId": "...", "name": "..."}],
  "year": 2018,
  "venue": "Canadian Journal of Botany",
  "externalIds": {"DOI": "10.1139/CJB-2017-0193", "DBLP": "..."},
  "openAccessPdf": {"url": "https://...", "status": "HYBRID"},
  "isOpenAccess": true
}
```

**Implementation Notes:**
- Handle rate limiting (100 requests/5 minutes for free tier, configurable with API key)
- Map to `OpenAlexWork` schema for pipeline compatibility (or create `SemanticScholarWork` adapter)
- Validate DOI formats before API calls (Semantic Scholar uses `DOI:` prefix)

---

### 2. Data Schema Refactoring
**Files:** 
- `src/llm_metadata/schemas/openalex_work.py` (extend or create adapter)
- `src/llm_metadata/schemas/fuster_features.py` (add source tracking)

**Changes:**
1. **Add source tracking to metadata models:**
   ```python
   class WorkMetadata(BaseModel):  # New unified model or extend OpenAlexWork
       work_id: str  # Can be OpenAlex ID, DOI, or Semantic Scholar paper ID
       source: Literal["openalex", "semantic_scholar", "dryad", "zenodo"]
       doi: Optional[str]
       title: str
       abstract: Optional[str]
       # ... rest of fields
   ```

2. **Update `DatasetFeatureExtraction` to track data provenance:**
   ```python
   class DatasetFeatureExtraction(BaseModel):
       # Existing fields...
       source_repository: Optional[str] = Field(description="Dryad, Zenodo, or Semantic Scholar")
       source_url: Optional[str] = Field(description="Original dataset/article URL")
   ```

3. **Extend validation schema for Semantic Scholar records:**
   - Update `src/llm_metadata/schemas/validation.py` to handle DOI-only records (no dataset repository ID)
   - Add validation for paper vs dataset distinction

---

### 3. Annotation Validation Pipeline Refactoring
**Files:**
- `notebooks/fuster_annotations_validation.ipynb` (extend to handle Semantic Scholar)
- New script: `src/llm_metadata/validate_semantic_scholar.py`

**Objectives:**
1. **Enrich Semantic Scholar records with API metadata:**
   - Fetch abstracts for records with missing/incomplete `full_text` field
   - Extract structured author, venue, year information
   - Retrieve open access status and PDF URLs

2. **Standardize URL fields across sources:**
   ```python
   # New unified schema
   dataset_url: Optional[str]      # Dryad/Zenodo dataset page
   article_doi: Optional[str]      # Associated article DOI
   article_url: Optional[str]      # Article landing page
   pdf_url: Optional[str]          # Direct PDF link (if OA)
   is_oa: bool                     # Open access flag
   oa_status: Optional[str]        # "gold", "green", "hybrid", "bronze", "closed"
   ```

3. **Generate validated output:**
   - Create `data/dataset_092624_validated_with_semanticscholar.xlsx`
   - Include new columns: `abstract_source`, `pdf_available`, `oa_license`

**Workflow:**
```python
# Pseudocode
for record in semantic_scholar_records:
    doi = extract_doi(record['url'])
    
    # Try Semantic Scholar first
    ss_result = semanticscholar.get_paper_by_doi(doi)
    if ss_result:
        record['full_text'] = ss_result.abstract or record['full_text']
        record['is_oa'] = ss_result.isOpenAccess
        record['pdf_url'] = ss_result.openAccessPdf.get('url')
    
    # Fallback to OpenAlex for PDFs if Semantic Scholar has no PDF
    if not record['pdf_url']:
        oa_result = openalex.get_work_by_doi(doi)
        if oa_result and oa_result.is_oa:
            record['pdf_url'] = oa_result.pdf_url
            record['is_oa'] = True
```

---

### 4. PDF Download Integration
**Files:**
- `src/llm_metadata/pdf_download.py` (extend fallback chain)
- `notebooks/download_dryad_pdfs_fuster.ipynb` (extend to Semantic Scholar)

**Changes:**
1. **Add Semantic Scholar as first fallback in chain:**
   ```python
   # New order: Semantic Scholar OA → OpenAlex → Unpaywall → EZproxy → Sci-Hub
   def download_pdf_for_doi(doi: str):
       # 1. Check Semantic Scholar for open access PDF
       ss_pdf_url = semanticscholar.get_pdf_url(doi)
       if ss_pdf_url:
           return download_from_url(ss_pdf_url)
       
       # 2-5. Existing fallback chain
       # ... (OpenAlex, Unpaywall, EZproxy, Sci-Hub)
   ```

2. **Update download metadata tracking:**
   - Add `download_source` field to track which API succeeded
   - Log Semantic Scholar success rate separately for analytics

3. **Batch download for Semantic Scholar records:**
   - Create notebook: `notebooks/download_semantic_scholar_pdfs.ipynb`
   - Use Prefect for parallel downloads (consistent with existing pattern)
   - Target: 80% success rate for 192 valid Semantic Scholar records

---

### 5. Data Coverage Analysis
**Files:**
- New notebook: `notebooks/semantic_scholar_coverage_analysis.ipynb`
- Extend existing: `notebooks/fuster_test_extraction_evaluation.ipynb`

**Metrics to Compute:**
1. **Abstract availability:**
   - Semantic Scholar: % with non-empty `full_text` after API enrichment
   - Target: ≥80% (154/192 valid records)

2. **PDF availability:**
   - Semantic Scholar OA PDFs: % successfully downloaded
   - Total (all sources): % with any PDF after fallback chain
   - Target: ≥80% (154/192 valid records)

3. **Open access proportion:**
   - By source: Semantic Scholar vs Dryad/Zenodo vs overall
   - By license type: gold/green/hybrid/bronze/closed
   - Compare to Fuster et al. reported OA rates

4. **Source breakdown:**
   ```python
   # Expected output table
   Source             | Total | Valid | Abstract% | PDF% | OA%
   -------------------|-------|-------|-----------|------|-----
   Dryad              |   XX  |  XX   |   100%    |  XX% | XX%
   Zenodo             |   XX  |  XX   |    XX%    |  XX% | XX%
   Semantic Scholar   |  254  |  192  |    TBD    | TBD  | TBD
   Overall            |  418  |  XXX  |    XX%    |  XX% | XX%
   ```

**Visualizations:**
- Venn diagram: Records with abstracts ∩ PDFs ∩ OA status
- Stacked bar chart: Source breakdown by availability status
- Scatter: Abstract length vs extraction quality (precision/recall)

---

### 6. Evaluation Pipeline Integration
**Files:**
- `src/llm_metadata/gpt_classify.py` (no changes needed)
- `notebooks/fuster_test_extraction_evaluation.ipynb` (extend to all records)
- `src/llm_metadata/prefect_pipeline.py` (add Semantic Scholar workflow)

**Changes:**
1. **Extend batch classification to all 418 records:**
   - Currently: 5-11 records (abstract-annotated Dryad only)
   - Target: All 418 records (299 valid across all sources)
   - Filter: `valid_yn == 'yes'` to focus on relevant datasets

2. **Add source-stratified evaluation:**
   ```python
   # Compute metrics separately for each source
   results = {
       'dryad': evaluate_indexed(dryad_records),
       'zenodo': evaluate_indexed(zenodo_records),
       'semantic_scholar': evaluate_indexed(semantic_scholar_records),
       'overall': evaluate_indexed(all_records)
   }
   ```

3. **Compare abstract-only vs full-text extraction:**
   - Semantic Scholar: Abstract-only (no full PDFs initially)
   - Dryad/Zenodo: Both abstract and full-text available
   - Hypothesis: Full-text improves recall for methods/location features

---

## Implementation Phases

### Phase 1: API Client & Schema (Week 1)
**Priority: HIGH**  
**Blocking:** All downstream work

- [ ] Create `src/llm_metadata/semanticscholar.py` module
  - [ ] Implement `get_paper_by_doi(doi: str)` with caching
  - [ ] Implement `batch_get_papers(dois: List[str])` for efficiency
  - [ ] Handle rate limiting with exponential backoff
  - [ ] Write unit tests with mocked API responses

- [ ] Refactor data schemas
  - [ ] Add `source` field to `OpenAlexWork` or create unified `WorkMetadata`
  - [ ] Extend `DatasetFeatureExtraction` with provenance fields
  - [ ] Update `validation.py` for DOI-only records

- [ ] Update CLAUDE.md with Semantic Scholar section
  - [ ] API authentication (free tier vs paid)
  - [ ] Rate limits and batch optimization
  - [ ] Error handling for missing papers

**Success Criteria:**
- API client successfully fetches metadata for 10 test DOIs from Semantic Scholar records
- Schema validation passes for 100% of enriched records
- Unit tests achieve 80% coverage for new module

---

### Phase 2: Annotation Validation Pipeline (Week 2)
**Priority: HIGH**  
**Depends on:** Phase 1

- [ ] Extend `fuster_annotations_validation.ipynb`
  - [ ] Add cell: "Enrich Semantic Scholar records with API metadata"
  - [ ] Fetch abstracts for `source == 'semantic_scholar'` records
  - [ ] Extract OA status and PDF URLs
  - [ ] Validate enriched data against schema

- [ ] Create `src/llm_metadata/validate_semantic_scholar.py`
  - [ ] Function: `enrich_semantic_scholar_records(df: pd.DataFrame) -> pd.DataFrame`
  - [ ] Batch API calls (500 DOIs at a time)
  - [ ] Progress tracking with tqdm
  - [ ] Cache results to avoid re-fetching

- [ ] Generate validated dataset with all sources
  - [ ] Output: `data/dataset_092624_validated_all_sources.xlsx`
  - [ ] Include new columns: `abstract_source`, `pdf_url`, `is_oa`, `oa_status`
  - [ ] Document field definitions in README

**Success Criteria:**
- ≥80% of Semantic Scholar records have non-empty abstracts (154/192)
- 100% have structured metadata (title, authors, year, venue)
- Validation achieves 100% schema compliance

---

### Phase 3: PDF Download & Coverage Analysis (Week 3)
**Priority: MEDIUM**  
**Depends on:** Phase 2

- [ ] Extend PDF download pipeline
  - [ ] Add Semantic Scholar OA check to `pdf_download.py`
  - [ ] Update fallback chain order
  - [ ] Track download source in metadata

- [ ] Create `notebooks/download_semantic_scholar_pdfs.ipynb`
  - [ ] Batch download with Prefect parallelization
  - [ ] Use existing fallback chain (OpenAlex → Unpaywall → EZproxy → Sci-Hub)
  - [ ] Generate `data/semantic_scholar_download_report.csv`

- [ ] Create `notebooks/semantic_scholar_coverage_analysis.ipynb`
  - [ ] Compute abstract/PDF/OA availability metrics
  - [ ] Generate source breakdown table
  - [ ] Create visualizations (Venn diagram, bar charts)
  - [ ] Export HTML report for presentation

**Success Criteria:**
- ≥80% of valid Semantic Scholar records have PDFs (154/192)
- Coverage analysis report ready for presentation
- OA proportion comparable to Dryad/Zenodo (target: 50-70%)

---

### Phase 4: Evaluation Pipeline Integration (Week 4)
**Priority: MEDIUM**  
**Depends on:** Phase 3

- [ ] Extend batch classification to all records
  - [ ] Update `fuster_test_extraction_evaluation.ipynb` to process 299 valid records
  - [ ] Add source-stratified evaluation
  - [ ] Compare abstract-only (Semantic Scholar) vs full-text (Dryad/Zenodo w/ PDFs)

- [ ] Add Semantic Scholar workflow to Prefect pipeline
  - [ ] Task: `enrich_semantic_scholar_task(df: pd.DataFrame)`
  - [ ] Task: `download_semantic_scholar_pdfs_task(dois: List[str])`
  - [ ] Task: `classify_semantic_scholar_abstracts_task(df: pd.DataFrame)`

- [ ] Generate comprehensive evaluation report
  - [ ] Per-source performance metrics
  - [ ] Feature-level analysis (species, location, temporal, data_type)
  - [ ] Error analysis: common failure modes by source

**Success Criteria:**
- Evaluation covers 100% of annotated dataset (418 records, 299 valid)
- Metrics table includes source-stratified F1 scores
- Report identifies which features benefit most from full-text vs abstract-only

---

## Technical Design Details

### Semantic Scholar API Client Architecture

```python
# src/llm_metadata/semanticscholar.py

import requests
from typing import Optional, List, Dict
from joblib import Memory
from pydantic import BaseModel
from ratelimit import limits, sleep_and_retry

# Configure caching (consistent with openalex.py)
cache_dir = "./cache"
memory = Memory(cache_dir, verbose=0)

class SemanticScholarPaper(BaseModel):
    """Semantic Scholar paper metadata."""
    paper_id: str
    title: str
    abstract: Optional[str] = None
    authors: List[Dict[str, str]] = []
    year: Optional[int] = None
    venue: Optional[str] = None
    doi: Optional[str] = None
    is_open_access: bool = False
    pdf_url: Optional[str] = None
    oa_status: Optional[str] = None  # HYBRID, GOLD, GREEN, BRONZE

@sleep_and_retry
@limits(calls=100, period=300)  # 100 calls per 5 minutes (free tier)
def _api_call(url: str, headers: Dict = None) -> Dict:
    """Rate-limited API call wrapper."""
    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()
    return response.json()

@memory.cache
def get_paper_by_doi(doi: str, api_key: Optional[str] = None) -> Optional[SemanticScholarPaper]:
    """
    Fetch paper metadata from Semantic Scholar by DOI.
    
    Args:
        doi: Paper DOI (with or without 'DOI:' prefix)
        api_key: Optional API key for higher rate limits
    
    Returns:
        SemanticScholarPaper or None if not found
    """
    # Normalize DOI format for Semantic Scholar
    clean_doi = doi.replace("https://doi.org/", "").replace("DOI:", "")
    url = f"https://api.semanticscholar.org/graph/v1/paper/DOI:{clean_doi}"
    
    # Request specific fields
    fields = "paperId,title,abstract,authors,year,venue,externalIds,openAccessPdf,isOpenAccess"
    params = {"fields": fields}
    
    headers = {}
    if api_key:
        headers["x-api-key"] = api_key
    
    try:
        data = _api_call(url, headers)
        
        # Extract PDF URL and status
        pdf_info = data.get("openAccessPdf", {})
        pdf_url = pdf_info.get("url") if pdf_info else None
        oa_status = pdf_info.get("status") if pdf_info else None
        
        return SemanticScholarPaper(
            paper_id=data["paperId"],
            title=data["title"],
            abstract=data.get("abstract"),
            authors=data.get("authors", []),
            year=data.get("year"),
            venue=data.get("venue"),
            doi=data.get("externalIds", {}).get("DOI"),
            is_open_access=data.get("isOpenAccess", False),
            pdf_url=pdf_url,
            oa_status=oa_status
        )
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            return None  # Paper not in Semantic Scholar
        raise

def batch_get_papers(dois: List[str], api_key: Optional[str] = None) -> List[Optional[SemanticScholarPaper]]:
    """
    Fetch multiple papers in a single batch request.
    
    Semantic Scholar supports up to 500 papers per batch.
    For larger lists, this function chunks and combines results.
    """
    results = []
    chunk_size = 500
    
    for i in range(0, len(dois), chunk_size):
        chunk = dois[i:i+chunk_size]
        # Note: Batch endpoint requires POST, not cached by joblib
        # Individual calls will be cached via get_paper_by_doi
        for doi in chunk:
            paper = get_paper_by_doi(doi, api_key)
            results.append(paper)
    
    return results

def to_openalex_work(paper: SemanticScholarPaper) -> Dict:
    """
    Convert Semantic Scholar paper to OpenAlexWork-compatible dict.
    
    This adapter allows Semantic Scholar data to flow through
    existing PDF download and chunking pipelines.
    """
    return {
        "openalex_id": f"https://semanticscholar.org/{paper.paper_id}",
        "doi": paper.doi,
        "title": paper.title,
        "abstract": paper.abstract,
        "authors": [{"author_name": a.get("name", ""), "orcid": None} for a in paper.authors],
        "is_oa": paper.is_open_access,
        "pdf_url": paper.pdf_url,
        "publication_year": paper.year,
        "source": "semantic_scholar"  # NEW: Track data source
    }
```

---

### Schema Extensions

```python
# src/llm_metadata/schemas/openalex_work.py

from typing import Literal

class OpenAlexWork(BaseModel):
    # Existing fields...
    openalex_id: str
    doi: Optional[str]
    title: str
    abstract: Optional[str]
    authors: List[OpenAlexAuthor]
    is_oa: bool
    pdf_url: Optional[str]
    
    # NEW: Track data source
    source: Literal["openalex", "semantic_scholar", "manual"] = "openalex"
    source_url: Optional[str] = Field(
        None, 
        description="Original source URL (dataset repo, Semantic Scholar, etc.)"
    )
```

```python
# src/llm_metadata/schemas/fuster_features.py

class DatasetFeatureExtraction(BaseModel):
    # Existing fields (species, data_type, etc.)...
    
    # NEW: Provenance tracking
    extraction_source: Literal["abstract", "full_text", "dataset"] = Field(
        description="Source used for feature extraction"
    )
    data_repository: Optional[str] = Field(
        None,
        description="Original data repository: Dryad, Zenodo, or article DOI for Semantic Scholar"
    )
```

---

### Validation Pipeline Workflow

```python
# New: src/llm_metadata/validate_semantic_scholar.py

import pandas as pd
from tqdm import tqdm
from typing import Optional
from llm_metadata import semanticscholar, openalex

def enrich_semantic_scholar_records(
    df: pd.DataFrame, 
    api_key: Optional[str] = None
) -> pd.DataFrame:
    """
    Enrich Semantic Scholar records with API metadata.
    
    Args:
        df: DataFrame with 'source' and 'url' columns
        api_key: Optional Semantic Scholar API key
    
    Returns:
        Enriched DataFrame with abstract, PDF, and OA columns
    """
    semantic_records = df[df['source'] == 'semantic_scholar'].copy()
    
    # New columns
    semantic_records['abstract_fetched'] = None
    semantic_records['pdf_url'] = None
    semantic_records['is_oa'] = False
    semantic_records['oa_status'] = None
    semantic_records['authors_list'] = None
    semantic_records['publication_year'] = None
    
    for idx, row in tqdm(semantic_records.iterrows(), total=len(semantic_records)):
        doi = row['url'].replace('https://doi.org/', '')
        
        # Try Semantic Scholar first
        paper = semanticscholar.get_paper_by_doi(doi, api_key)
        
        if paper:
            semantic_records.at[idx, 'abstract_fetched'] = paper.abstract
            semantic_records.at[idx, 'pdf_url'] = paper.pdf_url
            semantic_records.at[idx, 'is_oa'] = paper.is_open_access
            semantic_records.at[idx, 'oa_status'] = paper.oa_status
            semantic_records.at[idx, 'authors_list'] = '; '.join([a['name'] for a in paper.authors])
            semantic_records.at[idx, 'publication_year'] = paper.year
            
            # Fallback to OpenAlex if no PDF from Semantic Scholar
            if not paper.pdf_url:
                oa_work = openalex.get_work_by_doi(doi)
                if oa_work and oa_work.get('is_oa'):
                    semantic_records.at[idx, 'pdf_url'] = oa_work.get('pdf_url')
                    semantic_records.at[idx, 'is_oa'] = True
        else:
            # Fallback to OpenAlex entirely
            oa_work = openalex.get_work_by_doi(doi)
            if oa_work:
                semantic_records.at[idx, 'abstract_fetched'] = oa_work.get('abstract')
                semantic_records.at[idx, 'pdf_url'] = oa_work.get('pdf_url')
                semantic_records.at[idx, 'is_oa'] = oa_work.get('is_oa', False)
    
    # Merge back with original DataFrame
    df_enriched = df.copy()
    for col in ['abstract_fetched', 'pdf_url', 'is_oa', 'oa_status', 'authors_list', 'publication_year']:
        df_enriched[col] = df[col] if col in df.columns else None
        df_enriched.loc[semantic_records.index, col] = semantic_records[col]
    
    return df_enriched

def compute_coverage_metrics(df: pd.DataFrame) -> Dict[str, Dict]:
    """Compute abstract/PDF/OA availability by source."""
    metrics = {}
    
    for source in df['source'].unique():
        source_df = df[df['source'] == source]
        valid_df = source_df[source_df['valid_yn'] == 'yes']
        
        metrics[source] = {
            'total': len(source_df),
            'valid': len(valid_df),
            'abstract_pct': (valid_df['abstract_fetched'].notna().sum() / len(valid_df) * 100) if len(valid_df) > 0 else 0,
            'pdf_pct': (valid_df['pdf_url'].notna().sum() / len(valid_df) * 100) if len(valid_df) > 0 else 0,
            'oa_pct': (valid_df['is_oa'].sum() / len(valid_df) * 100) if len(valid_df) > 0 else 0
        }
    
    return metrics
```

---

## Risk Assessment & Mitigation

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| **Semantic Scholar API rate limits** | HIGH | HIGH | Use API key (5000 req/5min), implement caching, batch calls where possible |
| **Missing papers in Semantic Scholar** | MEDIUM | MEDIUM | Fallback to OpenAlex for metadata/PDFs, document coverage gaps |
| **Abstract quality variation** | MEDIUM | LOW | Compare extraction quality across sources, document per-source metrics |
| **OA proportion lower than target (80%)** | MEDIUM | MEDIUM | Use full fallback chain (Sci-Hub as last resort), adjust target based on reality |
| **Schema refactoring breaks existing pipelines** | LOW | HIGH | Add fields as optional, maintain backward compatibility, comprehensive testing |
| **DOI format inconsistencies** | LOW | MEDIUM | Normalize DOIs before API calls, handle edge cases (URLs vs bare DOIs) |

---

## Success Metrics

### Quantitative Targets
1. **Abstract coverage:** ≥80% of 192 valid Semantic Scholar records (≥154 records)
2. **PDF coverage:** ≥80% of 192 valid Semantic Scholar records (≥154 records)
3. **Open access proportion:** 50-70% (comparable to Dryad/Zenodo)
4. **API success rate:** ≥95% for Semantic Scholar lookups (allow 5% missing papers)
5. **Evaluation coverage:** 100% of 418 annotated records processed
6. **Processing time:** Complete enrichment pipeline in <1 hour for 254 records

### Qualitative Outcomes
1. **Source-stratified evaluation:** Precision/Recall/F1 computed separately for Dryad, Zenodo, Semantic Scholar
2. **Coverage analysis dashboard:** HTML report with visualizations ready for presentation
3. **Reproducible pipeline:** Notebooks and scripts documented for future dataset expansions
4. **Architecture documentation:** CLAUDE.md updated with Semantic Scholar section

---

## Open Questions

1. **API Key:** Should we use a free tier initially or request a Semantic Scholar API key for higher limits?
   - **Recommendation:** Start with free tier, upgrade if rate limits become blocking

2. **Data Model:** Extend `OpenAlexWork` vs create separate `SemanticScholarWork` model?
   - **Recommendation:** Extend `OpenAlexWork` with `source` field for unified pipeline

3. **Fallback Strategy:** Should Semantic Scholar be first or last in PDF fallback chain?
   - **Recommendation:** First for Semantic Scholar-sourced records, otherwise use existing order

4. **Validation Scope:** Re-validate entire annotated dataset or only Semantic Scholar records?
   - **Recommendation:** Validate all sources to ensure schema consistency, output unified file

5. **Presentation Timing:** Can we complete Phases 1-3 before Thursday presentation?
   - **Recommendation:** Prioritize API client (Phase 1) and coverage analysis (Phase 3), defer full evaluation (Phase 4)

---

## Related Documents

- **Task specification:** `tasks/integrate_semantic_scholar.md`
- **Project TODO:** `TODO.md` (lines 3-6, 50)
- **Presentation plan:** `docs/results_presentation_20260219/work_plan.md`
- **Architecture reference:** `CLAUDE.md` (Stage 1: Data Ingestion)
- **Existing API patterns:** `src/llm_metadata/openalex.py`, `src/llm_metadata/zenodo.py`
- **Validation notebooks:** `notebooks/fuster_annotations_validation.ipynb`
- **Evaluation framework:** `src/llm_metadata/groundtruth_eval.py`

---

## Next Steps

**Immediate actions (pre-presentation):**
1. Create `semanticscholar.py` API client with basic DOI lookup
2. Test on 10 sample Semantic Scholar records from annotated dataset
3. Generate coverage analysis for abstract/PDF/OA availability
4. Update presentation slides with Semantic Scholar data breakdown

**Post-presentation:**
1. Complete Phase 1 (API client + schema refactoring)
2. Run full enrichment pipeline on 254 Semantic Scholar records
3. Download PDFs using fallback chain
4. Integrate into evaluation pipeline for comprehensive benchmarking
