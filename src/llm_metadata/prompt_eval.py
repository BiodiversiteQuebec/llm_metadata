"""llm_metadata.prompt_eval

CLI + Python API for the extract-evaluate loop.

Runs GPT extraction against a subset of ground-truth records and computes
precision/recall/F1 metrics per field using groundtruth_eval.

Usage (Python API):
    from llm_metadata.prompt_eval import run_eval
    report = run_eval(
        prompt_module="prompts.abstract",
        subset_path="data/dev_subset.csv",
        model="gpt-5-mini",
    )

Usage (CLI):
    uv run python -m llm_metadata.prompt_eval \\
        --prompt prompts.abstract \\
        --subset data/dev_subset.csv \\
        --fields data_type,species,time_series \\
        --name run_01
"""

from __future__ import annotations

import ast
import importlib
import sys
import warnings
from pathlib import Path
from typing import Optional

from llm_metadata.groundtruth_eval import (
    DEFAULT_FIELD_STRATEGIES,
    EvaluationConfig,
    EvaluationReport,
    evaluate_indexed,
)
from llm_metadata.schemas.fuster_features import DatasetFeatures, DatasetFeaturesNormalized


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Columns that XLSX stores as Python list repr strings (from pandas .to_excel)
_LIST_COLS = ["data_type", "geospatial_info_dataset", "species"]

# Raw XLSX with abstract / full_text column (sibling of gt_path by default)
_DEFAULT_RAW_PATH = "data/dataset_092624.xlsx"

# Per-record metadata bundled into saved JSON for self-contained viewer runs
_RECORD_META_COLS = [
    "title", "source_url", "journal_url", "pdf_url",
    "is_oa", "cited_article_doi", "source",
    "valid_yn", "reason_not_valid", "has_abstract",
]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _parse_excel_val(val):
    """Parse Python list repr from Excel back to native types.

    pandas .to_excel() serialises list values as their repr string, e.g.
    "['genetic_analysis']" — we restore them here before Pydantic validation.
    """
    if val is None:
        return None
    try:
        import pandas as pd  # type: ignore
        if isinstance(val, float) and pd.isna(val):
            return None
    except ImportError:
        pass
    if isinstance(val, list):
        return val
    if isinstance(val, str):
        s = val.strip()
        if s.startswith("["):
            try:
                return ast.literal_eval(s)
            except Exception:
                pass
    return val


def _load_ground_truth(
    gt_path: str,
    raw_path: str,
) -> "pd.DataFrame":  # type: ignore[name-defined]
    """Load and merge validated GT with raw XLSX (for abstract text).

    Returns a DataFrame with an 'abstract' column (from full_text in raw)
    merged on record 'id'.
    """
    try:
        import pandas as pd  # type: ignore
    except ImportError as exc:
        raise ImportError(
            "pandas is required for prompt_eval; install with `pip install pandas openpyxl`."
        ) from exc

    validated_df = pd.read_excel(gt_path)

    # Parse list columns that may have been round-tripped through Excel repr
    for col in _LIST_COLS:
        if col in validated_df.columns:
            validated_df[col] = validated_df[col].map(_parse_excel_val)

    # Load abstract text from raw XLSX if it exists
    raw_xlsx = Path(raw_path)
    if raw_xlsx.exists() and "abstract" not in validated_df.columns:
        try:
            raw_df = pd.read_excel(str(raw_xlsx), usecols=["id", "full_text"])
            raw_df = raw_df.rename(columns={"full_text": "abstract"})
            raw_df["id"] = raw_df["id"].astype(int)
            validated_df["id"] = validated_df["id"].astype(int)
            validated_df = validated_df.merge(raw_df, on="id", how="left")
        except Exception as exc:
            warnings.warn(
                f"Could not merge abstract text from {raw_xlsx}: {exc}",
                stacklevel=3,
            )

    return validated_df


