Semantic scholar data integration

Context : Current workflow and evaluation is based only on the data from dryad and zenodo, which represent a subset of the data used in Fuster et al. 2024. The xlsx file provided by Fuster et al. contains additional datasets that were retrieved using semantic scholar, and that are not included in the current workflow. Integrating this data would allow us to expand our evaluation dataset and confirm the generalizability of our results.

Goal : Integrate the datasets retrieved from semantic scholar into our data retrieval, benchmark dataset validation, and evaluation pipelines, and analyze the coverage of this data in terms of valid records, pdf availability, and open access proportion. Aim is :
* Abstract : within 80 % of the valid records with abstracts within the xlsx file
* Full text : within 80 % of the valid records with pdfs and oa access within the xlsx file, and similar open access proportion as the rest of the dataset

Relevant context files :

* `CLAUDE.md` for overall agentic coding and projectsinstructions.
* `notebooks/README.md` and relevant notebooks (see latest entry lines 1027-1031)
* `docs/results_presentation_20260219/work_plan.md` for what I want to present this Thursday, and where I want to integrate the semantic scholar data in the presentation.
* `TODO.md` for the relevant tasks and sub-tasks to achieve this integration.
* `src/*` for the relevant code modules to refactor and implement the integration.
* `data/annotated_datasets_fuster.xlsx` for the data to integrate and analyze

Sub-tasks
  * [ ] Audit relevant code modules and pipelines to make sure we have good patterns and practices ahead of refactoring and integrating the data
  * [ ] Refactor annotated validation pipelines to streamline url fields (search engine (dryad, zenodo, semantic), journal_url, pdf_url, is_oa, title & abstract_full_text ... propose relevant fields) and integrate semantic scholar data (cited articles retrieval and pdf download) - might require to refactor codebase the pydantic model and modules that retrieves and process data (openalex, dryad, tbd)
  * [ ] Integrate semantic scholar api to retrieve cited articles and their metadata, and pdf if available
  * [ ] Data coverage analysis on validated data (proportion of valid records, by sources, with pdfs, with open access pdfs) including semantic scholar data - In exisitng or new notebooks