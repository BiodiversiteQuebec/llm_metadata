# Preliminary results presentation


## Todo

### Minimal
* Include semantic scholar data
* Add modulator features to extraction schema
* Run all abstract only
    * Feature based performance discussion with examples
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
    * Fuster approaches synthesis (based on *_location feature values)
        * Annotation from abstract only (TBD n rows)
        * Annotation including full text (TBD n rows)
        * Annotation including from dataset (xlsx, etc) (TBD n rows)
    * Main numbers
        * Data with pdfs
        * Data from Semantic Scholar
        * Open access data proportion
    * Scope
        * Only oa when pdf is available
        * Only valid : Not evaluating performance on irrelevant data (e.g. non-biodiversity datasets, etc), for which records were returned by the search engine query, but were deemed irrelevant - Another step could be to have a small extraction doing this classification

* Extraction
    * Model used - context 
    * Basic extraction demo using pydantic + openai API calls
    * Abstract only approach (Goal 299 records)
    * PDF files (Goal 48 oa records out of 73 valid records with pdfs) - TODO : Confirm number of valid records with pdfs, and oa proportion
    * Section based (Goal all oa records with pdfs)
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