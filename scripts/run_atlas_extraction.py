"""Extract the Atlas contribution features (schema AtlasContributionExtraction) over a manifest.

    UV_ENV_FILE=.env uv run python scripts/run_atlas_extraction.py \
        --manifest data/manifests/dev_subset_data_paper.csv --mode abstract --name atlas_abstract_dev --max-cost 0.04

Native structured output (the schema is small enough). Writes a run artifact to
artifacts/runs/<timestamp>_<name>.json; no evaluation here (scores come from
llm_metadata.atlas_contribution, compared with the annotation ceiling).
"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from llm_metadata.extraction import ExtractionConfig, estimate_run_cost, run_manifest_extraction
from llm_metadata.prompts.atlas_contribution import SYSTEM_MESSAGE
from llm_metadata.schemas.atlas_contribution import AtlasContributionExtraction
from llm_metadata.schemas.data_paper import DataPaperManifest


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--mode", default="abstract", choices=["abstract", "pdf_text"])
    ap.add_argument("--model", default="claude-haiku-5-5")
    ap.add_argument("--reasoning-effort", default="low")
    ap.add_argument("--name", required=True)
    ap.add_argument("--max-cost", type=float, required=True)
    ap.add_argument("--parallelism", type=int, default=5)
    a = ap.parse_args()

    manifest = DataPaperManifest.load_csv(a.manifest)
    config = ExtractionConfig(model=a.model, reasoning={"effort": a.reasoning_effort},
                              text_format=AtlasContributionExtraction, structured_output=True)
    est = estimate_run_cost(manifest, mode=a.mode, config=config, prompt=SYSTEM_MESSAGE,
                            assumed_output_tokens=600, skip_cache=True)
    print(f"Cost estimate: ${est['estimated_cost_usd']:.4f}")
    if est["estimated_cost_usd"] > a.max_cost:
        raise SystemExit(f"Estimate exceeds --max-cost {a.max_cost}; nothing was spent.")
    out = Path("artifacts/runs") / f"{datetime.now():%Y%m%d_%H%M%S}_{a.name}.json"
    art = run_manifest_extraction(manifest, mode=a.mode, parallelism=a.parallelism, prompt=SYSTEM_MESSAGE,
                                  config=config, output_path=out, manifest_path=a.manifest, name=a.name,
                                  description="Atlas contribution features (native structured output)", skip_cache=True)
    print(f"Total API cost: ${art.total_cost_usd:.4f}\nRun artifact saved to: {out}")


if __name__ == "__main__":
    main()
