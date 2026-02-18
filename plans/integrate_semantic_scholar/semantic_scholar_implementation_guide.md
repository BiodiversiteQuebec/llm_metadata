# Semantic Scholar Integration: Detailed Implementation Guide

> **Created:** 2026-02-17  
> **Context:** Agentic implementation plan for integrating Semantic Scholar data into llm_metadata pipeline  
> **Status:** Active Implementation

## Overview

This document provides detailed, task-by-task guidance for implementing Semantic Scholar integration into the llm_metadata project. Each task is designed to be assigned to an AI agent with clear inputs, outputs, and acceptance criteria.

---

## Phase 1: Code Audit & Architecture Review

### Task 1.1: Audit Existing Data Ingestion Modules

**Agent Type:** `explore`

**Objective:** Document the architecture patterns of existing API client modules to ensure consistency.

**Inputs:**
- `src/llm_metadata/dryad.py`
- `src/llm_metadata/zenodo.py`
- `src/llm_metadata/openalex.py`
- `src/llm_metadata/unpaywall.py`

**Tasks:**
1. Examine each module's structure and identify common patterns:
   - Base URL configuration
   - Authentication handling (tokens, API keys)
   - Request parameter building
   - Response parsing and return types
   - Error handling strategies
   - Caching mechanisms (joblib Memory)
2. Document API response structures for each service
3. Identify interface inconsistencies to avoid

**Outputs:**
- Architecture summary document (markdown) in `/tmp/api_audit_summary.md`
- List of patterns to follow for Semantic Scholar client
- List of anti-patterns to avoid

**Acceptance Criteria:**
- ✅ All 4 API modules reviewed
- ✅ Common patterns identified and documented
- ✅ Return type conventions clearly stated
- ✅ Caching strategy documented

---

### Task 1.2: Audit Validation and Schema Modules

**Agent Type:** `explore`

**Objective:** Understand current schema structure and identify extension points for multi-source support.

**Inputs:**
- `src/llm_metadata/schemas/validation.py`
- `src/llm_metadata/schemas/fuster_features.py`
- `data/dataset_092624.xlsx` (understand current column structure)

**Tasks:**
1. Review `DatasetFeatures` Pydantic model fields
2. Identify how data sources are currently tracked (if at all)
3. Document URL field structure and conventions
4. Examine validation logic for enum fields
5. Check how optional vs required fields are handled

**Outputs:**
- Schema analysis document in `/tmp/schema_audit.md`
- Proposed new fields for multi-source support
- Field validation strategy recommendations

**Acceptance Criteria:**
- ✅ Current URL field handling documented
- ✅ Source tracking approach identified
- ✅ Proposed schema extensions listed
- ✅ Validation strategy for new fields defined

---

### Task 1.3: Audit PDF Download Pipeline

**Agent Type:** `explore`

**Objective:** Understand the PDF acquisition fallback chain to confirm Semantic Scholar records can be processed without pipeline modification.

**Inputs:**
- `src/llm_metadata/pdf_download.py`
- `plans/external_sources_refactor.md`
- `notebooks/README.md` (lines 1020-1031 for Semantic Scholar notes)

**Tasks:**
1. Document the current fallback chain order (OpenAlex → Unpaywall → EZproxy → Sci-Hub)
2. Confirm that `download_pdf_with_fallback()` accepts any DOI regardless of source
3. Review success rate tracking mechanisms
4. Examine error handling and retry logic
5. Note configuration values (timeouts, size limits)

**Outputs:**
- PDF pipeline analysis in `/tmp/pdf_pipeline_audit.md`
- Confirmation that existing chain handles Semantic Scholar DOIs without changes
- Configuration values cataloged for reference

**Acceptance Criteria:**
- ✅ Fallback chain documented
- ✅ Confirmed no modifications needed for Semantic Scholar records
- ✅ Configuration values cataloged

---

## Phase 2: Data Schema Refactoring

### Task 2.1: Extend Validation Schema for Multi-Source Support

**Agent Type:** `general-purpose`

**Objective:** Modify Pydantic schemas to support multiple data sources with appropriate URL fields.

