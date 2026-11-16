"""Run an LLM relevance variant (R2 combined or R3 scoring only) over a manifest.

    UV_ENV_FILE=.env uv run python scripts/run_relevance_variant.py \
        --variant scoring --mode abstract --manifest data/manifests/dev_subset_data_paper.csv \
        --name r3_scoring_abstract --max-cost 0.05

The run artifact goes to artifacts/runs/ like any prompt_eval run. Score it with
``uv run python -m llm_metadata.relevance_eval <run.json>`` (both targets); for the
combined variant the feature fields can also be scored with ``llm_metadata.run_summary``.
"""

from __future__ import annotations

import argparse
import json

from llm_metadata.groundtruth_eval import EvaluationConfig, FieldEvalStrategy
from llm_metadata.prompt_eval import run_eval
from llm_metadata.prompts.relevance import COMBINED_SYSTEM_MESSAGE, SCORING_SYSTEM_MESSAGE
from llm_metadata.relevance_eval import targets
from llm_metadata.schemas.data_paper import DataPaperManifest
from llm_metadata.schemas.relevance import DatasetFeaturesWithRelevance, RelevanceScore, RelevanceTarget

VARIANTS = {
    "scoring": (SCORING_SYSTEM_MESSAGE, RelevanceScore),
    "combined": (COMBINED_SYSTEM_MESSAGE, DatasetFeaturesWithRelevance),
}


def relevance_gt(ids: list[int]) -> list[dict]:
    t = targets()
    return [
        {"gt_record_id": int(i), "relevance": t.loc[i, "rule"], "human_relevance": t.loc[i, "human"]}
        for i in ids
        if i in t.index
    ]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--variant", required=True, choices=sorted(VARIANTS))
    ap.add_argument("--mode", required=True, choices=["abstract", "pdf_text", "pdf_native"])
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--model", default="claude-haiku-5-5")
    ap.add_argument("--reasoning-effort", default="low")
    ap.add_argument("--name", required=True)
    ap.add_argument("--description", default=None)
    ap.add_argument("--max-cost", type=float, required=True)
    ap.add_argument("--assumed-output-tokens", type=int, default=1500)
    ap.add_argument("--parallelism", type=int, default=5)
    ap.add_argument("--skip-cache", action="store_true")
    ap.add_argument("--structured-output", action="store_true", help="Native structured output (API-constrained JSON) instead of schema in the prompt.")
    a = ap.parse_args()

    prompt, text_format = VARIANTS[a.variant]
    records = DataPaperManifest.load_csv(a.manifest).records
    gt = relevance_gt([r.gt_record_id for r in records])
    config = EvaluationConfig(field_strategies={"relevance": FieldEvalStrategy(match="exact")})
    run_eval(
        mode=a.mode,
        manifest=records,
        gt=gt,
        prompt=prompt,
        parallelism=a.parallelism,
        config=config,
        model=a.model,
        reasoning_effort=a.reasoning_effort,
        name=a.name,
        description=a.description or f"Relevance variant {a.variant} ({'R3 scoring only' if a.variant == 'scoring' else 'R2 combined'})",
        skip_cache=a.skip_cache,
        text_format=text_format,
        gt_model=RelevanceTarget,
        max_cost_usd=a.max_cost,
        assumed_output_tokens=a.assumed_output_tokens,
        structured_output=a.structured_output,
    )


if __name__ == "__main__":
    main()