def _build_true_by_id(
    df: "pd.DataFrame",  # type: ignore[name-defined]
    subset_dois: Optional[set[str]] = None,
) -> dict[str, DatasetFeaturesNormalized]:
    """Validate GT rows through DatasetFeaturesNormalized and return id-keyed dict.

    Record ID is ``str(int(row.id))``.  Rows without an abstract are skipped.
    If subset_dois is provided, only matching source_url DOIs are kept.
    """
    try:
        import pandas as pd  # type: ignore
    except ImportError as exc:
        raise ImportError("pandas is required") from exc

    # The relevant annotation columns (all fields in DatasetFeaturesNormalized)
    annotation_cols = [
        "data_type", "geospatial_info_dataset", "spatial_range_km2",
        "temporal_range", "temp_range_i", "temp_range_f",
        "species", "referred_dataset",
        "time_series", "multispecies", "threatened_species",
        "new_species_science", "new_species_region", "bias_north_south",
        "valid_yn", "reason_not_valid",
        "source", "source_url", "journal_url", "pdf_url", "is_oa", "cited_article_doi",
    ]
    available_cols = [c for c in annotation_cols if c in df.columns]

    true_by_id: dict[str, DatasetFeaturesNormalized] = {}

    for _, row in df.iterrows():
        # Skip rows without abstract
        abstract_val = row.get("abstract") if "abstract" in df.columns else None
        if abstract_val is None or (hasattr(abstract_val, "__float__") and _is_nan(abstract_val)):
            print(
                f"Warning: skipping record id={row.get('id', '?')} — no abstract text.",
                file=sys.stderr,
            )
            continue

        # Apply DOI filter if subset provided
        if subset_dois is not None:
            source_url = str(row.get("source_url", "") or "")
            doi = source_url.replace("https://doi.org/", "").strip()
            if doi not in subset_dois and source_url not in subset_dois:
                continue

        record_id = str(int(row["id"]))
        row_dict = {col: row[col] for col in available_cols if col in row.index}

        try:
            validated = DatasetFeaturesNormalized.model_validate(row_dict)
            true_by_id[record_id] = validated
        except Exception as exc:
            print(
                f"Warning: GT validation failed for id={record_id}: {exc}",
                file=sys.stderr,
            )

    return true_by_id


def _is_nan(val) -> bool:
    """Return True if val is a float NaN."""
    try:
        import math
        return math.isnan(float(val))
    except (TypeError, ValueError):
        return False


def _load_subset_dois(subset_path: str) -> set[str]:
    """Load DOIs from a dev_subset.csv file.

    The CSV must have a 'doi' column; other columns (source, notes) are ignored.
    Returns a set of DOI strings (bare, without https://doi.org/ prefix).
    """
    try:
        import pandas as pd  # type: ignore
    except ImportError as exc:
        raise ImportError("pandas is required") from exc

    subset_df = pd.read_csv(subset_path)
    if "doi" not in subset_df.columns:
        raise ValueError(
            f"dev_subset CSV at '{subset_path}' must have a 'doi' column; "
            f"found columns: {subset_df.columns.tolist()}"
        )
    return set(subset_df["doi"].dropna().str.strip().tolist())


def _strip_doi_prefix(doi: str) -> str:
    """Strip https://doi.org/ or http://doi.org/ prefix from a DOI string."""
    return (
        doi.replace("https://doi.org/", "")
        .replace("http://doi.org/", "")
        .strip()
    )


def _doi_to_pdf_path(doi: str, pdf_dir: str) -> Optional[Path]:
    """Return Path to the PDF for *doi* under *pdf_dir*, or None if not found.

    Convention: DOI slashes are replaced with underscores to form the filename,
    e.g. ``10.1371/journal.pone.0128238`` → ``10.1371_journal.pone.0128238.pdf``.
    """
    bare = _strip_doi_prefix(doi)
    filename = bare.replace("/", "_") + ".pdf"
    path = Path(pdf_dir) / filename
    return path if path.exists() else None


def _build_doi_by_id(df: "pd.DataFrame") -> "dict[str, str]":  # type: ignore[name-defined]
    """Return record_id -> bare DOI from the GT dataframe's source_url column."""
    result: dict[str, str] = {}
    for _, row in df.iterrows():
        source_url = str(row.get("source_url", "") or "")
        if not source_url:
            continue
        doi = _strip_doi_prefix(source_url)
        try:
            record_id = str(int(row["id"]))
        except (ValueError, TypeError):
            continue
        if doi:
            result[record_id] = doi
    return result


