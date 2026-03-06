"""Canonical contracts for data-paper extraction inputs and outputs."""

from __future__ import annotations

import csv
import json
import math
import warnings
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator

from llm_metadata.doi_utils import (
    doi_filename_stem as _doi_filename_stem,
    extract_doi_from_url,
    normalize_doi,
)
from llm_metadata.schemas.fuster_features import DataSource


def _is_nan_val(val: Any) -> bool:
    try:
        return math.isnan(float(val))
    except (TypeError, ValueError):
        return False


def _resolve_pdf_path(raw_path: str | None, pdf_dir: str | Path) -> Optional[str]:
    """Resolve a relative downloaded_pdf_path entry to an absolute path."""
    if not raw_path or str(raw_path).strip() in {"", "nan"}:
        return None
    clean = str(raw_path).replace("\\", "/").strip()
    return str(Path(pdf_dir) / clean)


def _load_gt_frame(gt_path: str | Path) -> "pd.DataFrame":  # type: ignore[name-defined]
    try:
        import pandas as pd  # type: ignore
    except ImportError as exc:
        raise ImportError("pandas is required; install with `pip install pandas openpyxl`.") from exc

    df = pd.read_excel(str(gt_path))
    df["id"] = df["id"].astype(int)
    return df


def _merge_raw_abstracts(
    gt_df: "pd.DataFrame",  # type: ignore[name-defined]
    gt_path: str | Path,
    raw_path: str | Path | None,
) -> "pd.DataFrame":  # type: ignore[name-defined]
    try:
        import pandas as pd  # type: ignore
    except ImportError as exc:
        raise ImportError("pandas is required; install with `pip install pandas openpyxl`.") from exc

    if "abstract" in gt_df.columns:
        return gt_df

    candidate = Path(raw_path) if raw_path is not None else Path(gt_path).with_name("dataset_092624.xlsx")
    if not candidate.exists():
        return gt_df

    raw_df = pd.read_excel(str(candidate), usecols=["id", "full_text"])
    raw_df = raw_df.rename(columns={"full_text": "abstract"})
    raw_df["id"] = raw_df["id"].astype(int)
    return gt_df.merge(raw_df, on="id", how="left")


def _load_pdf_manifest_frame(manifest_path: str | Path) -> "pd.DataFrame":  # type: ignore[name-defined]
    try:
        import pandas as pd  # type: ignore
    except ImportError as exc:
        raise ImportError("pandas is required; install with `pip install pandas openpyxl`.") from exc

    frame = pd.read_csv(str(manifest_path))
    if "record_id" not in frame.columns:
        raise ValueError(
            f"PDF manifest at '{manifest_path}' must have a 'record_id' column; "
            f"found: {frame.columns.tolist()}"
        )
    frame["record_id"] = frame["record_id"].astype(int)
    return frame


class ExtractionMode(str, Enum):
    ABSTRACT = "abstract"
    PDF_TEXT = "pdf_text"
    PDF_NATIVE = "pdf_native"
    SECTIONS = "sections"


class DataPaperRecord(BaseModel):
    """Canonical input record for all extraction modes."""

    gt_record_id: int = Field(..., description="Ground-truth integer record ID (primary key).")
    source: Optional[DataSource] = Field(None, description="Repository source type.")
    title: Optional[str] = Field(None, description="Paper title.")
    abstract: Optional[str] = Field(None, description="Abstract text used by abstract mode.")
    source_doi: Optional[str] = Field(None, description="Normalized bare dataset or repository DOI.")
    source_url: Optional[str] = Field(None, description="Original source dataset URL.")
    article_doi: Optional[str] = Field(None, description="Normalized bare article DOI.")
    article_url: Optional[str] = Field(None, description="Canonical article URL.")
    pdf_url: Optional[str] = Field(None, description="Public PDF URL when available.")
    pdf_local_path: Optional[str] = Field(None, description="Local path to downloaded PDF.")
    is_oa: Optional[bool] = Field(None, description="Whether the associated article is open access.")
    openalex_id: Optional[str] = Field(None, description="OpenAlex work ID.")
    semantic_scholar_paper_id: Optional[str] = Field(None, description="Semantic Scholar paper ID.")
    article_publisher: Optional[str] = Field(None, description="Publisher name.")

    @model_validator(mode="before")
    @classmethod
    def _normalize_dois(cls, data: dict) -> dict:
        for field in ("source_doi", "article_doi"):
            val = data.get(field)
            if isinstance(val, str) and val.strip():
                normalized = normalize_doi(val)
                data[field] = normalized if normalized else None
        return data

    def pdf_path_exists(self) -> bool:
        return bool(self.pdf_local_path and Path(self.pdf_local_path).exists())

    def doi_filename_stem(self) -> Optional[str]:
        doi = self.article_doi or self.source_doi
        return _doi_filename_stem(doi) if doi else None

    def canonical_id(self) -> str:
        return str(self.article_doi or self.source_doi or self.gt_record_id)


