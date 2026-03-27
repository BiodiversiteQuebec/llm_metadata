# Research MCP Server

**Status:** Draft  
**Date:** 2026-03-09

## Project Purpose

This plan defines a **self-standing research library** that will be exposed through an MCP interface and reused by other projects.

The project is not a thin wrapper around one repository's notebooks. It is meant to become a reusable research substrate for agents and applications that need to:

- discover papers
- retrieve papers and metadata
- parse and inspect full text
- build searchable local corpora
- preserve provenance
- assemble structured literature-review artifacts
- support downstream claim grounding and scientific writing

The MCP interface is the delivery surface. The real project is the underlying library: reusable research services, typed models, artifact conventions, and provenance-aware workflows.

An important constraint for the project is that it must save its artifacts in the **client project**, not in the research library's own repository state. The library should behave like infrastructure used by another project, and all durable outputs should belong to that client project's workspace.

## Important Academic Research Tasks

Academic research work repeatedly requires a common set of tasks that are operationally important and too often handled in an ad hoc way.

### Discovery and scoping

- search the scholarly landscape for relevant papers
- expand from one paper into citations, references, and related work
- identify which papers are likely central, peripheral, or redundant

### Acquisition and inspection

- resolve identifiers and metadata across sources
- retrieve abstracts and, when possible, PDFs
- record access failures and coverage gaps rather than silently dropping papers

### Reading and evidence gathering

- parse papers into inspectable sections
- locate the parts of papers that support specific concepts, claims, methods, or results
- move from whole-document reading to targeted retrieval over sections and chunks

### Research synthesis

- distinguish verified source content from analyst inference
- build source matrices, notes, and structured literature summaries
- compare papers along shared dimensions such as task, method, dataset, evaluation, and relevance

### Downstream writing and analysis

- collect evidence packets for related-work writing
- gather candidate passages for claim grounding
- preserve enough provenance that later arguments in notes, plans, or manuscripts can be traced back to sources
- iteratively refine a research direction, not just answer one-shot lookup requests

### Research framing and thread pursuit

- help define a project by proposing and refining search keywords
- expand outward from a seed paper, seed author, or seed concept
- pursue a thread through:
  - highly cited papers
  - references and citations
  - repeated authors
  - recurring journals
  - closely related concepts
- produce provisional judgments about:
  - which papers appear central
  - which authors appear influential
  - which journals appear most relevant
- make those judgments explicitly traceable to retrieved evidence rather than presenting them as opaque model preference

These are not optional convenience tasks. They are core research operations. When they are weakly supported, literature work becomes less reproducible, less auditable, and less useful for later analysis and writing.

## Target Research Flow

This project is motivated by a concrete research workflow that should be first-class and repeatable.

### Flow

1. Discover candidate papers.
2. Resolve them into normalized records.
3. Retrieve source text and PDFs when available.
4. Parse papers into sections and other structured artifacts.
5. Build local corpora from parsed content.
6. Retrieve relevant passages semantically instead of relying only on manual rereading.
7. Produce durable intermediate artifacts:
   - source matrices
   - reading packets
   - grounded notes
   - claim-support context bundles
   - keyword sets and search trails
   - thread-expansion summaries
   - ranked candidate papers / authors / journals with rationale
8. Feed those artifacts into downstream tasks such as:
   - project planning
   - literature synthesis
   - claim grounding
   - notebook experimentation
   - scientific paper drafting

### Quality requirements

The research workflow should make it easy to:

- reproduce paper discovery and retrieval
- preserve provenance at every step
- distinguish verified source material from model inference
- move from retrieval to parsing to corpus search without rebuilding context manually
- produce structured intermediate artifacts instead of ephemeral notebook state

### Current gaps this project is meant to fix

- weak reproducibility
- weak provenance
- weak separation between retrieval and synthesis
- weak support for durable literature-review artifacts
- too much dependence on ad hoc notebook state and analyst memory
- weak support for iterative research exploration across papers, authors, and citation threads

## Existing Work We Can Reuse

This repository already contains substantial research-oriented capabilities that can seed the new project:

- scholarly metadata lookup (`openalex.py`, `semantic_scholar.py`)
- PDF acquisition (`pdf_download.py`, `unpaywall.py`, `ezproxy.py`)
- full-text parsing via GROBID (`pdf_parsing.py`)
- chunking (`chunking.py`)
- embedding and vector retrieval (`embedding.py`, `vector_store.py`)