**Inputs:**
- Audit outputs from Task 1.2
- `src/llm_metadata/schemas/validation.py`
- `src/llm_metadata/schemas/fuster_features.py`
- Excel column analysis from notebooks

**Tasks:**
1. Add `DataSource` enum to `validation.py`:
   ```python
   class DataSource(str, Enum):
       DRYAD = "dryad"
       ZENODO = "zenodo"
       SEMANTIC_SCHOLAR = "semantic_scholar"
   ```
2. Add new fields to `DatasetFeatures`:
   - `source: DataSource` (required)
   - `source_url: Optional[HttpUrl]` (URL from search engine)
   - `journal_url: Optional[HttpUrl]` (direct journal page)
   - `pdf_url: Optional[HttpUrl]` (direct PDF link if available)
   - `is_oa: Optional[bool]` (open access flag)
   - `cited_article_doi: Optional[str]` (related article DOI)
3. Update field validators to handle new combinations
4. Ensure backward compatibility with existing data

**Outputs:**
- Modified `schemas/validation.py` with new fields
- Modified `schemas/fuster_features.py` if needed
- Unit tests for new field validation

**Acceptance Criteria:**
- ✅ Enum values match data sources
- ✅ URL fields properly typed with Pydantic HttpUrl
- ✅ Validators handle None/empty values gracefully
- ✅ Existing tests still pass
- ✅ New tests validate multi-source scenarios

---

### Task 2.2: Create Semantic Scholar API Client Module

**Agent Type:** `general-purpose`

**Objective:** Implement a robust Semantic Scholar API client following project patterns.

**Inputs:**
- API audit from Task 1.1
- Semantic Scholar API documentation: https://api.semanticscholar.org/api-docs/
- Pattern reference: `src/llm_metadata/openalex.py`

**Tasks:**
1. Create `src/llm_metadata/semantic_scholar.py`
2. Implement core functions:
   ```python
   def get_paper_by_doi(doi: str) -> Optional[Dict[str, Any]]
   def get_paper_by_title(title: str) -> Optional[Dict[str, Any]]
   def get_paper_citations(paper_id: str, limit: int = 100) -> List[Dict[str, Any]]
   def get_paper_references(paper_id: str, limit: int = 100) -> List[Dict[str, Any]]
   ```
3. Follow these patterns:
   - Use joblib Memory for caching
   - Include polite rate limiting (1 req/sec)
   - Use `requests.raise_for_status()` for error handling
   - Return `None` on 404, raise on other errors
   - Include docstrings with examples
4. Add configuration:
   - API key support via environment variable
   - Base URL constant
   - Timeout settings

**Outputs:**
- New file: `src/llm_metadata/semantic_scholar.py`
- Unit tests: `tests/test_semantic_scholar.py` (with mocked responses)
- API usage examples in docstrings

**Acceptance Criteria:**
- ✅ Matches OpenAlex module structure
- ✅ All core functions implemented
- ✅ Caching works correctly
- ✅ Rate limiting prevents API abuse
- ✅ Error handling is consistent
- ✅ Tests achieve >80% coverage

---

### Task 2.3: Update Existing Modules for Source Tracking

**Agent Type:** `general-purpose`

**Objective:** Ensure all data ingestion modules consistently track their source.

**Inputs:**
- Updated schema from Task 2.1
- `src/llm_metadata/dryad.py`
- `src/llm_metadata/zenodo.py`
- `src/llm_metadata/article_retrieval.py`

**Tasks:**
1. Modify `dryad.py`:
   - Add `source=DataSource.DRYAD` to all returned data structures
   - Ensure URL fields map correctly
2. Modify `zenodo.py`:
   - Add `source=DataSource.ZENODO` to all returned data structures
   - Ensure URL fields map correctly
3. Update `article_retrieval.py`:
   - Handle source field in DOI matching logic
   - Support Semantic Scholar article retrieval

**Outputs:**
- Modified source files with source tracking
- Updated tests for modified functions
- Migration notes for existing data

**Acceptance Criteria:**
- ✅ All data sources tracked consistently
- ✅ No breaking changes to existing workflows
- ✅ Tests verify source field presence
- ✅ URL fields properly mapped

---

## Phase 3: Data Processing Pipeline Integration

