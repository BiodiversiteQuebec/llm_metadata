# Data paper Manifest Refactor Plan

> **Status:** Proposed  
> **Created:** 2026-03-04  
> **Primary model:** `opus`

## Objective

Replace `dev_subset.csv` DOI-driven selection with a canonical manifest contract that:

1. uses `gt_record_id` as the primary join key,
2. stores normalized source/article DOI references,
3. resolves PDF input via explicit `pdf_local_path` (not inferred DOI filename),
4. preserves provider provenance (OpenAlex/Semantic Scholar) as normalized signals.

## Pushback / Architectural Decisions

1. Do **not** store raw OpenAlex/Semantic Scholar payloads in the manifest.
   Store normalized fields only; keep raw provider JSON in cache/artifacts if needed.
2. DOI cannot be the primary key.
   Use `gt_record_id` as canonical identity; DOI is metadata.
3. `pdf_local_path` must be first-class for PDF eval.
   DOI-to-filename inference remains a fallback only.
4. Fail fast on data integrity issues.
   Duplicate `gt_record_id` in GT inputs must trigger a validation error unless explicitly deduplicated.

## Proposed Contract

### Core record fields

- `gt_record_id: int` (required, unique)
- `source: DataSource | None` (e.g. "dryad", "zenodo", "openalex", "semantic_scholar", "manual")
- `source_doi: str | None` (dataset/repository DOI)
- `source_url: str | None` (original source data paper URL, if available)
- `article_doi: str | None` (paper DOI used for article-level retrieval/PDFs)
- `article_url: str | None` (canonical article URL, if available)
- `pdf_url: str | None`
- `pdf_local_path: str | None`
- `is_oa: bool | None`

### Provider provenance (normalized, optional)

- `openalex_id: str | None`
- `semantic_scholar_paper_id: str | None`
- `article_publisher: str | None`

## Work Units

#### WU-SR1: Add canonical schema + DOI utils `sonnet`

**deps:** none | **files:** `src/llm_metadata/schemas/data_paper.py`, `src/llm_metadata/doi_utils.py`, `src/llm_metadata/schemas/__init__.py`, `tests/test_data_paper_schema.py`, `tests/test_doi_utils.py`

- Implement `DataPaperRecord` and `DataPaperManifest` Pydantic models.
- Implement shared DOI utilities: normalize/equality/filename stem/candidate variants.
- Add validators: at least one DOI present, canonical DOI normalization, optional path existence checks.
- Export schema in `schemas/__init__.py`.

#### WU-SR2: Build manifest from existing assets `sonnet`

**deps:** WU-SR1 | **files:** `src/llm_metadata/data_paper_manifest.py`, `tests/test_data_paper_manifest.py`

- Add a builder that joins validated GT XLSX + `data/pdfs/fuster/manifest.csv` + optional subset input.
- Resolve `article_doi`, `source_doi`, `pdf_local_path` and provenance fields per record.
- Add integrity checks: unique `gt_record_id`, no orphan subset IDs, no ambiguous joins.
- Add CLI entrypoint for generating manifest outputs (CSV only).

#### WU-SR3: Refactor prompt_eval to manifest-first `opus`

**deps:** WU-SR1, WU-SR2 | **files:** `src/llm_metadata/prompt_eval.py`, `tests/test_prompt_eval_manifest.py`

- Add `--manifest` and `manifest_path` API argument.
- In PDF mode, load records from manifest and use `pdf_local_path` directly.
- Keep `--subset` for backward compatibility, but deprecate for PDF mode.
- Preserve report metadata by attaching manifest-derived fields.

#### WU-SR4: Integrate with PDF download + retrieval flows `opus`

**deps:** WU-SR1, WU-SR2 | **files:** `src/llm_metadata/article_retrieval.py`, `src/llm_metadata/pdf_download.py`, `src/llm_metadata/data_paper_manifest.py`, `tests/test_article_retrieval.py`, `tests/test_pdf_download.py`

- Normalize DOI handling in retrieval/download paths via shared `doi_utils`.
- Add helper methods to update manifest resolution fields after retrieval/download.
- Persist selection provenance (`candidate_pdf_urls`, `selected_pdf_url`, reason).
- Avoid introducing provider-specific raw payload storage into manifest rows.

#### WU-SR5: Add adapters for downstream pipelines `sonnet`