These capabilities are valuable, but today they are mostly exposed as project modules and notebooks. They are useful for exploratory work inside this repository, but not yet packaged as a reusable library that other projects can depend on.

The new project should therefore begin by extracting and hardening those capabilities behind stable service boundaries and typed outputs.

## Client Project Artifact Model

The library should treat the calling project as the home for durable state.

Artifacts that should be saved in the **client project** include:

- downloaded PDFs
- parsed TEI / document artifacts
- chunk artifacts
- vector-store state or collection metadata
- embeddings cache where applicable
- source matrices
- paper synthesis notes
- reading packets
- thread-expansion outputs
- claim-grounding context bundles

This is a core design requirement, not an implementation detail.

Implications:

- the library should accept an explicit client workspace or project root
- artifact paths should be derived from that client project
- the library should not default to saving research outputs inside the MCP server project's own repo
- outputs should be organized predictably so they can be inspected, versioned, or ignored by the client project as needed

Suggested client artifact structure:

- `research/papers/`
- `research/pdfs/`
- `research/parsed/`
- `research/chunks/`
- `research/vector/`
- `research/matrices/`
- `research/notes/`
- `research/threads/`
- `research/synthesis/`
- `research/cache/`

## Problem Statement

We need a reusable research library, exposed through an MCP interface, that turns the existing retrieval, parsing, chunking, and search work into **durable research tools**.

The MCP server should make it possible to perform the research tasks that are currently awkward, fragile, or insufficiently structured:

- run reproducible paper search over OpenAlex and Semantic Scholar instead of ad hoc discovery
- resolve papers into normalized, provenance-rich records instead of loose notes
- retrieve OA PDFs and capture failure provenance when access fails
- parse papers into section-aware text that can actually be inspected and cited
- build local corpora that can be semantically searched across papers, not only read one by one
- generate source-matrix-ready rows so literature review work becomes auditable
- separate verified source evidence from agent inference
- gather candidate passages for downstream claim grounding instead of jumping directly from paper to narrative synthesis
- iteratively grow a research corpus inside the client project instead of treating each request as stateless
- help define a project by proposing, refining, and tracking relevant search keywords
- pursue a research thread across citations, references, authors, journals, and related concepts
- generate provisional rankings and opinions about best papers, authors, and journals, together with explicit rationale and provenance
- support later writing tasks for scientific papers by preserving citations, excerpts, sections, and retrieval lineage

The project should be judged not only by whether it can "search papers," but by whether it improves the quality of the end-to-end research workflow.

## MCP Motivation

The MCP interface is the right surface for this project because the goal is not only to ship internal helper functions. The goal is to expose research capabilities as reusable tools that other agents and projects can call in a structured way.

MCP is valuable here because it allows the library to provide:

- stable tool contracts
- typed inputs and outputs
- reusable research primitives across projects
- structured provenance-bearing payloads
- a clean boundary between the research library and downstream agent workflows

The library should remain usable directly from Python, but MCP is the interface that makes the project portable and composable beyond this repository.

## Expected User Experience

The project should be designed around a real research workflow, not only around individual tools.

### Example user journey

The user is developing a new ecological research project on species distribution modelling.

1. The user creates a new project folder.
2. The user sets up the research MCP for that project.
3. The user writes initial research questions, intuitions, and rough methodological ideas in project docs.
4. The user places three already-downloaded papers into the project's PDF folder.
5. Through Codex or Claude Code, the user asks the system to:
   - ingest those PDFs
   - parse them
   - chunk them
   - index them into the project's vector store
6. The user asks methodological questions about those papers to sharpen their intuition.
7. The system helps write a methodological summary grounded in the processed papers.
8. The user asks for more relevant papers.
9. The system searches, downloads, parses, and adds those papers to the same project research workspace.
10. The system updates the project corpus, source matrix, and synthesis artifacts.
11. Later, the user wants to investigate a new methodological idea.
12. The user starts a focused review around that idea:
    - refine search vocabulary
    - discover new papers
    - ingest them into the existing project corpus
    - write a review or synthesis for that subtopic

### UX expectations implied by this workflow

The system should feel iterative and project-aware.

That means:

- the user should be able to start from a partially populated project, not only from zero
- previously added PDFs and indexed papers should remain part of the working corpus
- project documents, notes, search keywords, and synthesis artifacts should accumulate coherently over time
- the same project should support both:
  - broad literature building
  - narrow methodological deep dives

### What the user experience should support well

