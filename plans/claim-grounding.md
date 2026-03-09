# Post-Hoc Claim Grounding

**Status:** Draft  
**Date:** 2026-03-09

## Problem Statement

We need an **opt-in post-hoc claim grounding flow** that helps analysts understand why a field/value was annotated or extracted from a paper.

The goal is not to improve primary extraction directly in v1. The goal is to produce **value-level grounding artifacts** that support:

- prompt engineering and mismatch diagnosis
- manual audit of ground truth annotations
- side-by-side comparison of GT vs model predictions

An evidence result should answer:

- What exact value is being justified?
- What quote supports it?
- Where was that quote found?
- Is the support explicit, paraphrased, inferred, ambiguous, or unsupported?
- What short rationale links the quote to the value?

## Key Decisions

- Claim grounding is **not** a new extraction `mode`.
  Extraction mode already means text source (`abstract`, `pdf_text`, `pdf_native`, `sections`).
- Claim grounding is a **separate optional explanation step** run after extraction or annotation loading.
- Grounding should be generated for **atomic claims** (`field_name` + one target value), not whole-record blobs.
- v1 should focus on **positive claims only**. Null / negative claims are out of scope initially.
- v1 should prioritize mismatch-heavy fields:
  - `geospatial_info_dataset`
  - `data_type`
  - `species`
- Grounding should live in a **separate artifact/model**, not be dynamically injected into extraction schemas.
- Numeric confidence is not the primary signal. Use a qualitative support label instead.
- v1 should return the **single best quote per claim**.
- `is_contradicted` should remain a **separate boolean**, not a support label.
- Precise locators such as page numbers or character offsets are a **future extension**. v1 should use `source_section`.
- The safer architecture is still a **two-pass design**, not because structure and citations are universally incompatible, but because mixing strict extraction and quote-grounding weakens the contract.

## Non-Goals

- Replacing the current single-pass extraction pipeline
- Implementing a two-stage evidence-first extraction pipeline in production
- Scoring evidence quality automatically in v1
- Explaining every field on every record
- Explaining absence / null predictions in v1

## Proposed Scope

### Inputs

- source text actually seen by the extractor
- claim source: `gt`, `pred`, or both
- `field_name`
- atomic `target_value`
- field description / controlled vocabulary when available
- optional run metadata (`run_id`, extraction prompt id, extraction mode)

### Outputs

One grounding row per atomic claim:

- `doi`
- `claim_source`
- `field_name`
- `target_value`
- `match`
- `support_type`
- `quote`
- `source_section`
- `rationale`
- `is_contradicted`

## Recommended Model Shape

Keep contracts in `schemas/` and logic outside:

```python
class EvidenceSupportType(str, Enum):
    EXPLICIT = "explicit"
    PARAPHRASE = "paraphrase"
    INFERRED = "inferred"
    AMBIGUOUS = "ambiguous"
    UNSUPPORTED = "unsupported"


class EvidenceClaim(BaseModel):
    doi: str
    claim_source: Literal["gt", "pred"]
    field_name: str
    target_value: str
    match: bool | None = None


class EvidenceRecord(BaseModel):
    claim: EvidenceClaim
    support_type: EvidenceSupportType
    quote: str | None = None
    source_section: str | None = None
    rationale: str | None = None
    is_contradicted: bool = False


class EvidenceResult(BaseModel):
    records: list[EvidenceRecord]
```

Notes:

- Keep `target_value` atomic and stringified for transport simplicity.
- Do not attach evidence directly to `DatasetFeaturesExtraction`.
- The older `confidence: 0-5` design should be treated as an experiment, not the default contract.

## Prompt Design

The explanation prompt should receive:

- the original source text
- the target claim
- field description / vocabulary constraints

It should **not** receive the entire extraction schema or full extraction prompt by default.

Prompt objective:

> For the given claim, find the best supporting quote from the text and classify the support as explicit, paraphrase, inferred, ambiguous, or unsupported. Return a short rationale grounded in the quote.

## Evaluation Strategy

v1 evaluation is **human usefulness**, not automated correctness scoring.

Pilot review questions:

- Does the quote actually support the target value?
- Is the support label reasonable?
- Is the rationale short and readable?
- Does the evidence help explain a mismatch?

Useful derived counters:

- support type distribution
- empty quote rate
- unsupported rate by field
- contradiction rate by field

