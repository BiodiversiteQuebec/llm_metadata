# Evaluation Audit and Plain-Language Guide

This document is a plain-language audit of the project's ground-truth evaluation pipeline. It is written for readers who are comfortable with ecology, biodiversity data, and annotation work, but who may be newer to software evaluation vocabulary such as "grader", "rubric", "holdout set", or "continuous evaluation".

It covers four things:

1. What this project is trying to evaluate, and why that is harder than it sounds.
2. What is already implemented in this repository.
3. How the current implementation compares to evaluation best practices.
4. How OpenAI Evals and Hugging Face evaluation tools could help without replacing the current domain-specific pipeline.

## Executive summary

The project already has a serious local evaluation system for structured ecological metadata extraction. In practical terms, it can:

- compare model output against human annotations field by field
- use different matching rules for different kinds of fields
- save run artifacts for later review
- support side-by-side error analysis through notebooks and the Streamlit viewer

That is a strong foundation.

The main weaknesses are not that "there is no evaluation", but that the current evaluation stack is still missing some maturity features that make results easier to trust over time:

- one checked-in config family is stale and can evaluate the wrong field name
- one reported metric (`accuracy`) is mathematically invalid for multi-value fields like `species`
- there is no locked holdout set separate from the prompt-tuning subset
- there is no confidence interval or significance workflow, so small improvements may be noise
- there is no routine human-calibration loop to test whether automated grading still agrees with expert judgment
- there is no CI-style continuous evaluation on every prompt, code, or model change

The biggest conceptual takeaway is this:

The repository already has "graders". They are just mostly hand-written, deterministic graders in Python rather than API-hosted graders. A grader is simply the thing that decides whether a prediction is correct. A rubric is the rulebook that says what "correct" means.

For this project, the best near-term direction is a hybrid approach:

- keep the local evaluator as the source of truth for structured field correctness
- improve its statistical rigor and process discipline
- optionally use OpenAI Evals later for the harder semantic questions that deterministic matching does not capture well

## Diagram

```text
+-----------------------------------+
| Scientific papers and records     |
+-----------------------------------+
          |                   |
          |                   v
          |        +-------------------------------+
          |        | Extraction pipeline           |
          |        | abstract | sections | pdf     |
          |        +-------------------------------+
          |                   |
          |                   v
          |        +-------------------------------+
          |        | LLM predictions               |
          |        | structured metadata fields    |
          |        +-------------------------------+
          |                   |
          v                   v
+-----------------------------------+     +-------------------------------+
| Ground truth annotations          |---->| Local evaluation engine       |
| validated spreadsheet             |     | groundtruth_eval.py           |
+-----------------------------------+     +-------------------------------+
                                                   |
                                                   v
                                      +-------------------------------+
                                      | Field-specific graders        |
                                      | exact | enhanced species      |
                                      | fuzzy (optional)              |
                                      +-------------------------------+
                                                   |
                                                   v
                                      +-------------------------------+
                                      | Metrics and error records     |
                                      | precision | recall | F1       |
                                      | exact-match rate              |
                                      +-------------------------------+
                                                   |
                                                   v
                                      +-------------------------------+
                                      | Review layer                  |
                                      | JSON artifacts                |
                                      | notebooks                     |
                                      | Streamlit viewer              |
                                      +-------------------------------+
                                                   |
                                                   v
                                      +-------------------------------+
                                      | Prompt / pipeline iteration   |
                                      +-------------------------------+
                                                   |
                                                   v
                                      +-------------------------------+
                                      | Extraction pipeline           |
                                      +-------------------------------+

Recommended next layer:

  - locked holdout set
  - confidence intervals
  - human calibration loop
  - CI-style continuous eval
  - optional OpenAI / Hugging Face hosted eval tooling
```

Plain-language reading of the diagram:

- the project compares structured model predictions against validated human annotations
- those comparisons already use field-specific graders rather than one generic rule
- the outputs are then reviewed through metrics, saved artifacts, notebooks, and the viewer
- the missing pieces are mainly process hardening steps, not a totally new evaluation stack

## What this project is evaluating

The project is not trying to answer a broad question like "Is the model good?"

It is asking a narrower and more scientific question:

Can an LLM reliably extract ecological metadata fields from scientific dataset abstracts and article text, in a way that is useful for biodiversity data discovery and gap analysis?

In this repository, that means comparing model predictions against manually annotated ground truth for fields such as:

