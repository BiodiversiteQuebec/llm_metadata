# Semantic Scholar Integration: Visual Overview

## 📊 Project Context

```
┌─────────────────────────────────────────────────────────────────┐
│  LLM Metadata Pipeline (4-Stage Architecture)                   │
│                                                                   │
│  Stage 1: Data Ingestion & Preparation                          │
│  ├─ Dryad API Client ✅                                          │
│  ├─ Zenodo API Client ✅                                         │
│  └─ Semantic Scholar API Client ❌ ← THIS INTEGRATION           │
│                                                                   │
│  Stage 2: Schema & Prompt Engineering                           │
│  ├─ Pydantic Models ⚠️  (needs extension for multi-source)      │
│  └─ Validation Framework ⚠️ (needs source tracking)             │
│                                                                   │
│  Stage 3: LLM Inference & Batch Processing                      │
│  └─ Classification Pipeline ✅ (ready for Semantic Scholar)      │
│                                                                   │
│  Stage 4: Evaluation & Validation                               │
│  └─ Metrics & Reports ✅ (ready for cross-source comparison)     │
└─────────────────────────────────────────────────────────────────┘
```

## 🎯 Integration Goals

```
┌──────────────────────────────────────────────────────────────┐
│  CURRENT STATE                    TARGET STATE                │
│  ───────────────                  ────────────                │
│                                                                │
│  Data Sources:                    Data Sources:               │
│  • Dryad: 164 records             • Dryad: 164 records        │
│  • Zenodo: 135 records            • Zenodo: 135 records       │
│  • Semantic Scholar: 0 ❌          • Semantic Scholar: 254 ✅   │
│                                     (192 valid for analysis)  │
│  Total: 299 valid records         Total: 491 valid records   │
│                                                                │
│  Coverage Goals:                                               │
│  ✅ ≥80% of valid SS records have abstracts                    │
│  ✅ ≥80% of valid SS PDFs are open access                      │
│  ✅ Cross-source performance comparison                        │
└──────────────────────────────────────────────────────────────┘
```

## 🏗️ Architecture: Multi-Source Data Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                         DATA INGESTION LAYER                         │
└─────────────────────────────────────────────────────────────────────┘
         │                    │                      │
         ▼                    ▼                      ▼
    ┌─────────┐         ┌─────────┐          ┌───────────────┐
    │  Dryad  │         │ Zenodo  │          │    Semantic   │
    │   API   │         │   API   │          │   Scholar API │
    └─────────┘         └─────────┘          └───────────────┘
         │                    │                      │
         │ add_source:        │ add_source:          │ add_source:
         │ DRYAD              │ ZENODO               │ SEMANTIC_SCHOLAR
         │                    │                      │
         ▼                    ▼                      ▼
    ┌────────────────────────────────────────────────────────┐
    │         UNIFIED DATA MODEL (Pydantic)                  │
    │                                                          │
    │  Required Fields:      Optional Fields:                 │
    │  • title               • source_url                     │
    │  • abstract            • journal_url                    │
    │  • valid_yn            • pdf_url                        │
    │  • source ← NEW!       • is_oa ← NEW!                   │
    │                        • cited_article_doi ← NEW!       │
    └────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      VALIDATION & PROCESSING                         │
│  • Schema validation (Pydantic)                                      │
│  • URL parsing and categorization                                    │
│  • Open access status checking                                       │
│  • Cited article retrieval                                           │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     PDF ACQUISITION PIPELINE                         │
│  Fallback Chain:                                                     │
│  1. OpenAlex (direct OA)                                             │
│  2. Semantic Scholar ← NEW!                                          │
│  3. Unpaywall (green/gold OA)                                        │
│  4. EZproxy (institutional)                                          │
│  5. Sci-Hub (last resort)                                            │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                  EXTRACTION & EVALUATION                             │
│  • Abstract-based extraction                                         │
│  • Full-text extraction (GROBID → Sections → LLM)                   │
│  • Cross-source performance comparison                               │
│  • Coverage analysis by source                                       │
└─────────────────────────────────────────────────────────────────────┘
```

## 📋 Implementation Phases (Visual Timeline)

```
Timeline (with parallelization):
───────────────────────────────────────────────────────────────────

Week 1:
Day 1-2  │ PHASE 1: Audit ✅                                  │ 3h
         │ (explore agent - COMPLETED)                        │
         └─────────────────────────────────────────────────────┘
         
Day 2-3  │ PHASE 2: Schema Refactoring ⏭️                     │ 7h
         │ ┌──────────────┐  ┌─────────────────┐              │
         │ │ Task 2.1     │  │ Task 2.2        │ (parallel)   │
         │ │ Extend       │  │ Create SS API   │              │
         │ │ Schema (2h)  │  │ Client (3h)     │              │
         │ └──────┬───────┘  └────────┬────────┘              │
         │        └─────────┬──────────┘                       │
         │                  ▼                                  │
         │         ┌────────────────┐                          │
         │         │ Task 2.3       │                          │
         │         │ Update Modules │                          │
         │         │ (2h)           │                          │
         │         └────────────────┘                          │
         └─────────────────────────────────────────────────────┘

