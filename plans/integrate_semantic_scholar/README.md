# Semantic Scholar Integration - Task Documentation

> **Status:** Planning Complete ✅ | Ready for Implementation ⏭️  
> **Created:** 2026-02-17  
> **Deadline:** Thursday 2026-02-19 (Presentation)

## 📋 Document Index

This directory contains comprehensive planning documentation for integrating Semantic Scholar data into the llm_metadata pipeline.

### Quick Navigation

| Document | Purpose | Audience | Read Time |
|----------|---------|----------|-----------|
| **[integrate_semantic_scholar.md](./integrate_semantic_scholar.md)** | Original task requirements and context | Human stakeholders | 2 min |
| **[AGENT_EXECUTION_PLAN.md](./AGENT_EXECUTION_PLAN.md)** | Quick-start guide with commands | AI agents | 5 min |
| **[semantic_scholar_implementation_guide.md](./semantic_scholar_implementation_guide.md)** | Detailed 24-task breakdown | AI agents & developers | 30 min |
| **[VISUAL_OVERVIEW.md](./VISUAL_OVERVIEW.md)** | Architecture diagrams and timeline | Everyone | 10 min |
| **README.md** (this file) | Navigation and summary | Everyone | 3 min |

---

## 🎯 Quick Start

### For AI Agents Starting Work

**1. First time? Start here:**
```bash
Read: plans/VISUAL_OVERVIEW.md
# Get visual understanding of architecture and flow
```

**2. Ready to execute? Go here:**
```bash
Read: plans/AGENT_EXECUTION_PLAN.md
# Get your next task assignment and command to run
```

**3. Need task details? Reference this:**
```bash
Read: plans/semantic_scholar_implementation_guide.md
# Find your specific task (e.g., Task 2.1) with full specs
```

### For Human Reviewers

**Quick context:**
1. Start with `VISUAL_OVERVIEW.md` for architecture diagrams
2. Check progress in PR description (main tracking document)
3. Review `semantic_scholar_implementation_guide.md` for detailed plans

**What's being integrated:**
- 254 Semantic Scholar records (192 valid for analysis)
- +64% increase in evaluation dataset size
- Cross-source performance comparison capability
- Cited article retrieval functionality

---

## 🏗️ Architecture Overview

### Current State
```
Data Sources: Dryad (164) + Zenodo (135) = 299 valid records
Pipeline: 4-stage (Ingestion → Schema → LLM → Evaluation)
```

### Target State
```
Data Sources: Dryad (164) + Zenodo (135) + Semantic Scholar (192) = 491 valid records
Pipeline: Same 4-stage, extended for multi-source support
```

### Key Changes
1. **Multi-source schema** - Track data source for each record
2. **Semantic Scholar API client** - Follow OpenAlex pattern
3. **Extended URL fields** - Support source_url, journal_url, pdf_url
4. **PDF fallback chain** - Add Semantic Scholar as source
5. **Cross-source evaluation** - Compare performance by source

---

## 📋 Implementation Phases

### ✅ Phase 1: Audit (COMPLETE)
- Analyzed existing API clients (Dryad, Zenodo, OpenAlex)
- Documented schema structure and validation patterns
- Mapped PDF download pipeline and integration points

### ⏭️ Phase 2: Schema Refactoring (NEXT - Start Now)
- **Task 2.1**: Extend Pydantic schemas for multi-source support
- **Task 2.2**: Create Semantic Scholar API client
- **Task 2.3**: Update existing modules with source tracking

**Can start immediately:** Tasks 2.1 and 2.2 can run in parallel

### ⏸️ Phase 3: Pipeline Integration (Blocked by Phase 2)
- Parse and validate 254 Semantic Scholar records from Excel
- Implement cited article retrieval via API
- Integrate Semantic Scholar into PDF download fallback chain

### ⏸️ Phase 4: Coverage Analysis (Blocked by Phase 3)
- Compute metrics by source (total, valid, abstracts, PDFs, OA)
- Validate coverage goals (≥80% abstracts, ≥80% OA)
- Generate visualizations and export statistics

### ⏸️ Phase 5: Evaluation (Blocked by Phase 3)
- Run abstract extraction on Semantic Scholar records
- Run full-text extraction on Semantic Scholar PDFs
- **🎯 Task 5.3**: Update presentation materials (CRITICAL for Thursday)

### ⏸️ Phase 6: Documentation (Blocked by Phase 5)
- Update CLAUDE.md, notebooks/README.md, TODO.md
- Add comprehensive test coverage (≥80%)