- species
- data type
- geospatial information
- temporal range
- spatial range
- several boolean modulator fields such as `time_series` and `threatened_species`

The core project references for this are:

- [AGENTS.md](../AGENTS.md)
- [notebooks/README.md](../notebooks/README.md)
- [groundtruth_eval.py](../src/llm_metadata/groundtruth_eval.py)
- [prompt_eval.py](../src/llm_metadata/prompt_eval.py)
- [prompt_eval_results](../app/prompt_eval_results/)

This is a difficult evaluation problem because the task mixes several kinds of information:

- exact fields, such as booleans
- normalized vocabulary fields, such as `data_type`
- free-text biological names, such as `species`
- fields that may be absent from the abstract but present in the full paper
- fields where human annotators may have applied stricter scoping rules than the model does

In other words, this is not a single evaluation problem. It is a family of related evaluation problems, one per field.

## Key concepts in plain language

### Ground truth

Ground truth is the reference answer you treat as correct for evaluation purposes.

In this project, ground truth comes from the validated Fuster-style annotation spreadsheet. The model output is compared against those human annotations.

Important caution: ground truth is not automatically perfect. It is the best available reference, but it can still contain ambiguity, inconsistency, or hidden annotator assumptions.

### Metric

A metric is a number summarizing performance.

Common examples:

- precision: when the model says something is present, how often is it right?
- recall: when something is truly present, how often does the model find it?
- F1: a balance between precision and recall
- accuracy: proportion of total cases scored correctly

In ecology terms, precision is often the "over-claiming" question, while recall is the "missing real information" question.

### Grader

A grader is the mechanism that scores a prediction.

Examples:

- exact string match
- fuzzy match
- a Python function that compares sets or numbers
- another LLM acting as a judge

This repository already uses graders. For example, the `FieldEvalStrategy` registry in [groundtruth_eval.py](../src/llm_metadata/groundtruth_eval.py) says which grading algorithm to use for each field.

### Rubric

A rubric is the written rulebook behind the grader.

For example:

- "Count species as correct if the scientific or vernacular name clearly refers to the same organism."
- "Mark `time_series=True` only if repeated observations over time are explicitly stated."
- "Do not count geographic background context unless it refers to the dataset itself."

Rubrics can be informal and buried in code, or explicit and documented. Good evaluation systems make rubrics visible and stable.

### Deterministic grader

A deterministic grader always gives the same result for the same inputs.

Examples in this repo:

- exact comparison for booleans and normalized enums
- set-based comparison for list fields
- custom enhanced matching for `species`

Deterministic graders are excellent when the task can be stated clearly and operationalized in code.

### LLM-as-a-judge

This means using a model to score another model's output. For example:

- "Does this extracted species list match the intended ecological scope of the paper?"
- "Is the predicted `data_type` semantically equivalent to the expert annotation?"

This is useful when exact string matching is too brittle, but it adds new risks:

- judge bias
- prompt sensitivity
- poor agreement with humans if the rubric is vague

### Dev subset

The dev subset is the small set you actively use while iterating on prompts and code.

In this project, the 30-record manifest in `data/manifests/dev_subset_data_paper.csv` currently plays that role.

### Holdout set

A holdout set is a separate test set that you do not use while tuning prompts or code.

Why it matters:

If you keep improving prompts on the same 30 examples, you can slowly overfit to them. Your metrics rise on that subset, but the improvement may not generalize to new papers.

### CI-style continuous eval

This means evaluation runs automatically whenever something important changes, such as:

- a prompt edit
- a model switch
- a schema change
- a comparison strategy change

The software engineering idea is similar to continuous integration tests. Instead of running only when someone remembers, the eval becomes part of the normal development loop.

### Calibration

Calibration means checking whether the automated grader still agrees with human expert judgment.

A simple version would be:

1. sample 20 difficult cases
2. ask a human reviewer to score them
3. compare the human scores to the automated eval scores
4. investigate disagreements

Without calibration, an automated grader can drift away from what you actually care about.

### Confidence interval and significance

These are ways to express uncertainty in your metrics.

Example:

- Run A has species F1 = 0.28
- Run B has species F1 = 0.31

Is that a real improvement, or just noise from a small dataset?

Confidence intervals and significance tests help answer that question. They matter especially when the evaluation subset is small and some fields are rare.

## Project requirements and challenges

The evaluation requirements for this project are unusually strict because the output is structured ecological metadata, not free-form prose.

### Functional requirements

The evaluation pipeline needs to:

