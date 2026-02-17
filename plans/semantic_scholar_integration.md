# Agentic Implementation Plan: Semantic Scholar Data Integration

**Created:** 2026-02-17  
**Status:** Planning Phase  
**Context:** Integrate Semantic Scholar-sourced datasets into validation pipeline and evaluation benchmarks

---

## Executive Summary

This plan outlines the agentic implementation strategy for integrating Semantic Scholar datasets into the `llm_metadata` project. The integration aims to expand evaluation coverage from ~299 Dryad/Zenodo records to ~418 total records (including Semantic Scholar data from Fuster et al.'s original dataset), with a target of 80% abstract availability and 80% PDF/OA access within valid records.

**Key Insight from Exploration:** Semantic Scholar is simply another search engine used for dataset discovery. Integration requires processing the xlsx file to extract URLs and metadata, but does not fundamentally change the data retrieval workflow.

---

## Background & Context

### Current State
- **Data Sources:** Dryad, Zenodo (via APIs)
- **Evaluation Dataset:** `data/dataset_092624.xlsx` (418 records) and `data/dataset_092624_validated.xlsx` (cleaned subset)
- **Coverage:** ~75 article DOIs mapped; Dryad 100%, Zenodo 56.7%, Semantic Scholar 0%
- **Pipeline Stages:** Data Ingestion → Schema/Prompt → LLM Inference → Evaluation

### Problem Statement
The current evaluation pipeline excludes Semantic Scholar-sourced records from Fuster et al.'s original annotations, limiting:
1. **Evaluation coverage** - Missing ~119 potentially valid records
2. **Generalizability** - Results don't reflect full data diversity
3. **Presentation completeness** - Thursday 2026-02-19 presentation requires full dataset analysis

### Success Criteria
- **Abstract availability:** ≥80% of valid Semantic Scholar records
- **Full-text availability:** ≥80% of valid records with PDFs + OA access
- **Schema compliance:** 100% validation pass rate for integrated data
- **Pipeline integration:** Seamless processing alongside Dryad/Zenodo data

---

## Architecture Overview

### 4-Stage Pipeline Integration Points

```
┌─────────────────────────────────────────────────────────────────────┐
│ Stage 1: Data Ingestion & Preparation                              │
├─────────────────────────────────────────────────────────────────────┤
│ NEW: semantic_scholar.py                                            │
│  ├─ Parse xlsx "url" field (journal or SS search results)          │
│  ├─ Extract DOIs from cited_articles or journal pages              │
│  ├─ Integrate with article_retrieval.py for DOI resolution         │
│  └─ Utilize existing OpenAlex/Unpaywall/Sci-Hub fallback chain     │
│                                                                     │
│ REFACTOR: schemas/validation.py                                    │
│  ├─ Add source field: "dryad" | "zenodo" | "semantic_scholar"     │
│  ├─ Unify url fields: source_url, journal_url, pdf_url, is_oa     │
│  └─ Maintain backward compatibility with existing validations      │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ Stage 2-3: Schema/Inference (No Changes Required)                  │
├─────────────────────────────────────────────────────────────────────┤
│ - Pydantic models in schemas/fuster_features.py remain unchanged   │
│ - gpt_classify.py inference logic unaffected by data source        │
│ - Prefect pipelines can process mixed-source batches natively      │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ Stage 4: Evaluation & Validation                                   │
├─────────────────────────────────────────────────────────────────────┤
│ EXTEND: groundtruth_eval.py                                        │
│  ├─ Add source-stratified metrics (per-source P/R/F1)             │
│  └─ Generate comparative reports: Dryad vs Zenodo vs SS           │
│                                                                     │
│ NEW: notebooks/semantic_scholar_integration.ipynb                  │
│  ├─ Data coverage analysis (valid records, PDFs, OA by source)    │
│  ├─ Quality assessment (abstract length, completeness)            │
│  └─ Comparative performance benchmarking                           │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Implementation Strategy

### Phase 1: Pre-Implementation Audit (Agent: explore)
**Objective:** Understand existing patterns before making changes

**Tasks:**
1. **Code Pattern Analysis**
   - Review `dryad.py` and `zenodo.py` for API client patterns
   - Analyze `article_retrieval.py` for DOI resolution logic
   - Study `schemas/validation.py` for current field structure
   - Inspect `groundtruth_eval.py` for metric computation patterns

2. **Data Structure Analysis**
   - Examine `dataset_092624.xlsx` Semantic Scholar records
   - Identify URL patterns in `url` field (journal vs SS search)
   - Check `cited_articles` column for DOI availability
   - Determine abstract and full-text availability patterns

3. **Pipeline Integration Points**
   - Map existing Prefect workflows in `prefect_pipeline.py`
   - Identify where source-specific logic is hardcoded
   - Document extension points for new data sources

**Deliverables:**
- Audit report in `/plans/semantic_scholar_audit_report.md`
- Annotated code samples showing patterns to follow
- Data quality summary from xlsx exploration

**Estimated Effort:** 1-2 hours (single explore agent task)

---

### Phase 2: Schema & Validation Refactor (Agent: general-purpose)
**Objective:** Unify data model to support multi-source records

**Tasks:**
1. **Extend Pydantic Validation Schema** (`schemas/validation.py`)
   ```python
   class DataSource(str, Enum):
       DRYAD = "dryad"
       ZENODO = "zenodo"
       SEMANTIC_SCHOLAR = "semantic_scholar"
   
   class URLFields(BaseModel):
       """Unified URL structure for all sources"""
       source: DataSource
       source_url: str  # Repository/search engine URL
       journal_url: Optional[str] = None  # Article landing page
       pdf_url: Optional[str] = None  # Direct PDF link
       is_oa: bool = False
       oa_license: Optional[str] = None
   ```

2. **Backward Compatibility Layer**
   - Create migration function: `migrate_legacy_fields()` to convert old records
   - Add validators to auto-populate new fields from legacy `url` column
   - Ensure existing notebooks continue to work

3. **Validation Tests**
   - Test schema on all 418 records from `dataset_092624.xlsx`
   - Generate validation report: pass rate, error types, field coverage
   - Produce cleaned dataset: `data/dataset_092624_validated_v2.xlsx`

**Deliverables:**
- Updated `schemas/validation.py` with `DataSource` and `URLFields`
- Migration script: `scripts/migrate_url_fields.py`
- Test suite: `tests/test_semantic_scholar_validation.py`
- Validation report: `notebooks/results/semantic_scholar_validation_<timestamp>/`

**Estimated Effort:** 3-4 hours (general-purpose agent)

---

### Phase 3: Semantic Scholar Module Implementation (Agent: general-purpose)
**Objective:** Create data retrieval module for Semantic Scholar records

**Tasks:**
1. **Module Structure** (`src/llm_metadata/semantic_scholar.py`)
   ```python
   class SemanticScholarClient:
       """Lightweight client for Semantic Scholar API"""
       
       def __init__(self, api_key: Optional[str] = None):
           """Optional API key for higher rate limits"""
           pass
       
       def parse_xlsx_url(self, url: str) -> Dict[str, str]:
           """Extract metadata from xlsx url field"""
           # Pattern 1: Journal landing page → extract DOI
           # Pattern 2: SS search results → return search terms
           pass
       
       def resolve_doi_from_journal(self, journal_url: str) -> Optional[str]:
           """Extract DOI from journal page HTML"""
           # Use BeautifulSoup to scrape DOI metadata
           pass
       
       def get_cited_articles(self, paper_id: str) -> List[Dict]:
           """Retrieve cited articles via SS API (future work)"""
           pass
   ```

2. **Integration with Existing Retrieval**
   - Extend `article_retrieval.py` to handle `source="semantic_scholar"`
   - Reuse OpenAlex/Unpaywall/Sci-Hub fallback chain
   - Add Semantic Scholar records to `dataset_article_mapping.csv`

3. **Prefect Workflow Integration**
   - Create task: `fetch_semantic_scholar_abstracts()`
   - Extend `doi_classification_pipeline()` to accept mixed-source batches
   - Add source-aware logging for monitoring

**Deliverables:**
- New module: `src/llm_metadata/semantic_scholar.py`
- Tests: `tests/test_semantic_scholar.py`
- Updated: `article_retrieval.py`, `prefect_pipeline.py`
- Documentation: docstrings + usage examples

**Estimated Effort:** 4-6 hours (general-purpose agent)

**Dependencies:** Phase 2 schema must be complete

---

### Phase 4: Data Coverage Analysis (Agent: task/explore + notebook)
**Objective:** Quantify data availability and quality for presentation

**Tasks:**
1. **Jupyter Notebook Analysis** (`notebooks/semantic_scholar_coverage_analysis.ipynb`)
   ```python
   # Coverage Metrics by Source
   - Total records: Dryad, Zenodo, Semantic Scholar
   - Valid records (valid_yn == "yes")
   - Abstract availability (%, avg length)
   - PDF availability (count, %)
   - OA access proportion (is_oa == True, %)
   - License distribution (CC-BY, CC0, embargo, etc.)
   
   # Quality Metrics
   - Field completeness (% non-null per field)
   - Data type distribution (EBVDataType enum)
   - Spatial coverage (countries, regions)
   - Temporal range (start/end years)
   
   # Comparative Analysis
   - Dryad vs Zenodo vs Semantic Scholar boxplots
   - Statistical tests: χ² for categorical, t-test for continuous
   ```

2. **Data Retrieval Execution**
   - Run `semantic_scholar.py` on all 418 records
   - Download PDFs for available Semantic Scholar records
   - Update `registry.sqlite` with processing status

3. **Visualization & Reporting**
   - Generate HTML report with Plotly/Altair charts
   - Create summary tables for Thursday presentation
   - Save to `notebooks/results/semantic_scholar_coverage_<timestamp>/`

**Deliverables:**
- Notebook: `notebooks/semantic_scholar_coverage_analysis.ipynb`
- HTML report with interactive charts
- Summary CSV: `data/coverage_by_source.csv`
- Updated `notebooks/README.md` with findings

**Estimated Effort:** 2-3 hours (task agent for execution + explore for analysis)

**Dependencies:** Phase 3 module must be functional

---

### Phase 5: Batch Extraction & Evaluation (Agent: general-purpose + task)
**Objective:** Run full pipeline on integrated dataset and generate benchmarks

**Tasks:**
1. **Batch Abstract Extraction**
   - Run `gpt_classify.py` on all 418 records (Dryad + Zenodo + SS)
   - Save results: `data/extractions_all_sources_<timestamp>.json`
   - Track costs and token usage per source

2. **Full-Text Extraction (OA Records Only)**
   - Filter to `is_oa == True` records with PDFs
   - Run section-based extraction pipeline
   - Compare abstract-only vs full-text performance

3. **Source-Stratified Evaluation**
   - Extend `groundtruth_eval.py` to compute per-source metrics
   ```python
   report = evaluate_by_source(
       predictions=extractions,
       ground_truth=validated_data,
       sources=["dryad", "zenodo", "semantic_scholar"]
   )
   # Output: DataFrame with columns [source, field, precision, recall, f1]
   ```

4. **Benchmark Report Generation**
   - Create comparison notebook: `notebooks/semantic_scholar_benchmark.ipynb`
   - Generate HTML report with side-by-side comparisons
   - Include feature-level performance analysis (taxa, geo, temporal)

**Deliverables:**
- Batch extraction results: `data/extractions_all_sources_<timestamp>.json`
- Evaluation notebook: `notebooks/semantic_scholar_benchmark.ipynb`
- HTML benchmark report for presentation
- Updated evaluation module with source stratification

**Estimated Effort:** 4-6 hours (general-purpose agent for code, task agent for execution)

**Dependencies:** Phases 2, 3, 4 complete

---

### Phase 6: Documentation & Presentation Prep (Agent: task)
**Objective:** Update documentation and prepare materials for Thursday 2026-02-19

**Tasks:**
1. **Code Documentation**
   - Update `CLAUDE.md` with Semantic Scholar module
   - Add usage examples to `README.md`
   - Document API rate limits and fallback strategies

2. **Lab Journal Update** (`notebooks/README.md`)
   - Add timestamped entry following lab logging protocol
   - Summarize coverage metrics and key findings
   - Link to HTML reports and notebooks

3. **Presentation Materials** (`docs/results_presentation_20260219/`)
   - Update `work_plan.md` with completed integration
   - Create slides with coverage charts and performance comparisons
   - Prepare demo: live extraction on Semantic Scholar record

4. **TODO.md Cleanup**
   - Mark completed tasks as `[x]`
   - Document any blockers or follow-up work
   - Update priority markers (🔥)

**Deliverables:**
- Updated `CLAUDE.md`, `README.md`, `notebooks/README.md`
- Presentation materials in `docs/results_presentation_20260219/`
- Cleaned `TODO.md` with current status

**Estimated Effort:** 1-2 hours (task agent)

**Dependencies:** Phase 5 complete

---

## Testing Strategy

### Unit Tests
```python
# tests/test_semantic_scholar.py
def test_parse_journal_url():
    """Extract DOI from journal landing page"""
    
def test_parse_search_url():
    """Extract search terms from SS results page"""
    
def test_resolve_doi_via_openalex():
    """Fallback to OpenAlex for DOI resolution"""

# tests/test_validation_refactor.py
def test_url_field_migration():
    """Legacy url field converts to URLFields model"""
    
def test_data_source_enum():
    """DataSource enum accepts all sources"""
    
def test_backward_compatibility():
    """Old records still validate after schema update"""
```

### Integration Tests
```python
# tests/test_semantic_scholar_pipeline.py
def test_end_to_end_retrieval():
    """SS record → DOI → abstract → PDF → extraction"""
    
def test_mixed_source_batch():
    """Pipeline handles Dryad + Zenodo + SS in single batch"""
```

### Validation Tests
- Run `schemas/validation.py` on full 418-record dataset
- Target: 100% pass rate (matching current `dataset_092624_validated.xlsx`)

---

## Risk Assessment & Mitigation

### High Priority Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| **SS records lack DOIs** | High | High | Use journal URL scraping + OpenAlex fallback |
| **Low PDF availability (<80%)** | Medium | Medium | Document unavailable records; use abstract-only extraction |
| **Schema refactor breaks existing notebooks** | Medium | High | Comprehensive backward compatibility tests |
| **API rate limits (OpenAlex, SS)** | Medium | Low | Implement exponential backoff + caching |

### Medium Priority Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| **Data quality issues in xlsx** | Medium | Medium | Manual review + validation report |
| **Extraction performance varies by source** | Medium | Medium | Source-stratified reporting makes differences transparent |
| **Thursday deadline pressure** | High | Medium | Prioritize coverage analysis (Phase 4) over full extraction (Phase 5) |

---

## Success Metrics

### Quantitative Targets
- [ ] **Abstract coverage:** ≥80% of valid Semantic Scholar records (N ≥ 95 out of ~119)
- [ ] **PDF coverage:** ≥80% of valid records with PDFs (N ≥ 76 out of ~95)
- [ ] **OA proportion:** Match or exceed Dryad/Zenodo OA rates (~60-80%)
- [ ] **Schema validation:** 100% pass rate on 418 records
- [ ] **Pipeline integration:** Zero breaking changes to existing workflows

### Qualitative Targets
- [ ] **Code quality:** Follows existing patterns (Pydantic models, Prefect tasks, joblib caching)
- [ ] **Documentation:** Lab journal updated per protocol (7-point checklist)
- [ ] **Reproducibility:** All analyses runnable via notebooks with timestamped outputs
- [ ] **Presentation-ready:** HTML reports and charts suitable for Thursday talk

---

## Execution Timeline

### Recommended Agent Assignment

| Phase | Agent Type | Rationale | Duration |
|-------|-----------|-----------|----------|
| Phase 1: Audit | `explore` | Fast codebase understanding, no modifications | 1-2h |
| Phase 2: Schema | `general-purpose` | Complex refactor requiring full toolset | 3-4h |
| Phase 3: Module | `general-purpose` | New module creation + integration | 4-6h |
| Phase 4: Analysis | `task` (async) | Notebook execution + data processing | 2-3h |
| Phase 5: Benchmark | `general-purpose` + `task` | Code changes + long-running extractions | 4-6h |
| Phase 6: Docs | `task` | File updates, no complex logic | 1-2h |

**Total Estimated Effort:** 15-23 hours

### Parallel Execution Opportunities
- Phase 1 audit can inform Phase 2-3 simultaneously (2 agents)
- Phase 4 data retrieval can run async while Phase 5 evaluation code is written
- Phase 6 documentation can start once Phase 4 results are available

---

## Open Questions & Future Work

### Immediate Questions (address in Phase 1)
1. What proportion of SS records have usable DOIs in xlsx?
2. Are SS "url" fields parseable or require manual curation?
3. Do `cited_articles` being empty indicate unavailability or missing annotation?

### Future Enhancements (beyond current scope)
1. **Semantic Scholar API integration:** Retrieve cited articles programmatically (referenced in TODO.md)
2. **Grey literature expansion:** Expand beyond journal articles (TODO.md line 11)
3. **Front-end demo:** User testing interface for extraction results (work_plan.md line 19)
4. **Model comparison:** Abstract LLM interface for multi-provider support (work_plan.md line 20)

---

## References

**Task Files:**
- `tasks/integrate_semantic_scholar.md` - Primary requirements
- `TODO.md` - Task checklist and priorities
- `docs/results_presentation_20260219/work_plan.md` - Presentation requirements

**Codebase:**
- `CLAUDE.md` - Project architecture and patterns
- `notebooks/README.md` (lines 1027-1031) - SS exploration findings
- `src/llm_metadata/` - Existing module patterns
- `data/dataset_092624.xlsx` - Source data with SS records

**Related Plans:**
- `plans/article-full-text-chunking.md` - PDF processing workflow
- `plans/external_sources_refactor.md` - Data source integration patterns

---

## Appendix: Example Code Patterns

### A. Semantic Scholar Client (Phase 3)
```python
# src/llm_metadata/semantic_scholar.py
import re
from typing import Optional, Dict, List
from bs4 import BeautifulSoup
import requests

class SemanticScholarClient:
    """Retrieve metadata for Semantic Scholar-sourced datasets"""
    
    BASE_URL = "https://api.semanticscholar.org/graph/v1"
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.session = requests.Session()
        if api_key:
            self.session.headers["x-api-key"] = api_key
    
    def parse_xlsx_url(self, url: str) -> Dict[str, str]:
        """
        Extract metadata from xlsx url field.
        
        Args:
            url: Either journal landing page or SS search results URL
            
        Returns:
            Dict with keys: url_type, doi (if available), search_terms (if applicable)
            
        Examples:
            >>> parse_xlsx_url("https://doi.org/10.1234/example")
            {"url_type": "doi", "doi": "10.1234/example"}
            
            >>> parse_xlsx_url("https://semanticscholar.org/search?q=ecology")
            {"url_type": "search", "search_terms": "ecology"}
        """
        # Check for DOI pattern
        doi_match = re.search(r'10\.\d{4,}/[^\s]+', url)
        if doi_match:
            return {"url_type": "doi", "doi": doi_match.group(0)}
        
        # Check for SS search URL
        if "semanticscholar.org/search" in url:
            query = re.search(r'q=([^&]+)', url)
            return {
                "url_type": "search",
                "search_terms": query.group(1) if query else None
            }
        
        # Journal landing page (needs scraping)
        return {"url_type": "journal", "url": url}
    
    def resolve_doi_from_journal(self, journal_url: str) -> Optional[str]:
        """Extract DOI from journal page metadata"""
        try:
            response = self.session.get(journal_url, timeout=10)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Try meta tags
            doi_meta = soup.find('meta', {'name': 'citation_doi'})
            if doi_meta:
                return doi_meta.get('content')
            
            # Try DOI links
            doi_link = soup.find('a', href=re.compile(r'doi\.org'))
            if doi_link:
                doi = re.search(r'10\.\d{4,}/[^\s]+', doi_link['href'])
                return doi.group(0) if doi else None
        except Exception as e:
            print(f"Failed to resolve DOI from {journal_url}: {e}")
        
        return None
```

### B. Schema Extension (Phase 2)
```python
# schemas/validation.py (additions)
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, field_validator

class DataSource(str, Enum):
    """Data repository or search engine"""
    DRYAD = "dryad"
    ZENODO = "zenodo"
    SEMANTIC_SCHOLAR = "semantic_scholar"

class URLFields(BaseModel):
    """Unified URL structure supporting all sources"""
    
    source: DataSource = Field(
        description="Origin of the dataset record"
    )
    source_url: str = Field(
        description="Repository page or search engine URL"
    )
    journal_url: Optional[str] = Field(
        None,
        description="Article landing page on journal website"
    )
    pdf_url: Optional[str] = Field(
        None,
        description="Direct link to PDF if available"
    )
    is_oa: bool = Field(
        False,
        description="True if open access PDF available"
    )
    oa_license: Optional[str] = Field(
        None,
        description="License type (CC-BY, CC0, etc.)"
    )
    
    @field_validator('source_url', 'journal_url', 'pdf_url')
    @classmethod
    def validate_url(cls, v: Optional[str]) -> Optional[str]:
        """Ensure URLs are properly formatted"""
        if v is None:
            return v
        if not v.startswith(('http://', 'https://')):
            raise ValueError(f"URL must start with http:// or https://: {v}")
        return v

# Migration function for backward compatibility
def migrate_legacy_url_field(url: str, source: str) -> URLFields:
    """
    Convert old single 'url' field to new URLFields model.
    
    Args:
        url: Original URL from xlsx
        source: One of "dryad", "zenodo", "semantic_scholar"
    
    Returns:
        URLFields instance with populated fields
    """
    source_enum = DataSource(source)
    
    # Default: treat as source_url
    fields = URLFields(
        source=source_enum,
        source_url=url
    )
    
    # If URL contains doi.org, treat as journal_url
    if 'doi.org' in url and source_enum == DataSource.SEMANTIC_SCHOLAR:
        fields.journal_url = url
    
    return fields
```

### C. Evaluation Extension (Phase 5)
```python
# groundtruth_eval.py (additions)
import pandas as pd
from typing import Dict, List
from .schemas.validation import DataSource

def evaluate_by_source(
    predictions: pd.DataFrame,
    ground_truth: pd.DataFrame,
    sources: List[str],
    config: EvaluationConfig = None
) -> pd.DataFrame:
    """
    Compute precision/recall/F1 stratified by data source.
    
    Args:
        predictions: LLM extraction results with 'source' column
        ground_truth: Manual annotations with 'source' column
        sources: List of sources to evaluate (e.g., ["dryad", "zenodo"])
        config: Evaluation configuration (normalization, fuzzy matching)
    
    Returns:
        DataFrame with columns: [source, field, precision, recall, f1, support]
    """
    if config is None:
        config = EvaluationConfig()
    
    results = []
    
    for source in sources:
        # Filter to source-specific records
        pred_source = predictions[predictions['source'] == source]
        gt_source = ground_truth[ground_truth['source'] == source]
        
        # Compute metrics using existing evaluate_indexed()
        report = evaluate_indexed(
            pred_source,
            gt_source,
            config=config
        )
        
        # Add source column to results
        for field, metrics in report.field_metrics.items():
            results.append({
                'source': source,
                'field': field,
                'precision': metrics.precision,
                'recall': metrics.recall,
                'f1': metrics.f1,
                'support': metrics.support
            })
    
    return pd.DataFrame(results)

def generate_comparative_report(
    eval_df: pd.DataFrame,
    output_path: str
) -> None:
    """
    Generate HTML report comparing performance across sources.
    
    Creates:
    - Per-source summary tables
    - Field-level performance heatmaps
    - Statistical significance tests (χ² for categorical differences)
    """
    import plotly.express as px
    import plotly.graph_objects as go
    
    # Summary table
    summary = eval_df.groupby('source').agg({
        'precision': 'mean',
        'recall': 'mean',
        'f1': 'mean',
        'support': 'sum'
    }).round(3)
    
    # Heatmap by field and source
    pivot = eval_df.pivot(
        index='field',
        columns='source',
        values='f1'
    )
    
    fig = px.imshow(
        pivot,
        labels=dict(x="Data Source", y="Field", color="F1 Score"),
        aspect="auto",
        color_continuous_scale="RdYlGn"
    )
    
    # Write HTML report
    with open(output_path, 'w') as f:
        f.write("<h1>Source-Stratified Evaluation Report</h1>")
        f.write(summary.to_html())
        f.write(fig.to_html(full_html=False, include_plotlyjs='cdn'))
```

---

**End of Plan Document**

**Next Steps:**
1. Review this plan with stakeholders
2. Begin Phase 1 audit using `explore` agent
3. Create GitHub issue tracking completion of each phase
4. Update `notebooks/README.md` as phases complete