**deps:** WU-SR2 | **files:** `src/llm_metadata/manifest_adapters.py`, `src/llm_metadata/fulltext_pipeline.py`, `src/llm_metadata/pdf_pipeline.py`, `src/llm_metadata/section_pipeline.py`, `tests/test_manifest_adapters.py`

- Add adapter functions converting data-paper rows to existing pipeline input records.
- Keep fulltext/pdf/section pipeline schemas backward compatible.
- Prefer adapter layer over changing all existing pipeline manifests at once.

#### WU-SR6: Migrate dev_subset to manifest format `haiku`

**deps:** WU-SR2 | **files:** `data/dev_subset.csv`, `data/manifests/dev_subset_data_paper.csv`

- Generate `dev_subset` manifest using the same 30 GT IDs.
- Preserve subset notes/tags in manifest.
- Validate that all included records have resolved `article_doi`; for PDF mode, validate `pdf_local_path` availability.

#### WU-SR7: Validation + acceptance gates `sonnet`

**deps:** WU-SR3, WU-SR4, WU-SR5, WU-SR6 | **files:** `tests/*`, `data/prompt_eval_reports/*` (new run artifacts)

- Add integration test: manifest-driven prompt_eval PDF mode should not skip Dryad/Zenodo rows due to source DOI mismatch.
- Add regression test for duplicate GT IDs and ambiguous DOI joins.
- Run prompt_eval on dev subset with manifest and verify extraction coverage improvement.
- Confirm backward compatibility for abstract mode + old subset flag.
- Replay `data/prompt_eval_reports/dev_subset_pdf_file.log` run conditions and verify full 30/30 PDF coverage.

### WU-SR7 Replay Steps: `dev_subset_pdf_file` rerun (target: 30 PDFs)

1. Build `data/manifests/dev_subset_data_paper.csv` from the same 30 `data/dev_subset.csv` IDs.
2. Preflight-check manifest:
   - `row_count == 30`
   - `unique(gt_record_id) == 30`
   - all rows have non-empty `pdf_local_path`
   - every `pdf_local_path` exists on disk
3. Re-run PDF eval (same mode as historical run, now manifest-driven):
   - `uv run python -m llm_metadata.prompt_eval --prompt prompts.pdf_file --model gpt-5-mini --gt ./data/dataset_092624_validated.xlsx --pdf-dir ./data/pdfs/fuster/ --manifest data/manifests/dev_subset_data_paper.csv --name dev_subset_pdf_file`
4. Check log `data/prompt_eval_reports/dev_subset_pdf_file.log`:
   - no `PDF not found` lines
   - no `skipped ... (no PDF found)` summary
5. Check report `data/prompt_eval_reports/dev_subset_pdf_file.json`:
   - `records` contains 30 IDs
   - `extraction_success_true == 30`
6. If any record fails extraction, fix root cause and rerun until 30/30 succeeds.

#### WU-SR8: Documentation + task tracking updates `haiku`

**deps:** WU-SR7 | **files:** `TODO.md`, `notebooks/README.md`, `AGENTS.md` (if needed), `plans/data-paper-manifest-refactor.md`

- Add plan reference and execution status to `TODO.md`.
- Log results and observations in `notebooks/README.md` after migration runs.
- Document new manifest contract and deprecation path for DOI-only subset selection.

## Execution Rounds

Round 1: WU-SR1 || WU-SR2  
Round 2: WU-SR3 || WU-SR5  
Round 3: WU-SR4 || WU-SR6  
Round 4: WU-SR7  
Round 5: WU-SR8

## Acceptance Criteria

- Prompt eval PDF mode uses manifest `pdf_local_path` and no longer depends on `source_url` DOI naming.
- Source/article DOI normalization behavior is centralized in one utility module.
- Dev subset exists as a data-paper manifest reusing the same GT records.
- Provider provenance fields are available in normalized form without raw API blobs.
- Existing pipelines remain runnable through adapter compatibility.
- Historical `dev_subset_pdf_file` replay passes with full coverage:
  - `data/prompt_eval_reports/dev_subset_pdf_file.log` shows zero PDF-not-found skips
  - `data/prompt_eval_reports/dev_subset_pdf_file.json` includes results for all 30 records
  - `extraction_success_true == 30`.

## Risks

- Duplicate IDs in GT XLSX can break joins unless explicitly guarded.
- Existing notebooks may assume old manifest column names; adapters mitigate this but require migration docs.
- Some records may still fail extraction for model/output-token reasons unrelated to manifest quality.