- compare predictions to expert annotations at the field level
- support multiple extraction modes such as `abstract`, `sections`, and `pdf_native`
- normalize values before comparison so trivial formatting differences do not dominate the score
- use field-specific comparison rules because not all fields behave the same way
- preserve enough detail for paper-by-paper error analysis
- remain reproducible enough for notebook-based research and prompt iteration

### Domain challenges

The project also faces real scientific annotation challenges:

- `species` is semantically messy because scientific names, common names, grouped taxa, and incidental mentions can all appear in the same abstract
- `data_type` can be over-predicted because the model may infer multiple plausible types while the annotator chose a single primary type
- `geospatial_info_dataset` is easy to over-extract because a paper can mention places that are not actually the dataset's geographic information
- some fields are too rare for stable estimates on a small subset
- some fields are often absent from abstracts, so abstract-only evaluation can unfairly penalize the extractor
- the original annotation purpose may not perfectly match every downstream use of the extracted features

The notebook log already documents many of these issues, especially for `species`, `data_type`, and `geospatial_info_dataset`; see [notebooks/README.md](../notebooks/README.md).

## What is implemented today

### 1. A local deterministic evaluation engine

The core evaluator is [groundtruth_eval.py](../src/llm_metadata/groundtruth_eval.py).

Its current design includes:

- `EvaluationConfig` for normalization and matching settings
- `FieldEvalStrategy` for field-specific grading logic
- `DEFAULT_FIELD_STRATEGIES` as the field registry
- per-record `FieldResult`
- aggregated `FieldMetrics`
- `EvaluationReport` for storing the full evaluation result

This is already a real grading framework, not just an ad hoc notebook script.

### 2. Field-specific grading strategies

The project correctly does not treat all fields the same. The default registry currently evaluates 12 fields:

| Field | Current strategy | Why |
|---|---|---|
| `temp_range_i` | exact | numeric year |
| `temp_range_f` | exact | numeric year |
| `spatial_range_km2` | exact | numeric value |
| `data_type` | exact | controlled vocabulary normalized by schema validators |
| `geospatial_info_dataset` | exact | controlled vocabulary normalized by schema validators |
| `species` | enhanced species matching | domain-specific naming complexity |
| `time_series` | exact | boolean |
| `multispecies` | exact | boolean |
| `threatened_species` | exact | boolean |
| `new_species_science` | exact | boolean |
| `new_species_region` | exact | boolean |
| `bias_north_south` | exact | boolean |

This field-specific design is one of the strongest parts of the current implementation.

### 3. Prompt-eval orchestration

[prompt_eval.py](../src/llm_metadata/prompt_eval.py) ties extraction and evaluation together:

- loads a manifest
- runs extraction in a chosen mode
- loads ground truth
- builds indexed truth/prediction maps
- runs `evaluate_indexed()`
- saves a run artifact and extraction CSV

This is a good pattern because it connects the eval directly to the extraction system people are iterating on.

### 4. Structured artifacts and viewer support

The repository also has:

- saved JSON artifacts in [app/prompt_eval_results](../app/prompt_eval_results/)
- notebook-level experiment logs in [notebooks/README.md](../notebooks/README.md)
- a Streamlit inspection app in [app_eval_viewer.py](../src/llm_metadata/app/app_eval_viewer.py)

That combination is valuable. Good eval practice is not only about one summary score. It is also about being able to inspect where and why the model failed.

### 5. Existing baseline runs

The committed prompt-eval artifacts in [app/prompt_eval_results](../app/prompt_eval_results/) show that the pipeline has been run end-to-end on the 30-record dev subset for three modes:

| Run artifact | Mode | Records | Successes | Cost (USD) |
|---|---|---:|---:|---:|
| `20260306_124617_dev_subset_abstract.json` | `abstract` | 30 | 30 | 0.2068 |
| `20260306_124556_dev_subset_sections.json` | `sections` | 30 | 30 | 0.2201 |
| `20260306_124634_dev_subset_pdf_file.json` | `pdf_native` | 30 | 30 | 0.2944 |

That means the system is operational, not hypothetical.

## Audit findings

### High severity: stale checked-in eval configs

The codebase has moved from `geospatial_info` to `geospatial_info_dataset` in the current field registry and documentation, but the checked-in JSON config files still use the old name:

- [eval_default.json](../configs/eval_default.json)
- [eval_fuzzy_species.json](../configs/eval_fuzzy_species.json)
- [eval_strict.json](../configs/eval_strict.json)