- **Project initialization**
  - declare project root
  - initialize research workspace layout
  - register where PDFs, parsed artifacts, vector state, notes, and synthesis docs live

- **Local corpus bootstrapping**
  - start from papers the user already has
  - ingest local PDFs without forcing external search first
  - build a usable vector store early

- **Conversational methodological exploration**
  - answer questions over the project's current corpus
  - surface quotes, sections, and paper provenance
  - help the user refine intuition rather than only dump summaries

- **Synthesis writing**
  - produce methodological summaries and scoped reviews
  - save them in project space as durable artifacts
  - connect every synthesis back to supporting papers and excerpts

- **Corpus growth**
  - search for missing or adjacent papers
  - ingest new papers into the same project
  - update matrices, notes, and search trails as the corpus evolves

- **Focused review threads**
  - allow the user to branch into a subtopic or new idea
  - refine vocabulary and search terms
  - run a targeted mini-review without losing the broader project context

### Design consequences

This expected UX implies several non-negotiable design choices:

- the research workspace must be **project-scoped**
- ingestion of **local PDFs** must be a first-class workflow
- the vector store must support **incremental growth**
- synthesis artifacts must be **saved back into the client project**
- search, retrieval, indexing, and synthesis should all be usable in an **iterative loop**
- the system should support both:
  - question answering over current corpus
  - expansion of the corpus when the current corpus is insufficient

This is a stronger target than "paper search plus chunk retrieval." The intended UX is closer to a project-level research companion with durable memory, provenance, and corpus growth.

## Goals

- Reuse existing repository modules rather than duplicating pipeline logic
- Expose research primitives as MCP tools with typed, provenance-aware outputs
- Support both one-off paper lookup and iterative corpus building
- Make outputs useful for notebooks, claim grounding, and scientific paper drafting
- Keep the server general enough to reuse outside biodiversity workflows

## Non-Goals

- Replacing the existing extraction pipeline
- Turning the MCP server into a full agent framework
- Building a generic citation manager
- Solving every access / paywall problem
- Mixing domain-specific extraction prompts into the general research tool surface

## Key Design Decisions

- The MCP server should wrap existing modules, not fork them.
- Tool outputs should be **structured and provenance-rich**.
- General research tools should be separated from biodiversity-specific extraction logic.
- Corpus state should live in existing durable stores where possible:
  - in this library's source project, existing code may still use `data/` and `artifacts/`
  - in the new standalone project, durable outputs should be redirected into the **client project's research workspace**
- The first version should prefer **read / retrieve / parse / index / search** tools over writing-heavy orchestration.
- MCP tools should return enough metadata to support later source matrices and claim-grounding artifacts.
- The system should support **iterative research sessions** where later calls build on saved project artifacts rather than starting from zero.
- Ranking or evaluative outputs such as "best paper" or "best author" must be emitted as **traceable judgments**, not unsupported claims.

## Proposed Tool Surface

### Discovery

#### `search_openalex`

- Input:
  - query
  - filters
  - per_page
- Wraps:
  - `openalex.search_works`
  - `openalex.get_works_by_filters_all`
- Returns:
  - normalized paper summaries
  - DOI
  - title
  - abstract availability
  - OA / PDF hints
  - source provenance

#### `search_semantic_scholar`

- Input:
  - title or doi
  - optional citation / reference expansion flags
- Wraps:
  - `semantic_scholar.get_paper_by_doi`
  - `semantic_scholar.get_paper_by_title`
  - citations / references helpers
- Returns:
  - normalized paper metadata
  - citation graph snippets
  - PDF / OA hints when available

### Retrieval

#### `get_paper_record`

- Input:
  - doi or title
  - source preference
- Behavior:
  - resolve one paper into a normalized cross-source record
- Returns:
  - canonical metadata object with source provenance

#### `suggest_project_keywords`

- Input:
  - project description
  - optional seed papers, authors, or concepts
- Behavior:
  - propose a search vocabulary for the project
  - organize keywords into likely themes, synonyms, and expansion directions
- Returns:
  - keyword sets
  - search suggestions
  - rationale
  - optional saved artifact path in client project

#### `download_paper_pdf`

- Input:
  - doi
  - optional destination
  - optional fallback policy
- Wraps:
  - `pdf_download.download_pdf_with_fallback`
- Returns:
  - local path
  - chosen download path / source
  - OA status if known
  - failure provenance if unsuccessful

### Parsing

#### `parse_pdf_to_document`