---

## ⏱️ Timeline

| Phase | Sequential | With Parallelization | Status |
|-------|-----------|---------------------|--------|
| Phase 1 | 3h | 3h | ✅ Complete |
| Phase 2 | 7h | 3h | ⏭️ Ready |
| Phase 3 | 8h | 5h | ⏸️ Blocked |
| Phase 4 | 4h | 3h* | ⏸️ Blocked |
| Phase 5 | 8h | 5h* | ⏸️ Blocked |
| Phase 6 | 4h | 1.5h | ⏸️ Blocked |
| **Total** | **34h** | **20.5h** | - |

*Phases 4 and 5 can run partially in parallel

**Critical path to presentation:** 10-12 hours minimum

---

## 🎯 Success Criteria

### Data Integration
- [ ] 254 Semantic Scholar records loaded and validated
- [ ] 192 valid records identified (biodiversity-relevant)
- [ ] ≥80% have abstracts (≥154 records)
- [ ] ≥80% of PDFs are open access
- [ ] Coverage analysis shows source breakdown

### Code Quality
- [ ] Semantic Scholar API client follows project patterns
- [ ] Multi-source schema backward compatible
- [ ] Test coverage ≥80% for new code
- [ ] No regressions in existing tests
- [ ] All integration tests passing

### Research Output
- [ ] Abstract extraction runs on all sources
- [ ] Full-text extraction includes Semantic Scholar
- [ ] Cross-source performance comparison complete
- [ ] Presentation materials updated by Thursday
- [ ] Lab log entries document findings

---

## 🤖 Agent Assignment Guide

### By Agent Type

**explore agent:**
- Phase 1 audit tasks ✅ (complete)
- Phase 4 Task 4.2 (validate coverage goals)
- Phase 5 Task 5.3 (update presentation)
- Phase 6 Tasks 6.1, 6.2, 6.4 (documentation)

**general-purpose agent:**
- Phase 2 all tasks (schema, API, updates)
- Phase 3 all tasks (parsing, retrieval, PDF)
- Phase 4 Task 4.1 (coverage analysis)
- Phase 5 Tasks 5.1, 5.2 (evaluation)
- Phase 6 Task 6.3 (tests)

**task agent:**
- Phase 4 Task 4.1 (alternative to general-purpose)
- Useful for straightforward notebook execution

### Parallelization Strategy

**Round 1 (Now):**
- Task 2.1 (general-purpose) || Task 2.2 (general-purpose)

**Round 2:**
- Task 2.3 (general-purpose) - depends on 2.1

**Round 3:**
- Task 3.1 (general-purpose) - depends on 2.3

**Round 4:**
- Task 3.2 (general-purpose) || Task 3.3 (general-purpose)

**Round 5:**
- Task 4.1 (task) || Task 5.1 (general-purpose) || Task 5.2 (general-purpose)

**Round 6:**
- Task 4.2 (explore) → Task 5.3 (explore) 🎯

**Round 7 (Final):**
- Task 6.1 (explore) || Task 6.2 (explore) || Task 6.3 (general-purpose) || Task 6.4 (explore)

---

## 📦 Deliverables Checklist

### Code Changes
- [ ] `src/llm_metadata/semantic_scholar.py` (new)
- [ ] `src/llm_metadata/schemas/validation.py` (modified)
- [ ] `src/llm_metadata/dryad.py` (modified)
- [ ] `src/llm_metadata/zenodo.py` (modified)
- [ ] `src/llm_metadata/article_retrieval.py` (modified)
- [ ] `src/llm_metadata/pdf_download.py` (modified)
- [ ] `tests/test_semantic_scholar.py` (new)

### Notebooks
- [ ] `notebooks/semantic_scholar_data_integration.ipynb` (new)
- [ ] `notebooks/data_coverage_analysis.ipynb` (new/updated)
- [ ] `notebooks/fuster_test_extraction_evaluation.ipynb` (updated)
- [ ] `notebooks/fulltext_extraction_evaluation.ipynb` (updated)

### Data Files
- [ ] `data/dataset_092624_semantic_scholar_validated.xlsx`
- [ ] `data/semantic_scholar_cited_articles.csv`
- [ ] `notebooks/results/semantic_scholar_evaluation_[date]/`
- [ ] `notebooks/results/data_coverage_summary_[date]/`

