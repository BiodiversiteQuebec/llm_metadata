from llm_metadata.prompt_eval import run_eval

run_1 = {
    "mode": "abstract",
    "manifest_path": "data/manifests/dev_subset_data_paper.csv",
    "parallelism": 8,
    "name": "pe_model_medium_change_abstract",
    "description": "Run with better model/effort to see if it improves performance on modulator fields and [data_type, geospatial_info_dataset] compared to low thinking effort (20260131_run)",
    "model": "gpt-5.4",
    "reasoning_effort": "medium",
}
run_2 = {
    "mode": "pdf_native",
    "manifest_path": "data/manifests/dev_subset_data_paper.csv",
    "parallelism": 8,
    "name": "pe_model_medium_pdf_native",
    "description": "Run with better model/effort to see if it improves performance on modulator fields and [data_type, geospatial_info_dataset] compared to low thinking effort (20260131_run)",
    "model": "gpt-5.4",
    "reasoning_effort": "medium",
}

if __name__ == "__main__":
    run_eval(**run_1)
    run_eval(**run_2)