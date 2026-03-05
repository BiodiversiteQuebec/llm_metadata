"""data_paper_manifest — Build and persist canonical DataPaperManifest.

Joins the validated GT XLSX with the fuster PDF manifest CSV to produce a
DataPaperManifest where each record has a resolved pdf_local_path.

Typical usage
-------------
    from llm_metadata.data_paper_manifest import build_manifest, save_manifest_csv

    manifest = build_manifest(
        gt_path="data/dataset_092624_validated.xlsx",
        pdf_manifest_path="data/pdfs/fuster/manifest.csv",
        pdf_dir="data/pdfs",
        subset_ids={9, 19, 27},   # optional: filter to these gt_record_ids
    )
    save_manifest_csv(manifest, "data/manifests/dev_subset_data_paper.csv")

CLI
---
    uv run python -m llm_metadata.data_paper_manifest \\
        --gt data/dataset_092624_validated.xlsx \\
        --pdf-manifest data/pdfs/fuster/manifest.csv \\
        --pdf-dir data/pdfs \\
        --subset-ids 9,19,27 \\
        --output data/manifests/dev_subset_data_paper.csv
"""

from __future__ import annotations

import csv
import math
import sys
import warnings
from pathlib import Path
from typing import Optional

from llm_metadata.schemas.data_paper import DataPaperManifest, DataPaperRecord
from llm_metadata.doi_utils import extract_doi_from_url


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _resolve_pdf_path(raw_path: str, pdf_dir: str | Path) -> Optional[str]:
    """Resolve a relative downloaded_pdf_path entry to an absolute path.

    The fuster manifest stores paths like ``fuster\\10.1002_ece3.4685.pdf``
    which are relative to the *pdf_dir* root (e.g. ``data/pdfs``).
    Both forward- and back-slashes are normalised.
    """
    if not raw_path or str(raw_path).strip() in ("", "nan"):
        return None
    # Normalise path separators
    clean = str(raw_path).replace("\\", "/").strip()
    resolved = Path(pdf_dir) / clean
    return str(resolved)


def _load_gt(gt_path: str | Path) -> "pd.DataFrame":  # type: ignore[name-defined]
    """Load the validated GT XLSX and return a DataFrame."""
    try:
        import pandas as pd  # type: ignore
    except ImportError as exc:
        raise ImportError("pandas is required; pip install pandas openpyxl") from exc

    df = pd.read_excel(str(gt_path))
    df["id"] = df["id"].astype(int)
    return df


def _load_pdf_manifest(manifest_path: str | Path) -> "pd.DataFrame":  # type: ignore[name-defined]
    """Load the fuster PDF manifest CSV."""
    try:
        import pandas as pd  # type: ignore
    except ImportError as exc:
        raise ImportError("pandas is required") from exc

    m = pd.read_csv(str(manifest_path))
    if "record_id" not in m.columns:
        raise ValueError(
            f"PDF manifest at '{manifest_path}' must have a 'record_id' column; "
            f"found: {m.columns.tolist()}"
        )
    m["record_id"] = m["record_id"].astype(int)
    return m


# ---------------------------------------------------------------------------
# Public builder API
# ---------------------------------------------------------------------------


