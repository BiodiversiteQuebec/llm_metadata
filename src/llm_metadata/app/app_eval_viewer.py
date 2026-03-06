"""Streamlit app for interactive extraction run browsing.

Usage:
    uv run streamlit run app/app_eval_viewer.py

## Tab map

| Tab | Purpose |
|-----|---------|
| Overview | Run metadata, prompt, schema, logs |
| Extraction Output | Non-eval extraction stats, field coverage, raw output dataframe |
| Detailed Metrics | Per-field F1/P/R table with multi-row select; mismatch table with multi-row select |
| Dataset Results | Paper selector → metadata panel + raw extraction output + field results table |
| Compare Runs | Side-by-side delta table with multi-row select |

## Data file dependencies

| File | Required | Used for |
|------|----------|---------|
| `${EVAL_VIEWER_RESULTS_DIR}` (default: `${PROMPT_EVAL_OUTPUT_DIR}` or `artifacts/runs`) | Yes — app stops if none found | Run artifacts (`RunArtifact` JSON) |
| `data/dataset_092624_validated.xlsx` | Optional fallback | Paper title, DOI, links, validity chips in Dataset Results for older run JSON |
| `data/dataset_092624.xlsx` | Optional fallback | Abstract text (full_text column) for older run JSON |
"""
import importlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

import pandas as pd
import streamlit as st
from streamlit.runtime import exists as streamlit_runtime_exists
from streamlit.runtime.scriptrunner_utils.script_run_context import get_script_run_ctx
from streamlit.web.bootstrap import run as streamlit_bootstrap_run

from llm_metadata.gpt_extract import MODEL_COST_PER_1M_TOKENS
from llm_metadata.groundtruth_eval import EvaluationConfig, EvaluationReport, FieldMetrics, FieldResult
from llm_metadata.schemas.data_paper import DataPaperManifest, RunArtifact, RunRecord