### Documentation
- [ ] `CLAUDE.md` (Stage 1 updated with Semantic Scholar)
- [ ] `notebooks/README.md` (lab log entries)
- [ ] `TODO.md` (task status updates)
- [ ] `docs/results_presentation_20260219/work_plan.md` (presentation content) 🎯

---

## 🔍 Key Concepts

### Multi-Source Architecture
Track data origin for each record using `DataSource` enum:
```python
class DataSource(str, Enum):
    DRYAD = "dryad"
    ZENODO = "zenodo"
    SEMANTIC_SCHOLAR = "semantic_scholar"
```

### URL Field Structure
Different URL types for comprehensive tracking:
- `source_url`: Original search engine result URL
- `journal_url`: Direct journal article page
- `pdf_url`: Direct PDF download link
- `is_oa`: Boolean flag for open access status

### PDF Acquisition Fallback Chain
Extended chain with Semantic Scholar:
1. OpenAlex (direct OA)
2. **Semantic Scholar** ← NEW!
3. Unpaywall (green/gold OA)
4. EZproxy (institutional)
5. Sci-Hub (last resort)

### Conservative Extraction Philosophy
LLM prompt instructs: "Only extract explicitly stated information"
- Minimizes false positives
- Prioritizes precision over recall
- Better for data gap analysis use case

---

## ⚠️ Known Risks & Mitigations

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| API rate limits | Medium | Medium | Implement 1 req/sec limit, aggressive caching |
| Coverage goals not met | Low | Medium | Early validation in Task 3.1, contingency documented |
| Schema breaking changes | Low | High | Backward compatibility testing, careful validation |
| Timeline slip for presentation | Medium | High | Critical path identified, parallel execution planned |

---

## 📞 Communication Protocol

### Progress Reporting
Use `report_progress` tool after completing each meaningful unit:
- After finishing each task
- After resolving blocking issues
- When changing implementation approach
- Before and after major milestones

### Handoff Between Agents
When completing a task, include in commit message:
1. Task number and brief description
2. Changes made (files modified/added)
3. Issues encountered and solutions
4. Tasks unblocked by this work
5. Suggested next priority

Example:
```
✅ Task 2.1 Complete: Extended validation schema

Changes:
- Added DataSource enum
- Added 6 new optional fields to DatasetFeatures
- Updated validators with None handling
- Added 12 unit tests

Unblocked: Task 2.3 (Update Existing Modules)
Next: Wait for Task 2.2 or start 2.3
```

---

## 🚀 Getting Started

**For AI agents (next step):**
```bash
# Navigate to project
cd /home/runner/work/llm_metadata/llm_metadata

# Read execution plan
cat plans/AGENT_EXECUTION_PLAN.md

# Start Task 2.1 or 2.2 (or both in parallel)
# Follow commands in AGENT_EXECUTION_PLAN.md
```

**For human reviewers:**
1. Review PR description for current status
2. Check `VISUAL_OVERVIEW.md` for architecture understanding
3. Monitor `report_progress` commits for progress updates
4. Review implementation details in `semantic_scholar_implementation_guide.md`

---

## 📚 Additional Resources

### Project Documentation
- Main project docs: `../CLAUDE.md`
- Development workflow: `../CLAUDE.md` (Notebook-Based Experimentation)
- Lab logging protocol: `../notebooks/README.md`

### External APIs
- Semantic Scholar API: https://api.semanticscholar.org/api-docs/
- OpenAlex API: https://docs.openalex.org/
- Unpaywall API: https://unpaywall.org/products/api

### Related Plans
- `article-full-text-chunking.md` - Full-text processing architecture
- `external_sources_refactor.md` - PDF download pipeline insights
- `two-stage-evidence-extraction.md` - Evidence tracking approach

---

## ✅ Planning Phase Summary

**Completed:**
- ✅ Code audit of existing API clients and schemas
- ✅ Architecture review of PDF pipeline
- ✅ Detailed 24-task implementation plan
- ✅ Agent execution plan with parallelization strategy
- ✅ Visual overview with diagrams and timeline
- ✅ Dependency mapping and risk assessment
- ✅ Success criteria and deliverables defined

**Ready for:**
- ⏭️ Phase 2 implementation (Tasks 2.1 and 2.2 can start immediately)
- ⏭️ Agent delegation with clear task specifications
- ⏭️ Parallel execution to meet presentation deadline

---

**Last Updated:** 2026-02-17  
**Next Review:** After Phase 2 completion  
**Questions?** Refer to `semantic_scholar_implementation_guide.md` for detailed guidance
