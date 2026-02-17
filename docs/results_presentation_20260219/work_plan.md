# Preliminary results presentation


## Todo

### Minimal
* Include semantic scholar data
* Run all oa full text
    * Feature based performance discussion with examples
* Run all oa full text with section-based approach
    * Feature based performance discussion with examples

### Nice to have
* Prompt engineering to improve performance
* Openai evals
* Front-end demo for user testing
* Model comparison & llm abstraction layer
* Benchmark ds from gbif


## Introduction

* Fuster Valentin workflow : Feature + modulator -> classification -> evaluation
* Proposed workflow : LLM based feature extraction

Goal : Automated metadata extraction from scientific documents using LLMs, comparing abstract-only vs full-text approaches, and evaluating against manual annotations for precision/recall/F1.

## Methods

* Data
    * Fuster datasets with manual annotations for validation
    * Main numbers
        * Data with pdfs
        * Data from Semantic Scholar
        * Open access data proportion

* Extraction
    * Basic extraction demo using pydantic + openai API calls
    * Abstract only approach
    * PDF files
    * Section based
    * Embeddings + vector DB approach

* Evaluation
    * Ground truth processing vs LLM output : pydantic models for data validation + structured comparison
    * Species comparison
    * Metrics : Precision, Recall, F1

* Prompt engineering
    * Baseline prompt for abstract-only extraction
    * Full-text prompt construction with section delimiters and token management

## Results

* Approaches comparison
    * Precision/Recall/F1 for each approach
    * Token usage and cost analysis for each approach
    * Example extractions illustrating differences in output quality
    * Field specific performance (e.g., better location extraction with full text)

* Demo front-end showcasing extraction results and allowing user testing