### Task 3.1: Parse and Validate Semantic Scholar Records from xlsx

> **Merged with:** Presentation work plan WU-A2 ("Validate All-Source Ground Truth Data").
> This task is now executed as part of WU-A2. The implementation edits the existing
> `notebooks/fuster_annotations_validation.ipynb` instead of creating a new notebook.

**Agent Type:** `general-purpose`

**Objective:** Load all data (Dryad+Zenodo+SS) from the Excel file and validate against updated schemas. SS-specific concerns (URL parsing, source filtering) are handled within the same notebook.

**Inputs:**
- `data/dataset_092624.xlsx`
- Updated schemas from Phase 2 / WU-A1
- Existing notebook: `notebooks/fuster_annotations_validation.ipynb`

**Tasks:**
1. Edit `notebooks/fuster_annotations_validation.ipynb` (do NOT create a new notebook)
2. Load and validate ALL records (Dryad+Zenodo+SS) through updated `DatasetFeaturesNormalized`
3. Parse URL fields for SS records:
   - Extract journal URLs vs Semantic Scholar search URLs
   - Map to appropriate schema fields
   - Handle empty/malformed URLs
4. Filter to valid records (~491 across all sources)
5. Compute coverage stats by source: records, with abstracts, with DOIs, with `cited_articles`
6. Validation error breakdown by source
7. Export: `data/dataset_092624_validated.xlsx`

**Outputs:**
- Updated notebook: `notebooks/fuster_annotations_validation.ipynb`
- Validated data: `data/dataset_092624_validated.xlsx`
- Statistics report (in notebook output)
- Log entry in `notebooks/README.md`

**Acceptance Criteria:**
- ✅ All records processed (Dryad+Zenodo+SS, including 254 SS records)
- ✅ Validation errors clearly documented, broken down by source
- ✅ URL fields correctly mapped for SS records
- ✅ Statistics show ≥80% of SS records have abstracts
- ✅ Existing notebook extended (not a new notebook)

---

### Task 3.2: Implement Cited Article Retrieval Workflow

**Agent Type:** `general-purpose`

**Objective:** Use Semantic Scholar API to retrieve cited articles for datasets.

**Inputs:**
- Semantic Scholar API client from Task 2.2
- Validated data from Task 3.1
- Pattern: `src/llm_metadata/article_retrieval.py`

**Tasks:**
1. Create function to retrieve cited articles:
   ```python
   def get_cited_articles_for_dataset(
       dataset_title: str,
       dataset_doi: Optional[str] = None
   ) -> List[Dict[str, Any]]:
       """Retrieve cited articles using Semantic Scholar API."""
   ```
2. Add to Prefect pipeline if exists, or create standalone workflow
3. Process Semantic Scholar records:
   - Search by dataset title or DOI
   - Retrieve citing papers
   - Extract article DOIs and metadata
   - Store in `data/semantic_scholar_cited_articles.csv`
4. Handle edge cases:
   - No results found
   - Multiple matching papers
   - Rate limit errors
5. Generate mapping file similar to `data/dataset_article_mapping.csv`

**Outputs:**
- Function in appropriate module (or new `src/llm_metadata/semantic_scholar_retrieval.py`)
- Mapping file: `data/semantic_scholar_cited_articles.csv`
- Notebook demonstrating usage
- Statistics on retrieval success rate

**Acceptance Criteria:**
- ✅ Function handles all edge cases
- ✅ Rate limiting prevents API errors
- ✅ Mapping file follows existing conventions
- ✅ Retrieval success rate documented
- ✅ Failed retrievals logged with reasons

---

### Note on PDF Download for Semantic Scholar Records

PDF acquisition for Semantic Scholar records does **not** require modifying `pdf_download.py`. The existing fallback chain (OpenAlex → Unpaywall → EZproxy → Sci-Hub) is applied to the DOIs of Semantic Scholar records directly, exactly as it is for Dryad and Zenodo records. Semantic Scholar's `openAccessPdf` field draws from the same open access repositories already covered by Unpaywall and OpenAlex, making a dedicated step redundant. PDF success rates will be reported as part of Task 4.1.

---

## Phase 4: Data Coverage Analysis

