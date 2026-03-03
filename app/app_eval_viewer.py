"""Streamlit app for interactive EvaluationReport results browsing.

Usage:
    uv run streamlit run app/app_eval_viewer.py

## Tab map

| Tab | Purpose |
|-----|---------|
| Overview | Run metadata, foldable GT dataset table, foldable rendered system prompt |
| Detailed Metrics | Per-field F1/P/R table with multi-row select; mismatch table with multi-row select |
| Dataset Results | Paper selector → metadata panel + field results table with multi-row select |
| Compare Runs | Side-by-side delta table with multi-row select |
| Notes | Rich text editor for per-run analyst notes, save to disk, open in VS Code |

## Data file dependencies

| File | Required | Used for |
|------|----------|---------|
| `${EVAL_VIEWER_RESULTS_DIR}` (default: `data`) | Yes — app stops if none found | Run results (EvaluationReport), including bundled records + system message when present |
| `data/dataset_092624_validated.xlsx` | Optional fallback | Paper title, DOI, links, validity chips in Dataset Results for older run JSON |
| `data/dataset_092624.xlsx` | Optional fallback | Abstract text (full_text column) for older run JSON |
| `data/{run}_notes.md` | Optional (created on first save) | Per-run analyst notes |
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

from llm_metadata.groundtruth_eval import EvaluationReport

RESULTS_DIR = os.getenv("EVAL_VIEWER_RESULTS_DIR")
if not RESULTS_DIR:
    legacy_glob = os.getenv("EVAL_VIEWER_RESULTS_GLOB")
    if legacy_glob:
        RESULTS_DIR = str(Path(legacy_glob).parent)
    else:
        RESULTS_DIR = "data"
GT_VALIDATED_PATH = Path("data/dataset_092624_validated.xlsx")
GT_RAW_PATH = Path("data/dataset_092624.xlsx")
APP_DIR = Path(__file__).resolve().parent
ASSETS_DIR = APP_DIR / "assets"
FAVICON_PATH = ASSETS_DIR / "favicon.ico"
LOGO_PATH = ASSETS_DIR / "FRVersion horizontale 2 ligne (couleur)_cropped.png"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _resolve_result_files(results_dir: str) -> list[Path]:
    """Resolve JSON result files from a directory path."""
    path = Path((results_dir or "").strip() or "data")
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


# ── Page config & header ─────────────────────────────────────────────────────

st.set_page_config(
    page_title="Extraction evaluation viewer",
    page_icon=str(FAVICON_PATH) if FAVICON_PATH.exists() else None,
    layout="wide",
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


# ── Data loading ─────────────────────────────────────────────────────────────

@st.cache_data
def load_report(path: Path) -> tuple[EvaluationReport, dict]:
    report = EvaluationReport.load(path)
    with open(path, encoding="utf-8") as f:
        meta = json.load(f)
    return report, meta


_GT_META_COLS = [
    "id", "title", "source_url", "journal_url", "pdf_url",
    "is_oa", "cited_article_doi", "source", "valid_yn", "reason_not_valid", "has_abstract",
    "extraction_success",
]


def _records_from_meta(meta: dict) -> Optional[pd.DataFrame]:
    """Build id-indexed metadata DataFrame from run JSON metadata."""
    records = meta.get("records")
    if not isinstance(records, dict) or not records:
        return None

    rows: list[dict] = []
    for record_id, rec in records.items():
        if not isinstance(rec, dict):
            continue
        rows.append({
            "id": str(record_id),
            "title": rec.get("title"),
            "source_url": rec.get("source_url"),
            "journal_url": rec.get("journal_url"),
            "pdf_url": rec.get("pdf_url"),
            "is_oa": rec.get("is_oa"),
            "cited_article_doi": rec.get("cited_article_doi"),
            "source": rec.get("source"),
            "valid_yn": rec.get("valid_yn"),
            "reason_not_valid": rec.get("reason_not_valid"),
            "has_abstract": rec.get("has_abstract"),
            "extraction_success": rec.get("extraction_success"),
        })

    if not rows:
        return None

    df = pd.DataFrame(rows)
    if "source_url" in df.columns:
        df["doi"] = (
            df["source_url"]
            .fillna("")
            .astype(str)
            .str.replace(r"https?://doi\.org/", "", regex=True)
            .str.strip()
        )
    else:
        df["doi"] = ""
    return df.set_index("id")


def _abstracts_from_meta(meta: dict) -> dict[str, str]:
    """Extract id -> abstract text from run JSON metadata."""
    records = meta.get("records")
    if not isinstance(records, dict) or not records:
        return {}

    abstracts: dict[str, str] = {}
    for record_id, rec in records.items():
        if not isinstance(rec, dict):
            continue
        abstract = rec.get("abstract")
        if abstract is None or (isinstance(abstract, float) and pd.isna(abstract)):
            continue
        abstract_str = str(abstract).strip()
        if abstract_str:
            abstracts[str(record_id)] = abstract_str
    return abstracts


def _system_message_from_meta(meta: dict) -> Optional[str]:
    """Extract serialized system message from run JSON metadata."""
    system_message = meta.get("system_message")
    if isinstance(system_message, str) and system_message.strip():
        return system_message
    return None


def _chosen_eval_config_summary(meta: dict) -> str:
    """Build a compact one-line summary of the active eval config."""
    config = meta.get("config")
    if not isinstance(config, dict) or not config:
        return "No eval config recorded."

    field_strategies = config.get("field_strategies")
    if isinstance(field_strategies, dict) and field_strategies:
        strategy_names = sorted({
            str(v.get("match", "exact"))
            for v in field_strategies.values()
            if isinstance(v, dict)
        })
        strategy_part = ", ".join(strategy_names) if strategy_names else "exact"
        return f"{len(field_strategies)} fields; match strategies: {strategy_part}"

    return "Config present, but no field strategies found."

@st.cache_data
def load_gt_index() -> Optional[pd.DataFrame]:
    """Load id → full metadata lookup from validated XLSX."""
    if not GT_VALIDATED_PATH.exists():
        return None
    available = [c for c in _GT_META_COLS if c in pd.read_excel(
        str(GT_VALIDATED_PATH), nrows=0).columns]
    df = pd.read_excel(str(GT_VALIDATED_PATH), usecols=available)
    df["doi"] = df["source_url"].str.replace(r"https?://doi\.org/", "", regex=True).str.strip()
    df["id"] = df["id"].astype(str)
    return df.set_index("id")


@st.cache_data
def load_abstracts() -> dict[str, str]:
    """Load id → abstract text from raw XLSX (full_text column)."""
    if not GT_RAW_PATH.exists():
        return {}
    df = pd.read_excel(str(GT_RAW_PATH), usecols=["id", "full_text"])
    df["id"] = df["id"].astype(str)
    df = df.dropna(subset=["full_text"])
    return dict(zip(df["id"], df["full_text"]))


report_a, meta_a = load_report(run_a_path)
gt_index = _records_from_meta(meta_a)
if gt_index is None:
    gt_index = load_gt_index()  # fallback for older JSON runs

abstracts = _abstracts_from_meta(meta_a)
if not abstracts:
    abstracts = load_abstracts()  # fallback for older JSON runs


# ── Tabs ─────────────────────────────────────────────────────────────────────
tab_overview, tab_metrics, tab_records, tab_compare = st.tabs(
    ["Overview", "Detailed Metrics", "Dataset Results", "Compare Runs"]
)


# ════════════════════════════════════════════════════════════════════════════
# TAB 1 — Overview
# ════════════════════════════════════════════════════════════════════════════
with tab_overview:
    timestamp = meta_a.get("timestamp", "—")
    st.markdown(f"**Run:** `{run_a_name}`  |  **Timestamp:** `{timestamp}`")
    st.markdown(f"**Chosen eval config:** {_chosen_eval_config_summary(meta_a)}")

    details_cols = st.columns(3)
    details_cols[0].metric("Prompt", meta_a.get("prompt_module", "—"))
    details_cols[1].metric("Model", meta_a.get("model", "—"))
    cost_val = meta_a.get("cost_usd", "—")
    if cost_val != "—":
        cost_val = f"${cost_val:.4f}"
    details_cols[2].metric("Cost (USD)", cost_val)

    evaluated_record_ids = {str(r.record_id) for r in report_a.field_results}
    total_evaluated = len(evaluated_record_ids)
    dataset_rows = (
        gt_index.loc[gt_index.index.isin(evaluated_record_ids)]
        if gt_index is not None else pd.DataFrame()
    )

    if not dataset_rows.empty:
        source_series = dataset_rows["source"].fillna("").astype(str).str.strip().str.lower()
        source_dryad = int((source_series == "dryad").sum())
        source_zenodo = int((source_series == "zenodo").sum())
        source_semantic = int(source_series.str.contains("semantic", regex=False).sum())

        is_oa_series = dataset_rows["is_oa"].fillna("").astype(str).str.strip().str.lower()
        is_oa_yes = int(is_oa_series.isin({"1", "1.0", "true", "yes"}).sum())

        has_pdf_series = dataset_rows["pdf_url"].fillna("").astype(str).str.strip()
        has_pdf = int((has_pdf_series != "").sum())
    else:
        source_dryad = 0
        source_zenodo = 0
        source_semantic = 0
        is_oa_yes = 0
        has_pdf = 0

    count_cols = st.columns(6)
    count_cols[0].metric("Records evaluated", total_evaluated)
    count_cols[1].metric("From Dryad", source_dryad)
    count_cols[2].metric("From Zenodo", source_zenodo)
    count_cols[3].metric("From Semantic Scholar", source_semantic)
    count_cols[4].metric("is_oa", is_oa_yes)
    count_cols[5].metric("Has PDF", has_pdf)

    st.divider()

    # Ground truth dataset (foldable)
    with st.expander("Ground truth dataset", expanded=False):
        if gt_index is not None:
            _gt_df = gt_index.reset_index()
            if "extraction_success" in _gt_df.columns:
                success_norm = _gt_df["extraction_success"].fillna(False).astype(str).str.strip().str.lower()
                _gt_df["success"] = success_norm.isin({"1", "1.0", "true", "yes"}).map(lambda ok: "✅" if ok else "❌")
            st.dataframe(_gt_df, use_container_width=True)
            _export_buttons(_gt_df, "gt_index", "Ground truth dataset")
        else:
            st.warning(f"XLSX not found at `{GT_VALIDATED_PATH}`")

    # Schema (foldable — DatasetFeatures JSON schema sent to the model)
    with st.expander("Output schema (DatasetFeatures)", expanded=False):
        schema_data = meta_a.get("schema")
        if isinstance(schema_data, dict) and schema_data:
            st.code(json.dumps(schema_data, indent=2), language="json")
        else:
            st.caption(
                "No schema recorded. Regenerate with a current `prompt_eval` run "
                "or inspect `DatasetFeatures.model_json_schema()` directly."
            )

    # Prompt (foldable, rendered system message)
    with st.expander("Prompt", expanded=False):
        serialized_message = _system_message_from_meta(meta_a)
        if serialized_message:
            st.code(serialized_message, language=None)
        else:
            prompt_module_path = meta_a.get("prompt_module")
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

    # Evaluation config (foldable, full serialized config)
    with st.expander("Evaluation config", expanded=False):
        full_config = meta_a.get("config")
        if isinstance(full_config, dict) and full_config:
            st.code(json.dumps(full_config, indent=2), language="json")
        else:
            st.info("No eval config metadata recorded in this run.")

    # Run logs (foldable)
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


# ════════════════════════════════════════════════════════════════════════════
# TAB 2 — Detailed Metrics
# ════════════════════════════════════════════════════════════════════════════
with tab_metrics:
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
    _export_buttons(_sorted_metrics_df, "metrics", "Per-field metrics",
                    event=metrics_event)

    st.divider()

    st.subheader("Mismatches")

    # Field selector + mismatch table for selected field
    all_fields = report_a.fields()
    selected_field = st.selectbox(
        "Select field for mismatches",
        all_fields,
        index=0,
        key="metrics_field_select",
    )

    # Mismatch table for selected field
    errors = report_a.errors_for_field(selected_field)
    m = report_a.metrics_for(selected_field)

    if m is not None:
        p_str = f"{m.precision:.3f}" if m.precision is not None else "N/A"
        r_str = f"{m.recall:.3f}" if m.recall is not None else "N/A"
        f1_str = f"{m.f1:.3f}" if m.f1 is not None else "N/A"
        st.markdown(
            f"**Selected field :** {selected_field} "
            f"({len(errors)} / {m.n} records | P={p_str} R={r_str} F1={f1_str})"
        )
    else:
        st.markdown(f"**Selected field :** {selected_field} ({len(errors)} mismatches)")

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
        _export_buttons(error_df, f"mismatch_{selected_field}",
                        f"**Selected field :** {selected_field}",
                        event=mismatch_event)
    else:
        st.success("No mismatches for this field.")


# ════════════════════════════════════════════════════════════════════════════
# TAB 3 — Dataset Results
# ════════════════════════════════════════════════════════════════════════════
with tab_records:
    # Build record list: record_id → title + doi (from gt_index if available)
    all_record_ids = sorted(
        {str(r.record_id) for r in report_a.field_results},
        key=lambda x: int(x) if x.isdigit() else x,
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

    record_labels = [_record_label(rid) for rid in all_record_ids]
    label_to_id = dict(zip(record_labels, all_record_ids))

    selected_label = st.selectbox(
        "Select paper",
        record_labels,
        format_func=lambda x: x,
        key="record_selector",
    )
    selected_record_id = label_to_id[selected_label]

    st.divider()

    # Dataset metadata panel
    if gt_index is not None and selected_record_id in gt_index.index:
            meta_row = gt_index.loc[selected_record_id]

            def _raw(col: str):
                if col not in meta_row.index:
                    return None
                v = meta_row[col]
                return v.iloc[0] if hasattr(v, "iloc") else v

            def _scalar(col: str) -> str:
                v = _raw(col)
                return "" if (v is None or (isinstance(v, float) and pd.isna(v))) else str(v)

            title_full = _scalar("title") or "Untitled"
            st.subheader(title_full)

            # Collapsible abstract
            abstract_text = abstracts.get(selected_record_id, "")
            with st.expander("Abstract", expanded=False):
                if abstract_text:
                    st.markdown(abstract_text)
                else:
                    st.caption("No abstract available for this record.")

            # Link badges
            _SOURCE_LABELS = {
                "dryad": "Dryad", "zenodo": "Zenodo",
                "semantic_scholar": "Semantic Scholar",
            }
            links: list[str] = []
            if src_url := _scalar("source_url"):
                src_label = _SOURCE_LABELS.get(
                    (_scalar("source") or "").strip().lower(), "Source"
                )
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

            # Metadata chips row
            chip_cols = st.columns(4)
            chip_cols[0].metric("Source", _scalar("source") or "—")
            is_oa_val = _raw("is_oa")
            is_oa_yes = str(is_oa_val).strip().lower() in {"1", "1.0", "true", "yes"}
            chip_cols[1].metric("Open access", "Yes" if is_oa_yes else "No")
            chip_cols[2].metric("Valid", _scalar("valid_yn") or "—")
            has_abs_val = _raw("has_abstract")
            has_abs_yes = str(has_abs_val).strip().lower() in {"1", "1.0", "true", "yes"}
            chip_cols[3].metric("Has abstract", "Yes" if has_abs_yes else "No")
            doi_str = _scalar("doi")
            st.text_input(
                "DOI",
                value=doi_str or "—",
                disabled=True,
                key=f"doi_display_{selected_record_id}",
            )

            if reason := _scalar("reason_not_valid"):
                st.caption(f"Exclusion reason: {reason}")

    st.divider()

    # Build side-by-side results table for this record
    record_results = report_a.results_for_record(selected_record_id)
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
            record_df, use_container_width=True, hide_index=True,
            selection_mode="multi-row", on_select="rerun",
            key=f"record_table_{selected_record_id}",
        )
        _export_buttons(record_df, f"record_{selected_record_id}",
                        f"Record {selected_record_id} results",
                        event=record_event)
    else:
        st.info("No results for this record.")


# ════════════════════════════════════════════════════════════════════════════
# TAB 4 — Compare Runs
# ════════════════════════════════════════════════════════════════════════════
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
        report_cmp_a, _ = load_report(result_file_map[run_a_cmp])
        report_cmp_b, _ = load_report(result_file_map[run_b_cmp])

        metrics_cmp_a = report_cmp_a.metrics_to_pandas()
        metrics_cmp_b = report_cmp_b.metrics_to_pandas()

        merged = metrics_cmp_a.merge(metrics_cmp_b, on="field", suffixes=("_A", "_B"))
        for metric in ["f1", "precision", "recall"]:
            a_col, b_col = f"{metric}_A", f"{metric}_B"
            if a_col in merged and b_col in merged:
                merged[f"Δ_{metric}"] = (merged[b_col] - merged[a_col]).round(3)

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


# ════════════════════════════════════════════════════════════════════════════
# TAB 5 — Notes
# ════════════════════════════════════════════════════════════════════════════
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