class DataPaperManifest(BaseModel):
    """Collection of DataPaperRecord entries with integrity guarantees."""

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
                f"Duplicate gt_record_id values found in manifest: {sorted(set(duplicates))}."
            )
        return self

    def __len__(self) -> int:
        return len(self.records)

    def __iter__(self):
        return iter(self.records)

    def by_id(self) -> dict[int, DataPaperRecord]:
        return {rec.gt_record_id: rec for rec in self.records}

    def with_pdf(self) -> list[DataPaperRecord]:
        return [record for record in self.records if record.pdf_local_path]

    def with_existing_pdf(self) -> list[DataPaperRecord]:
        return [record for record in self.records if record.pdf_path_exists()]

    def validate_pdf_coverage(self) -> dict[str, Any]:
        with_path = 0
        on_disk = 0
        missing: list[int] = []
        no_path: list[int] = []
        for record in self.records:
            if record.pdf_local_path:
                with_path += 1
                if Path(record.pdf_local_path).exists():
                    on_disk += 1
                else:
                    missing.append(record.gt_record_id)
            else:
                no_path.append(record.gt_record_id)
        return {
            "total": len(self.records),
            "with_pdf_local_path": with_path,
            "pdf_on_disk": on_disk,
            "missing_from_disk": missing,
            "no_pdf_path": no_path,
        }

    def to_csv_rows(self) -> list[dict[str, Any]]:
        return [record.model_dump() for record in self.records]

    def with_pdf_path(self, gt_record_id: int, pdf_local_path: str) -> "DataPaperManifest":
        updated = []
        found = False
        for record in self.records:
            if record.gt_record_id == gt_record_id:
                updated.append(record.model_copy(update={"pdf_local_path": pdf_local_path}))
                found = True
            else:
                updated.append(record)
        if not found:
            raise KeyError(f"gt_record_id {gt_record_id!r} not found in manifest.")
        return DataPaperManifest(records=updated)

    def save_csv(self, output_path: str | Path) -> Path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = list(DataPaperRecord.model_fields.keys())
        with out.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for row in self.to_csv_rows():
                writer.writerow({key: ("" if row.get(key) is None else row[key]) for key in fieldnames})
        return out

    @classmethod
    def load_csv(cls, csv_path: str | Path) -> "DataPaperManifest":
        path = Path(csv_path)
        if not path.exists():
            raise FileNotFoundError(f"Manifest CSV not found: {path}")

        records: list[DataPaperRecord] = []
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                clean = {key: (value if value != "" else None) for key, value in row.items()}
                try:
                    clean["gt_record_id"] = int(clean["gt_record_id"])
                except (TypeError, ValueError) as exc:
                    raise ValueError(f"Invalid gt_record_id in row: {row}") from exc
                if clean.get("is_oa") is not None:
                    clean["is_oa"] = str(clean["is_oa"]).lower() in {"true", "1", "yes"}
                records.append(DataPaperRecord(**clean))
        return cls(records=records)

    @classmethod
    def build(
        cls,
        *,
        gt_path: str | Path = "data/dataset_092624_validated.xlsx",
        pdf_manifest_path: str | Path | None = "data/pdfs/fuster/manifest.csv",
        pdf_dir: str | Path = "data/pdfs",
        raw_path: str | Path | None = None,
        subset_ids: Optional[set[int]] = None,
        allow_missing_pdf: bool = True,
        deduplicate_gt: bool = False,
    ) -> "DataPaperManifest":
        gt = _load_gt_frame(gt_path)
        gt = _merge_raw_abstracts(gt, gt_path, raw_path)

        if gt["id"].duplicated().any():
            duplicates = gt["id"][gt["id"].duplicated()].tolist()
            if deduplicate_gt:
                warnings.warn(
                    f"Duplicate id values in GT XLSX: {sorted(set(duplicates))}. Keeping first occurrence.",
                    stacklevel=2,
                )
                gt = gt.drop_duplicates(subset=["id"], keep="first")
            else:
                raise ValueError(f"Duplicate id values found in GT XLSX: {sorted(set(duplicates))}.")

        if subset_ids is not None:
            missing_from_gt = subset_ids - set(gt["id"])
            if missing_from_gt:
                raise ValueError(f"Subset IDs not found in GT XLSX: {sorted(missing_from_gt)}.")
            gt = gt[gt["id"].isin(subset_ids)].copy()

        pdf_frame = None
        if pdf_manifest_path is not None:
            pdf_frame = _load_pdf_manifest_frame(pdf_manifest_path)
            if pdf_frame["record_id"].duplicated().any():
                duplicates = pdf_frame["record_id"][pdf_frame["record_id"].duplicated(keep=False)].tolist()
                warnings.warn(
                    f"Duplicate record_id values in PDF manifest: {sorted(set(duplicates))}. Keeping last occurrence.",
                    stacklevel=2,
                )
                pdf_frame = pdf_frame.drop_duplicates(subset=["record_id"], keep="last")
            gt = gt.merge(
                pdf_frame,
                left_on="id",
                right_on="record_id",
                how="left",
                suffixes=("", "_pdf"),
            )

        records: list[DataPaperRecord] = []
        no_pdf_ids: list[int] = []
        for _, row in gt.iterrows():
            gt_id = int(row["id"])
            raw_source_url = str(row.get("source_url") or "").strip() or None
            raw_cited_article = str(row.get("cited_article_doi") or "").strip() or None
            raw_dl_path = str(row.get("downloaded_pdf_path") or "").strip() or None

            pdf_local_path = _resolve_pdf_path(raw_dl_path, pdf_dir)
            if pdf_local_path is None:
                no_pdf_ids.append(gt_id)

            is_oa_val = row.get("is_oa_pdf") if "is_oa_pdf" in row.index else None
            if is_oa_val is None or _is_nan_val(is_oa_val):
                is_oa_val = row.get("is_oa")
            is_oa = None if is_oa_val is None or _is_nan_val(is_oa_val) else bool(is_oa_val)

            pdf_url_val = str(row.get("pdf_url_xlsx") or "").strip() or None
            if not pdf_url_val:
                pdf_url_val = str(row.get("pdf_url") or "").strip() or None

            abstract_val = row.get("abstract")
            if _is_nan_val(abstract_val):
                abstract_val = None

            records.append(
                DataPaperRecord(
                    gt_record_id=gt_id,
                    source=str(row.get("source") or "").strip() or None,
                    title=str(row.get("title") or "").strip() or None,
                    abstract=str(abstract_val).strip() if abstract_val else None,
                    source_doi=extract_doi_from_url(raw_source_url) if raw_source_url else None,
                    source_url=raw_source_url,
                    article_doi=extract_doi_from_url(raw_cited_article) if raw_cited_article else None,
                    article_url=str(row.get("journal_url") or "").strip() or None,
                    pdf_url=pdf_url_val,
                    pdf_local_path=pdf_local_path,
                    is_oa=is_oa,
                    openalex_id=str(row.get("openalex_id") or "").strip() or None,
                    semantic_scholar_paper_id=str(row.get("semantic_scholar_paper_id") or "").strip() or None,
                    article_publisher=str(row.get("article_publisher") or "").strip() or None,
                )
            )

        if no_pdf_ids and not allow_missing_pdf and pdf_manifest_path is not None:
            raise ValueError(f"{len(no_pdf_ids)} records have no resolved pdf_local_path: {sorted(no_pdf_ids)}")
        if no_pdf_ids and pdf_manifest_path is not None:
            warnings.warn(
                f"{len(no_pdf_ids)} records have no resolved pdf_local_path: {sorted(no_pdf_ids)}",
                stacklevel=2,
            )

        return cls(records=records)