### Task 4.1: Create Data Coverage Analysis Notebook

**Agent Type:** `task` (for running analysis) or `general-purpose` (for creating notebook)

**Objective:** Generate comprehensive statistics on data coverage across all sources.

**Inputs:**
- Validated data from all sources
- `data/dataset_092624_validated.xlsx`
- `data/semantic_scholar_cited_articles.csv`
- PDF download logs

**Tasks:**
1. Create or update notebook: `notebooks/data_coverage_analysis.ipynb`
2. Compute metrics by source (Dryad, Zenodo, Semantic Scholar):
   ```python
   metrics = {
       'total_records': len(df),
       'valid_records': len(df[df['valid_yn'] == 'valid']),
       'has_abstract': len(df[df['abstract'].notna()]),
       'has_cited_doi': len(df[df['cited_article_doi'].notna()]),
       'has_pdf': len(df[df['pdf_downloaded'] == True]),
       'is_oa': len(df[df['is_oa'] == True])
   }
   ```
3. Calculate proportions and percentages
4. Create visualizations:
   - Bar chart: Records by source
   - Pie chart: OA proportion by source
   - Table: Detailed metrics comparison
5. Export summary statistics:
   - `notebooks/results/data_coverage_summary_[date]/summary_table.csv`
   - `notebooks/results/data_coverage_summary_[date]/figures/`

**Outputs:**
- Notebook with analysis
- Summary statistics CSV
- Visualization figures (PNG/SVG)
- Lab log entry in `notebooks/README.md`

**Acceptance Criteria:**
- ✅ All three sources analyzed
- ✅ Semantic Scholar shows ≥80% abstract coverage
- ✅ OA proportion documented and compared
- ✅ Visualizations are clear and publication-ready
- ✅ Results exported for presentation use

---

### Task 4.2: Validate Coverage Goals

**Agent Type:** `explore` or `task`

**Objective:** Verify that integration meets the stated coverage goals.

**Inputs:**
- Analysis outputs from Task 4.1
- Goals from `plans/integrate_semantic_scholar.md`

**Tasks:**
1. Check abstract coverage goal:
   - Target: ≥80% of valid records
   - Compare actual vs target
   - Document any gaps
2. Check PDF/OA coverage goal:
   - Target: ≥80% of valid records with PDFs are OA
   - Compare actual vs target
   - Document access barriers
3. Compare OA proportion across sources:
   - Calculate significance of differences
   - Identify best sources for open access
4. Document limitations:
   - API restrictions
   - Missing data patterns
   - Retrieval failures

**Outputs:**
- Coverage validation report (markdown)
- Gap analysis with recommendations
- Updated presentation materials

**Acceptance Criteria:**
- ✅ All goals validated against metrics
- ✅ Gaps clearly documented with reasons
- ✅ Recommendations for improvement provided
- ✅ Results suitable for presentation

---

## Phase 5: Evaluation Pipeline Integration

### Task 5.1: Update Evaluation Notebooks for Semantic Scholar

**Agent Type:** `general-purpose`

**Objective:** Extend abstract extraction evaluation to include Semantic Scholar records.

**Inputs:**
- Validated Semantic Scholar data
- `notebooks/fuster_test_extraction_evaluation.ipynb`
- `src/llm_metadata/gpt_classify.py`
- `src/llm_metadata/groundtruth_eval.py`

**Tasks:**
1. Extend existing notebook or create new section
2. Load all validated data (including Semantic Scholar)
3. Run abstract extraction on Semantic Scholar records:
   ```python
   for idx, row in ss_df.iterrows():
       result = classify_abstract(row['abstract'])
       predictions.append(result)
   ```
4. Compute evaluation metrics:
   - Precision, Recall, F1 per field
   - Aggregate metrics by source
   - Statistical comparison across sources
5. Generate comparative report:
   - Side-by-side examples
   - Error analysis by source
   - Feature-level performance comparison

**Outputs:**
- Updated/new notebook with Semantic Scholar evaluation
- Evaluation report: `notebooks/results/semantic_scholar_evaluation_[date]/index.html`
- Metrics summary CSV
- Lab log entry