def build_manifest(
    gt_path: str | Path = "data/dataset_092624_validated.xlsx",
    pdf_manifest_path: str | Path = "data/pdfs/fuster/manifest.csv",
    pdf_dir: str | Path = "data/pdfs",
    subset_ids: Optional[set[int]] = None,
    allow_missing_pdf: bool = True,
    deduplicate_gt: bool = False,
) -> DataPaperManifest:
    """Build a DataPaperManifest by joining GT XLSX with the PDF manifest.

    Parameters
    ----------
    gt_path:
        Path to the validated ground-truth XLSX.
    pdf_manifest_path:
        Path to the PDF download manifest CSV (fuster/manifest.csv).
    pdf_dir:
        Root directory for PDF files. Relative paths in the PDF manifest
        are resolved against this directory.
    subset_ids:
        Optional set of gt_record_ids to include. When provided, only these
        records appear in the output manifest.
    allow_missing_pdf:
        If False, raises ValueError when a record has no resolved PDF.
        Default True (warnings only).
    deduplicate_gt:
        If True, silently keep the first occurrence of duplicate gt_record_ids
        in the GT XLSX (with a warning). If False (default), raises ValueError
        on any duplicates — the recommended behavior for data integrity.

    Returns
    -------
    DataPaperManifest
        Validated manifest. Raises on duplicate gt_record_ids.
    """
    try:
        import pandas as pd  # type: ignore
    except ImportError as exc:
        raise ImportError("pandas is required") from exc

    # Load GT XLSX
    gt = _load_gt(gt_path)

    # Load PDF manifest
    pdf_m = _load_pdf_manifest(pdf_manifest_path)

    # Check for duplicate gt_record_ids in GT
    if gt["id"].duplicated().any():
        dups = gt["id"][gt["id"].duplicated()].tolist()
        if deduplicate_gt:
            warnings.warn(
                f"Duplicate id values in GT XLSX: {sorted(set(dups))}. "
                "Keeping first occurrence per id (deduplicate_gt=True).",
                stacklevel=2,
            )
            gt = gt.drop_duplicates(subset=["id"], keep="first")
        else:
            raise ValueError(
                f"Duplicate id values found in GT XLSX: {sorted(set(dups))}. "
                "Pass deduplicate_gt=True to keep first occurrence, "
                "or deduplicate the input file."
            )

    # Check for duplicate record_ids in PDF manifest; keep last (most recent download)
    if pdf_m["record_id"].duplicated().any():
        dups = pdf_m["record_id"][pdf_m["record_id"].duplicated(keep=False)].tolist()
        warnings.warn(
            f"Duplicate record_id in PDF manifest: {sorted(set(dups))}. "
            "Keeping last occurrence per record_id.",
            stacklevel=2,
        )
        pdf_m = pdf_m.drop_duplicates(subset=["record_id"], keep="last")

    # Filter GT to subset if requested
    if subset_ids is not None:
        missing_from_gt = subset_ids - set(gt["id"])
        if missing_from_gt:
            raise ValueError(
                f"Subset IDs not found in GT XLSX: {sorted(missing_from_gt)}. "
                "Verify subset IDs against the ground truth dataset."
            )
        gt = gt[gt["id"].isin(subset_ids)].copy()

    # Merge PDF manifest info (left join so every GT record is included)
    merged = gt.merge(pdf_m, left_on="id", right_on="record_id", how="left", suffixes=("", "_pdf"))

    records: list[DataPaperRecord] = []
    no_pdf_ids: list[int] = []

    for _, row in merged.iterrows():
        gt_id = int(row["id"])

        # --- source_doi: from GT source_url (dataset repository DOI) ---
        raw_source_url = str(row.get("source_url") or "")
        source_doi = extract_doi_from_url(raw_source_url) if raw_source_url else None

        # --- article_doi: from GT cited_article_doi ---
        raw_cited = str(row.get("cited_article_doi") or "")
        article_doi = extract_doi_from_url(raw_cited) if raw_cited else None

        # --- pdf_local_path: from PDF manifest downloaded_pdf_path ---
        raw_dl_path = str(row.get("downloaded_pdf_path") or "")
        pdf_local_path: Optional[str] = None
        if raw_dl_path and raw_dl_path not in ("nan", ""):
            pdf_local_path = _resolve_pdf_path(raw_dl_path, pdf_dir)

        # --- is_oa: prefer PDF manifest value, fall back to GT ---
        is_oa_val = row.get("is_oa_pdf") if "is_oa_pdf" in row.index else row.get("is_oa")
        if is_oa_val is None or (hasattr(is_oa_val, "__float__") and _is_nan_val(is_oa_val)):
            is_oa_val = row.get("is_oa")
        is_oa: Optional[bool] = None
        if is_oa_val is not None and not _is_nan_val(is_oa_val):
            try:
                is_oa = bool(is_oa_val)
            except (TypeError, ValueError):
                pass

        # --- source ---
        source_val = str(row.get("source") or "").strip() or None

        # --- pdf_url: prefer PDF manifest pdf_url_xlsx, fall back to GT pdf_url ---
        pdf_url_val = str(row.get("pdf_url_xlsx") or "").strip() or None
        if not pdf_url_val:
            pdf_url_val = str(row.get("pdf_url") or "").strip() or None

        # --- article_url: from GT journal_url ---
        article_url_val = str(row.get("journal_url") or "").strip() or None

        if pdf_local_path is None:
            no_pdf_ids.append(gt_id)

        rec = DataPaperRecord(
            gt_record_id=gt_id,
            source=source_val,
            source_doi=source_doi,
            source_url=raw_source_url or None,
            article_doi=article_doi,
            article_url=article_url_val,
            pdf_url=pdf_url_val,
            pdf_local_path=pdf_local_path,
            is_oa=is_oa,
        )
        records.append(rec)

    if no_pdf_ids and not allow_missing_pdf:
        raise ValueError(
            f"{len(no_pdf_ids)} records have no resolved pdf_local_path: {sorted(no_pdf_ids)}"
        )
    if no_pdf_ids:
        warnings.warn(
            f"{len(no_pdf_ids)} records have no resolved pdf_local_path: {sorted(no_pdf_ids)}",
            stacklevel=2,
        )

    return DataPaperManifest(records=records)