RESULTS_DIR = os.getenv("EVAL_VIEWER_RESULTS_DIR") or os.getenv("PROMPT_EVAL_OUTPUT_DIR") or "artifacts/runs"
GT_VALIDATED_PATH = Path("data/dataset_092624_validated.xlsx")
GT_RAW_PATH = Path("data/dataset_092624.xlsx")
APP_DIR = Path(__file__).resolve().parent
ASSETS_DIR = APP_DIR / "assets"
FAVICON_PATH = ASSETS_DIR / "favicon.ico"
LOGO_PATH = ASSETS_DIR / "FRVersion horizontale 2 ligne (couleur)_cropped.png"
EXTRACTION_BASE_COLUMNS = [
    "gt_record_id",
    "record_id",
    "mode",
    "status",
    "title",
    "extraction_method",
    "cache_status",
    "cached_tokens",
    "cost_usd",
    "error_message",
    "pdf_path",
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _resolve_result_files(results_dir: str) -> list[Path]:
    """Resolve JSON result files from a directory path."""
    path = Path((results_dir or "").strip() or "artifacts/runs")
    files = [p for p in path.glob("*.json") if p.is_file()]
    return sorted(files, key=lambda p: (p.name.lower(), str(p).lower()))


def _build_file_label_map(result_files: list[Path]) -> dict[str, Path]:
    """Build unique labels for run selection, handling duplicate file names."""
    name_counts: dict[str, int] = {}
    for path in result_files:
        name_counts[path.name] = name_counts.get(path.name, 0) + 1

    label_map: dict[str, Path] = {}
    for path in result_files:
        if name_counts[path.name] == 1:
            label = path.name
        else:
            try:
                label = str(path.relative_to(Path.cwd()))
            except ValueError:
                label = str(path)
        label_map[label] = path
    return label_map


def _notes_path(run_path: Path) -> Path:
    """Return path for the notes file: same folder as run JSON, .md extension."""
    return run_path.with_name(f"{run_path.stem}_notes.md")


def _log_path(run_path: Path) -> Path:
    """Return path for the run log file: same folder as run JSON, .log extension."""
    return run_path.with_suffix(".log")


def _notes_header(run_path: Path, meta: dict) -> str:
    """Build a markdown header with run metadata for a new notes file."""
    run_name = run_path.name
    prompt = meta.get("prompt_module", "—")
    model = meta.get("model", "—")
    cost = meta.get("cost_usd")
    cost_str = f"${cost:.4f}" if cost is not None else "—"
    ts = meta.get("timestamp", "—")
    try:
        run_ref = str(run_path.relative_to(Path.cwd()))
    except ValueError:
        run_ref = str(run_path)
    return (
        f"# Notes — {run_name}\n\n"
        f"**Prompt:** `{prompt}` · "
        f"**Model:** {model} · "
        f"**Cost:** {cost_str} · "
        f"**Timestamp:** {ts} · "
        f"**Run file:** `{run_ref}`\n\n"
        f"---\n\n"
    )


def _ensure_notes_file(run_path: Path, meta: dict) -> Path:
    """Return the notes file path, creating it with a metadata header if missing."""
    path = _notes_path(run_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(_notes_header(run_path, meta), encoding="utf-8")
    return path


def _open_notes_in_editor(run_path: Path, meta: dict) -> None:
    """Open the run's notes file in VS Code. Creates the file if missing."""
    path = _ensure_notes_file(run_path, meta)
    if sys.platform == "win32":
        os.startfile(str(path))  # noqa: S606 — opens with default .md handler
    else:
        subprocess.Popen(["code", str(path)])


def _df_to_markdown(df: pd.DataFrame) -> str:
    """Convert a DataFrame to a markdown table string."""
    header = "| " + " | ".join(str(c) for c in df.columns) + " |"
    sep = "| " + " | ".join("---" for _ in df.columns) + " |"
    rows = [
        "| " + " | ".join(str(v) for v in row) + " |"
        for _, row in df.iterrows()
    ]
    return "\n".join([header, sep, *rows])


def _selected_rows(df: pd.DataFrame, event) -> list[int]:
    """Extract selected row indices from a dataframe selection event."""
    if event and event.selection and event.selection.rows:
        return list(event.selection.rows)
    return []


def _export_buttons(df: pd.DataFrame, key: str, label: str,
                    event=None) -> None:
    """Render CSV / Markdown / Close export buttons.

    When *event* carries a row selection, only those rows are exported.
    A caption indicates the source table and row count.
    """
    sel = _selected_rows(df, event)
    export_df = df.iloc[sel] if sel else df

    show_key = f"export_show_{key}"
    col_csv, col_md, col_close, _ = st.columns([1, 1, 1, 7])
    if col_csv.button("CSV", key=f"export_csv_{key}", type="tertiary"):
        st.session_state[show_key] = "csv"
    if col_md.button("Markdown", key=f"export_md_{key}", type="tertiary"):
        st.session_state[show_key] = "md"
    if col_close.button("Close", key=f"export_close_{key}", type="tertiary"):
        st.session_state.pop(show_key, None)

    show = st.session_state.get(show_key)
    if show:
        count = f"{len(sel)} of {len(df)} rows selected" if sel else f"all {len(df)} rows"
        if show == "csv":
            caption_line = f"# Rows sampled from: {label} — {count}"
            st.code(export_df.to_csv(index=False) + caption_line, language=None)
        elif show == "md":
            caption_line = f"<!-- Rows sampled from: {label} — {count} -->"
            st.code(_df_to_markdown(export_df) + f"\n\n{caption_line}", language="markdown")


def _report_from_doc(doc: dict) -> Optional[EvaluationReport]:
    if not isinstance(doc, dict) or not doc.get("field_results"):
        return None

    config = EvaluationConfig.from_dict(doc.get("config", {}))
    field_results = [
        FieldResult(
            record_id=str(result["record_id"]),
            field=result["field"],
            true_value=result.get("true_value"),
            pred_value=result.get("pred_value"),
            match=result["match"],
            tp=result.get("tp", 0),
            fp=result.get("fp", 0),
            fn=result.get("fn", 0),
            tn=result.get("tn", 0),
        )
        for result in doc.get("field_results", [])
    ]

    field_metrics: dict[str, FieldMetrics] = {}
    for field_name, metrics in doc.get("field_metrics", {}).items():
        field_metrics[field_name] = FieldMetrics(
            field=field_name,
            tp=metrics.get("tp", 0),
            fp=metrics.get("fp", 0),
            fn=metrics.get("fn", 0),
            tn=metrics.get("tn", 0),
            n=metrics.get("n", 0),
            exact_matches=metrics.get("exact_matches", 0),
        )

    return EvaluationReport(
        field_results=field_results,
        field_metrics=field_metrics,
        config=config,
        abstracts=doc.get("abstracts", {}),
    )


@st.cache_data
def load_run_payload(path: str) -> tuple[Optional[RunArtifact], Optional[EvaluationReport], dict]:
    run_path = Path(path)
    meta = json.loads(run_path.read_text(encoding="utf-8"))
    try:
        artifact = RunArtifact.model_validate(meta)
    except Exception:
        artifact = None
    report_doc = artifact.evaluation if artifact is not None and artifact.evaluation else meta
    return artifact, _report_from_doc(report_doc), meta


def _records_from_legacy_meta(meta: dict) -> Optional[pd.DataFrame]:
    records = meta.get("records")
    if not isinstance(records, dict) or not records:
        return None

    rows: list[dict] = []
    for record_id, rec in records.items():
        if not isinstance(rec, dict):
            continue
        source_url = rec.get("source_url")
        doi = (
            str(source_url).replace("https://doi.org/", "").strip()
            if source_url is not None and str(source_url).strip()
            else None
        )
        rows.append(
            {
                "id": str(record_id),
                "title": rec.get("title"),
                "source_url": source_url,
                "journal_url": rec.get("journal_url"),
                "pdf_url": rec.get("pdf_url"),
                "is_oa": rec.get("is_oa"),
                "cited_article_doi": rec.get("cited_article_doi"),
                "source": rec.get("source"),
                "valid_yn": rec.get("valid_yn"),
                "reason_not_valid": rec.get("reason_not_valid"),
                "has_abstract": rec.get("has_abstract"),
                "doi": doi,
                "abstract": rec.get("abstract"),
            }
        )
    return pd.DataFrame(rows).set_index("id") if rows else None


@st.cache_data
def load_manifest_index(manifest_path: str) -> pd.DataFrame:
    manifest = DataPaperManifest.load_csv(manifest_path)
    rows = [
        {
            "id": str(record.gt_record_id),
            "title": record.title,
            "source_url": record.source_url,
            "journal_url": record.article_url,
            "pdf_url": record.pdf_url,
            "is_oa": record.is_oa,
            "cited_article_doi": record.article_doi,
            "source": record.source.value if record.source is not None else None,
            "valid_yn": None,
            "reason_not_valid": None,
            "has_abstract": bool(record.abstract and record.abstract.strip()),
            "doi": record.article_doi or record.source_doi,
            "abstract": record.abstract,
        }
        for record in manifest.records
    ]
    return pd.DataFrame(rows).set_index("id")


@st.cache_data
def load_gt_index() -> Optional[pd.DataFrame]:
    if not GT_VALIDATED_PATH.exists():
        return None
    df = pd.read_excel(str(GT_VALIDATED_PATH))
    keep_cols = [
        "id",
        "title",
        "source_url",
        "journal_url",
        "pdf_url",
        "is_oa",
        "cited_article_doi",
        "source",
        "valid_yn",
        "reason_not_valid",
        "has_abstract",
    ]
    available = [col for col in keep_cols if col in df.columns]
    df = df[available].copy()
    if "source_url" in df.columns:
        df["doi"] = df["source_url"].fillna("").astype(str).str.replace(r"https?://doi\.org/", "", regex=True).str.strip()
    else:
        df["doi"] = None
    df["id"] = df["id"].astype(str)
    return df.set_index("id")


@st.cache_data
def load_abstracts() -> dict[str, str]:
    if not GT_RAW_PATH.exists():
        return {}
    df = pd.read_excel(str(GT_RAW_PATH), usecols=["id", "full_text"])
    df["id"] = df["id"].astype(str)
    df = df.dropna(subset=["full_text"])
    return dict(zip(df["id"], df["full_text"]))


def _merge_record_index(primary: Optional[pd.DataFrame], secondary: Optional[pd.DataFrame]) -> Optional[pd.DataFrame]:
    if primary is None:
        return secondary
    if secondary is None:
        return primary
    return primary.combine_first(secondary)


def _record_index_for_run(artifact: Optional[RunArtifact], meta: dict) -> Optional[pd.DataFrame]:
    manifest_index = None
    if artifact is not None and artifact.manifest_path:
        manifest_path = Path(artifact.manifest_path)
        if manifest_path.exists():
            manifest_index = load_manifest_index(str(manifest_path))
    return _merge_record_index(_merge_record_index(manifest_index, _records_from_legacy_meta(meta)), load_gt_index())


def _abstracts_for_run(record_index: Optional[pd.DataFrame], report: Optional[EvaluationReport]) -> dict[str, str]:
    abstracts: dict[str, str] = {}
    if record_index is not None and "abstract" in record_index.columns:
        for record_id, value in record_index["abstract"].dropna().items():
            text = str(value).strip()
            if text:
                abstracts[str(record_id)] = text
    if report is not None and report.abstracts:
        abstracts.update({str(key): value for key, value in report.abstracts.items() if value})
    if not abstracts:
        abstracts = load_abstracts()
    return abstracts


def _system_message_from_payload(artifact: Optional[RunArtifact], meta: dict) -> Optional[str]:
    if artifact is not None and artifact.system_message.strip():
        return artifact.system_message
    system_message = meta.get("system_message")
    return system_message if isinstance(system_message, str) and system_message.strip() else None


def _artifact_records_by_id(artifact: Optional[RunArtifact]) -> dict[str, RunRecord]:
    if artifact is None:
        return {}
    return {str(record.gt_record_id): record for record in artifact.records}


def _is_populated_value(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) > 0
    return True


def _cache_status(record: RunRecord) -> str:
    usage_cost = record.usage_cost or {}
    cached_tokens = usage_cost.get("cached_tokens")
    if cached_tokens is None:
        return "unknown"
    return "hit" if cached_tokens > 0 else "miss"


def _input_tokens_used(record: RunRecord) -> Optional[int]:
    usage_cost = record.usage_cost or {}
    input_tokens = usage_cost.get("input_tokens")
    if input_tokens is None:
        return None
    return max(input_tokens - (usage_cost.get("cached_tokens") or 0), 0)


def _input_tokens_value(record: RunRecord) -> Optional[int]:
    usage_cost = record.usage_cost or {}
    return usage_cost.get("input_tokens")


def _cost_value_usd(record: RunRecord, model: str) -> Optional[float]:
    usage_cost = record.usage_cost or {}
    total_cost = usage_cost.get("total_cost")
    cached_tokens = usage_cost.get("cached_tokens")
    model_costs = MODEL_COST_PER_1M_TOKENS.get(model)
    if total_cost is None or cached_tokens is None or model_costs is None:
        return None
    cache_delta = cached_tokens * (model_costs["input"] - model_costs["cache"]) / 1_000_000
    return round(total_cost + cache_delta, 4)


def _cache_savings_usd(record: RunRecord, model: str) -> Optional[float]:
    cost_value = _cost_value_usd(record, model)
    cost_used = (record.usage_cost or {}).get("total_cost")
    if cost_value is None or cost_used is None:
        return None
    return round(cost_value - cost_used, 4)


def _field_coverage_df(artifact: Optional[RunArtifact]) -> pd.DataFrame:
    if artifact is None:
        return pd.DataFrame()
    success_records = [record for record in artifact.records if record.status == "success"]
    if not success_records:
        return pd.DataFrame()
    field_names: list[str] = []
    seen: set[str] = set()
    for record in success_records:
        if not record.output:
            continue
        for field_name in record.output.keys():
            if field_name in seen:
                continue
            seen.add(field_name)
            field_names.append(field_name)
    rows = []
    for field_name in field_names:
        populated = sum(
            1
            for record in success_records
            if record.output is not None and _is_populated_value(record.output.get(field_name))
        )
        rows.append(
            {
                "field": field_name,
                "records_with_value": populated,
                "success_records": len(success_records),
                "fill_rate": round(populated / len(success_records), 3),
            }
        )
    return pd.DataFrame(rows).sort_values(["fill_rate", "field"], ascending=[False, True]).reset_index(drop=True)


def _extraction_df(artifact: Optional[RunArtifact]) -> pd.DataFrame:
    if artifact is None:
        return pd.DataFrame()
    rows = artifact.to_extraction_rows()
    for row, record in zip(rows, artifact.records):
        usage_cost = record.usage_cost or {}
        row["cache_status"] = _cache_status(record)
        row["cached_tokens"] = usage_cost.get("cached_tokens")
        row["input_tokens_used"] = _input_tokens_used(record)
        row["input_tokens_value"] = _input_tokens_value(record)
        row["cost_used_usd"] = usage_cost.get("total_cost")
        row["cost_value_usd"] = _cost_value_usd(record, artifact.model)
        row["cache_savings_usd"] = _cache_savings_usd(record, artifact.model)
    return pd.DataFrame(rows)


def main() -> None:
    # ── Page config & header ─────────────────────────────────────────────────
    st.set_page_config(
        page_title="Extraction evaluation viewer",
        page_icon=str(FAVICON_PATH) if FAVICON_PATH.exists() else None,
        layout="wide",
    )
    st.markdown(
        """
        <style>
        div[data-testid="stMetric"] {
            background: linear-gradient(180deg, #fbfcfe 0%, #f4f7fb 100%);
            border: 1px solid rgba(15, 23, 42, 0.08);
            border-radius: 14px;
            padding: 0.55rem 0.75rem;
            box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
        }
        div[data-testid="stMetricLabel"] p {
            font-weight: 700;
            letter-spacing: 0.01em;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    if LOGO_PATH.exists():
        st.image(str(LOGO_PATH), width=120)

    header_left, header_right = st.columns([3, 2])
    with header_left:
        st.title("Extraction evaluation viewer")
        with st.expander("ℹ️ About this viewer", expanded=False):
            st.caption(
                "Explore AI-extracted ecological metadata from scientific dataset abstracts and "
                "its evaluation against expert annotations to support biodiversity monitoring "
                "and data-gap analysis.\n\n"
                "Select an extraction run from the dropdown on the right, then use the tabs "
                "below to inspect run metadata, field metrics, mismatches, and record-level "
                "results."
            )

    result_files = _resolve_result_files(RESULTS_DIR)
    result_file_map = _build_file_label_map(result_files)
    file_labels = list(result_file_map.keys())

    if not file_labels:
        st.warning(
            "No result files found. "
            f"Set `EVAL_VIEWER_RESULTS_DIR` (current: `{RESULTS_DIR}`) "
            "or run `prompt_eval` first."
        )
        st.stop()

    with header_right:
        st.write("")  # vertical spacing to align with title baseline
        run_a_label = st.selectbox(
            "Run", file_labels, index=0, label_visibility="collapsed",
            format_func=lambda label: result_file_map[label].stem,
        )
    run_a_path = result_file_map[run_a_label]
    run_a_name = run_a_path.name

    artifact_a, report_a, meta_a = load_run_payload(str(run_a_path))
    gt_index = _record_index_for_run(artifact_a, meta_a)
    abstracts = _abstracts_for_run(gt_index, report_a)
    run_records_by_id = _artifact_records_by_id(artifact_a)
    extraction_df = _extraction_df(artifact_a)
    coverage_df = _field_coverage_df(artifact_a)

    # ── Tabs ─────────────────────────────────────────────────────────────────
    tab_overview, tab_output, tab_metrics, tab_records, tab_compare = st.tabs(
        ["Overview", "Extraction Output", "Detailed Metrics", "Dataset Results", "Compare Runs"]
    )

    # ════════════════════════════════════════════════════════════════════════
    # TAB 1 — Overview
    # ════════════════════════════════════════════════════════════════════════
    with tab_overview:
        timestamp = artifact_a.created_at if artifact_a is not None else meta_a.get("timestamp", "—")
        st.markdown(f"**Run:** `{run_a_name}`  |  **Timestamp:** `{timestamp}`")
        if artifact_a is not None and artifact_a.manifest_path:
            st.markdown(f"**Manifest:** `{artifact_a.manifest_path}`")

        details_cols = st.columns(4)
        details_cols[0].metric("Prompt", artifact_a.prompt_module if artifact_a is not None else meta_a.get("prompt_module", "—"))
        details_cols[1].metric("Model", artifact_a.model if artifact_a is not None else meta_a.get("model", "—"))
        details_cols[2].metric("Mode", artifact_a.mode.value if artifact_a is not None else meta_a.get("mode", "—"))
        cost_val = artifact_a.total_cost_usd if artifact_a is not None else meta_a.get("cost_usd")
        details_cols[3].metric("Cost (USD)", f"${cost_val:.4f}" if isinstance(cost_val, (int, float)) else "—")

        evaluated_record_ids = (
            {str(record.gt_record_id) for record in artifact_a.records}
            if artifact_a is not None
            else {str(r.record_id) for r in report_a.field_results} if report_a is not None else set()
        )
        total_evaluated = len(evaluated_record_ids)
        dataset_rows = (
            gt_index.loc[gt_index.index.isin(evaluated_record_ids)]
            if gt_index is not None else pd.DataFrame()
        )

        if not dataset_rows.empty:
            source_series = dataset_rows["source"].fillna("").astype(str).str.strip().str.lower()
            source_dryad = int((source_series == "dryad").sum())
            source_zenodo = int((source_series == "zenodo").sum())
            is_oa_series = dataset_rows["is_oa"].fillna("").astype(str).str.strip().str.lower()
            is_oa_yes = int(is_oa_series.isin({"1", "1.0", "true", "yes"}).sum())

            has_pdf_series = dataset_rows["pdf_url"].fillna("").astype(str).str.strip()
            has_pdf = int((has_pdf_series != "").sum())
        else:
            source_dryad = 0
            source_zenodo = 0
            is_oa_yes = 0
            has_pdf = 0

        count_cols = st.columns(5)
        count_cols[0].metric("Records", total_evaluated)
        count_cols[1].metric("From Dryad", source_dryad)
        count_cols[2].metric("From Zenodo", source_zenodo)
        count_cols[3].metric("Open access", is_oa_yes)
        count_cols[4].metric("Has PDF URL", has_pdf)

        st.divider()

        with st.expander("Run records", expanded=False):
            if gt_index is not None:
                _gt_df = gt_index.reset_index()
                st.dataframe(_gt_df, use_container_width=True, hide_index=True)
                _export_buttons(_gt_df, "gt_index", "Run records")
            else:
                st.caption("No record metadata available for this run.")

        with st.expander("Output schema (DatasetFeaturesExtraction)", expanded=False):
            schema_data = meta_a.get("schema")
            if isinstance(schema_data, dict) and schema_data:
                st.code(json.dumps(schema_data, indent=2), language="json")
            else:
                st.caption("No schema recorded in this run artifact.")

        with st.expander("Prompt", expanded=False):
            serialized_message = _system_message_from_payload(artifact_a, meta_a)
            if serialized_message:
                st.code(serialized_message, language=None)
            else:
                prompt_module_path = artifact_a.prompt_module if artifact_a is not None else meta_a.get("prompt_module")
                if prompt_module_path:
                    try:
                        mod = importlib.import_module(f"llm_metadata.{prompt_module_path}")
                        system_msg = getattr(mod, "SYSTEM_MESSAGE", None)
                        if system_msg:
                            st.code(system_msg, language=None)
                        else:
                            st.warning(f"Module `{prompt_module_path}` has no `SYSTEM_MESSAGE`.")
                    except Exception as exc:
                        st.error(f"Could not import `{prompt_module_path}`: {exc}")
                else:
                    st.info("No prompt metadata recorded in this run.")

        with st.expander("Evaluation config", expanded=False):
            if report_a is not None:
                st.code(json.dumps(report_a.config.to_dict(), indent=2), language="json")
            else:
                st.caption("This run does not include evaluation results.")

        with st.expander("Logs", expanded=False):
            log_file = _log_path(run_a_path)
            if log_file.exists():
                try:
                    log_text = log_file.read_text(encoding="utf-8")
                except Exception as exc:
                    st.error(f"Could not read log file `{log_file}`: {exc}")
                else:
                    st.text_area(
                        "Run log",
                        value=log_text,
                        height=320,
                        disabled=True,
                        key=f"run_log_{run_a_name}",
                    )
            else:
                st.caption(f"No log file found for this run at `{log_file}`.")

    # ════════════════════════════════════════════════════════════════════════
    # TAB 2 — Extraction Output
    # ════════════════════════════════════════════════════════════════════════
    with tab_output:
        if artifact_a is None:
            st.info("Raw extraction output is unavailable for legacy evaluation-only JSON files.")
        else:
            total_records = len(artifact_a.records)
            success_count = sum(record.status == "success" for record in artifact_a.records)
            skipped_count = sum(record.status == "skipped" for record in artifact_a.records)
            error_count = sum(record.status == "error" for record in artifact_a.records)
            output_count = sum(record.output is not None for record in artifact_a.records)
            usage_records = [record for record in artifact_a.records if record.status == "success" and record.usage_cost]
            cache_hit_count = sum(_cache_status(record) == "hit" for record in usage_records)
            cache_miss_count = sum(_cache_status(record) == "miss" for record in usage_records)
            avg_cost = artifact_a.total_cost_usd / success_count if success_count else None
            total_input_tokens_used = sum(_input_tokens_used(record) or 0 for record in usage_records)
            total_input_tokens_value = sum(_input_tokens_value(record) or 0 for record in usage_records)
            total_cached_tokens = sum((record.usage_cost or {}).get("cached_tokens", 0) or 0 for record in usage_records)
            total_cost_used = round(sum((record.usage_cost or {}).get("total_cost", 0) or 0 for record in usage_records), 4)
            cost_value_rows = [cost for cost in (_cost_value_usd(record, artifact_a.model) for record in usage_records) if cost is not None]
            total_cost_value = round(sum(cost_value_rows), 4) if cost_value_rows else None
            total_cache_savings = round(total_cost_value - total_cost_used, 4) if total_cost_value is not None else None
            populated_counts = [
                sum(_is_populated_value(value) for value in (record.output or {}).values())
                for record in artifact_a.records
                if record.status == "success"
            ]
            avg_populated = sum(populated_counts) / len(populated_counts) if populated_counts else None

            st.markdown(
                (
                    "<div style='display:inline-block;margin-bottom:0.45rem;padding:0.18rem 0.68rem;"
                    "border-radius:999px;background:linear-gradient(90deg,#e8f2ff 0%,#d9ecff 100%);"
                    "color:#0f4c81;font-size:0.82rem;font-weight:700;'>Run & cache</div>"
                ),
                unsafe_allow_html=True,
            )
            top_cols = st.columns(8)
            top_cols[0].metric("🧾 Run", total_records)
            top_cols[1].metric("✅ Success", success_count)
            top_cols[2].metric("⏭ Skipped", skipped_count)
            top_cols[3].metric("⛔ Errors", error_count)
            top_cols[4].metric("📤 Output", output_count)
            top_cols[5].metric("🧩 Avg fill", f"{avg_populated:.1f}" if avg_populated is not None else "—")
            top_cols[6].metric("💾 Hits", cache_hit_count)
            top_cols[7].metric("🫥 Misses", cache_miss_count)

            st.markdown(
                (
                    "<div style='display:inline-block;margin:0.35rem 0 0.45rem;padding:0.18rem 0.68rem;"
                    "border-radius:999px;background:linear-gradient(90deg,#eef9ed 0%,#e0f4d8 100%);"
                    "color:#2d6a2d;font-size:0.82rem;font-weight:700;'>Tokens & cost</div>"
                ),
                unsafe_allow_html=True,
            )
            bottom_cols = st.columns(7)
            bottom_cols[0].metric("🪙 Tok used", f"{total_input_tokens_used:,}" if usage_records else "—")
            bottom_cols[1].metric("🪙 Tok value", f"{total_input_tokens_value:,}" if usage_records else "—")
            bottom_cols[2].metric("🪙 Cached", f"{total_cached_tokens:,}" if usage_records else "—")
            bottom_cols[3].metric("💵 Cost used", f"${total_cost_used:.4f}" if usage_records else "—")
            bottom_cols[4].metric("💵 Cost value", f"${total_cost_value:.4f}" if total_cost_value is not None else "—")
            bottom_cols[5].metric("💵 Saved", f"${total_cache_savings:.4f}" if total_cache_savings is not None else "—")
            bottom_cols[6].metric("💵 Avg/run", f"${avg_cost:.4f}" if avg_cost is not None else "—")
            if usage_records:
                st.caption(
                    "Token value / cost value are the no-cache baseline. "
                    "Tokens used / cost used reflect the cached run, with hits based on `usage_cost.cached_tokens` > 0."
                )

            st.divider()
            st.subheader("Field coverage")
            if coverage_df.empty:
                st.caption("No successful extraction outputs were recorded.")
            else:
                coverage_event = st.dataframe(
                    coverage_df,
                    use_container_width=True,
                    hide_index=True,
                    selection_mode="multi-row",
                    on_select="rerun",
                    key="coverage_table",
                )
                _export_buttons(coverage_df, "coverage", "Extraction field coverage", event=coverage_event)

            st.divider()
            st.subheader("Extraction rows")
            selected_status = st.selectbox(
                "Status filter",
                ["all", "success", "skipped", "error"],
                index=0,
                key="extraction_status_filter",
            )
            filtered_extraction_df = extraction_df
            if selected_status != "all" and not filtered_extraction_df.empty:
                filtered_extraction_df = filtered_extraction_df[filtered_extraction_df["status"] == selected_status].reset_index(drop=True)

            if filtered_extraction_df.empty:
                st.caption("No extraction rows match the current filter.")
            else:
                extraction_event = st.dataframe(
                    filtered_extraction_df,
                    use_container_width=True,
                    hide_index=True,
                    selection_mode="multi-row",
                    on_select="rerun",
                    key="extraction_rows_table",
                )
                _export_buttons(filtered_extraction_df, "extraction_rows", "Extraction rows", event=extraction_event)

    # ════════════════════════════════════════════════════════════════════════
    # TAB 3 — Detailed Metrics
    # ════════════════════════════════════════════════════════════════════════
    with tab_metrics:
        if report_a is None:
            st.info("This run does not include evaluation results.")
        else:
            metrics_df = report_a.metrics_to_pandas()

            st.subheader("Per-field metrics")

            _sorted_metrics_df = metrics_df.sort_values("f1", ascending=False).reset_index(drop=True)
            metrics_event = st.dataframe(
                _sorted_metrics_df,
                use_container_width=True,
                selection_mode="multi-row",
                on_select="rerun",
                key="metrics_table",
            )
            _export_buttons(_sorted_metrics_df, "metrics", "Per-field metrics", event=metrics_event)

            st.divider()
            st.subheader("Mismatches")

            all_fields = report_a.fields()
            selected_field = st.selectbox(
                "Select field for mismatches",
                all_fields,
                index=0,
                key="metrics_field_select",
            )

            errors = report_a.errors_for_field(selected_field)
            m = report_a.metrics_for(selected_field)

            p_str = f"{m.precision:.3f}" if m.precision is not None else "N/A"
            r_str = f"{m.recall:.3f}" if m.recall is not None else "N/A"
            f1_str = f"{m.f1:.3f}" if m.f1 is not None else "N/A"
            st.markdown(
                f"**Selected field:** {selected_field} "
                f"({len(errors)} / {m.n} records | P={p_str} R={r_str} F1={f1_str})"
            )

            if errors:
                def _error_doi(record_id) -> str:
                    rid = str(record_id)
                    if gt_index is None or rid not in gt_index.index:
                        return rid
                    row = gt_index.loc[rid]
                    raw_doi = row["doi"]
                    if isinstance(raw_doi, pd.Series):
                        doi_val = raw_doi.iloc[0] if not raw_doi.empty else None
                    else:
                        doi_val = raw_doi
                    if pd.notna(doi_val) and str(doi_val).strip():
                        return str(doi_val).strip()
                    return rid

                error_rows = [
                    {
                        "doi": _error_doi(r.record_id),
                        "true_value": str(r.true_value),
                        "pred_value": str(r.pred_value),
                        "tp": r.tp,
                        "fp": r.fp,
                        "fn": r.fn,
                    }
                    for r in errors
                ]
                error_df = pd.DataFrame(error_rows)

                mismatch_event = st.dataframe(
                    error_df,
                    use_container_width=True,
                    selection_mode="multi-row",
                    on_select="rerun",
                    key=f"mismatch_table_{selected_field}",
                )
                _export_buttons(error_df, f"mismatch_{selected_field}", f"Mismatches for {selected_field}", event=mismatch_event)
            else:
                st.success("No mismatches for this field.")

    # ════════════════════════════════════════════════════════════════════════
    # TAB 4 — Dataset Results
    # ════════════════════════════════════════════════════════════════════════
    with tab_records:
        all_record_ids = (
            [str(record.gt_record_id) for record in artifact_a.records]
            if artifact_a is not None
            else sorted({str(r.record_id) for r in report_a.field_results}, key=lambda x: int(x) if x.isdigit() else x)
            if report_a is not None
            else []
        )

        def _record_label(rid: str) -> str:
            if gt_index is not None and rid in gt_index.index:
                row = gt_index.loc[rid]
                title_val = row["title"].iloc[0] if hasattr(row["title"], "iloc") else row["title"]
                doi_val = row["doi"].iloc[0] if hasattr(row["doi"], "iloc") else row["doi"]
                title = str(title_val) if bool(pd.notna(title_val)) else "Untitled"
                doi = str(doi_val) if bool(pd.notna(doi_val)) else rid
                short_title = title[:60] + "…" if len(title) > 60 else title
                return f"{short_title}\n{doi}"
            return f"Record {rid}"

        if not all_record_ids:
            st.info("No record-level results are available for this run.")
        else:
            record_labels = [_record_label(rid) for rid in all_record_ids]
            label_to_id = dict(zip(record_labels, all_record_ids))

            selected_label = st.selectbox(
                "Select paper",
                record_labels,
                format_func=lambda x: x,
                key="record_selector",
            )
            selected_record_id = label_to_id[selected_label]
            selected_run_record = run_records_by_id.get(selected_record_id)

            st.divider()

            if gt_index is not None and selected_record_id in gt_index.index:
                meta_row = gt_index.loc[selected_record_id]

                def _raw(col: str):
                    if col not in meta_row.index:
                        return None
                    value = meta_row[col]
                    return value.iloc[0] if hasattr(value, "iloc") else value

                def _scalar(col: str) -> str:
                    value = _raw(col)
                    return "" if (value is None or (isinstance(value, float) and pd.isna(value))) else str(value)

                title_full = _scalar("title") or "Untitled"
                st.subheader(title_full)

                with st.expander("Abstract", expanded=False):
                    abstract_text = abstracts.get(selected_record_id, "")
                    if abstract_text:
                        st.markdown(abstract_text)
                    else:
                        st.caption("No abstract available for this record.")

                source_labels = {"dryad": "Dryad", "zenodo": "Zenodo", "semantic_scholar": "Semantic Scholar"}
                links: list[str] = []
                if src_url := _scalar("source_url"):
                    src_label = source_labels.get((_scalar("source") or "").strip().lower(), "Source")
                    links.append(f"[{src_label}]({src_url})")
                if j_url := _scalar("journal_url"):
                    links.append(f"[Article]({j_url})")
                if pdf_url := _scalar("pdf_url"):
                    links.append(f"[PDF]({pdf_url})")
                if cited_doi := _scalar("cited_article_doi"):
                    if not cited_doi.startswith("http"):
                        cited_doi = f"https://doi.org/{cited_doi}"
                    links.append(f"[Cited article]({cited_doi})")
                if links:
                    st.markdown("  ·  ".join(links))

                chip_cols = st.columns(5)
                chip_cols[0].metric("Source", _scalar("source") or "—")
                is_oa_val = _raw("is_oa")
                is_oa_yes = str(is_oa_val).strip().lower() in {"1", "1.0", "true", "yes"}
                chip_cols[1].metric("Open access", "Yes" if is_oa_yes else "No")
                chip_cols[2].metric("Valid", _scalar("valid_yn") or "—")
                has_abs_val = _raw("has_abstract")
                has_abs_yes = str(has_abs_val).strip().lower() in {"1", "1.0", "true", "yes"}
                chip_cols[3].metric("Has abstract", "Yes" if has_abs_yes else "No")
                if selected_run_record is not None:
                    chip_cols[4].metric("Run status", selected_run_record.status)

                doi_str = _scalar("doi")
                st.text_input("DOI", value=doi_str or "—", disabled=True, key=f"doi_display_{selected_record_id}")

                if reason := _scalar("reason_not_valid"):
                    st.caption(f"Exclusion reason: {reason}")

            if selected_run_record is not None:
                st.divider()
                run_cols = st.columns(4)
                run_cols[0].metric("Method", selected_run_record.extraction_method or "—")
                run_cols[1].metric(
                    "Cost (USD)",
                    f"${((selected_run_record.usage_cost or {}).get('total_cost') or 0):.4f}" if selected_run_record.usage_cost else "—",
                )
                run_cols[2].metric("Has output", "Yes" if selected_run_record.output is not None else "No")
                run_cols[3].metric("PDF path", "Yes" if selected_run_record.pdf_path else "No")

                output_rows = [
                    {
                        "field": field_name,
                        "value": json.dumps(value, ensure_ascii=True) if isinstance(value, (list, dict)) else value,
                    }
                    for field_name, value in sorted((selected_run_record.output or {}).items())
                ]
                st.subheader("Extracted output")
                if output_rows:
                    output_df = pd.DataFrame(output_rows)
                    output_event = st.dataframe(
                        output_df,
                        use_container_width=True,
                        hide_index=True,
                        selection_mode="multi-row",
                        on_select="rerun",
                        key=f"record_output_{selected_record_id}",
                    )
                    _export_buttons(output_df, f"record_output_{selected_record_id}", f"Record {selected_record_id} extracted output", event=output_event)
                else:
                    st.caption(selected_run_record.error_message or "No extracted output for this record.")

            if report_a is not None:
                st.divider()
                record_results = report_a.results_for_record(selected_record_id)
                st.subheader("Evaluation results")
                if record_results:
                    rows = [
                        {
                            "field": r.field,
                            "true_value": str(r.true_value),
                            "predicted": str(r.pred_value),
                            "match": "✓" if r.match else "✗",
                            "tp": r.tp,
                            "fp": r.fp,
                            "fn": r.fn,
                        }
                        for r in sorted(record_results, key=lambda r: r.field)
                    ]
                    record_df = pd.DataFrame(rows)
                    record_event = st.dataframe(
                        record_df,
                        use_container_width=True,
                        hide_index=True,
                        selection_mode="multi-row",
                        on_select="rerun",
                        key=f"record_table_{selected_record_id}",
                    )
                    _export_buttons(record_df, f"record_{selected_record_id}", f"Record {selected_record_id} results", event=record_event)
                else:
                    st.info("No evaluation results for this record.")

    # ════════════════════════════════════════════════════════════════════════
    # TAB 5 — Compare Runs
    # ════════════════════════════════════════════════════════════════════════
    with tab_compare:
        col_a, col_b = st.columns(2)
        _fmt_run = lambda label: result_file_map[label].stem
        with col_a:
            run_a_cmp = st.selectbox("Run A", file_labels, index=0, key="cmp_run_a",
                                      format_func=_fmt_run)
        with col_b:
            other_names = [n for n in file_labels if n != run_a_cmp]
            run_b_cmp = st.selectbox(
                "Run B",
                other_names if other_names else file_labels,
                index=0,
                key="cmp_run_b",
                format_func=_fmt_run,
            )

        if run_a_cmp == run_b_cmp:
            st.warning("Select two different runs to compare.")
        else:
            _, report_cmp_a, _ = load_run_payload(str(result_file_map[run_a_cmp]))
            _, report_cmp_b, _ = load_run_payload(str(result_file_map[run_b_cmp]))

            if report_cmp_a is None or report_cmp_b is None:
                st.info("Both selected runs must include evaluation payloads to compare.")
            else:
                metrics_cmp_a = report_cmp_a.metrics_to_pandas()
                metrics_cmp_b = report_cmp_b.metrics_to_pandas()

                merged = metrics_cmp_a.merge(metrics_cmp_b, on="field", suffixes=("_A", "_B"))
                for metric in ["f1", "precision", "recall"]:
                    a_col, b_col = f"{metric}_A", f"{metric}_B"
                    if a_col in merged and b_col in merged:
                        merged[f"Δ_{metric}"] = (
                            pd.to_numeric(merged[b_col], errors="coerce")
                            - pd.to_numeric(merged[a_col], errors="coerce")
                        ).round(3)

                display_cols = [
                    "field",
                    "n_A",
                    "precision_A", "precision_B", "Δ_precision",
                    "recall_A", "recall_B", "Δ_recall",
                    "f1_A", "f1_B", "Δ_f1",
                ]
                available = [c for c in display_cols if c in merged.columns]
                compare_df = merged[available].sort_values("Δ_f1", ascending=True, na_position="last")

                st.subheader(f"Field comparison: {run_a_cmp} vs {run_b_cmp}")
                st.caption("Sorted by Δ F1 ascending — regressions at top.")
                compare_event = st.dataframe(
                    compare_df, use_container_width=True, hide_index=True,
                    selection_mode="multi-row", on_select="rerun",
                    key="compare_table",
                )
                _export_buttons(compare_df, "compare",
                                f"Compare: {run_a_cmp} vs {run_b_cmp}",
                                event=compare_event)

    # ════════════════════════════════════════════════════════════════════════
    # TAB 6 — Notes
    # ════════════════════════════════════════════════════════════════════════
    # with tab_notes:
    #     from streamlit_lexical import streamlit_lexical

    #     note_key = f"run_note_{run_a_label}"
    #     notes_file = _notes_path(run_a_path)

    #     # Load from disk on first access; seed with metadata header for new files
    #     if note_key not in st.session_state:
    #         if notes_file.exists():
    #             st.session_state[note_key] = notes_file.read_text(encoding="utf-8")
    #         else:
    #             st.session_state[note_key] = _notes_header(run_a_path, meta_a)

    #     # Header row: title left, action buttons right-aligned
    #     hdr_title, _, hdr_save, hdr_open = st.columns([6, 2, 1, 1])
    #     hdr_title.subheader(f"Notes — {run_a_name}")
    #     save_clicked = hdr_save.button("Save", type="primary", key="notes_save",
    #                                    use_container_width=True)
    #     open_clicked = hdr_open.button("Open in Windows", key="notes_open_vscode",
    #                                    use_container_width=True)

    #     st.caption(f"Notes are located at `{notes_file.resolve()}`")

    #     editor_value = streamlit_lexical(
    #         value=st.session_state[note_key],
    #         placeholder="Write run-level observations, field analysis, recommendations...",
    #         height=500,
    #         key=f"lexical_notes_{run_a_name}",
    #     )
    #     if editor_value is not None:
    #         st.session_state[note_key] = editor_value

    #     if save_clicked:
    #         notes_file.parent.mkdir(parents=True, exist_ok=True)
    #         notes_file.write_text(st.session_state[note_key], encoding="utf-8")
    #         st.toast("Notes saved.", icon="✅")
    #     if open_clicked:
    #         _open_notes_in_editor(run_a_path, meta_a)
    #         st.toast(f"Opening {notes_file.name}...")


def run() -> None:
    """Run the app either inside Streamlit or by bootstrapping Streamlit for plain Python execution."""
    if get_script_run_ctx(suppress_warning=True) is not None or streamlit_runtime_exists():
        main()
        return

    streamlit_bootstrap_run(
        str(Path(__file__).resolve()),
        is_hello=False,
        args=sys.argv[1:],
        flag_options={},
    )


if __name__ == "__main__":
    run()