**Acceptance Criteria:**
- ✅ All Semantic Scholar records evaluated
- ✅ Metrics computed per source
- ✅ Report includes cross-source comparison
- ✅ Examples illustrate differences
- ✅ Results reproducible

---

### Task 5.2: Full-Text Evaluation with Semantic Scholar Data

**Agent Type:** `general-purpose`

**Objective:** Process Semantic Scholar PDFs and evaluate full-text extraction.

**Inputs:**
- Downloaded PDFs from Semantic Scholar
- `notebooks/fulltext_extraction_evaluation.ipynb`
- GROBID service (Docker)
- `src/llm_metadata/pdf_parsing.py`

**Tasks:**
1. Process Semantic Scholar PDFs:
   - Parse with GROBID
   - Extract sections
   - Chunk and embed
2. Run full-text extraction:
   - Section-based approach
   - Compare with abstract-only results
3. Evaluate against ground truth:
   - Compute metrics
   - Compare extraction quality
   - Analyze error patterns
4. Generate comparative analysis:
   - Abstract vs full-text by source
   - Performance by document quality
   - Cost-benefit analysis

**Outputs:**
- Updated full-text evaluation notebook
- Evaluation report with Semantic Scholar results
- Comparative metrics table
- Lab log entry

**Acceptance Criteria:**
- ✅ Semantic Scholar PDFs processed
- ✅ Full-text extraction evaluated
- ✅ Comparison with abstract-only shown
- ✅ Source-specific patterns identified
- ✅ Results inform best practices

---

### Task 5.3: Update Presentation Materials

**Agent Type:** `explore` or `general-purpose`

**Objective:** Integrate Semantic Scholar results into presentation materials.

**Inputs:**
- All evaluation outputs from Phase 4 and 5
- `docs/results_presentation_20260219/work_plan.md`
- Coverage analysis from Task 4.1

**Tasks:**
1. Update Methods section:
   - Add Semantic Scholar data description
   - Update sample size numbers
   - Add source breakdown table
2. Update Results section:
   - Add cross-source comparison figures
   - Include Semantic Scholar performance metrics
   - Add OA proportion comparison
3. Create new figures for presentation:
   - Data source pie chart
   - Performance by source bar chart
   - Coverage heatmap
4. Update discussion points:
   - Source-specific insights
   - Generalizability of results
   - Future work recommendations

**Outputs:**
- Updated `work_plan.md`
- New figures in presentation-ready format
- Updated metrics tables
- Speaking notes for presentation

**Acceptance Criteria:**
- ✅ All sections updated with Semantic Scholar data
- ✅ Figures are publication-quality
- ✅ Numbers are accurate and current
- ✅ Narrative integrates new findings
- ✅ Presentation ready for Thursday delivery

---

## Phase 6: Documentation & Testing

### Task 6.1: Update CLAUDE.md

**Agent Type:** `explore`

**Objective:** Document the Semantic Scholar integration in project documentation.

**Inputs:**
- All implementation outputs
- Current `CLAUDE.md`
- API patterns from Task 1.1

**Tasks:**
1. Add Semantic Scholar to Stage 1 (Data Ingestion):
   - Module description
   - Key functions
   - Usage patterns
2. Update multi-source architecture section:
   - Document source tracking approach
   - Explain URL field conventions
   - Note validation patterns
3. Add troubleshooting section:
   - Common API errors
   - Rate limiting guidance
   - Fallback strategies
4. Update data files section:
   - List new CSV files
   - Document validation outputs
5. Add example commands:
   - Running Semantic Scholar retrieval
   - Validating multi-source data

**Outputs:**
- Updated `CLAUDE.md`
- No breaking changes to existing documentation

**Acceptance Criteria:**
- ✅ Semantic Scholar thoroughly documented
- ✅ Multi-source patterns explained
- ✅ Examples are executable
- ✅ Troubleshooting covers common issues
- ✅ Consistent with existing documentation style

---

### Task 6.2: Update notebooks/README.md

**Agent Type:** `explore`

**Objective:** Add lab log entries documenting the integration work.

**Inputs:**
- All notebook outputs
- Metrics from Phase 4 and 5
- Current `notebooks/README.md`

