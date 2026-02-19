"""Streamlit app for interactive EvaluationReport results browsing.

Usage:
    uv run streamlit run src/llm_metadata/app_eval_viewer.py
"""
import json
from pathlib import Path

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

report_a, meta_a = load_report(run_a_name)
report_b, meta_b = (load_report(run_b_name) if run_b_name != "(none)" else (None, None))

# Main area: per-field metrics
st.header("Per-Field Metrics")

import pandas as pd

metrics_a = report_a.metrics_to_pandas()

if report_b is not None:
    metrics_b = report_b.metrics_to_pandas()
    merged = metrics_a.merge(metrics_b, on="field", suffixes=("_A", "_B"))
    for col in ["f1", "precision", "recall"]:
        a_col, b_col = f"{col}_A", f"{col}_B"
        if a_col in merged and b_col in merged:
            merged[f"delta_{col}"] = merged[b_col] - merged[a_col]

    def _fmt(v):
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return "-"
        return f"{v:.3f}"

    display_cols = ["field", "n_A", "precision_A", "recall_A", "f1_A",
                    "precision_B", "recall_B", "f1_B", "delta_f1"]
    available = [c for c in display_cols if c in merged.columns]
    display_df = merged[available].sort_values("delta_f1", ascending=False, na_position="last")
    st.dataframe(display_df, use_container_width=True)
else:
    display_df = metrics_a.sort_values("f1", ascending=False)
    st.dataframe(display_df, use_container_width=True)

# Mismatch explorer
st.header("Mismatch Explorer")
fields = report_a.fields()
selected_field = st.selectbox("Select field", fields)

if selected_field:
    errors = report_a.errors_for_field(selected_field)
    m = report_a.metrics_for(selected_field)
    st.write(f"**{selected_field}**: {len(errors)} mismatches / {m.n} records | P={m.precision:.3f if m.precision else 'N/A'} R={m.recall:.3f if m.recall else 'N/A'} F1={m.f1:.3f if m.f1 else 'N/A'}")

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

# Run metadata
with st.sidebar.expander("Run A metadata"):
    for k, v in meta_a.items():
        if k not in ("field_metrics", "field_results", "config", "field_strategies"):
            st.write(f"**{k}:** {v}")
