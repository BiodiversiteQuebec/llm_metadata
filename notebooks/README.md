# Notebooks Log Book

This folder contains analysis and validation notebooks for ecological dataset characterization.

## Recent Activity

### 2026-01-06: Fuster et al. annotation cleaning and validation
**Task:** Cleaning and validation of manual annotations from `dataset_092624.xlsx` based on the Fuster et al. dataset feature description using pydantic and validation functions.

**Work Performed:**
- **Notebook:** `notebooks/fuster_annotations_validation.ipynb`
- **Architecture Simplification:** Migrated from a dual-layer (Pandera + Pydantic) system to a consolidated Pydantic-only validation engine. This reduced code complexity by 50% while maintaining strict data types.
- **Improved Data Cleaning:** Implemented global "before" validators to handle common annotator noise:
    - Normalization of European decimals (`0,5` -> `0.5`).
    - Suppression of placeholder values (`not given`, `NA`, `no`) into `None`.
    - Dynamic splitting and flattening of comma-separated lists for `data_type` and `geospatial_info`.
- **Vocabulary Support:** Added `species_richness` and refined fuzzy-matching for EBV Enums to improve mapping success.

**Result:**
Achieved **100% validation success** across all 418 rows of the input dataset.

**Output:**
Valid data stored as `data/dataset_092624_validated.xlsx`.

---

### 2026-01-07: Feature Extraction Evaluation Pipeline
**Task:** Build end-to-end pipeline to test GPT-based feature extraction against manual annotations and evaluate extraction quality.

**Work Performed:**
- **Notebook:** `notebooks/fuster_test_extraction_evaluation.ipynb`
- **Data Selection:** Filtered 5 Dryad records where `valid_yn='yes'` and `_position` columns contain 'abstract' (ensuring features were annotated from abstract text).
- **Validation:** Confirmed 100% schema compliance of test records against `DatasetFeatureExtraction` Pydantic model.
- **Automated Extraction:** Ran `gpt-4o-mini` classification on abstracts using structured output with `DatasetFeatureExtraction` schema.
- **Side-by-Side Comparison:** Built comparison DataFrame showing manual vs automated extractions for visual inspection.
- **Evaluation:** Used `evaluation.py` utilities (`evaluate_indexed`, `micro_average`, `macro_f1`) to compute precision/recall/F1 metrics.

**Results:**
| Metric | Value |
|--------|-------|
| Micro-average Precision | 0.333 |
| Micro-average Recall | 0.487 |
| Micro-average F1 | 0.396 |
| Macro-average F1 | 0.471 |

**Per-Field Performance:**
- **Strong:** `temp_range_i`, `temp_range_f` (F1 = 0.67), `species` (F1 = 0.61)
- **Weak:** `temporal_range` (F1 = NaN), `geospatial_info_dataset` (F1 = 0.21), `data_type` (F1 = 0.27)

**Key Issues Identified:**
1. **Vocabulary mismatch:** Manual annotations use free-text (e.g., "presence only, EBV genetic analysis") vs strict enums
2. **Over-extraction:** Model identifies more categories than annotators (high FP for `data_type`, `geospatial_info`)
3. **String vs semantic matching:** `temporal_range` fails exact match despite equivalent content

**Next Steps:**
- Implement vocabulary normalization mapping for `data_type`
- Add fuzzy matching for `temporal_range` and `species`
- Expand test set to all 11 abstract-annotated Dryad records
- Refine prompt with few-shot examples aligned to annotation guidelines

**Report:**
📊 [View HTML Report](results/fuster_test_extraction_evaluation_20260107_01/index.html)

---

### 2026-01-07: Model Change Experiment
**Task:** Test alternative model (`gpt-5-mini`) for feature extraction to compare performance. Model is way cheaper, than previous `gpt-4`.