**Tasks:**
1. Add date header for integration work
2. Write lab log entries following template:
   - Task description
   - Work performed
   - Results (quantitative metrics)
   - Key issues identified
   - Next steps
   - Report links
3. Include key findings:
   - Coverage statistics
   - Extraction performance
   - API integration learnings
   - Data quality insights

**Outputs:**
- Updated `notebooks/README.md`
- Well-formatted entries with metrics

**Acceptance Criteria:**
- ✅ Entries follow lab logging protocol
- ✅ Metrics are clearly presented
- ✅ Links to reports work
- ✅ Findings are actionable
- ✅ Chronological order maintained

---

### Task 6.3: Add Tests for New Functionality

**Agent Type:** `general-purpose`

**Objective:** Ensure code quality with comprehensive test coverage.

**Inputs:**
- New modules from Phase 2
- Test patterns from existing tests
- `tests/` directory

**Tasks:**
1. Unit tests for `semantic_scholar.py`:
   - Mock API responses
   - Test error handling
   - Verify caching
   - Test rate limiting
2. Integration tests for multi-source validation:
   - Test schema validation with each source
   - Test URL field combinations
   - Test enum values
3. Test data coverage functions:
   - Verify metric calculations
   - Test filtering logic
   - Check edge cases
4. Run full test suite:
   - Ensure no regressions
   - Fix any broken tests
   - Achieve ≥80% coverage for new code

**Outputs:**
- New test files as needed
- Updated existing tests
- Test coverage report
- All tests passing

**Acceptance Criteria:**
- ✅ New code has ≥80% test coverage
- ✅ All tests pass
- ✅ Mock API responses realistic
- ✅ Edge cases covered
- ✅ Integration tests verify end-to-end flow

---

### Task 6.4: Update TODO.md

**Agent Type:** `explore`

**Objective:** Reflect completion status and identify follow-up work.

**Inputs:**
- Current `TODO.md`
- Completed tasks from all phases
- Issues identified during implementation

**Tasks:**
1. Mark completed tasks:
   - [x] Semantic Scholar data integration sub-tasks
   - Update task status
2. Add new follow-up tasks identified:
   - Performance improvements
   - Additional data sources
   - API enhancements
3. Reorganize priorities:
   - Move completed to Done section
   - Promote important next steps
4. Add notes on lessons learned:
   - API integration patterns
   - Validation strategies
   - Testing approaches

**Outputs:**
- Updated `TODO.md`
- Clear prioritization
- Context for future work

**Acceptance Criteria:**
- ✅ Completed tasks marked
- ✅ New tasks from implementation added
- ✅ Priorities reflect current state
- ✅ Notes provide context

---

## Agent Delegation Guidelines

### Recommended Agent Types by Phase

**Phase 1 (Audit):**
- Agent: `explore`
- Rationale: Fast exploration and documentation without code changes
- Parallel execution: All 3 tasks can run in parallel

**Phase 2 (Schema Refactoring):**
- Agent: `general-purpose`
- Rationale: Complex code changes requiring full toolset
- Execution: Task 2.2 can start in parallel with 2.1; Task 2.3 depends on 2.1 completion

**Phase 3 (Pipeline Integration):**
- Agent: `general-purpose`
- Rationale: Multi-step data processing and API integration
- Execution: Sequential — Task 3.2 depends on 3.1; no pdf_download.py modification required (use existing chain on Semantic Scholar DOIs)

**Phase 4 (Coverage Analysis):**
- Agent: `task` for notebook execution, `general-purpose` for notebook creation
- Rationale: Straightforward analysis with clear success/failure
- Execution: Can run in parallel with Phase 5 once data is ready

**Phase 5 (Evaluation):**
- Agent: `general-purpose`
- Rationale: Complex evaluation logic and report generation
- Execution: Tasks 5.1 and 5.2 can run in parallel once data from 3.1 is ready; 5.3 requires both complete

**Phase 6 (Documentation):**
- Agent: `explore` for documentation, `task` for test execution
- Rationale: Fast documentation updates, validation of test suite
- Execution: All tasks can run in parallel

### Handoff Protocol

When delegating to an agent:
1. Provide this document as context
2. Reference specific task number (e.g., "Execute Task 2.2")
3. Include all listed inputs
4. Verify acceptance criteria before marking complete
5. Save outputs to specified locations
6. Update progress in the main task tracking document

