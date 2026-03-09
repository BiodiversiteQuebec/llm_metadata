# Claim Grounding Research

**Status:** WU-E0 synthesis  
**Date:** 2026-03-09

## Executive Summary

The closest prior art to this repository's proposed evidence work is **post-hoc claim grounding**, not generic explainability and not a new extraction mode.

Across product docs and research literature, the strongest recurring pattern is:

1. produce a structured claim or prediction
2. attach or retrieve supporting evidence for that claim
3. keep the evidence artifact separate from the primary prediction contract

The main implication for this repo is straightforward:

- keep primary extraction on provider-enforced structured outputs
- run evidence as a second, optional claim-level pass
- model evidence as **quote + locator + support type + short rationale**
- avoid numeric confidence as the central design primitive

The best scientific framing is likely:

- **claim-level evidence attribution for biodiversity metadata extraction**
- or **post-hoc grounding / provenance for structured extraction**

The weakest framing is:

- generic "evidence mode"
- generic "confidence estimation"
- generic "explainable AI"

## Recommended Terminology

Ranked by relevance to this project:

1. **Claim-level evidence attribution**
   - Best fit for `field_name + target_value -> supporting quote`.
   - Emphasizes that the unit of analysis is the atomic claim, not the whole document.

2. **Post-hoc claim grounding**
   - Best architectural label for the proposed workflow.
   - Makes clear that extraction and explanation are separate stages.

3. **Evidence inference**
   - Strong fit when the task is "does this document support claim X, and where?"
   - Especially relevant from biomedical literature.

4. **Scientific claim verification / rationale selection**
   - Useful adjacent framing for evidence retrieval and justification.
   - Slightly broader than this repo because those tasks often predict support/refute labels.

5. **Provenance / attribution for structured extraction**
   - Good systems framing.
   - Useful for docs and app UI language.

6. **Rationale extraction**
   - Useful research term, but broader and often tied to classification tasks.

7. **Explainability / XAI**
   - Too broad to guide design decisions here.

## Most Relevant External Sources

### Tier 1: Directly useful for design