def update_record_pdf_path(
    manifest: DataPaperManifest,
    gt_record_id: int,
    pdf_local_path: str,
) -> DataPaperManifest:
    """Return a new manifest with the pdf_local_path updated for one record.

    Since DataPaperRecord is immutable (Pydantic), returns a new
    DataPaperManifest with the updated record replaced in-place.

    Parameters
    ----------
    manifest:
        The source manifest (not mutated).
    gt_record_id:
        The ground-truth record ID whose pdf_local_path to update.
    pdf_local_path:
        New local path to set on the matching record.

    Returns
    -------
    DataPaperManifest
        New manifest instance with the updated record.

    Raises
    ------
    KeyError
        If *gt_record_id* is not found in *manifest*.
    """
    updated_records: list[DataPaperRecord] = []
    found = False
    for rec in manifest.records:
        if rec.gt_record_id == gt_record_id:
            updated_records.append(
                rec.model_copy(update={"pdf_local_path": pdf_local_path})
            )
            found = True
        else:
            updated_records.append(rec)

    if not found:
        raise KeyError(
            f"gt_record_id {gt_record_id!r} not found in manifest. "
            f"Available IDs: {sorted(r.gt_record_id for r in manifest.records)[:10]}..."
        )

    return DataPaperManifest(records=updated_records)


def _is_nan_val(val) -> bool:
    """Return True if val is a float NaN."""
    try:
        return math.isnan(float(val))
    except (TypeError, ValueError):
        return False


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------


# Column order for CSV output — derived from model fields so it stays in sync.
_MANIFEST_COLUMNS: list[str] = list(DataPaperRecord.model_fields.keys())


def save_manifest_csv(manifest: DataPaperManifest, output_path: str | Path) -> Path:
    """Write *manifest* to a CSV file at *output_path*.

    Creates parent directories if they don't exist.
    Returns the resolved output Path.
    """
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_MANIFEST_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in manifest.to_csv_rows():
            writer.writerow({k: ("" if row.get(k) is None else row[k]) for k in _MANIFEST_COLUMNS})

    return out


def load_manifest_csv(csv_path: str | Path) -> DataPaperManifest:
    """Load a DataPaperManifest from a CSV previously written by save_manifest_csv.

    Raises ValueError if the CSV is missing required columns.
    """
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"Manifest CSV not found: {path}")

    records: list[DataPaperRecord] = []
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Convert empty strings to None
            clean = {k: (v if v != "" else None) for k, v in row.items()}
            # gt_record_id must be int
            try:
                clean["gt_record_id"] = int(clean["gt_record_id"])
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Invalid gt_record_id in row: {row}") from exc
            # is_oa is bool
            if clean.get("is_oa") is not None:
                clean["is_oa"] = clean["is_oa"].lower() in ("true", "1", "yes")
            records.append(DataPaperRecord(**clean))

    return DataPaperManifest(records=records)


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI: generate a DataPaperManifest CSV from GT XLSX + PDF manifest."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Build a canonical data-paper manifest CSV.",
    )
    parser.add_argument("--gt", default="data/dataset_092624_validated.xlsx",
                        help="Path to validated GT XLSX.")
    parser.add_argument("--pdf-manifest", default="data/pdfs/fuster/manifest.csv",
                        dest="pdf_manifest",
                        help="Path to fuster PDF download manifest CSV.")
    parser.add_argument("--pdf-dir", default="data/pdfs",
                        dest="pdf_dir",
                        help="Root directory for PDF files.")
    parser.add_argument(
        "--subset-ids",
        default=None,
        help="Comma-separated gt_record_id values to include (e.g., 9,19,27).",
    )
    parser.add_argument("--output", required=True,
                        help="Output path for the manifest CSV.")
    parser.add_argument("--strict", action="store_true",
                        help="Fail if any record has no resolved pdf_local_path.")
    parser.add_argument("--deduplicate-gt", action="store_true", dest="deduplicate_gt",
                        help="Keep first occurrence of duplicate GT IDs (warn instead of error).")
    args = parser.parse_args()

    print(f"Building manifest from GT={args.gt}, PDF manifest={args.pdf_manifest}")
    subset_ids: Optional[set[int]] = None
    if args.subset_ids:
        try:
            subset_ids = {int(token.strip()) for token in args.subset_ids.split(",") if token.strip()}
        except ValueError as exc:
            raise ValueError(
                f"Invalid --subset-ids value {args.subset_ids!r}; expected comma-separated integers."
            ) from exc

    manifest = build_manifest(
        gt_path=args.gt,
        pdf_manifest_path=args.pdf_manifest,
        pdf_dir=args.pdf_dir,
        subset_ids=subset_ids,
        allow_missing_pdf=not args.strict,
        deduplicate_gt=args.deduplicate_gt,
    )

    out = save_manifest_csv(manifest, args.output)

    cov = manifest.validate_pdf_coverage()
    print(f"Manifest written: {out}")
    print(f"  Records:        {cov['total']}")
    print(f"  With PDF path:  {cov['with_pdf_local_path']}")
    print(f"  PDF on disk:    {cov['pdf_on_disk']}")
    if cov["no_pdf_path"]:
        print(f"  No PDF path:    {len(cov['no_pdf_path'])} records (ids: {cov['no_pdf_path'][:5]}{'...' if len(cov['no_pdf_path']) > 5 else ''})")
    if cov["missing_from_disk"]:
        print(f"  Path set but file missing: {len(cov['missing_from_disk'])} records")

    sys.exit(0)


if __name__ == "__main__":
    main()