Week 1-2:
Day 3-4  │ PHASE 3: Pipeline Integration                      │ 8h
         │         ┌────────────────┐                          │
         │         │ Task 3.1       │                          │
         │         │ (merged into   │                          │
         │         │  WU-A2)        │                          │
         │         └────────┬───────┘                          │
         │                  ▼                                  │
         │ ┌────────────────┴────────────────┐                │
         │ │                                  │                │
         │ ▼                                  ▼                │
         │ ┌──────────────┐     ┌────────────────┐            │
         │ │ Task 3.2     │     │ Task 3.3       │ (parallel) │
         │ │ Cited Arts   │     │ PDF Download   │            │
         │ │ (3h)         │     │ (2h)           │            │
         │ └──────────────┘     └────────────────┘            │
         └─────────────────────────────────────────────────────┘

Week 2:
Day 5-6  │ PHASE 4: Coverage Analysis (parallel with Phase 5) │ 4h
         │ ┌──────────────┐     ┌────────────────┐            │
         │ │ Task 4.1     │────▶│ Task 4.2       │            │
         │ │ Analysis     │     │ Validate Goals │            │
         │ │ (3h)         │     │ (1h)           │            │
         │ └──────────────┘     └────────────────┘            │
         │                                                     │
Day 5-7  │ PHASE 5: Evaluation Integration                    │ 8h
         │ ┌──────────────┐     ┌────────────────┐            │
         │ │ Task 5.1     │     │ Task 5.2       │ (parallel) │
         │ │ Abstract     │     │ Full-text      │            │
         │ │ Eval (3h)    │     │ Eval (3h)      │            │
         │ └──────┬───────┘     └────────┬───────┘            │
         │        └─────────┬────────────┘                    │
         │                  ▼                                  │
         │         ┌────────────────┐                          │
         │         │ Task 5.3       │ 🎯 CRITICAL              │
         │         │ Update Pres.   │                          │
         │         │ (2h)           │                          │
         │         └────────────────┘                          │
         └─────────────────────────────────────────────────────┘

Day 7-8  │ PHASE 6: Documentation & Testing (all parallel)    │ 4h
         │ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐               │
         │ │ 6.1  │ │ 6.2  │ │ 6.3  │ │ 6.4  │               │
         │ │CLAUDE│ │README│ │Tests │ │TODO  │               │
         │ │(1h)  │ │(1h)  │ │(1.5h)│ │(0.5h)│               │
         │ └──────┘ └──────┘ └──────┘ └──────┘               │
         └─────────────────────────────────────────────────────┘

Total: ~31h sequential, ~18-20h with optimal parallelization
```

## 🤖 Agent Assignment Strategy

```
┌──────────────────────────────────────────────────────────────┐
│ PHASE                    AGENT TYPE           COMPLEXITY      │
├──────────────────────────────────────────────────────────────┤
│ Phase 1: Audit ✅          explore             Low           │
│                                                               │
│ Phase 2: Schema           general-purpose      Medium-High   │
│   Task 2.1 ⚡               general-purpose      Medium       │
│   Task 2.2 ⚡               general-purpose      High         │
│   Task 2.3                general-purpose      Low           │
│                                                               │
│ Phase 3: Pipeline         general-purpose      Medium        │
│   Task 3.1                merged into WU-A2     —             │
│   Task 3.2                general-purpose      Medium        │
│   Task 3.3                general-purpose      Medium        │
│                                                               │
│ Phase 4: Coverage         task/general-purpose Low           │
│   Task 4.1                task                  Low          │
│   Task 4.2                explore              Low           │
│                                                               │
│ Phase 5: Evaluation       general-purpose      High          │
│   Task 5.1                general-purpose      High          │
│   Task 5.2                general-purpose      High          │
│   Task 5.3 🎯              explore/general      Medium       │
│                                                               │
│ Phase 6: Docs/Tests       explore/task         Low-Medium    │
│   Task 6.1                explore              Low           │
│   Task 6.2                explore              Low           │
│   Task 6.3                general-purpose      Medium        │
│   Task 6.4                explore              Low           │
└──────────────────────────────────────────────────────────────┘

