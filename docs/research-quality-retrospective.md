# Research Quality Retrospective

**Scope:** Retrospective on WU-E0 (`docs/claim-grounding-research.md`)  
**Date:** 2026-03-09

## Bottom Line

WU-E0 was **good design research**, but only **moderate literature research**.

It was good enough to:

- improve terminology
- narrow scope
- reject weak architectural ideas
- strengthen the active plan

It was not strong enough to:

- support a publication-grade related work section
- justify strong novelty claims
- count as a systematic review

## What We Did Well

- Identified the right framing shift: from generic "evidence mode" to **post-hoc claim grounding**.
- Linked literature search to design decisions instead of collecting references passively.
- Distinguished product-doc patterns from research-paper task formulations.
- Chose adjacent task families that are genuinely relevant:
  - evidence inference
  - scientific claim verification
  - rationale evaluation
- Produced concrete outcomes for the repo:
  - better naming
  - better scope
  - better schema direction
  - better publication expectations

## What Was Weak

- The search was not systematic.
- We did not define inclusion and exclusion criteria in advance.
- We did not maintain a source matrix showing exactly how each source informed the synthesis.
- We mixed several evidence classes:
  - provider docs
  - benchmark papers
  - domain-near applied papers
  - grey literature
- Some source judgments were based on abstracts, task familiarity, or high-level summaries rather than full-paper reading.
- We did not do disciplined backward and forward citation chaining.
- Domain-specific biodiversity and ecology coverage remained thinner than the benchmark / NLP coverage.
- We corrected one overstatement during review, which is a sign that the first synthesis pass was slightly ahead of direct source verification.

## Was It Good Research?

### As design research

Yes.

The work was successful because it changed decisions:

- evidence is post-hoc, not a new mode
- atomic claims are the right unit
- numeric confidence should not be central
- the work is more likely publishable as part of the broader extraction paper

That is a legitimate and valuable outcome.

### As literature research

Only partly.

The work did not yet meet the bar for:

- systematic coverage
- reproducible search process
- defensible completeness
- publication-ready related work synthesis

The result is best described as:

- an informed exploratory synthesis
- a design-oriented research memo
- not a rigorous literature review

## Were Paywalled Papers a Limit?

Yes, but in a specific way.

Paywalls did not fully block early framing work. Abstracts, benchmark pages, and accessible papers were enough to identify the nearest task families and improve the plan.

Paywalls do become a serious limit when we need:

- precise annotation protocol details
- exact evidence definitions
- evaluation methodology
- edge cases and failure modes
- defensible comparison claims in a paper

So the constraint is not mainly "we cannot discover relevant papers." The constraint is:

- we cannot verify the methods deeply enough from metadata alone

## How The Research Could Have Been Better

### 1. Use a declared research protocol

Before reading sources, define:

- target questions
- source classes
- inclusion criteria
- exclusion criteria
- what counts as "directly verified"

### 2. Build a source matrix

For each source, record:

- citation
- source type
- domain
- task
- evidence unit
- output format
- evaluation approach
- direct relevance to repo
- confidence in our summary
- whether full text was read

### 3. Separate source tiers more clearly

Keep distinct sections for:

- product / API docs
- benchmark and task papers
- domain-near applied papers
- grey literature

This prevents overly smooth synthesis across sources with very different evidentiary weight.

### 4. Read fewer papers, but more deeply

A better approach would have been:

- deeply read 4 to 8 high-priority papers
- extract task, labels, evidence representation, and evaluation
- only then expand outward

### 5. Do citation chasing

For the most relevant papers:

- read key references they cite
- inspect who cites them later

That would improve both coverage and confidence.

### 6. Make uncertainty explicit

The synthesis should explicitly mark:

- direct source verification
- inference from abstracts or summaries
- unresolved questions

## Should This Become a Skill?

Yes, likely.

The value would not be in automating the conclusions. The value would be in standardizing the workflow.

A useful research-synthesis skill should enforce:

- upfront research questions
- source-tier separation
- a required source matrix
- explicit verification status
- a "limits of synthesis" section
- a final translation step from literature findings to repo design decisions

This would improve consistency and reduce the risk of persuasive but weak synthesis.

## How This Can Support Scientific Paper Writing

The WU-E0 work can already support paper drafting in several ways.

### Introduction

- Clarify why claim grounding matters for structured biodiversity extraction.
- Motivate transparency, auditability, and prompt-iteration support.

### Related Work

- Organize adjacent literature into clearer families:
  - claim grounding / evidence inference
  - scientific claim verification
  - rationale evaluation
  - biodiversity / ecology LLM extraction

### Methods

- Justify the two-pass architecture.
- Justify atomic claims as the unit of evidence.
- Justify qualitative support labels over numeric confidence.

### Discussion

- Position the contribution as transparency and audit support, not generic XAI.
- Explain where the work is novel in biodiversity extraction and where it is not novel in NLP broadly.

### Limitations

- State lack of gold evidence annotations.
- State partial literature coverage and paywall constraints.
- State that current evidence evaluation is human usefulness, not benchmark-grade scoring.

## What We Still Lack

To make this useful for serious paper writing, we still need:

- a structured source matrix
- full-text notes for the highest-priority papers
- stronger biodiversity / ecology-specific related work coverage
- a sharper novelty claim tied to actual experiments
- a manual annotation protocol for claim grounding
- an evaluation design for grounding quality
- a clearer comparison to alternative architectures
- a paper outline showing exactly where claim grounding enters the main story

## Recommended Next Step

The next research upgrade should be a **small but rigorous literature table**, not a broader narrative memo.

Suggested deliverable:

- `docs/claim-grounding-source-matrix.md` or `.csv`

Minimum columns:

- source
- year
- type
- domain
- task
- evidence unit
- evidence output
- evaluation method
- full text read
- direct relevance
- notes

That would give the project a better foundation for both implementation and manuscript writing.
