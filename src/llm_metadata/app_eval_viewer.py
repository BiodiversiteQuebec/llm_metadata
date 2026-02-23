"""Streamlit app for interactive EvaluationReport results browsing.

Usage:
    uv run streamlit run src/llm_metadata/app_eval_viewer.py
"""
import json
from pathlib import Path

import pandas as pd
import streamlit as st

from llm_metadata.groundtruth_eval import EvaluationReport

RESULTS_DIR = Path("results")

st.set_page_config(page_title="Prompt Eval Viewer", layout="wide")
st.title("Prompt Eval Results Viewer")

# Sidebar: run picker
st.sidebar.header("Select Runs")

result_files = sorted(RESULTS_DIR.glob("*.json")) if RESULTS_DIR.exists() else []
file_names = [f.name for f in result_files]

if not file_names:
    st.warning(f"No result files found in `{RESULTS_DIR}/`. Run `prompt_eval` first.")
    st.stop()

run_a_name = st.sidebar.selectbox("Run A", file_names, index=0)
run_b_name = st.sidebar.selectbox("Run B (optional)", ["(none)"] + file_names, index=0)


@st.cache_data
def load_report(name: str):
    path = RESULTS_DIR / name
    report = EvaluationReport.load(path)
    with open(path) as f:
        meta = json.load(f)
    return report, meta


def _fmt_pct(v) -> str:
    """Format a metric value (0–1 float or None) as a 3-decimal string."""
    if v is None:
        return "N/A"
    return f"{v:.3f}"


report_a, meta_a = load_report(run_a_name)
report_b, meta_b = (load_report(run_b_name) if run_b_name != "(none)" else (None, None))

# ---------------------------------------------------------------------------
# Sidebar: run metadata
# ---------------------------------------------------------------------------
_META_SKIP = {"field_metrics", "field_results", "config", "abstracts"}

with st.sidebar.expander("Run A metadata"):
    for k, v in meta_a.items():
        if k not in _META_SKIP:
            st.write(f"**{k}:** {v}")

if meta_b is not None:
    with st.sidebar.expander("Run B metadata"):
        for k, v in meta_b.items():
            if k not in _META_SKIP:
                st.write(f"**{k}:** {v}")

# ---------------------------------------------------------------------------
# Per-field metrics table + bar chart
# ---------------------------------------------------------------------------
st.header("Per-Field Metrics")

metrics_a = report_a.metrics_to_pandas()

if report_b is not None:
    metrics_b = report_b.metrics_to_pandas()
    merged = metrics_a.merge(metrics_b, on="field", suffixes=("_A", "_B"))
    for col in ["f1", "precision", "recall"]:
        a_col, b_col = f"{col}_A", f"{col}_B"
        if a_col in merged and b_col in merged:
            merged[f"delta_{col}"] = merged[b_col] - merged[a_col]

    display_cols = [
        "field", "n_A",
        "precision_A", "recall_A", "f1_A",
        "precision_B", "recall_B", "f1_B",
        "delta_f1",
    ]
    available = [c for c in display_cols if c in merged.columns]
    display_df = merged[available].sort_values("delta_f1", ascending=False, na_position="last")
    st.dataframe(display_df, use_container_width=True)

    # Bar chart: F1 comparison Run A vs Run B
    st.subheader("F1 Comparison (A vs B)")
    chart_df = (
        merged[["field", "f1_A", "f1_B"]]
        .rename(columns={"f1_A": run_a_name, "f1_B": run_b_name})
        .set_index("field")
    )
    st.bar_chart(chart_df)
else:
    display_df = metrics_a.sort_values("f1", ascending=False)
    st.dataframe(display_df, use_container_width=True)

    st.subheader("F1 by Field")
    chart_df = metrics_a[["field", "f1"]].set_index("field")
    st.bar_chart(chart_df)

# ---------------------------------------------------------------------------
# Mismatch explorer (Run A)
# ---------------------------------------------------------------------------
st.header("Mismatch Explorer")
fields_a = report_a.fields()
selected_field = st.selectbox("Select field", fields_a)

if selected_field:
    errors = report_a.errors_for_field(selected_field)
    m = report_a.metrics_for(selected_field)
    st.write(
        f"**{selected_field}**: {len(errors)} mismatches / {m.n} records | "
        f"P={_fmt_pct(m.precision)} R={_fmt_pct(m.recall)} F1={_fmt_pct(m.f1)}"
    )

    page_size = 10
    n_pages = max(1, (len(errors) + page_size - 1) // page_size)
    page = st.number_input("Page", min_value=1, max_value=n_pages, value=1, step=1) - 1

    for r in errors[page * page_size : (page + 1) * page_size]:
        with st.expander(f"Record: {r.record_id} | TP={r.tp} FP={r.fp} FN={r.fn}"):
            col1, col2 = st.columns(2)
            with col1:
                st.write("**True value:**")
                st.write(r.true_value)
            with col2:
                st.write("**Predicted value:**")
                st.write(r.pred_value)
            abstract = report_a.abstracts.get(str(r.record_id), "")
            if abstract:
                with st.expander("Abstract"):
                    st.write(abstract)

# ---------------------------------------------------------------------------
# Mismatch explorer (Run B, shown when two runs are selected)
# ---------------------------------------------------------------------------
if report_b is not None:
    st.header("Mismatch Explorer — Run B")
    fields_b = report_b.fields()
    selected_field_b = st.selectbox("Select field (Run B)", fields_b, key="field_b")

    if selected_field_b:
        errors_b = report_b.errors_for_field(selected_field_b)
        m_b = report_b.metrics_for(selected_field_b)
        st.write(
            f"**{selected_field_b}** (Run B): {len(errors_b)} mismatches / {m_b.n} records | "
            f"P={_fmt_pct(m_b.precision)} R={_fmt_pct(m_b.recall)} F1={_fmt_pct(m_b.f1)}"
        )

        page_size_b = 10
        n_pages_b = max(1, (len(errors_b) + page_size_b - 1) // page_size_b)
        page_b = (
            st.number_input("Page (B)", min_value=1, max_value=n_pages_b, value=1, step=1) - 1
        )

        for r in errors_b[page_b * page_size_b : (page_b + 1) * page_size_b]:
            with st.expander(f"Record: {r.record_id} | TP={r.tp} FP={r.fp} FN={r.fn}"):
                col1, col2 = st.columns(2)
                with col1:
                    st.write("**True value:**")
                    st.write(r.true_value)
                with col2:
                    st.write("**Predicted value:**")
                    st.write(r.pred_value)
                abstract_b = report_b.abstracts.get(str(r.record_id), "")
                if abstract_b:
                    with st.expander("Abstract"):
                        st.write(abstract_b)

# ---------------------------------------------------------------------------
# Record explorer — all fields for a selected record
# ---------------------------------------------------------------------------
st.header("Record Explorer")
all_record_ids = sorted({r.record_id for r in report_a.field_results})
selected_record = st.selectbox("Select record", all_record_ids, key="record_select")

if selected_record:
    abstract = report_a.abstracts.get(str(selected_record), "")
    if abstract:
        with st.expander("Abstract text"):
            st.write(abstract)

    record_results = report_a.results_for_record(selected_record)
    rows = [
        {
            "field": r.field,
            "match": "✓" if r.match else "✗",
            "true_value": str(r.true_value),
            "pred_value": str(r.pred_value),
            "tp": r.tp,
            "fp": r.fp,
            "fn": r.fn,
        }
        for r in record_results
    ]
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True)
