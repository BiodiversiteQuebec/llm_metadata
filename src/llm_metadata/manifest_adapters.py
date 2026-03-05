"""manifest_adapters — Convert DataPaperRecord to pipeline input formats.

Adapter functions convert DataPaperManifest records to the dict/tuple formats
expected by existing pipeline modules (fulltext_pipeline, pdf_pipeline,
section_pipeline).  These adapters keep existing pipelines backward compatible
without modifying their internal schemas.

Usage example
-------------
    from llm_metadata.data_paper_manifest import load_manifest_csv
    from llm_metadata.manifest_adapters import manifest_to_fulltext_inputs
    from llm_metadata.fulltext_pipeline import FulltextInputRecord

    manifest = load_manifest_csv("data/manifests/dev_subset_data_paper.csv")
    inputs = manifest_to_fulltext_inputs(manifest)
    records = [FulltextInputRecord(**d) for d in inputs]
"""

from __future__ import annotations

import warnings

from llm_metadata.schemas.data_paper import DataPaperManifest, DataPaperRecord


# ---------------------------------------------------------------------------
# Single-record adapters
# ---------------------------------------------------------------------------


def record_to_fulltext_input(rec: DataPaperRecord) -> dict:
    """Convert a DataPaperRecord to a dict compatible with FulltextInputRecord.

    FulltextInputRecord fields
    --------------------------
    article_doi : str  (required)
    dataset_doi : Optional[str]
    pdf_path    : str  (required)
    title       : Optional[str]

    ``article_doi`` falls back to ``source_doi`` when the article DOI is absent.
    ``pdf_path`` is taken from ``pdf_local_path``.

    Raises
    ------
    ValueError
        If both ``article_doi`` and ``source_doi`` are None (no usable DOI).
    ValueError
        If ``pdf_local_path`` is None (no local PDF path to pass downstream).
    """
    doi = rec.article_doi or rec.source_doi
    if doi is None:
        raise ValueError(
            f"Record gt_record_id={rec.gt_record_id} has no article_doi or "
            "source_doi; cannot build FulltextInputRecord."
        )
    if rec.pdf_local_path is None:
        raise ValueError(
            f"Record gt_record_id={rec.gt_record_id} has no pdf_local_path; "
            "cannot build FulltextInputRecord."
        )
    return {
        "article_doi": doi,
        "dataset_doi": rec.source_doi,
        "pdf_path": rec.pdf_local_path,
        "title": None,
    }


def record_to_pdf_input(rec: DataPaperRecord) -> dict:
    """Convert a DataPaperRecord to a dict compatible with PDFInputRecord or SectionInputRecord.

    Both PDFInputRecord and SectionInputRecord share the same schema:

    id       : str  (required) — set to article_doi, falling back to source_doi
    pdf_path : str  (required) — set to pdf_local_path
    metadata : Optional[dict]  — carries gt_record_id for traceability

    Raises
    ------
    ValueError
        If both ``article_doi`` and ``source_doi`` are None.
    ValueError
        If ``pdf_local_path`` is None.
    """
    doi = rec.article_doi or rec.source_doi
    if doi is None:
        raise ValueError(
            f"Record gt_record_id={rec.gt_record_id} has no article_doi or "
            "source_doi; cannot build PDFInputRecord/SectionInputRecord."
        )
    if rec.pdf_local_path is None:
        raise ValueError(
            f"Record gt_record_id={rec.gt_record_id} has no pdf_local_path; "
            "cannot build PDFInputRecord/SectionInputRecord."
        )
    return {
        "id": doi,
        "pdf_path": rec.pdf_local_path,
        "metadata": {"gt_record_id": rec.gt_record_id},
    }


# PDFInputRecord and SectionInputRecord have identical schemas — one adapter covers both.
record_to_section_input = record_to_pdf_input


# ---------------------------------------------------------------------------
# Manifest-level adapters
# ---------------------------------------------------------------------------


def manifest_to_fulltext_inputs(manifest: DataPaperManifest) -> list[dict]:
    """Convert all records in a manifest to FulltextInputRecord dicts.

    Records that lack ``pdf_local_path`` or both DOI fields are skipped with a
    warning.  All other records are converted.

    Returns
    -------
    list[dict]
        Dicts ready to be passed to ``FulltextInputRecord(**d)``.
    """
    results: list[dict] = []
    for rec in manifest.records:
        try:
            results.append(record_to_fulltext_input(rec))
        except ValueError as exc:
            warnings.warn(
                f"[manifest_adapters] Skipping record {rec.gt_record_id}: {exc}",
                stacklevel=2,
            )
    return results


def manifest_to_pdf_inputs(
    manifest: DataPaperManifest,
    skip_missing_pdf: bool = True,
) -> list[dict]:
    """Convert all records in a manifest to PDFInputRecord dicts.

    Parameters
    ----------
    manifest:
        Source manifest.
    skip_missing_pdf:
        When True (default), records without ``pdf_local_path`` are silently
        skipped.  When False, they raise ValueError via ``record_to_pdf_input``.

    Returns
    -------
    list[dict]
        Dicts ready to be passed to ``PDFInputRecord(**d)``.
    """
    results: list[dict] = []
    for rec in manifest.records:
        if skip_missing_pdf and rec.pdf_local_path is None:
            continue
        try:
            results.append(record_to_pdf_input(rec))
        except ValueError as exc:
            warnings.warn(
                f"[manifest_adapters] Skipping record {rec.gt_record_id}: {exc}",
                stacklevel=2,
            )
    return results
