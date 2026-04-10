import json
from pathlib import Path

from llm_metadata.prompt_eval import run_eval
from llm_metadata.schemas.data_paper import DataPaperManifest

MANIFEST_PATH = "data/manifests/dev_subset_data_paper.csv"
GT_PATH = "data/gt/fuster_gt.json"

manifest = DataPaperManifest.load_csv(MANIFEST_PATH).records
gt = json.loads(Path(GT_PATH).read_text(encoding="utf-8"))

run_1 = {
    "mode": "abstract",
    "manifest": manifest,
    "gt": gt,
    "parallelism": 8,
    "name": "pe_model_medium_change_abstract",
    "description": "Run with better model/effort to see if it improves performance on modulator fields and [data_type, geospatial_info_dataset] compared to low thinking effort (20260131_run)",
    "model": "gpt-5.4",
    "reasoning_effort": "medium",
}
run_2 = {
    "mode": "pdf_native",
    "manifest": manifest,
    "gt": gt,
    "parallelism": 8,
    "name": "pe_model_medium_pdf_native",
    "description": "Run with better model/effort to see if it improves performance on modulator fields and [data_type, geospatial_info_dataset] compared to low thinking effort (20260131_run)",
    "model": "gpt-5.4",
    "reasoning_effort": "medium",
}

if __name__ == "__main__":
    run_eval(**run_1)
    run_eval(**run_2)