- Input:
  - local PDF path
  - optional output paths
  - optional GROBID URL
- Wraps:
  - `pdf_parsing.process_pdf`
  - `pdf_parsing.parse_tei_to_document`
- Returns:
  - parsed document summary
  - abstract
  - sections
  - artifact paths
  - parse provenance

#### `get_document_sections`

- Input:
  - parsed document path or DOI / PDF path
  - section filters
- Returns:
  - normalized section list
  - section ids
  - titles
  - text excerpts

### Corpus Construction

#### `chunk_document`

- Input:
  - parsed document path
  - chunking config
- Wraps:
  - `chunking.chunk_document`
- Returns:
  - chunk summaries
  - token counts
  - content flags
  - saved artifact path if persisted

#### `index_document_chunks`

- Input:
  - parsed document or chunk artifact
  - collection name
- Wraps:
  - embedding pipeline
  - `vector_store.upsert_chunks`
- Returns:
  - indexed chunk count
  - collection name
  - document identifier
  - indexing provenance

### Retrieval Over Local Corpus

#### `semantic_search_corpus`

- Input:
  - query
  - collection name
  - filters
  - top_k
- Wraps:
  - `vector_store.search_chunks`
- Returns:
  - ranked chunk hits
  - scores
  - document identifiers
  - section metadata
  - chunk provenance

#### `build_reading_packet`

- Input:
  - query
  - corpus identifiers or collection
  - top_k
- Behavior:
  - aggregate top semantic hits into a structured reading packet
- Returns:
  - source list
  - excerpts
  - section provenance
  - suggested reading order

#### `expand_research_thread`

- Input:
  - seed DOI, author, journal, or concept
  - expansion policy
  - depth / limit
- Behavior:
  - expand through citations, references, repeated authors, recurring journals, and semantically related papers
- Returns:
  - discovered papers
  - thread structure
  - relevance rationale
  - saved thread artifact path

#### `rank_research_entities`

- Input:
  - corpus or thread artifact
  - target entity type: paper | author | journal
  - ranking objective
- Behavior:
  - produce provisional ranked judgments from available corpus signals
- Returns:
  - ranked entities
  - explicit scoring / rationale fields
  - provenance for why the entity was ranked highly
  - warnings about incompleteness or uncertainty

### Research Artifacts

#### `build_source_matrix_rows`

- Input:
  - papers or search results
  - optional fields to populate
- Behavior:
  - convert normalized metadata into rows for a literature-review matrix
- Returns:
  - matrix-ready structured rows

#### `write_paper_synthesis`

- Input:
  - corpus identifiers, thread artifact, or source matrix
  - synthesis objective
- Behavior:
  - assemble a structured synthesis artifact for the client project
- Returns:
  - synthesis sections
  - cited supporting excerpts
  - artifact path

#### `collect_claim_grounding_context`

- Input:
  - doi / document id
  - field or claim query
  - optional local corpus search query
- Behavior:
  - gather the best candidate sections / chunks for downstream claim grounding
- Returns:
  - evidence candidates
  - source section metadata
  - retrieval provenance

## Canonical Output Shapes

All tools should return typed payloads with a shared provenance block.

Suggested common metadata:

- `source_system`
- `source_url`
- `doi`
- `paper_id`
- `title`
- `retrieved_at`
- `local_path`
- `artifact_path`
- `client_project_root`
- `section_id`
- `chunk_id`
- `collection_name`
- `thread_id`

This is critical. The server should not return bare strings when it could return a provenance-bearing object.

## Module Boundaries

### Reuse Directly

- `openalex.py`
- `semantic_scholar.py`
- `pdf_download.py`
- `pdf_parsing.py`
- `chunking.py`
- `embedding.py`
- `vector_store.py`
- `openai_io.py`

### Add New Modules

- `src/llm_metadata/research_mcp_models.py`
  - MCP-facing request / response models
- `src/llm_metadata/research_services.py`
  - normalization adapters around existing modules
- `src/llm_metadata/research_mcp_server.py`
  - MCP server entry point and tool registration

### New Project Concerns To Add

- client workspace / artifact path resolution
- project-scoped cache policy
- thread artifact management
- ranking / opinion payloads with provenance
- synthesis artifact writing

### Keep Out Of First MCP Surface

- `gpt_extract.py`
- `extraction.py`
- `prompt_eval.py`
- biodiversity-specific prompt logic

These can be integrated later, but they should not define the first version of a general research server.

