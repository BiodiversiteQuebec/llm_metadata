# Article and results plan

Scope : We do the same thing than Fuster & Valentin (2024) but with LLMs instead of NLP classification.

## Introduction

* Fuster Valentin workflow : Feature + modulator -> classification -> evaluation
* Proposed workflow : LLM based feature extraction
* Litterature review : LLMs for metadata extraction, LLMs for scientific document processing, etc

Goal : 

* Automated metadata extraction from scientific documents using LLMs, comparing abstract-only vs full-text approaches, and evaluating against manual annotations for precision/recall/F1.
* Performance for relevancy classification and comparison with manual and NLP classification results from Fuster & Valentin (2024)


## Methods

* Data
    * Fuster manual annotations (based on *_location feature values)
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
    * Schematic representation of the extraction process (e.g., data flow diagram)
        * Basic extraction demo/representation using pydantic + openai API calls
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

* Benefits of prompt engineering (Baseline vs improved prompt)

* Approaches comparison (Abstract-only vs Full-text vs Section-based)
    * Precision/Recall/F1 for each approach
    * Repetition analysis
    * Token usage and cost analysis for each approach
    * Example extractions illustrating differences in output quality
    * Field specific performance (e.g., better location extraction with full text)

* Performance on relevancy classification
    * Segmantized by field (e.g., location, species, etc)
    * Overall performance metrics
    * Manuscript-ready comparison draft: `docs/relevance_classification_comparison_draft.md`

* Demo front-end showcasing extraction results and allowing user testing

## Discussion

* Field-base performance insights (e.g., location vs species extraction)
* Trade-offs between abstract-only and full-text approaches (e.g., cost vs accuracy)
* Performance comparison with NLP classification (Fuster & Valentin, 2024)
    * Reuse manuscript-ready subsection draft from `docs/relevance_classification_comparison_draft.md`
* Techniques to improve benchmark database and feature extraction performance
* Benefits, limitations and perspectives/futures/dreams for LLM-based extraction for Biodiversité Québec

---

## Todo

### Minimal
*  [x] Include semantic scholar data
*  [x] Add modulator features to extraction schema
*  [ ] Run all abstract only
    *  [ ] Feature based performance discussion with examples
*  [ ] Run all oa full text
    *  [ ] Feature based performance discussion with examples
*  [ ] Run all oa full text with section-based approach
    *  [ ] Feature based performance discussion with examples

### Nice to have
*  [ ] Prompt engineering to improve performance
*  [ ] Openai evals
*  [x] Front-end demo for user testing
*  [ ] Model comparison & llm abstraction layer
*  [ ] Benchmark ds from gbif / ecology data paper