### Dependencies Between Tasks

```
1.1, 1.2, 1.3 (Parallel)
     ↓
2.1 ← 1.2
     ↓
2.2 ← 1.1 (can start in parallel with 2.1)
     ↓
2.3 ← 2.1
     ↓
3.1 ← 2.1, 2.3
     ↓
3.2 ← 2.2, 3.1
     ↓
4.1 ← 3.1, 3.2   (PDF downloads run existing chain on SS DOIs, no new task)
     ↓
4.2 ← 4.1
     ↓
5.1, 5.2 ← 3.1 (parallel after data ready)
     ↓
5.3 ← 5.1, 5.2
     ↓
6.1, 6.2, 6.3, 6.4 (Parallel after all implementation done)
```

---

## Risk Mitigation

### Identified Risks

1. **API Rate Limits**
   - Risk: Semantic Scholar API may throttle requests
   - Mitigation: Implement 1 req/sec rate limit, use caching aggressively

2. **Data Quality Issues**
   - Risk: Semantic Scholar records may have missing/malformed data
   - Mitigation: Robust validation with clear error messages, manual review of edge cases

3. **Schema Migration**
   - Risk: Breaking changes to existing workflows
   - Mitigation: Ensure backward compatibility, comprehensive testing

4. **Coverage Goals Not Met**
   - Risk: Semantic Scholar data may not meet 80% thresholds
   - Mitigation: Early validation in Task 3.1, contingency plan to expand data sources

5. **Integration Complexity**
   - Risk: Multi-source schema changes may introduce regressions in existing Dryad/Zenodo workflows
   - Mitigation: Backward-compatible schema extensions, no changes to pdf_download.py, thorough testing of existing workflows

---

## Success Metrics Summary

| Metric | Target | Validation Point |
|--------|--------|------------------|
| Semantic Scholar records loaded | 254 | Task 3.1 |
| Valid records | 192 | Task 3.1 |
| Abstract coverage | ≥80% (154 records) | Task 4.1 |
| PDF availability (via existing fallback chain) | Report actual % | Task 4.1 |
| OA proportion | ≥80% of PDFs | Task 4.2 |
| API client test coverage | ≥80% | Task 6.3 |
| Integration tests passing | 100% | Task 6.3 |
| Evaluation complete | All sources | Task 5.1, 5.2 |
| Documentation updated | All sections | Task 6.1, 6.2 |

---

## Timeline Estimates

| Phase | Estimated Time | Critical Path |
|-------|----------------|---------------|
| Phase 1 | 2-3 hours | Yes (blocks Phase 2) |
| Phase 2 | 6-8 hours | Yes (blocks Phase 3) |
| Phase 3 | 5-7 hours | Yes (blocks Phase 4, 5) |
| Phase 4 | 3-4 hours | Partial (blocks 5.3) |
| Phase 5 | 6-8 hours | Yes (blocks 6, presentation) |
| Phase 6 | 3-4 hours | No (can overlap) |
| **Total** | **25-34 hours** | **Critical: 20-26 hours** |

With parallel execution and agent delegation, wall clock time could be reduced to 13-18 hours.

---

## Questions for Human Review

Before starting implementation, clarify:

1. **API Access**: Do we have a Semantic Scholar API key? Is there a rate limit?
2. **Data Priority**: Should we prioritize abstract coverage or PDF coverage if we can't achieve both?
3. **Presentation Deadline**: Confirm Thursday presentation deadline and required outputs
4. **Validation Threshold**: Is 80% coverage a hard requirement or aspirational goal?
5. **Testing Scope**: Should we add integration tests for all data sources or just Semantic Scholar?

---

## References

- Semantic Scholar API Docs: https://api.semanticscholar.org/api-docs/
- Project Architecture: `/home/runner/work/llm_metadata/llm_metadata/CLAUDE.md`
- Task Context: `/home/runner/work/llm_metadata/llm_metadata/plans/integrate_semantic_scholar.md`
- Notebook Conventions: `/home/runner/work/llm_metadata/llm_metadata/notebooks/README.md`