## Risks

### 1. Project-specific coupling

Risk:

- The MCP surface becomes too tied to biodiversity extraction internals.

Mitigation:

- Keep general research tools independent from extraction prompts and evaluation contracts.

### 2. Weak provenance

Risk:

- Retrieved snippets lose source / section / artifact traceability.

Mitigation:

- Make provenance required on all retrieval outputs.

### 3. PDF access instability

Risk:

- OA gaps and publisher constraints reduce reliability.

Mitigation:

- Return structured failure provenance.
- Treat download as best-effort, not guaranteed.

### 4. Parsing variability

Risk:

- GROBID output quality varies by publisher and PDF layout.

Mitigation:

- Preserve raw artifact paths and parse diagnostics.
- Avoid pretending parsed sections are perfect.

### 5. Vector-search overconfidence

Risk:

- Semantic hits are treated as verified evidence.

Mitigation:

- Clearly label semantic search as candidate retrieval, not truth.

### 6. Unsupported opinions

Risk:

- The server emits "best paper" or "best author" judgments that sound authoritative but are weakly grounded.

Mitigation:

- Treat all rankings as provisional opinions
- Require rationale and provenance on ranking outputs
- Emit uncertainty and corpus-coverage warnings

### 7. Artifact sprawl in client projects

Risk:

- Iterative workflows generate too many poorly organized artifacts.

Mitigation:

- Define a strict client artifact layout
- Use stable naming and manifest-like project metadata
- Make it easy to inspect and prune saved outputs

## Execution Rounds

Round 1: WU-RM0 || WU-RM1  
Round 2: WU-RM2 || WU-RM3  
Round 3: WU-RM4  
Round 4: WU-RM5 || WU-RM6  
Round 5: WU-RM7  
Round 6: WU-RM8

#### WU-RM0: Project Scaffold `opus`

**deps:** none | **files:** `README.md`, `AGENTS.md`, project structure

- Define the initial standalone project identity and scope
- Draft the first `README.md` for the new project:
  - what it is
  - who it is for
  - what problems it solves
  - what artifacts it manages in client projects
- Draft the first `AGENTS.md` for the new project:
  - research protocol expectations
  - provenance rules
  - client-project artifact rules
  - boundary between library logic and MCP interface
- Propose the initial project structure:
  - package layout
  - docs
  - examples
  - tests
  - MCP entry point
- Mark all unresolved architectural items that need explicit discussion and decisions before implementation starts
- Explicitly scope the project around the intended user journey by answering:
  - What is the formal **project initialization** flow?
  - What is the canonical representation of a **research project**?
  - What persistent project state should exist:
    - research questions
    - intuitions
    - keyword sets
    - corpus membership
    - threads
    - syntheses
  - What is the first-class workflow for **local PDF ingestion**?
  - What is the first-class workflow for **asking methodological questions over the current corpus**?
  - How should the system decide between:
    - answering from the current corpus
    - expanding the corpus with new papers
  - What is the distinction between:
    - broad project synthesis
    - focused subtopic / idea review
  - What artifacts and manifests should represent those two modes?
  - How should rankings and evaluative outputs fit into the UX without becoming unsupported claims?
  - Which of these concepts must exist in v1 versus later phases?

#### WU-RM1: Project Research `opus`

**deps:** none | **files:** `docs/project-research.md`, `plans/research-mcp-server.md`

- Research existing projects, tools, and skills that already tackle parts of this space
- Include at minimum:
  - literature-review and academic-research skills already identified
  - relevant paper-research / synthesis systems and repos
  - the Nature paper:
    - *Synthesizing scientific literature with retrieval-augmented language models* (`10.1038/s41586-025-10072-4`)
- Study how those systems frame:
  - retrieval
  - iterative refinement
  - citation grounding
  - corpus ownership
  - evaluation
- Take inspiration from how we conducted research for this task, but improve the process:
  - make source verification explicit
  - separate directly verified claims from inference
  - record what was learned from papers versus product docs versus skills
- Produce a short recommendation section on:
  - what to emulate
  - what to avoid
  - where this project should deliberately differentiate itself
- Explicitly answer the question:
  - **Is this project relevant and worth building as a standalone reusable library + MCP server?**
- Make the answer concrete by assessing:
  - whether there is a real gap not already covered well by existing tools or skills
  - whether the proposed artifact model and iterative workflow are meaningfully differentiated
  - whether this should remain a project idea, become a thin wrapper, or justify a full standalone project