This matters because a user following older documented examples can run evaluation with a stale config and silently evaluate the wrong field.

Why this is important:

- it breaks the "single source of truth" idea for evaluation fields
- it makes cross-run comparisons less trustworthy
- it creates confusion for prompt iteration because results may depend on whether the in-code defaults or JSON config were used

### Medium severity: `accuracy` is mathematically invalid for multi-value fields

The `FieldMetrics.accuracy` property currently computes:

`(tp + tn) / n`

where `n` is incremented once per record, even for fields where `tp` can be greater than 1 because the field contains multiple items, such as `species`.

As a result, some saved artifacts already report impossible values above 1.0 for `accuracy`.

Examples from committed run artifacts include:

- `20260306_124617_dev_subset_abstract.json`, where `species` reports `accuracy = 1.1333`
- `20260306_124556_dev_subset_sections.json`, where `species` reports `accuracy = 1.0333`

This is not just a cosmetic bug. It is a measurement bug. A metric that can exceed 1.0 while claiming to be accuracy is not interpretable.

Practical recommendation:

- do not report `accuracy` for set/list fields in its current form
- either remove it for those fields or redefine it carefully for multi-label settings
- rely more heavily on precision, recall, F1, and exact-match rate for the current structured extraction task

### Low severity: `EvaluationReport.abstracts` and saved payloads are out of sync

The report model documents an `abstracts` mapping, but the prompt-eval serialization path does not currently populate or persist it consistently.

This is not the most serious problem because the viewer has a fallback strategy, but it is still a small contract mismatch between code, docs, and artifacts.

### Process gap: no locked holdout set

The project currently has a clear dev subset for prompt iteration, which is good.

But there does not yet appear to be a clearly locked holdout subset reserved for "final" testing after prompt changes. That means improvements on the dev subset may partly reflect overfitting to the same recurring examples.

### Process gap: no CI-style continuous eval loop

At the moment, evals are run manually or notebook-first. That is common in research projects, but it is not yet a continuous evaluation system.

What is missing is an automatic process that says, in effect:

- "run the core eval set every time the prompt changes"
- "compare to baseline"
- "fail or flag the change if target metrics regress"

### Process gap: no significance or uncertainty workflow

The current reports provide point estimates such as precision, recall, and F1. That is useful, but it does not answer:

- how stable are these metrics?
- is a small change likely real?
- which fields are too rare for a reliable estimate on this subset?

For a 30-record dev subset, this matters a lot.

### Process gap: no routine human-calibration loop

The local graders are sensible, but there is no documented periodic process that compares automated evaluation outcomes against expert human review on a fresh batch of difficult cases.

That means the system could slowly optimize toward the grader rather than toward the ecological interpretation that matters scientifically.

## How the current implementation compares to evaluation best practices

### Where the project is already strong

#### Clear task definition

The project has a clear evaluation target: field-level ecological metadata extraction against annotated reference data.

That is much better than vague "the output seems good" evaluation.

#### Task-specific grading

This is a major strength. The repo already uses field-specific graders instead of forcing one metric or one comparator onto all fields.

That aligns well with modern evaluation advice from both OpenAI and Hugging Face: use task-appropriate metrics and do not rely only on generic summary numbers.

#### Rich artifact logging

The project saves evaluation artifacts, extraction outputs, logs, and notebook observations. That is a strong basis for reproducible analysis.

#### Error analysis culture

The notebook log and viewer workflow show that the team is already treating evaluation as an investigation process, not just a scoreboard.

That is exactly the right instinct for scientific extraction work.

### Where the project is only partially aligned

#### Representative dataset design

The project has real annotated data and a curated dev subset, which is excellent.

However, from a best-practice perspective it still needs:

- a documented split policy
- a locked holdout set
- explicit handling of class imbalance and rare fields

#### Human agreement checks

The project relies heavily on expert annotations and manual notebook analysis, but the calibration of the automated grading logic itself is not yet formalized.

This is especially relevant for semantically fuzzy fields such as `species` and `geospatial_info_dataset`.

### Where the project is currently behind best practice

#### Continuous evaluation

Best practice is to re-run a stable eval suite whenever important parts of the system change. This repo does not yet appear to automate that loop.

#### Statistical uncertainty

Best practice is not only to report point estimates, but also to communicate uncertainty. This is especially important when sample sizes are small or label prevalence is low.

#### Clear rubric documentation for hard fields