def _record_meta_value(val):
    """Convert DataFrame scalar values to JSON-safe metadata values."""
    if val is None:
        return None
    if hasattr(val, "item") and callable(val.item):
        try:
            val = val.item()
        except Exception:
            pass
    try:
        import pandas as pd  # type: ignore
        if pd.isna(val):
            return None
    except Exception:
        pass
    return val


def _build_records_dict(
    df: "pd.DataFrame",  # type: ignore[name-defined]
    record_ids: set[str],
) -> dict[str, dict]:
    """Build record_id -> metadata dict used by the eval viewer."""
    records: dict[str, dict] = {}
    available_meta = [c for c in _RECORD_META_COLS if c in df.columns]

    for _, row in df.iterrows():
        try:
            record_id = str(int(row["id"]))
        except (ValueError, TypeError):
            continue
        if record_id not in record_ids:
            continue

        record_meta = {
            col: _record_meta_value(row.get(col))
            for col in available_meta
        }
        record_meta["abstract"] = _record_meta_value(row.get("abstract"))
        records[record_id] = record_meta

    for record_id in record_ids:
        if record_id not in records:
            records[record_id] = {
                col: None for col in _RECORD_META_COLS
            }
            records[record_id]["abstract"] = None

    return records


# ---------------------------------------------------------------------------
# Public Python API
# ---------------------------------------------------------------------------


