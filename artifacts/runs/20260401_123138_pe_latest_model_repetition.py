from llm_metadata.prompt_eval import run_eval

run_1 = {
    "mode": "abstract",
    "manifest_path": "data/manifests/dev_subset_data_paper.csv",
    "parallelism": 8,
    "name": "pe_model_medium_change_abstract",
    "description": "Run with better model/effort to see if it improves performance on modulator fields and [data_type, geospatial_info_dataset] compared to low thinking effort (20260131_run). Same than previous 20260401 run using gpt-5.4-medium to see if bad results are a repeatability issue or not. Is our prompt deterministic? Does it always fail on the same fields? Do we get the same results with the same model/effort?",
    "model": "gpt-5.4",
    "reasoning_effort": "medium",
    "skip_cache": True,
}
run_2 = {
    "mode": "pdf_native",
    "manifest_path": "data/manifests/dev_subset_data_paper.csv",
    "parallelism": 8,
    "name": "pe_model_medium_pdf_native",
    "description": "Same than previous 20260401 run using gpt-5.4-medium to see if bad results are a repeatability issue or not. Is our prompt deterministic? Does it always fail on the same fields? Do we get the same results with the same model/effort?",
    "model": "gpt-5.4",
    "reasoning_effort": "medium",
    "skip_cache": True,
}

if __name__ == "__main__":
    run_eval(**run_1)
    run_eval(**run_2)