- End the work unit with a plan review:
  - identify which parts of `plans/research-mcp-server.md` are confirmed by the research
  - identify which parts should be revised, narrowed, deferred, or removed
  - update the plan accordingly after the research synthesis is complete

#### WU-RM2: Tool Surface Spec `opus`

**deps:** WU-RM0, WU-RM1 | **files:** `plans/research-mcp-server.md`, `docs/research-quality-retrospective.md`

- Finalize the MCP tool list, output shapes, and provenance contract
- Decide what belongs in v1 versus later phases
- Define the general-versus-domain-specific boundary
- Define the client-project artifact model and iterative session model

#### WU-RM3: Service Boundary Audit `sonnet`

**deps:** none | **files:** `src/llm_metadata/openalex.py`, `src/llm_metadata/semantic_scholar.py`, `src/llm_metadata/pdf_download.py`, `src/llm_metadata/pdf_parsing.py`, `src/llm_metadata/chunking.py`, `src/llm_metadata/vector_store.py`

- Audit existing module APIs for MCP readiness
- Identify normalization wrappers needed to present stable outputs
- Identify blocking side effects or assumptions that should be isolated

#### WU-RM4: Shared Research Models + Service Adapters `sonnet`

**deps:** WU-RM0, WU-RM1, WU-RM2, WU-RM3 | **files:** `src/llm_metadata/research_mcp_models.py`, `src/llm_metadata/research_services.py`

- Implement normalized request / response models
- Implement adapter functions over existing modules
- Standardize provenance fields and error payloads
- Add client-project path resolution and saved-artifact contracts

#### WU-RM5: MCP Server Skeleton `sonnet`

**deps:** WU-RM4 | **files:** `src/llm_metadata/research_mcp_server.py`

- Create MCP server entry point
- Register v1 read-oriented tools
- Add structured error handling and logging

#### WU-RM6: Notebook Pilot `sonnet`

**deps:** WU-RM4 | **files:** `notebooks/`, `notebooks/README.md`

- Demonstrate a literature workflow using the new service layer
- Example flow:
  - define project keywords
  - search papers
  - download one OA PDF
  - parse with GROBID
  - chunk and index
  - run semantic search
  - build source-matrix rows
  - expand one citation / author thread
  - produce one synthesis artifact saved in project space
- Record strengths and pain points before hardening the MCP surface

#### WU-RM7: Corpus + Provenance Hardening `sonnet`

**deps:** WU-RM5, WU-RM6 | **files:** `src/llm_metadata/research_services.py`, `src/llm_metadata/research_mcp_server.py`, `tests/`

- Harden provenance fields
- Add tests for normalized outputs and failure cases
- Verify that semantic retrieval results preserve enough source metadata for later claim grounding

#### WU-RM8: Skill Layer Spec `haiku`

**deps:** WU-RM5, WU-RM7 | **files:** `docs/`, possible future skill folder

- Draft the companion research-synthesis skill spec
- Define the methodology that should sit on top of the MCP tools
- Keep the skill thin and protocol-oriented

## Initial Acceptance Criteria

- A user can search for papers via MCP and get normalized records
- A user can define or refine project search keywords via MCP
- A user can retrieve or resolve one paper into a provenance-rich record
- A user can parse at least one local PDF into sections via MCP
- A user can chunk and index a parsed document through the server
- A user can run semantic retrieval and receive section / chunk provenance
- A user can generate source-matrix-ready rows from retrieved papers
- A user can expand a research thread from a seed paper / author / concept
- A user can save durable artifacts into the client project's research workspace
- A user can request provisional rankings of papers, authors, or journals and receive rationale-bearing outputs
- The v1 server does not depend on biodiversity-specific extraction prompts

## Open Questions

- Should the first MCP server be stdio-only, or also support HTTP transport later?
- Should vector-store operations assume one shared collection or per-project collections?
- Which failure metadata should be standardized for PDF download and parse steps?
- Should source-matrix generation live in the server, or remain a client-side artifact helper?
- Should claim-grounding context collection be in v1, or wait until the grounding pipeline matures?
- Which ranking heuristics are acceptable in v1 for papers, authors, and journals?
- How should client projects declare their preferred artifact layout and retention policy?

## Out Of Scope

- End-to-end scientific paper drafting inside the MCP server
- Automated novelty assessment
- Full citation-graph analysis UI
- Replacement of notebooks as the primary experimentation surface
