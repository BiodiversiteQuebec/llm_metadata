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

  * [ ] Batch classification for manually annotated data

  * [x] Research : Single shot vs multiple shots and LLMs (tested gpt-4o-mini vs gpt-5-mini)

* [ ] Evaluation of LLM feature extraction

  * [x] Metrics definition & utils (evaluation.py with precision/recall/F1)

  * [ ] Benchmark report generation



## Feature extraction from abstract

* [ ] Dryad update -> notebook

* [ ] Feature schema model (incl score and definition, excerpt)

  * [ ] Geographic information model incl GADM level, protected areas, ecosystem
  
  * [ ] Taxonomic information model incl information descriptors (species, groupe paraphylétique, etc)

* [ ] Taxonomic & geographic referencement

  * [ ] Référencement des informations de géographie

  * [ ] Référencement des informations taxonomiques



## Feature extraction from paper full text

* [x] Recherche d'articles à partir d'un api de papiers scientifiques
  * [x] Article DOI retrieval from Excel cited_articles column (24.4% coverage)
  * [x] Article DOI retrieval from Dryad/Zenodo APIs (fallback method)
  * [x] Generated dataset-to-article mapping CSV (75 article DOIs from 299 valid datasets)
  * [x] Coverage: Dryad 100%, Zenodo 56.7%

* [ ] Full papers folder + repo
  * [x] Small db with paper metadata (dataset_article_mapping.csv with 75 article DOIs)
  * [ ] **NEXT: Download PDFs using Unpaywall API** (https://api.unpaywall.org/v2/{doi}?email={email})
    * [ ] Implement Unpaywall API client with rate limiting
    * [ ] Check open access availability (is_oa flag)
    * [ ] Download PDFs from best_oa_location
    * [ ] Store PDFs in data/pdfs/ organized by source
    * [ ] Generate metadata file with download status and OA license info
    * [ ] Handle restricted access articles (log for manual retrieval)
  * [ ] Téléchargement d'articles en distribution ouverte (via Unpaywall)
  * [ ] Téléchargement d'articles en distribution restreinte (manual/institutional access)

* [ ] Chunking & embeddings

  * [ ] Scientific articles chunking + vector db

  * [ ] Section detection (methodology) and add it to metadata



Web app dashboard











Jour 1 - Abstract benchmarking

Jour 2 - Dryad feature dashboard

Jour 3 - Benchmark full paper

Jour 4 - QCBS 2025 papers

Jour 5 - Feature extraction from data