class RunRecord(BaseModel):
    """Per-record extraction artifact."""

    gt_record_id: int
    record_id: str
    mode: ExtractionMode
    status: str
    error_message: Optional[str] = None
    title: Optional[str] = None
    abstract: Optional[str] = None
    pdf_path: Optional[str] = None
    input_text: Optional[str] = None
    extraction_method: Optional[str] = None
    usage_cost: Optional[dict[str, Any]] = None
    output: Optional[dict[str, Any]] = None


class RunArtifact(BaseModel):
    """Canonical persisted output for extraction and prompt-eval runs."""

    name: str
    mode: ExtractionMode
    manifest_path: Optional[str] = None
    prompt_module: str
    system_message: str
    model: str
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    records: list[RunRecord] = Field(default_factory=list)
    evaluation: Optional[dict[str, Any]] = None

    @property
    def total_cost_usd(self) -> float:
        return round(
            sum((record.usage_cost or {}).get("total_cost", 0) or 0 for record in self.records),
            4,
        )

    def extraction_csv_fieldnames(self) -> list[str]:
        base_fields = [
            "gt_record_id",
            "record_id",
            "mode",
            "status",
            "title",
            "extraction_method",
            "cost_usd",
            "error_message",
            "pdf_path",
        ]
        seen = set(base_fields)
        output_fields: list[str] = []
        for record in self.records:
            if not record.output:
                continue
            for key in record.output.keys():
                if key in seen:
                    continue
                seen.add(key)
                output_fields.append(key)
        return [*base_fields, *output_fields]

    @staticmethod
    def _csv_cell(value: Any) -> Any:
        if value is None:
            return ""
        if isinstance(value, (list, dict)):
            return json.dumps(value, ensure_ascii=True)
        return value

    def to_extraction_rows(self) -> list[dict[str, Any]]:
        fieldnames = self.extraction_csv_fieldnames()
        rows: list[dict[str, Any]] = []
        for record in self.records:
            row: dict[str, Any] = {
                "gt_record_id": record.gt_record_id,
                "record_id": record.record_id,
                "mode": record.mode.value,
                "status": record.status,
                "title": record.title,
                "extraction_method": record.extraction_method,
                "cost_usd": (record.usage_cost or {}).get("total_cost"),
                "error_message": record.error_message,
                "pdf_path": record.pdf_path,
            }
            if record.output:
                row.update(record.output)
            rows.append({key: self._csv_cell(row.get(key)) for key in fieldnames})
        return rows

    def save_json(self, output_path: str | Path) -> Path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(self.model_dump_json(indent=2), encoding="utf-8")
        return out

    def save_extraction_csv(self, output_path: str | Path) -> Path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = self.extraction_csv_fieldnames()
        with out.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for row in self.to_extraction_rows():
                writer.writerow(row)
        return out

    @classmethod
    def load_json(cls, input_path: str | Path) -> "RunArtifact":
        return cls.model_validate_json(Path(input_path).read_text(encoding="utf-8"))

    def predictions_by_id(self, model_type: type[BaseModel]) -> dict[str, BaseModel]:
        predictions: dict[str, BaseModel] = {}
        for record in self.records:
            if record.status != "success" or record.output is None:
                continue
            predictions[str(record.gt_record_id)] = model_type.model_validate(record.output)
        return predictions