Legend:
⚡ = Can start immediately (not blocked)
🎯 = Critical for presentation deadline
```

## 🔄 Dependency Flow Diagram

```
                    START
                      │
                      ▼
        ┌─────────────────────────┐
        │  Phase 1: Audit ✅       │
        │  (explore agent)         │
        │  Tasks 1.1, 1.2, 1.3     │
        └──────────┬──────────────┘
                   │
        ┌──────────┴──────────┐
        │                     │
        ▼                     ▼
   ┌─────────┐          ┌──────────┐
   │ Task    │          │ Task     │    ⚡ CAN START NOW
   │ 2.1     │          │ 2.2      │    (both in parallel)
   │ Schema  │          │ SS API   │
   └────┬────┘          └─────┬────┘
        │                     │
        │    ┌────────────────┘
        │    │
        ▼    ▼
   ┌──────────┐
   │ Task 2.3 │
   │ Update   │
   │ Modules  │
   └─────┬────┘
         │
         ▼
   ┌──────────┐
   │ Task 3.1 │
   │ (merged  │
   │ → WU-A2) │
   └────┬─────┘
        │
        └────────┬────────────┐
                 │            │
                 ▼            ▼
          ┌──────────┐  ┌──────────┐
          │ Task 3.2 │  │ Task 3.3 │  (parallel)
          │ Cited    │  │ PDF      │
          │ Articles │  │ Download │
          └────┬─────┘  └────┬─────┘
               │             │
        ┌──────┴─────┬───────┴──────┐
        │            │              │
        ▼            ▼              ▼
   ┌─────────┐  ┌─────────┐  ┌─────────┐
   │ Task    │  │ Task    │  │ Task    │  (all parallel)
   │ 4.1     │  │ 5.1     │  │ 5.2     │
   │ Coverage│  │ Abstract│  │ Fulltext│
   │ Analysis│  │ Eval    │  │ Eval    │
   └────┬────┘  └────┬────┘  └────┬────┘
        │            │            │
        ▼            └─────┬──────┘
   ┌─────────┐            │
   │ Task    │            │
   │ 4.2     │◀───────────┘
   │ Validate│
   └────┬────┘
        │
        ▼
   ┌──────────┐
   │ Task 5.3 │ 🎯 CRITICAL FOR PRESENTATION
   │ Update   │
   │ Slides   │
   └────┬─────┘
        │
        ▼
   ┌──────────────────────────────────┐
   │  Phase 6: Final Documentation    │
   │  Tasks 6.1, 6.2, 6.3, 6.4        │  (all parallel)
   └────────────┬─────────────────────┘
                │
                ▼
              DONE ✅
```

## 📊 Success Metrics Dashboard

```
┌─────────────────────────────────────────────────────────────┐
│  INTEGRATION SUCCESS METRICS                                 │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  Data Coverage:                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ Semantic Scholar Records Loaded:    254 / 254  ✅    │    │
│  │ Valid for Analysis:                 192 / 254  ✅    │    │
│  │ Abstract Coverage:                  ≥80%       🎯    │    │
│  │ PDF Coverage:                       TBD        🎯    │    │
│  │ Open Access (of PDFs):              ≥80%       🎯    │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                               │
│  Code Quality:                                               │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ API Client Test Coverage:           ≥80%       🎯    │    │
│  │ Integration Tests Passing:          100%       🎯    │    │
│  │ No Regressions:                     ✅         🎯    │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                               │
│  Deliverables:                                               │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ ☐ Semantic Scholar API client                       │    │
│  │ ☐ Extended validation schemas                       │    │
│  │ ☐ Data coverage analysis notebook                   │    │
│  │ ☐ Cross-source evaluation reports                   │    │
│  │ ☐ Updated presentation materials 🎯                  │    │
│  │ ☐ Comprehensive documentation                       │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘

Legend: 🎯 = Target to meet  |  ✅ = Completed
```

## 🚀 Quick Start Commands

```bash
# For agents starting Phase 2 (next steps):

# Option 1: Start Task 2.1 (Schema Extension)
cd /home/runner/work/llm_metadata/llm_metadata
task explore "Execute Task 2.1 from plans/semantic_scholar_implementation_guide.md"

# Option 2: Start Task 2.2 (API Client)
cd /home/runner/work/llm_metadata/llm_metadata
task explore "Execute Task 2.2 from plans/semantic_scholar_implementation_guide.md"

# Option 3: Both in parallel (recommended)
# Launch two agents simultaneously with above commands
```

## 📚 Document Navigation

```
plans/
├── integrate_semantic_scholar.md              ← Original requirements
├── semantic_scholar_implementation_guide.md   ← 24 detailed tasks
├── AGENT_EXECUTION_PLAN.md                   ← Quick-start guide
└── VISUAL_OVERVIEW.md (this file)            ← Visual summary
```

**For quick orientation:** Start here (VISUAL_OVERVIEW.md)  
**For execution:** Use AGENT_EXECUTION_PLAN.md  
**For task details:** Reference semantic_scholar_implementation_guide.md  
**For context:** Read integrate_semantic_scholar.md

---

**Current Status:** Planning ✅ | Ready for Phase 2 ⏭️

**Next Action:** Execute Task 2.1 and/or 2.2 with `general-purpose` agents