**Work Performed:**
- **Notebook:** `notebooks/fuster_test_extraction_evaluation.ipynb`
- **Model Change:** Switched from `gpt-4` to `gpt-5-mini` in `classify_abstract()` call. Include new reasoning parameter (effort: "low") while loosing temperature setting. This is a new setting that can be played with for GPT-5 series models.
- **Configuration:** Maintained same extraction schema (`DatasetFeatureExtraction`).

**Results:**
| Metric | Value |
|--------|-------|
| Micro-average Precision | 0.296 |
| Micro-average Recall | 0.538 |
| Micro-average F1 | 0.382 |
| Macro-average F1 | 0.491 |

**Comparison to gpt-4o-mini:**
- Precision decreased: 0.333 → 0.296
- Recall increased: 0.487 → 0.538
- Micro F1 decreased: 0.396 → 0.382
- Macro F1 increased: 0.471 → 0.491

**Analysis:**
`gpt-5-mini` shows a tradeoff pattern: higher recall but lower precision compared to `gpt-4`. The model extracts more features (better coverage) but with more false positives. The macro F1 improvement suggests more balanced performance across different field types, though overall micro F1 is slightly lower. Big payoff will be done on the individual vocabulary normalization, fuzzy matching, and feature based prompt refinement.

**Next Steps:**
- Integrate vocabulary normalization and fuzzy matching as planned.
- Separate extraction and validation steps.
- Just ignore temporal_range exact matching for now.
- Implement evidence extraction for key fields to improve precision. ([chat-gpt discussion](https://chatgpt.com/share/695ed6c1-e640-8001-8318-612ebbedd8bd)). I want to understand better why the model made certain extraction decisions (looking at you `data_type` and `geospatial_info_dataset` fields.
- Feature-based prompt refinement with examples. Especially for `species`.

---

### 2026-01-07: Vocabulary Normalization & Fuzzy Matching
**Task:** Implement vocabulary normalization and fuzzy matching to improve evaluation accuracy.

**Work Performed:**
- **Notebook:** `notebooks/fuster_test_extraction_evaluation.ipynb`
- **Vocabulary Normalization:** Created mapping dictionaries for `data_type` → `EBVDataType` and `geospatial_info_dataset` → `GeospatialInfoType` enums
- **Fuzzy Matching:** Implemented `rapidfuzz`-based species matching with threshold=70 to handle taxonomic name variations
- **Dropped Temporal Fields:** Removed `temporal_range`, `temp_range_i`, `temp_range_f` from evaluation (not relevant for abstract-only extraction)

**Results (with normalization):**
| Metric | Value | Change |
|--------|-------|--------|
| Micro-average Precision | 0.293 | -1% |
| Micro-average Recall | 0.708 | +32% ⬆️ |
| Micro-average F1 | 0.415 | +9% ⬆️ |
| Macro-average F1 | 0.395 | -20% |

**Per-Field Performance:**
- **Species**: Recall = 1.0 (perfect!), F1 = 0.53 — Fuzzy matching dramatically improved recall
- **Spatial range**: Precision = 1.0, Recall = 0.25, F1 = 0.40 — Conservative extraction
- **Data type**: Precision = 0.27, Recall = 0.57, F1 = 0.36 — Over-extraction persists
- **Geospatial info**: Precision = 0.18, Recall = 0.75, F1 = 0.29 — Consistent over-prediction

**Key Findings:**
1. Fuzzy matching is highly effective for species field
2. Over-extraction of `data_type` and `geospatial_info_dataset` is semantic (model interpretation differs from annotators), not vocabulary mismatch
3. Temporal fields removed since abstract-only extraction doesn't reliably capture dates

**Next Steps:**
- Evidence extraction for model reasoning transparency
- Expand test set to all 11 Dryad records
- Prompt refinement with few-shot examples

---

### 2026-01-08: Article Full Text Retrieval Exploration
**Task:** Explore methods to retrieve full text articles associated with Dryad/Zenodo data papers from the Fuster et al. annotated dataset.

**Work Performed:**
- **Notebook:** `notebooks/article_fulltext_retrieval_exploration.ipynb`
- **Hypothesis Testing:** Evaluated three potential sources for article full text access:
  1. **H1: Full text in Excel** - Checked if `full_text` column contains article text or just abstracts
  2. **H2: Article URLs in Excel** - Searched for article DOIs/URLs in dataset columns
  3. **H3: Repository API metadata** - Queried Dryad/Zenodo APIs for article links

**Results:**

**Hypothesis 1 - Full Text Column:**
- ❌ The `full_text` column contains **abstracts only** (1.4k-2.8k characters)
- Not suitable for full article retrieval

**Hypothesis 2 - Article URLs in Excel:** ✅ **PRIMARY SOLUTION**
- ✅ **SUCCESS!** The `cited_articles` column contains DOI links to source articles
- Coverage across valid datasets (n=299):
  - **Dryad: 94.6%** (35/37 datasets have article DOIs)
  - **Zenodo: 56.7%** (38/67 datasets have article DOIs)
  - Semantic Scholar: 0% (expected, as these are already articles)
- **Overall coverage: 24.4%** (73/299 valid datasets)

**Hypothesis 3 - Repository API Metadata:** ✅ **FALLBACK SOLUTION**
- ✅ **Dryad API** provides article DOIs via `relatedWorks` field:
  - Relationship type: `"primary_article"`
  - Access: `dataset['relatedWorks'][0]['identifier']`
  - Example: `https://doi.org/10.1371/journal.pone.0128238`
- ✅ **Zenodo API** provides article DOIs via `related_identifiers` field:
  - Relationship type: `"isCitedBy"`
  - Access: `metadata['related_identifiers'][0]['identifier']`
  - Example: `10.1093/jhered/esx103`

**Tested Examples:**
| Dataset Source | Dataset DOI | Article DOI | Method |
|----------------|-------------|-------------|---------|
| Dryad ID 9 | `10.5061/dryad.1771t` | `10.1371/journal.pone.0128238` | Excel + API |
| Dryad ID 13 | `10.5061/dryad.24rj8` | `10.1639/0007-2745-119.1.008` | Excel + API |
| Zenodo ID 5 | `10.5061/dryad.121sk` | `10.1093/jhered/esx103` | Excel + API |

**Key Findings:**
1. **Recommended workflow:** First check `cited_articles` column (instant access), then fall back to API queries
2. **High success rate for Dryad:** 94.6% coverage means nearly all Dryad datasets can be linked to articles
3. **All article DOIs in standard format** ready for downstream tools (Unpaywall, Semantic Scholar, etc.)
4. **API provides same information:** Both Excel and API methods yield identical DOIs, confirming data reliability

**Next Steps:**
- Implement DOI-to-PDF retrieval using Unpaywall API (`https://api.unpaywall.org/v2/{doi}`)
- Build mapping database: `dataset_doi` → `article_doi` → `article_pdf_path`
- Handle open access detection (check `is_oa` and `oa_locations` from Unpaywall)
- Create batch download utility with progress tracking and error handling

---

### 2026-01-08: PDF Chunking and RAG Infrastructure Implementation
**Task:** Implement complete PDF-to-RAG pipeline infrastructure for full-text feature extraction from scientific articles.

**Work Performed:**
- **Architecture:** Implemented modular pipeline following `tasks/article-full-text-chunking.md` specification
- **Services:** Configured Docker Compose with GROBID (PDF parsing) and Qdrant (vector storage)
- **Core Modules:**
  1. `pdf_parsing.py` - GROBID client + TEI XML parsing with section hierarchy extraction
  2. `section_normalize.py` - Regex-based heading normalization to canonical section types
  3. `chunking.py` - Section-aware chunking with tiktoken token counting (target: 450, max: 650, overlap: 80 tokens)
  4. `embedding.py` - OpenAI text-embedding-3-large wrapper with JSONL caching
  5. `vector_store.py` - Qdrant client with filtered search and payload indexing
  6. `registry.py` - SQLite registry for document processing status tracking
- **Schemas:** Created `chunk_metadata.py` with Pydantic models for section/chunk metadata and integration with existing `OpenAlexWork`
- **Infrastructure:**
  - Updated `pyproject.toml` with dependencies: lxml, qdrant-client, tiktoken, rich, grobid-client-python
  - Created `.env` entries for GROBID_URL and QDRANT_URL
  - Initialized `data/registry.sqlite` with documents and chunks tables
  - Created `artifacts/tei/` and `artifacts/chunks/` directories
- **Notebook:** Created `notebooks/pdf_chunking_exploration.ipynb` for end-to-end pipeline testing

**Results:**
✓ All 10 core modules implemented (7 Python modules + 3 infrastructure files)
✓ Unit tests pass for section normalization (10/10 test cases)
✓ Chunking test: 2 chunks from 88-token sample (54+35 tokens, detecting equations/tables/figures)
✓ Registry database initialized with documents and chunks tables

**Architecture Highlights:**
- **Section-aware chunking:** Never crosses section boundaries, preserves semantic coherence
- **Token-based sizing:** Uses tiktoken for deterministic chunking compatible with OpenAI embeddings API
- **Idempotent pipeline:** SHA256-based caching for embeddings, registry-based status tracking
- **Rich metadata:** Chunk payloads include document, section, and content flags (equations, tables, figures)
- **Filtered retrieval:** Qdrant indexes on doi, publication_year, section_type, is_references, author_orcids

**Key Design Patterns:**
1. **Conservative extraction:** Follows Fuster methodology - only extract information explicitly supported by text
2. **Pydantic-first validation:** Unified schema layer for type safety and serialization
3. **Local-first processing:** Docker services for GROBID/Qdrant avoid vendor lock-in
4. **Notebook-driven development:** Per CLAUDE.md workflow, all testing/evaluation via notebooks

**Known Limitations (v1):**
- Tables and figures ignored (no structured extraction or OCR)
- GROBID dependency requires Docker (fallback: pymupdf for v1.1)
- No Prefect orchestration yet (manual batch processing only)
- Section classification uses regex patterns (could add ML-based fallback)

**Next Steps:**
1. Test full pipeline with actual Fuster dataset PDFs
2. Compare full-text vs abstract-only feature extraction quality
3. Measure throughput and OpenAI embedding costs for batch processing
4. Implement Prefect flow for automated batch processing
5. Evaluate RAG retrieval quality with section-type filtering

---

### 2026-01-08: PDF Chunking Pipeline - End-to-End Testing and Query Examples
**Task:** Debug and test complete PDF-to-RAG pipeline with semantic search and metadata filtering capabilities.

**Work Performed:**
- **Notebook:** `notebooks/pdf_chunking_exploration.ipynb`
- **Bug Fixes:**
  1. **GROBID API Call:** Replaced broken `grobid_client` CLI with direct REST API using `requests.post()` to `/api/processFulltextDocument`
  2. **Variable Naming Conflict:** Fixed Python scoping issue in `chunking.py` where loop variable `chunk_text` shadowed function name - renamed to `text_content`
  3. **Qdrant Point IDs:** Implemented `chunk_id_to_int()` using MD5 hash to convert string IDs to required integers, stored original IDs in payload as `chunk_id_str`
  4. **Qdrant API Updates:** Updated `search_chunks()` to use new `query_points()` method instead of deprecated `search()`, fixed `get_collection_stats()` with `hasattr()` checks
- **Feature Enhancements:**
  1. **Semantic Query Search:** Added natural language query example ("Provide a description of the datasets used within the study") with OpenAI embedding generation and relevance-ranked retrieval
  2. **Metadata Filtering:** Implemented three filtering patterns:
     - Filter by normalized section type (e.g., all DISCUSSION chunks)
     - Filter by raw section title keywords (e.g., sections containing "dataset")
     - Filter by content flags (e.g., chunks with figure mentions)
  3. **Enhanced Visualizations:** Added chunk count histogram by section type alongside token distribution plots

**Pipeline Test Results:**
| Stage | Status | Details |
|-------|--------|---------|
| GROBID Parsing | ✓ | Extracted 23 sections from test PDF (10.1002_ece3.1476.pdf, 6.3 MB) |
| Section Normalization | ✓ | Classified sections: 18 OTHER, 3 DISCUSSION, 2 INTRO, 1 ABSTRACT, 1 CONCLUSION |
| Chunking | ✓ | Generated 25 chunks, avg 359 tokens (range: 7-649), 60% with figure mentions |
| Embeddings | ✓ | Created 3072-dimensional vectors using text-embedding-3-large, cached to JSONL |
| Qdrant Indexing | ✓ | Stored 25 points with full metadata payload |
| Retrieval | ✓ | Both semantic and metadata-based queries working |
| Registry | ✓ | Document tracked in SQLite with SHA256 hash |

**Semantic Search Example:**
Query: *"Provide a description of the datasets used within the study"*
- **Top Match (Score: 0.4119):** "Ecological survey dataset" section with detailed methodology description
- **Key Finding:** Raw section titles preserved in payload enable semantic matching on section names
- Successfully retrieved 5 relevant chunks describing datasets, sampling methods, and data sources

**Metadata Filtering Examples:**
1. **Section Type Filter:** Retrieved 3 DISCUSSION chunks (all 548-628 tokens)
2. **Section Title Filter:** Found 3 chunks with "dataset" in title (Forest survey, Ecological survey, Ecological district)
3. **Content Flag Filter:** Retrieved 5 chunks with `has_figure_mention=True`

**Key Insights:**
- **Dual metadata storage** (raw `section_title` + normalized `section_type`) provides flexibility for both semantic and categorical queries
- **Section-aware chunking** preserves context boundaries (no cross-section splits)
- **Token-based sizing** ensures chunks fit within embedding model limits (8191 tokens for text-embedding-3-large)
- **Metadata filtering** offers fast structural queries without embedding overhead

**Performance Metrics:**
- Parsing time: ~20 seconds for 6.3 MB PDF
- Chunking: <1 second for 25 chunks
- Embedding generation: ~2 seconds for 25 chunks (with caching)
- Indexing: ~13 seconds (includes collection recreation)
- Retrieval: <200ms per query

**Next Steps:**
1. Batch process all Fuster dataset PDFs (~73 articles with DOIs)
2. Compare RAG-based feature extraction vs abstract-only extraction
3. Implement hybrid search (semantic + metadata filtering combined)
4. Add citation formatting with section path in RAG responses
5. Evaluate retrieval quality with precision@k metrics

---

### 2026-01-08: PDF Retrieval Infrastructure for Fuster Dataset Articles
**Task:** Implement robust PDF download pipeline for scientific articles linked to Dryad datasets with multiple fallback strategies.

**Work Performed:**
- **Notebook:** `notebooks/download_dryad_pdfs_fuster.ipynb`
- **Infrastructure Modules:**
  1. `openalex.py` - OpenAlex API integration for work metadata and PDF URL extraction
  2. `pdf_download.py` - Multi-strategy PDF downloader with `download_pdf_with_fallback()` function
  3. `ezproxy.py` - Browser cookie extraction for university proxy authentication
- **Download Strategies (in order):**
  1. **OpenAlex PDF URL** - Direct download from publisher-provided open access links
  2. **Unpaywall API fallback** - Query alternative OA locations if primary URL fails
  3. **EZProxy retry** - Attempt download through institutional proxy with browser cookies
- **Workflow Improvements:**
  - Single-pass OpenAlex API calls with caching (eliminates redundant requests)
  - Proper error handling and status tracking for each download attempt
  - Manifest CSV generation for tracking download success/failure
  - Polite API usage with rate limiting (1s between OpenAlex calls, 0.5s between downloads)

**Dataset Integration:**
- Loaded `data/dataset_article_mapping.csv` (created from Hypothesis 2 work on 2026-01-08)
- Filtered to Dryad datasets with valid article DOIs (35/37 = 94.6% coverage)
- Sample processing: 5 randomly selected works for testing

**Results:**
| Status | Count | Details |
|--------|-------|---------|
| Downloaded | Variable | Success depends on OA status and proxy configuration |
| No OpenAlex work | 0 | All DOIs resolved successfully |
| Failed | Variable | Expected for closed-access articles without proxy |

**Key Features:**
- **Fallback resilience:** Three-tier strategy maximizes retrieval success
- **Institutional access:** EZProxy support enables retrieval of subscription-only articles when browser cookies available
- **Metadata preservation:** Tracks OpenAlex ID, OA status, PDF URL source, and download path
- **Output organization:** PDFs saved to `data/pdfs/fuster/` with DOI-based filenames

**Dependencies Added:**
- `playwright` for browser automation (optional, for cookie extraction)
- `browser-cookie3` for reading browser cookies (Firefox/Chrome/Edge)

**Manifest Structure:**
```csv
article_doi, dataset_doi, title, openalex_id, oa_status, openalex_pdf_url, downloaded_pdf_path, status, error
```

**Troubleshooting Guide Included:**
1. Set `OPENALEX_EMAIL` in `.env` for Unpaywall API (polite pool access)
2. Run browser-based authentication first, then extract cookies
3. Expect failures for closed-access articles without institutional access

**Next Steps:**
0. Debug notebook with EZProxy (certificate issues)
1. Batch download all fuster OA articles
2. Monitor download success rates across OA status categories
3. Process full Fuster dataset (all 35 Dryad + 38 Zenodo article DOIs)
4. Build article_doi → PDF path mapping for RAG indexing
5. Workaround when doi points to Wiley direct PDF link (https://onlinelibrary-wiley-com.ezproxy.usherbrooke.ca/doi/pdfdirect/10.1111/fwb.13497?download=true)

---

### 2026-01-09: Sci-Hub Integration for PDF Download Fallback
**Task:** Integrate Sci-Hub as an additional fallback strategy for downloading paywalled articles when OpenAlex, Unpaywall, and EZproxy methods fail.

**Work Performed:**
- **Notebook:** `notebooks/download_all_fuster_pdfs.ipynb`
- **Module Addition:** Integrated `scihub.py` module (forked from [zaytoun/scihub.py](https://github.com/zaytoun/scihub.py/)) into `src/llm_metadata/`
- **Fallback Strategy:** Extended `download_pdf_with_fallback()` to include Sci-Hub as fourth-tier fallback:
  1. OpenAlex PDF URL (open access)
  2. Unpaywall API (green/gold OA)
  3. EZproxy authentication (institutional access)
  4. **Sci-Hub (last resort for paywalled content)**
- **Implementation Details:** 
  - Sci-Hub attempts to resolve DOI → PDF via sci-hub.io mirror network
  - Includes retry logic and automatic mirror switching on connection failures
  - SSL verification disabled for compatibility with Sci-Hub mirrors
  - User-Agent rotation to avoid rate limiting
  - Forked from existing Sci-Hub Python client for simplicity https://github.com/zaytoun/scihub.py

**Key Features:**
- **Automatic mirror selection:** Queries sci-hub.now.sh for active mirror list
- **Robust error handling:** Falls back gracefully if Sci-Hub is unavailable
- **Citation tracking:** Logs which download strategy succeeded in manifest

**Legal/Ethical Note:**
Sci-Hub operates in a legal grey area. Use prioritizes open access and institutional channels first. Sci-Hub fallback is intended for research purposes where legitimate access methods are exhausted.