def run_eval(
    *,
    prompt_module: Optional[str] = None,
    subset_path: Optional[str] = None,
    config: Optional[EvaluationConfig] = None,
    config_path: Optional[str] = None,
    fields: Optional[list[str]] = None,
    model: str = "gpt-5-mini",
    gt_path: str = "data/dataset_092624_validated.xlsx",
    raw_path: str = _DEFAULT_RAW_PATH,
    pdf_dir: Optional[str] = None,
    name: Optional[str] = None,
) -> EvaluationReport:
    """Run extraction + evaluation on a subset of records.

    Args:
        prompt_module: Dotted module path (relative to llm_metadata) for the
            prompt, e.g. "prompts.abstract" or "prompts.pdf_file".  The module
            must expose a SYSTEM_MESSAGE string.  Defaults to
            "prompts.pdf_file" when *pdf_dir* is set, "prompts.abstract"
            otherwise.
        subset_path: Path to dev_subset.csv (doi, source, notes). If None,
            uses all records from gt_path that have an abstract.
        config: EvaluationConfig to use. Takes precedence over config_path.
        config_path: Path to a JSON config file (EvaluationConfig.from_json).
            If both config and config_path are None, uses DEFAULT_FIELD_STRATEGIES.
        fields: Optional list of field names to evaluate. If None, the config's
            field_strategies keys are used (or common model fields).
        model: OpenAI model name.
        gt_path: Path to validated ground truth XLSX.
        raw_path: Path to the raw XLSX containing the abstract/full_text column.
            Defaults to ``data/dataset_092624.xlsx`` alongside gt_path.
        pdf_dir: Directory containing PDFs named ``{doi_with_slashes_as_underscores}.pdf``.
            When set, extraction uses the OpenAI File API (classify_pdf_file)
            instead of abstract text.  Records without a matching PDF are skipped.
        name: Optional run name. When provided, auto-saves to ``data/{name}.json``.

    Returns:
        EvaluationReport with per-field metrics and per-record results.
        The report has an extra ``total_cost_usd`` float attribute with the
        cumulative API cost for the run.
    """
    # Default prompt module based on extraction mode
    if prompt_module is None:
        prompt_module = "prompts.pdf_file" if pdf_dir is not None else "prompts.abstract"
    # 1. Resolve evaluation config
    if config is not None:
        eval_config = config
    elif config_path is not None:
        eval_config = EvaluationConfig.from_json(config_path)
    else:
        eval_config = EvaluationConfig(field_strategies=DEFAULT_FIELD_STRATEGIES)

    # 2. Load prompt module and resolve SYSTEM_MESSAGE
    try:
        mod = importlib.import_module(f"llm_metadata.{prompt_module}")
    except ModuleNotFoundError:
        # Allow fully-qualified module path as fallback
        mod = importlib.import_module(prompt_module)
    system_message: str = mod.SYSTEM_MESSAGE

    # 3. Derive raw_path from gt_path if caller didn't specify
    gt_resolved = Path(gt_path)
    if raw_path == _DEFAULT_RAW_PATH:
        # If gt_path lives in the same 'data/' dir, look for the companion file
        companion = gt_resolved.parent / "dataset_092624.xlsx"
        if companion.exists():
            raw_path = str(companion)

    # 4. Load ground truth DataFrame (merges abstract from raw xlsx)
    df = _load_ground_truth(str(gt_resolved), raw_path)

    # 5. Load subset DOIs if provided
    subset_dois: Optional[set[str]] = None
    if subset_path is not None:
        subset_dois = _load_subset_dois(subset_path)

    # 6. Validate GT rows into Pydantic models, keyed by record id
    true_by_id = _build_true_by_id(df, subset_dois=subset_dois)

    if not true_by_id:
        raise ValueError(
            "No valid ground truth records found. Check gt_path, subset_path, "
            "and that the raw XLSX with abstract text is accessible."
        )

    # 7. Run extraction for each GT record
    pred_by_id: dict[str, DatasetFeatures] = {}
    results: list[dict] = []

    if pdf_dir is not None:
        # --- PDF mode: use OpenAI File API ---
        from llm_metadata.gpt_classify import classify_pdf_file  # local import

        doi_by_id = _build_doi_by_id(df)
        skipped_no_doi = 0
        skipped_no_pdf = 0

        for record_id, _true_model in true_by_id.items():
            doi = doi_by_id.get(record_id)
            if doi is None:
                skipped_no_doi += 1
                print(
                    f"Warning: no source DOI for id={record_id}, skipping.",
                    file=sys.stderr,
                )
                continue

            pdf_path = _doi_to_pdf_path(doi, pdf_dir)
            if pdf_path is None:
                skipped_no_pdf += 1
                print(
                    f"Warning: PDF not found for doi={doi} in {pdf_dir}, skipping.",
                    file=sys.stderr,
                )
                continue

            try:
                result = classify_pdf_file(
                    pdf_path=pdf_path,
                    system_message=system_message,
                    model=model,
                    text_format=DatasetFeatures,
                )
                pred_by_id[record_id] = result["output"]
                results.append(result)
            except Exception as exc:
                print(
                    f"Warning: extraction failed for id={record_id} ({doi}): {exc}",
                    file=sys.stderr,
                )

        if skipped_no_doi or skipped_no_pdf:
            print(
                f"PDF mode: skipped {skipped_no_doi} records (no DOI), "
                f"{skipped_no_pdf} records (no PDF found).",
                file=sys.stderr,
            )

    else:
        # --- Abstract mode ---
        from llm_metadata.gpt_classify import classify_abstract  # local import

        # Build id -> abstract mapping from the dataframe
        if "abstract" in df.columns:
            abstract_by_id = {
                str(int(row["id"])): str(row["abstract"])
                for _, row in df.iterrows()
                if not _is_nan(row.get("abstract"))
                and row.get("abstract") is not None
                and str(int(row["id"])) in true_by_id
            }
        else:
            abstract_by_id = {}

        for record_id, _true_model in true_by_id.items():
            abstract = abstract_by_id.get(record_id)
            if abstract is None:
                print(
                    f"Warning: no abstract for record id={record_id}, skipping extraction.",
                    file=sys.stderr,
                )
                continue

            try:
                result = classify_abstract(
                    abstract=abstract,
                    system_message=system_message,
                    model=model,
                    text_format=DatasetFeatures,
                )
                pred_by_id[record_id] = result["output"]
                results.append(result)
            except Exception as exc:
                print(
                    f"Warning: extraction failed for id={record_id}: {exc}",
                    file=sys.stderr,
                )

    # 8. Evaluate
    report = evaluate_indexed(
        true_by_id=true_by_id,
        pred_by_id=pred_by_id,
        fields=fields,
        config=eval_config,
    )

    # 9. Attach total cost as a simple attribute
    total_cost = sum(
        (r.get("usage_cost") or {}).get("total_cost", 0) or 0
        for r in results
    )
    report.total_cost_usd = total_cost  # type: ignore[attr-defined]

    # 10. Attach self-contained run metadata for downstream save calls
    records_dict = _build_records_dict(df, set(true_by_id.keys()))
    report.records = records_dict  # type: ignore[attr-defined]
    report.system_message = system_message  # type: ignore[attr-defined]
    report.subset_path = subset_path  # type: ignore[attr-defined]

    if name:
        save_path = Path("data") / f"{name}.json"
        report.save(
            save_path,
            name=name,
            prompt_module=prompt_module,
            model=model,
            cost_usd=total_cost,
            records=records_dict,
            system_message=system_message,
            subset_path=subset_path,
        )
        report.saved_path = str(save_path)  # type: ignore[attr-defined]

    return report


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------