The project has grading logic, but some of the rubric still lives implicitly in code and notebook practice. The harder the field, the more valuable it is to write the rubric down explicitly.

### Scorecard

| Best-practice area | Current state | Assessment |
|---|---|---|
| Clear task definition | Strong field-level extraction objective | Strong |
| Ground-truth reference data | Validated spreadsheet and manifest-based selection | Strong |
| Field-specific graders | Exact, fuzzy, enhanced-species strategies | Strong |
| Run artifact logging | JSON artifacts, logs, notebook history, viewer | Strong |
| Error analysis workflow | Notebook log plus viewer-based inspection | Strong |
| Locked holdout set | Not yet formalized | Needs work |
| Continuous evaluation | Manual, not automated | Needs work |
| Confidence intervals / significance | Not implemented | Needs work |
| Human calibration loop | Informal, not systematic | Needs work |
| Config consistency | Drift between code registry and JSON configs | Needs work |
| Metric validity | `accuracy` wrong for some multi-value fields | Needs work |

## Why these best practices matter in plain language

### Why separate dev and holdout sets matter

If you keep checking the same 30 papers while improving prompts, you learn those papers very well. That is useful for debugging, but it can produce a false sense of general progress.

The holdout set answers a different question:

"Did the improvement still help on papers we did not keep looking at during development?"

That is the closest thing to an honest exam.

### Why continuous eval matters

Without continuous eval, a seemingly harmless change can quietly break a field you were not looking at.

Example:

- you tighten the prompt to reduce `species` over-extraction
- `species` precision improves
- but `time_series` recall drops

If you only inspect the target field, you may miss the regression.

### Why calibration matters

A grader is only helpful if it reflects the real scientific judgment you care about.

For example, suppose a deterministic comparison says the model is wrong because it predicted a scientific name while the annotator used a common name. If an expert reviewer says "that should count as correct", the grader needs adjustment.

That is a calibration problem, not a model problem.

### Why confidence intervals matter

When you are deciding whether Prompt B is better than Prompt A, a tiny increase in F1 can be misleading.

Confidence intervals help you avoid overreacting to small, unstable changes.

## How OpenAI Evals API fits this project

OpenAI's current evaluation guidance is helpful here because it separates three ideas:

- define a task clearly
- define the test data schema
- define testing criteria through graders

In OpenAI Evals terminology, an eval is roughly:

- a dataset schema
- a set of graders
- one or more runs

That maps surprisingly well onto this repository:

| OpenAI concept | Rough equivalent in this repo |
|---|---|
| `data_source_config` | ground-truth row schema plus manifest-selected records |
| `testing_criteria` | `FieldEvalStrategy` plus Python comparison logic |
| eval run | `prompt_eval.run_eval()` output artifact |
| grader | exact, fuzzy, enhanced-species, or a future LLM judge |

### What OpenAI Evals could improve

OpenAI Evals could help the project with:

- clearer separation of eval definition versus eval run
- standardized grader objects
- hosted run tracking and report URLs
- webhook- or CI-friendly automation
- easier introduction of semantic or rubric-based grading for hard cases

For example, the hardest fields in this repo are not just exact matching problems. They are interpretation problems:

- Was this species mention actually in the scope of the dataset?
- Is the predicted `data_type` semantically equivalent to the annotator's choice?
- Did the model extract dataset-level geography, or just geographic background context?

These are places where an LLM grader could be useful if it is carefully calibrated.

### What OpenAI Evals would not replace

OpenAI Evals would not replace:

- the project's Pydantic normalization logic
- the domain-specific species comparison logic
- the importance of reviewing real mismatches manually
- the need for good ground truth

In other words, OpenAI Evals is best seen as an additional orchestration and grading layer, not as a full substitute for the current local evaluator.

### What a sensible hybrid design would look like

The most sensible future architecture is probably:

1. local deterministic eval for the 12 structured fields
2. optional OpenAI graders for hard semantic review questions
3. human spot-checking to calibrate both

That keeps the project's strongest current asset, namely domain-specific deterministic scoring, while adding a path for more nuanced grading later.

## How Hugging Face evaluation tools fit this project

Hugging Face does not offer exactly the same thing as OpenAI's Evals API, but its evaluation ecosystem is still very relevant here.

### Hugging Face Evaluate

