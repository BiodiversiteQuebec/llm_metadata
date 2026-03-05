"""schemas.data_paper — Canonical manifest schema for data-paper records.

DataPaperRecord is the primary join unit for the evaluation pipeline.
It uses gt_record_id as the canonical identity key and stores normalized
source/article DOI references alongside a first-class pdf_local_path field.

Design decisions (see plans/data-papers-manifest-refactor.md):
- gt_record_id is the primary key, not DOI.
- source_doi and article_doi are metadata fields, not join keys.
- pdf_local_path is first-class; DOI-to-filename inference is a fallback only.
- Raw provider payloads (OpenAlex/Semantic Scholar JSON) are NOT stored here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field, model_validator

from llm_metadata.schemas.fuster_features import DataSource
from llm_metadata.doi_utils import normalize_doi, doi_filename_stem as _doi_filename_stem


class DataPaperRecord(BaseModel):
    """Canonical record for a data paper in the evaluation manifest.

    Fields
    ------
    gt_record_id
        Integer primary key from the ground truth XLSX (``id`` column).
        Must be unique within a manifest.
    source
        Repository source (dryad, zenodo, semantic_scholar, …).
    source_doi
        DOI of the dataset/repository record (normalized, bare form).
        Corresponds to ``source_url`` in the GT XLSX.
    source_url
        Original source dataset URL as it appears in the GT XLSX.
    article_doi
        DOI of the associated scientific article (normalized, bare form).
        Corresponds to ``cited_article_doi`` in the GT XLSX.
    article_url
        Canonical article URL (journal landing page, if available).
    pdf_url
        Publicly accessible PDF URL (may be OA or institutional).
    pdf_local_path
        Absolute or project-relative path to the downloaded PDF.
        This is the authoritative source for PDF eval mode.
    is_oa
        Whether the article is open access.
    openalex_id
        OpenAlex work ID (e.g. W2741809807), if resolved.
    semantic_scholar_paper_id
        Semantic Scholar paperId, if resolved.
    article_publisher
        Publisher name, if known.
    """

    gt_record_id: int = Field(..., description="Ground truth integer record ID (primary key).")
    source: Optional[DataSource] = Field(None, description="Repository source type.")
    source_doi: Optional[str] = Field(None, description="Normalized bare dataset/repository DOI.")
    source_url: Optional[str] = Field(None, description="Original source dataset URL.")
    article_doi: Optional[str] = Field(None, description="Normalized bare article DOI.")
    article_url: Optional[str] = Field(None, description="Canonical article URL.")
    pdf_url: Optional[str] = Field(None, description="Publicly accessible PDF URL.")
    pdf_local_path: Optional[str] = Field(None, description="Local path to downloaded PDF.")
    is_oa: Optional[bool] = Field(None, description="Whether the article is open access.")
    openalex_id: Optional[str] = Field(None, description="OpenAlex work ID.")
    semantic_scholar_paper_id: Optional[str] = Field(None, description="Semantic Scholar paper ID.")
    article_publisher: Optional[str] = Field(None, description="Publisher name.")

    @model_validator(mode="before")
    @classmethod
    def _normalize_dois(cls, data: dict) -> dict:
        """Normalize DOI fields to bare lowercase form on construction."""
        for field in ("source_doi", "article_doi"):
            val = data.get(field)
            if val and isinstance(val, str):
                normalized = normalize_doi(val)
                data[field] = normalized if normalized else None
        return data

    def pdf_path_exists(self) -> bool:
        """Return True if pdf_local_path is set and the file exists on disk."""
        if not self.pdf_local_path:
            return False
        return Path(self.pdf_local_path).exists()

    def doi_filename_stem(self) -> Optional[str]:
        """Return the DOI-derived filename stem (article_doi preferred, then source_doi)."""
        doi = self.article_doi or self.source_doi
        return _doi_filename_stem(doi) if doi else None


class DataPaperManifest(BaseModel):
    """Collection of DataPaperRecord entries with integrity guarantees.

    Duplicate gt_record_id values trigger a validation error.
    """

    records: list[DataPaperRecord] = Field(default_factory=list)

    @model_validator(mode="after")
    def _no_duplicate_ids(self) -> "DataPaperManifest":
        seen: set[int] = set()
        duplicates: list[int] = []
        for rec in self.records:
            if rec.gt_record_id in seen:
                duplicates.append(rec.gt_record_id)
            seen.add(rec.gt_record_id)
        if duplicates:
            raise ValueError(
                f"Duplicate gt_record_id values found in manifest: {sorted(set(duplicates))}. "
                "Deduplicate GT inputs before building a manifest."
            )
        return self

    def __len__(self) -> int:
        return len(self.records)

    def __iter__(self):
        return iter(self.records)

    def by_id(self) -> dict[int, DataPaperRecord]:
        """Return a dict mapping gt_record_id → DataPaperRecord."""
        return {rec.gt_record_id: rec for rec in self.records}

    def with_pdf(self) -> list[DataPaperRecord]:
        """Return records that have a pdf_local_path set."""
        return [r for r in self.records if r.pdf_local_path]

    def with_existing_pdf(self) -> list[DataPaperRecord]:
        """Return records where pdf_local_path exists on disk."""
        return [r for r in self.records if r.pdf_path_exists()]

    def validate_pdf_coverage(self) -> dict:
        """Return a coverage summary dict for preflight checks."""
        with_path = 0
        on_disk = 0
        missing: list[int] = []
        no_path: list[int] = []
        for r in self.records:
            if r.pdf_local_path:
                with_path += 1
                if Path(r.pdf_local_path).exists():
                    on_disk += 1
                else:
                    missing.append(r.gt_record_id)
            else:
                no_path.append(r.gt_record_id)
        return {
            "total": len(self.records),
            "with_pdf_local_path": with_path,
            "pdf_on_disk": on_disk,
            "missing_from_disk": missing,
            "no_pdf_path": no_path,
        }

    def to_csv_rows(self) -> list[dict]:
        """Return records as a list of flat dicts suitable for CSV export."""
        return [r.model_dump() for r in self.records]