def _print_metrics_table(report: EvaluationReport) -> None:
    """Print a simple ASCII table of per-field precision/recall/F1."""
    header = f"{'Field':<25} {'N':>5}  {'P':>6}  {'R':>6}  {'F1':>6}"
    separator = "-" * len(header)
    print(header)
    print(separator)
    for fname in sorted(report.field_metrics.keys()):
        m = report.field_metrics[fname]
        p = f"{m.precision:.3f}" if m.precision is not None else "  N/A"
        r = f"{m.recall:.3f}" if m.recall is not None else "  N/A"
        f1 = f"{m.f1:.3f}" if m.f1 is not None else "  N/A"
        print(f"{fname:<25} {m.n:>5}  {p:>6}  {r:>6}  {f1:>6}")

    # Print total cost if attached
    total_cost = getattr(report, "total_cost_usd", None)
    if total_cost is not None:
        print(f"\nTotal API cost: ${total_cost:.4f}")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI entry point: uv run python -m llm_metadata.prompt_eval [args]"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Run extraction + evaluation loop for a prompt against ground truth."
    )
    parser.add_argument(
        "--prompt",
        default=None,
        help=(
            "Prompt module path relative to llm_metadata "
            "(e.g. prompts.abstract, prompts.pdf_file). "
            "Defaults to prompts.pdf_file when --pdf-dir is set, prompts.abstract otherwise."
        ),
    )
    parser.add_argument(
        "--pdf-dir",
        default=None,
        dest="pdf_dir",
        help=(
            "Directory containing PDFs named {doi_with_slashes_as_underscores}.pdf. "
            "When set, switches to PDF extraction mode using the OpenAI File API."
        ),
    )
    parser.add_argument(
        "--subset",
        default=None,
        help="Path to dev_subset.csv (columns: doi, source, notes). "
             "If omitted, all GT records with an abstract are used.",
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Path to an EvaluationConfig JSON file.",
    )
    parser.add_argument(
        "--fields",
        default=None,
        help="Comma-separated list of field names to evaluate. "
             "If omitted, uses the config's field_strategies keys.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Path to save the EvaluationReport as JSON.",
    )
    parser.add_argument(
        "--name",
        default=None,
        help="Run name. Auto-saves to data/{name}.json. --output takes precedence.",
    )
    parser.add_argument(
        "--model",
        default="gpt-5-mini",
        help="OpenAI model name (default: gpt-5-mini).",
    )
    parser.add_argument(
        "--gt",
        default="data/dataset_092624_validated.xlsx",
        help="Path to the validated ground truth XLSX.",
    )
    args = parser.parse_args()

    fields = [f.strip() for f in args.fields.split(",")] if args.fields else None

    report = run_eval(
        prompt_module=args.prompt,
        subset_path=args.subset,
        config_path=args.config,
        fields=fields,
        model=args.model,
        gt_path=args.gt,
        pdf_dir=args.pdf_dir,
        name=args.name if not args.output else None,
    )

    _print_metrics_table(report)

    if args.output:
        # Resolve the effective prompt module name for metadata
        effective_prompt = args.prompt or (
            "prompts.pdf_file" if args.pdf_dir else "prompts.abstract"
        )
        report.save(
            args.output,
            name=args.name,
            prompt_module=effective_prompt,
            model=args.model,
            cost_usd=getattr(report, "total_cost_usd", None),
            records=getattr(report, "records", None),
            system_message=getattr(report, "system_message", None),
            subset_path=args.subset,
        )
        print(f"\nReport saved to: {args.output}")
    elif args.name:
        saved_path = getattr(report, "saved_path", f"data/{args.name}.json")
        print(f"\nReport saved to: {saved_path}")


if __name__ == "__main__":
    main()
