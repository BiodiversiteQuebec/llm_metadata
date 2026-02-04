# TO DO

* [ ] Dryad analysis : Run abstracts extraction and main numbers
* [ ] Benchmark dataset : Comparison pipeline
* [ ] Benchmark dataset : Run LLMs on benchmark abstracts
* [ ] Research : types of data from dataset
* [ ] Research : grey literature for biodiversity data



## Benchmarking from abstracts

* [x] Pydantic model for benchmark dataset and normalization of annotated data

* [x] Refine pydantic model based on feature descriptions from Fuster et al.

  * [x] Species field. Make sure that the definition covers values examples in the annotated data

  * [x] valid_yn and reason_not_valid fields. Make sure that the definition covers values in the annotated data as enum, incl "other" reason

* [ ] LLM feature extraction pipeline

  * [x] Test run on sample annotated abstracts

  * [x] GPT wrapper and model update

  * [ ] Prompt engineering for feature extraction and model refinement 🔥

  * [ ] Research : Single shot vs multiple shots and LLMs (tested gpt-4o-mini vs gpt-5-mini)

  * [ ] Batch classification for manually annotated data

* [ ] Evaluation of LLM feature extraction

  * [x] Metrics definition & utils (evaluation.py with precision/recall/F1)

  * [ ] Benchmark report generation

## Benchmarking from papers full text

* [ ] Retrieval of paper DOIs from dataset repositories (Dryad, Zenodo) 🔥

  * [x] Article DOI retrieval from Excel cited_articles column (24.4% coverage)
  * [x] Article DOI retrieval from Dryad/Zenodo APIs (fallback method)
  * [x] Generated dataset-to-article mapping CSV (75 article DOIs from 299 valid datasets)
  * [x] Coverage: Dryad 100%, Zenodo 56.7%
  * [ ] Investigation of zenodo marked datasets with dryad urls 🔥
  * [ ] Investigation of datasets with source `semantic_scholar` 🔥

* [x] Retrieval of annotated papers full text (url + pdfs) from DOIs (OpenAlex + Unpaywall fallback)

* [x] Download all benchmark pdfs 🔥

  * [ ] Why only 75 articles ?

* [x] Paper full text chunking + vector db infrastructure + workflow (with metadata: sections, page numbers, authors, doi, etc) 🔥
  * [x] Docker infrastructure: compose up GROBID + Qdrant (`docker-compose.yml`)
  * [x] Prototyping notebook: `notebooks/pdf_chunking_exploration.ipynb`
  * [x] TEI parsing module: `src/llm_metadata/pdf_parsing.py`
  * [x] Section normalization: `src/llm_metadata/section_normalize.py`
  * [x] Chunking with tiktoken: `src/llm_metadata/chunking.py`
  * [x] Embedding wrapper: `src/llm_metadata/embedding.py`
  * [x] Qdrant indexing: `src/llm_metadata/vector_store.py`
  * [x] Chunk metadata schema: `src/llm_metadata/schemas/chunk_metadata.py`
  * [x] Registry SQLite: `data/registry.sqlite`
  * See [tasks/article-full-text-chunking.md](tasks/article-full-text-chunking.md) for full plan

* Batch section identification + feature extraction + evaluation

* [ ] LLM feature extraction from full text (with context retrieval from vector db) for sample annotated data + evaluation

* [ ] Feature prompt engineering

* [ ] Batch classification

* [ ] Evaluation of LLM feature extraction from full text

## Feature extraction from abstract

* [ ] Dryad update -> notebook

* [ ] Feature schema model (incl score and definition, excerpt)

  * [ ] Geographic information model incl GADM level, protected areas, ecosystem
  
  * [ ] Taxonomic information model incl information descriptors (species, groupe paraphylétique, etc)

* [ ] Taxonomic & geographic referencement

  * [ ] Référencement des informations de géographie

  * [ ] Référencement des informations taxonomiques



## Feature extraction from paper full text

* [x] Recherche d'articles à partir d'un api de papiers scientifiques (OpenAlex)

* [x] Full papers folder + repo
  * [x] Small db with paper metadata (dataset_article_mapping.csv with 75 article DOIs)
  * [x] Download PDFs using OpenAlex
    * [x] Implement Unpaywall API client with rate limiting
    * [x] Check open access availability (is_oa flag)
    * [x] Download PDFs from best_oa_location
    * [x] Store PDFs in data/pdfs/ organized by source
    * [x] Generate metadata file with download status and OA license info
    * [x] Handle restricted access articles (log for manual retrieval)
  * [x] Téléchargement d'articles en distribution ouverte (via Unpaywall)
  * [x] Téléchargement d'articles en distribution restreinte (manual/institutional access)
  * [x] Téléchargement d'articles en distribution restreinte (via sci-hub)

* [x] Chunking & embeddings
  * [x] Scientific articles chunking + vector db
  * [x] Section detection (methodology) and add it to metadata
  * [x] Retrieval and vector db integration notebook

* [ ] LLM feature extraction from full text
  * [x] Section-specific (methods) -> Great results on 1 article
    * [ ] Batch processing of annotated articles
  * [ ] Full-text
  * [ ] Retrieval-augmented generation (RAG) approach based on vector db

## To production

* [ ] Streamline artifacts, manifests, data storage
* [ ] Workflow orchestration prefect
* [ ] Full db model (articles, datasets, features, runs, evaluations, etc) and postgres setup
* [ ] Refactor tests related to pipelines to reflect project structure
* [ ] Refactor classification modules to reflect pipelines structure


Web app dashboard











Jour 1 - Abstract benchmarking

Jour 2 - Dryad feature dashboard

Jour 3 - Benchmark full paper

Jour 4 - QCBS 2025 papers

Jour 5 - Feature extraction from data