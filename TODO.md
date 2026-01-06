# TO DO

* [ ] Dryad analysis : Run abstracts extraction and main numbers
* [ ] Benchmark dataset : Comparison pipeline
* [ ] Benchmark dataset : Run LLMs on benchmark abstracts
* [ ] Research : types of data from dataset
* [ ] Research : grey literature for biodiversity data



## Benchmarking from abstracts

* [x] Pydantic model for benchmark dataset and normalization of annotated data

* [ ] LLM feature extraction pipeline

  * [ ] Batch classification for manually annotated data

  * [ ] Research : Single shot vs multiple shots and LLMs

* [ ] Evaluation of LLM feature extraction

  * [ ] Metrics definition & utils

  * [ ] Benchmark report generation



## Feature extraction from abstract

* [ ] Dryad update -> notebook

* [ ] Feature schema model (incl score and definition, excerpt)

  * [ ] Geographic information model incl GADM level, protected areas, ecosystem
  
  * [ ] Taxonomic information model incl information descriptors (species, groupe paraphylétique, etc)

* [ ] Taxonomic & geographic referencement

  * [ ] Référencement des informations de géographie

  * [ ] Référencement des informations taxonomiques



Feature extraction from paper full text

* [ ] Recherche d'articles à partir d'un api de papiers scientifiques
* [ ] Full papers folder + repo
  * [ ] Small db with paper metadata (title, authors, etc) from benchmark
  * [ ] Téléchargement d'articles en distribution ouverte
  * [ ] Téléchargement d'articles en distribution restreinte

* [ ] Chunking & embeddings

  * [ ] Scientific articles chunking + vector db

  * [ ] Section detection (methodology) and add it to metadata



Web app dashboard











Jour 1 - Abstract benchmarking

Jour 2 - Dryad feature dashboard

Jour 3 - Benchmark full paper

Jour 4 - QCBS 2025 papers

Jour 5 - Feature extraction from data