The [Evaluate](https://huggingface.co/docs/evaluate/en/index) library is strong for:

- computing standard metrics cleanly
- combining multiple metrics
- thinking clearly about train, validation, and test splits
- saving and comparing results
- adding confidence intervals in some evaluator workflows

For this repository, Hugging Face Evaluate is especially useful as a reference for good metric hygiene and uncertainty reporting.

### Hugging Face Lighteval

[Lighteval](https://huggingface.co/docs/lighteval/en/index) is more focused on LLM evaluation and benchmarking across multiple backends, with sample-by-sample result inspection.

That makes it conceptually closer to OpenAI Evals for broad LLM benchmarking, though the current repo's field-by-field structured extraction task still depends heavily on local domain logic.

### Best fit for this project

The most realistic use of Hugging Face evaluation ideas in this repository would be:

- adopt clearer dataset split discipline from Evaluate guidance
- add uncertainty estimates or bootstrap confidence intervals where possible
- use Lighteval only if the project starts benchmarking several models or backends more systematically

## Recommended roadmap

### Short term: fix trust issues in the current evaluator

1. Update all checked-in eval config JSON files so they match the in-code field registry and use `geospatial_info_dataset`.
2. Remove or redefine `accuracy` for multi-value fields.
3. Make the `EvaluationReport` serialization contract internally consistent.
4. Write a short rubric note for the hardest fields, especially `species`, `data_type`, and `geospatial_info_dataset`.

### Medium term: improve scientific rigor

1. Create and document three splits:
   - prompt-iteration dev subset
   - locked holdout test subset
   - optional error-analysis subset for difficult cases
2. Add confidence intervals or bootstrap-based uncertainty estimates for key metrics.
3. Add a simple calibration workflow in which a human expert reviews a small set of disagreements every few runs.

### Longer term: add automation and semantic grading

1. Add CI-style evaluation on important changes.
2. Pilot one or two OpenAI Evals graders for the fields where deterministic comparison is too brittle.
3. Compare automated semantic grading against expert human review before trusting it at scale.

## Bottom line

This repository is already doing real evaluation work. The main issue is not lack of evaluation, but lack of evaluation hardening.

The current local evaluator is already a strong fit for structured ecological metadata extraction because it understands field-specific comparison rules. That is something a generic hosted eval tool will not magically know.

So the right message is not:

"Throw away the current system and use OpenAI Evals."

It is:

"Keep the current system, fix the measurement bugs, strengthen the process, and only add hosted or LLM-based graders where they solve a real semantic problem."

## Suggested reading

### Project sources

- [AGENTS.md](../AGENTS.md)
- [notebooks/README.md](../notebooks/README.md)
- [groundtruth_eval.py](../src/llm_metadata/groundtruth_eval.py)
- [prompt_eval.py](../src/llm_metadata/prompt_eval.py)
- [evaluation.md](./evaluation.md)
- [prompt_eval_results](../app/prompt_eval_results/)

### OpenAI docs

- OpenAI, "Evaluation best practices"  
  https://developers.openai.com/api/docs/guides/evaluation-best-practices/
- OpenAI, "Evaluating model performance"  
  https://developers.openai.com/api/docs/guides/evals/
- OpenAI, "Graders"  
  https://developers.openai.com/api/docs/guides/graders/
- OpenAI Cookbook, "Building resilient prompts using an evaluation flywheel"  
  https://developers.openai.com/cookbook/examples/evaluation/building_resilient_prompts_using_an_evaluation_flywheel/
- OpenAI Cookbook, "Eval-driven system design"  
  https://developers.openai.com/cookbook/examples/partners/eval_driven_system_design/receipt_inspection/

### Hugging Face docs

- Hugging Face Evaluate documentation  
  https://huggingface.co/docs/evaluate/en/index
- Hugging Face Evaluate, "A quick tour"  
  https://huggingface.co/docs/evaluate/main/en/a_quick_tour
- Hugging Face Evaluate, "Types of evaluations"  
  https://huggingface.co/docs/evaluate/main/en/types_of_evaluations
- Hugging Face Evaluate, "Considerations for model evaluation"  
  https://huggingface.co/docs/evaluate/en/considerations
- Hugging Face Evaluate, "Using the evaluator"  
  https://huggingface.co/docs/evaluate/v0.4.0/base_evaluator
- Hugging Face Lighteval documentation  
  https://huggingface.co/docs/lighteval/en/index

### Research context

- Fuster-Calvo A, Valentin S, Tamayo WC, Gravel D. 2025. Evaluating the feasibility of automating dataset retrieval for biodiversity monitoring. PeerJ 13:e18853.  
  https://doi.org/10.7717/peerj.18853