## Research Questions

Phase 0 should produce `docs/claim-grounding-research.md` and answer:

- What adjacent concepts are most relevant?
  - evidence extraction
  - rationale generation
  - provenance / attribution for structured extraction
  - grounded extraction / cite-then-extract patterns
- What prior work is closest to our workflow?
  - OpenAI / Anthropic / LangChain docs and cookbooks
  - scientific IE / biomedical IE literature
  - ecology / biodiversity extraction literature where available
- How do others evaluate explanation or evidence quality?
- Are there reusable schema patterns for evidence records?
- Is there a publishable contribution here on its own, or only as part of a broader extraction paper?

Expected output:

- ranked synthesis of relevant concepts and sources
- a sharpened terminology and methodology section for this plan
- a recommendation on scientific scope

## Execution Rounds

Round 1: WU-E0 || WU-E1  
Round 2: WU-E2  
Round 3: WU-E3 || WU-E4  
Round 4: WU-E5

#### WU-E0: Research Synthesis `opus`

**deps:** none | **files:** `docs/claim-grounding-research.md`, `plans/claim-grounding.md`

- Review adjacent concepts, prior art, and evaluation patterns
- Rank concepts and sources by relevance to this repository
- Tighten terminology and scope recommendations for evidence work

#### WU-E1: Notebook Pilot Design `sonnet`

**deps:** none | **files:** `notebooks/`, `plans/claim-grounding.md`

- Define a notebook-first pilot on the first 5 dev-subset records
- Restrict scope to `geospatial_info_dataset`, `data_type`, and `species`
- Produce a comparison table with GT claim grounding and prediction claim grounding

#### WU-E2: Grounding Contracts + Prompt Builder `sonnet`

**deps:** WU-E0, WU-E1 | **files:** `src/llm_metadata/schemas/evidence.py`, `src/llm_metadata/evidence.py`

- Refactor evidence contracts around atomic claims and qualitative support labels
- Keep schemas in `schemas/evidence.py`
- Implement prompt builder and evidence extraction call in `evidence.py`
- Avoid dynamic schema mutation patterns for production code

#### WU-E3: `prompt_eval` Integration `sonnet`

**deps:** WU-E2 | **files:** `src/llm_metadata/prompt_eval.py`, `src/llm_metadata/extraction.py`

- Add optional evidence pass flags
- Preferred interface:
  - `--with-evidence`
  - `--explain-from gt|pred|both`
  - optional `--evidence-fields species,data_type,...`
- Persist evidence artifacts separately from primary extraction output

#### WU-E4: Viewer Integration `sonnet`

**deps:** WU-E2 | **files:** `src/llm_metadata/app/app_eval_viewer.py`

- Add an Evidence tab for claim-level inspection
- Show quote, support type, rationale, and contradiction flag
- Allow filtering by field, claim source, support type, and match status

#### WU-E5: Lab Logging + Plan Update `haiku`

**deps:** WU-E3, WU-E4 | **files:** `notebooks/README.md`, `TODO.md`, `plans/claim-grounding.md`

- Log pilot findings and implementation outcomes
- Add or update TODO references only after the pilot scope is confirmed
- Revise this plan based on measured cost and usefulness

## Initial Acceptance Criteria

- Evidence can be generated for atomic claims from GT or predictions
- The first 5 dev-subset records can be reviewed in notebook form
- At least one comparison table exists with:
  - title
  - doi
  - field
  - target value
  - match
  - GT evidence
  - prediction evidence
- The artifact clearly distinguishes unsupported vs inferred vs explicit support
- The design does not alter the core extraction schema contract

## Open Questions

- Should v1 pass only field descriptions, or also pass enum vocabularies/examples per field?
- Should `match` be stored on the claim or derived later from eval outputs?
- Should the evidence artifact be embedded inside run JSON, or saved as a sibling file?
- When evidence is generated from GT, how much annotation context should be shown to the model?

## Publication Note

This work is most publishable as part of the broader biodiversity extraction paper unless we later add a manually annotated grounding benchmark or a more rigorous evidence-quality evaluation protocol.

## Out of Scope

- Additional extraction passes whose purpose is to reconcile GT and predictions automatically
- Re-architecting extraction around evidence-first grounding
- Full-scale run coverage before the 5-record pilot proves useful