1. **Anthropic citations docs**
   - Closest product pattern to what we want.
   - Claude can cite provided documents directly, with sentence/page/block level locators.
   - Most important architectural lesson: Anthropic documents that citations are a distinct response mechanism and that, when you ask for structured formatting, the model may need explicit instruction to preserve citations inside that format.
   - Source: [Anthropic citations docs](https://docs.anthropic.com/en/docs/build-with-claude/citations)

2. **OpenAI structured outputs docs**
   - Best product source for why the primary extraction contract should remain strict and provider-enforced.
   - Reinforces keeping extraction reliability and evidence generation as separate concerns.
   - Source: [OpenAI structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs/)

3. **LangChain structured output docs**
   - Useful design confirmation from orchestration tooling.
   - LangChain also separates provider-native structured output from tool-based fallbacks, which aligns with keeping evidence outside the main schema.
   - Source: [LangChain structured output](https://docs.langchain.com/oss/python/langchain/structured-output)

4. **Evidence Inference / Evidence Inference 2.0**
   - Closest research task to "given a scientific document and a target claim, find support and infer the result."
   - Strong precedent for claim-conditioned evidence selection over scientific text.
   - Sources:
     - [Inferring Which Medical Treatments Work from Reports of Clinical Trials](https://aclanthology.org/N19-1371/)
     - [Evidence Inference 2.0: More Data, Better Models](https://aclanthology.org/2020.bionlp-1.13/)

5. **SciFact**
   - Strong precedent for scientific claim verification with rationale annotations over abstracts.
   - Very relevant for evidence retrieval and support/refute style reasoning.
   - Source: [Fact or Fiction: Verifying Scientific Claims](https://aclanthology.org/2020.emnlp-main.609/)

### Tier 2: Useful for evaluation framing

6. **ERASER benchmark**
   - Most useful source for rationale evaluation concepts.
   - Important lesson: rationale quality should be evaluated not only by span overlap, but also by whether the rationale is faithful to the prediction.
   - Source: [ERASER](https://aclanthology.org/2020.acl-main.408/)

7. **DocRED and later evidence-aware document RE work**
   - Useful as adjacent evidence-selection work for document-level extraction.
   - Less direct than Evidence Inference or SciFact because the task is relation extraction, not value-level metadata attribution.
   - Source: [DocRED](https://aclanthology.org/P19-1074)

### Tier 3: Domain-near extraction papers

8. **Gougherty and Clipp (2024)**
   - Ecology-specific extraction benchmark.
   - Valuable because it shows that ecology extraction work currently evaluates **accuracy and QA needs**, not evidence attribution.
   - Source: [Testing the reliability of an AI-based large language model to extract ecological information from the scientific literature](https://www.nature.com/articles/s44185-024-00043-9)

9. **Ikeda et al. (2025)**
   - Bioscience metadata curation with LLMs.
   - Relevant for metadata extraction at scale; again, the evaluation emphasis is extraction utility, not evidence justification.
   - Source: [Extraction of biological terms using large language models enhances the usability of metadata in the BioSample database](https://academic.oup.com/gigascience/article/doi/10.1093/gigascience/giaf070/8171981)

10. **Kommineni et al. (2024) biodiversity case study**
   - Relevant grey literature / conference abstract in biodiversity information retrieval.
   - Useful as domain-near evidence that the field is still focused on retrieval and agreement, not claim-level evidence artifacts.
   - Source: [Automating Information Retrieval from Biodiversity Literature Using Large Language Models: A Case Study](https://zenodo.org/records/13751744)

## What Product Documentation Suggests

### OpenAI

OpenAI's structured outputs guidance makes the primary extraction contract very clear: use schema-constrained outputs when you want reliable, typed extraction from unstructured text. The docs emphasize schema adherence rather than explanation generation. Source: [OpenAI structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs/).

OpenAI's web search and deep research docs show a separate pattern for attribution: citations are carried in annotations with source metadata and location indices, not embedded as arbitrary reasoning text inside the main answer. Sources:

- [OpenAI web search output and citations](https://developers.openai.com/api/docs/guides/tools-web-search/)
- [OpenAI deep research output structure](https://developers.openai.com/api/docs/guides/deep-research/)

Design implication:

- OpenAI docs support **strict extraction first, attribution second**
- they do **not** suggest folding quote-level evidence into the extraction schema as the default architecture

### Anthropic

Anthropic is the strongest direct product precedent for document-grounded evidence. Their citations feature:

- works over user-provided documents
- returns source locations at sentence/page/block granularity
- treats citations as a structured response layer over claims

Most important for this repo: Anthropic documents that citations remain more reliable when treated as their own mechanism, and that structured response formats may require explicit prompting to preserve citations inside that format. Source: [Anthropic citations docs](https://docs.anthropic.com/en/docs/build-with-claude/citations).

Design implication:

- a two-pass design is still the safer architecture for this repo because it avoids mixing strict extraction requirements with quote-grounding requirements in one response
- this supports the repo's revised plan, even though Anthropic does not describe a hard incompatibility

### LangChain

LangChain's docs are not about evidence directly, but they reinforce the same separation:

- provider-native structured output when strict schema adherence is needed
- tool-based fallback when native support is unavailable

The docs explicitly describe provider-native structured output as the most reliable option when available. Source: [LangChain structured output](https://docs.langchain.com/oss/python/langchain/structured-output).

Design implication:

- keep extraction on provider-native structured output
- do not degrade the extraction contract just to shoehorn in evidence fields

## What Research Literature Suggests

### 1. The closest research family is claim-conditioned evidence selection

The Evidence Inference papers ask a question very close to ours: given a scientific document and a target claim frame, identify the supporting evidence and infer the result. Sources:

- [Lehman et al. 2019](https://aclanthology.org/N19-1371/)
- [DeYoung et al. 2020](https://aclanthology.org/2020.bionlp-1.13/)

This is closer to the repo's intended evidence pass than generic explanation work because:

- the input is a document plus a target claim
- the output depends on support found in the text
- the evidence is part of task definition, not just optional commentary

### 2. Scientific claim verification is a strong adjacent model

SciFact frames the task as selecting abstracts containing evidence that supports or refutes a claim, with rationale annotations. Source: [Wadden et al. 2020](https://aclanthology.org/2020.emnlp-main.609/).

This is highly relevant for:

- support / unsupported / contradicted distinctions
- abstract-only evidence work
- human-readable justifications tied to text spans

Less relevant:

- SciFact focuses on claim verification labels, while this repo needs structured metadata value attribution

### 3. Rationale benchmarks help with evaluation language

ERASER is the most useful general benchmark for how to talk about evidence quality. Source: [DeYoung et al. 2020](https://aclanthology.org/2020.acl-main.408/).

Its main contribution for us is not task similarity, but evaluation vocabulary:

- alignment with human rationales
- faithfulness of the rationale to the prediction

That matters because a quote can look plausible while not actually explaining why the value was produced.

### 4. Ecology and biodiversity papers are using LLM extraction, but not usually evidence artifacts

The ecology and biodiversity papers I found are mostly about:

- extraction accuracy
- throughput gains
- inter-annotator agreement or human-vs-model agreement
- workflow utility

They are generally **not** about quote-level evidence attribution.

Examples:

- [Gougherty and Clipp 2024](https://www.nature.com/articles/s44185-024-00043-9)
- [Ikeda et al. 2025](https://academic.oup.com/gigascience/article/doi/10.1093/gigascience/giaf070/8171981)
- [Kommineni et al. 2024 case study](https://zenodo.org/records/13751744)

Inference from available abstracts and descriptions:

- biodiversity/ecology extraction appears to have a genuine gap in evidence-oriented evaluation
- that makes this repo's proposed evidence work more novel within the domain than within NLP broadly

## How Others Evaluate Extraction Quality

### Common extraction metrics

Across the domain-near literature, the common pattern is still:

- accuracy
- precision / recall / F1
- agreement with human annotation
- task-specific utility metrics

This matches the current repo evaluation architecture and should remain the main evaluation path for extraction itself.

### Common evidence / rationale metrics

In rationale and evidence literature, the main patterns are:

- evidence span overlap with gold rationales
- support / refute classification quality
- faithfulness-style measures
- human judgment of usefulness

ERASER is the clearest source for alignment-plus-faithfulness framing. Source: [ERASER](https://aclanthology.org/2020.acl-main.408/).

### What this means for this repo

For this repo, v1 evidence evaluation should be:

1. **human usefulness first**
2. optional descriptive counters second
3. no gold-span overlap metric unless we later create manual evidence annotations

Recommended v1 review rubric:

- Does the quote actually support the claim?
- Is the support label reasonable?
- Is the rationale short and non-hand-wavy?
- Does this artifact help diagnose a mismatch?

Recommended v1 counters:

- unsupported rate
- empty quote rate
- contradiction rate
- support-type distribution by field

## Schema Implications

The literature and docs strongly favor an **atomic claim schema**.

Recommended shape:

- `claim`
  - `doi`
  - `claim_source`
  - `field_name`
  - `target_value`
  - optional `match`
- `evidence`
  - `support_type`
  - `quote`
  - `source_section`
  - optional character/page/block locator later
  - `rationale`
  - `is_contradicted`

### Why this is better than the old schema

The current experimental schema in [evidence.py](/C:/Users/beav3503/dev/llm_metadata/src/llm_metadata/schemas/evidence.py) centers `confidence: 0-5`.

That is weakly supported by the prior art for this use case:

- product patterns center citations and locators
- research tasks center supporting evidence spans and labels
- prior notebook findings in this repo already suggest numeric confidence is miscalibrated

Recommended replacement:

- `support_type: explicit | paraphrase | inferred | ambiguous | unsupported`

Optional future additions:

- `quote_start`
- `quote_end`
- `page_start`
- `page_end`
- `content_block_start`
- `content_block_end`
- `evidence_notes`

Not recommended for v1:

- multiple free-form reasoning fields
- confidence percentages
- trying to mirror the entire extraction schema inside the evidence record

## Architectural Recommendation

The external evidence supports this architecture:

### Recommended

1. Run normal extraction with provider-enforced structured output.
2. Convert GT or predictions into atomic claims.
3. Run a second prompt over source text plus claim plus field description.
4. Persist evidence as a sibling artifact.
5. Review evidence in notebook / viewer.

### Not recommended

1. Making evidence a new extraction mode.
2. Dynamically injecting evidence into the extraction contract.
3. Forcing evidence and strict structured extraction into the same API response.
4. Centering the workflow on confidence scoring.

## Scope Recommendation

The most defensible scope is:

- evidence for **structured output extraction from biodiversity papers**
- especially for high-error, semantically ambiguous fields
- used for prompt engineering, audit, and qualitative mismatch analysis

The scope should **not** expand yet to:

- general explanation of all model behavior
- full "reasoning trace" capture
- full evidence-first extraction redesign

## Publishability Assessment

### Honest assessment

As a standalone contribution, this is **probably not yet strong enough** unless the work includes a new annotated benchmark or a rigorous evaluation protocol for evidence quality.

### Most plausible publication paths

1. **As part of a broader biodiversity extraction paper**
   - Strongest current option.
   - Evidence work becomes a transparency / audit / prompt-iteration contribution inside the main extraction study.

2. **As a methods note or workshop paper**
   - Plausible if the repo produces:
     - a clear claim-level evidence schema
     - a small manually reviewed evidence set
     - an analysis showing how evidence artifacts improve error diagnosis or prompt iteration

3. **As a standalone full paper**
   - Only plausible if you add at least one of:
     - manually annotated evidence spans
     - comparative experiments across evidence architectures
     - strong evidence-quality metrics and inter-rater agreement
     - a reusable benchmark for biodiversity metadata grounding

## Recommendations For `plans/claim-grounding.md`

The revised plan is directionally correct. Based on this research, I recommend preserving these decisions:

- evidence is post-hoc, not a mode
- evidence is claim-level, not record-level
- numeric confidence is deprecated
- the first pilot is notebook-first and mismatch-focused
- single best quote per claim should be the default
- `is_contradicted` should stay separate from `support_type`
- precise locators should stay out of v1

Additional recommendation:

- in implementation docs and CLI, prefer `with-evidence` / `explain-from` / `claim grounding` language over `evidence mode`

## Practical Next-Step Questions

These are the most useful unresolved questions after WU-E0:

1. Should v1 return only the **single best quote**, or allow multiple quotes per claim?
   - Recommendation: single best quote first.

2. Should support labels include `contradicted`, or keep contradiction as a separate boolean?
   - Recommendation: keep `is_contradicted` separate from `support_type`.

3. Should locators be textual only (`source_section`) or precise offsets?
   - Recommendation: `source_section` first; offsets later if needed.

4. Should evidence artifacts be embedded in run JSON?
   - Recommendation: no. Save as sibling artifacts.

## References

- OpenAI. [Structured model outputs](https://developers.openai.com/api/docs/guides/structured-outputs/).
- OpenAI. [Web search](https://developers.openai.com/api/docs/guides/tools-web-search/).
- OpenAI. [Deep research](https://developers.openai.com/api/docs/guides/deep-research/).
- Anthropic. [Citations](https://docs.anthropic.com/en/docs/build-with-claude/citations).
- LangChain. [Structured output](https://docs.langchain.com/oss/python/langchain/structured-output).
- Lehman E, DeYoung J, Barzilay R, Wallace BC. 2019. [Inferring Which Medical Treatments Work from Reports of Clinical Trials](https://aclanthology.org/N19-1371/).
- DeYoung J, Lehman E, Nye B, Marshall I, Wallace BC. 2020. [Evidence Inference 2.0: More Data, Better Models](https://aclanthology.org/2020.bionlp-1.13/).
- Wadden D, Lin S, Lo K, Wang LL, van Zuylen M, Cohan A, Hajishirzi H. 2020. [Fact or Fiction: Verifying Scientific Claims](https://aclanthology.org/2020.emnlp-main.609/).
- DeYoung J, Jain S, Rajani NF, Lehman E, Xiong C, Socher R, Wallace BC. 2020. [ERASER: A Benchmark to Evaluate Rationalized NLP Models](https://aclanthology.org/2020.acl-main.408/).
- Yao Y, Ye D, Li P, Han X, Lin Y, Liu Z, Liu Z, Huang L, Zhou J, Sun M. 2019. [DocRED: A Large-Scale Document-Level Relation Extraction Dataset](https://aclanthology.org/P19-1074).
- Gougherty AV, Clipp HL. 2024. [Testing the reliability of an AI-based large language model to extract ecological information from the scientific literature](https://www.nature.com/articles/s44185-024-00043-9).
- Ikeda S, Zou Z, Bono H, Moriya Y, Kawashima S, Katayama T, Oki S, Ohta T. 2025. [Extraction of biological terms using large language models enhances the usability of metadata in the BioSample database](https://academic.oup.com/gigascience/article/doi/10.1093/gigascience/giaf070/8171981).
- Kommineni VK, Ahmed W, Koenig-Ries B, Samuel S. 2024. [Automating Information Retrieval from Biodiversity Literature Using Large Language Models: A Case Study](https://zenodo.org/records/13751744).
