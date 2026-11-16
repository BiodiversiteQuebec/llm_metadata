"""Run the frozen configuration once on the held-out set.

    UV_ENV_FILE=.env uv run python scripts/run_heldout_pass.py --config configs/final_heldout.json --final
    uv run python scripts/run_heldout_pass.py --config configs/final_heldout.json --check   # digests only, no API call
    uv run python scripts/run_heldout_pass.py --config configs/final_heldout.json --write-digests   # freeze

The config lists the conditions (input mode x approach), the model and effort, a cost
limit per condition, and the SHA-256 of every system prompt. The run refuses to start if
a prompt no longer matches its frozen digest, or without --final. Each condition writes a
normal run artifact under artifacts/runs/ named heldout_<condition>.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from llm_metadata.prompts import abstract, pdf_file, section
from llm_metadata.prompts.relevance import COMBINED_SYSTEM_MESSAGE, SCORING_SYSTEM_MESSAGE

PROMPTS = {
    "abstract": abstract.SYSTEM_MESSAGE,
    "pdf_file": pdf_file.SYSTEM_MESSAGE,
    "section": section.SYSTEM_MESSAGE,
    "relevance_combined": COMBINED_SYSTEM_MESSAGE,
    "relevance_scoring": SCORING_SYSTEM_MESSAGE,
}


def digests() -> dict[str, str]:
    return {k: hashlib.sha256(v.encode("utf-8")).hexdigest() for k, v in PROMPTS.items()}


def command(cond: dict, cfg: dict) -> list[str]:
    common = ["--model", cfg["model"], "--reasoning-effort", cfg["effort"], "--manifest", cond["manifest"],
              "--name", f"heldout_{cond['name']}", "--max-cost", str(cond["max_cost"]),
              "--parallelism", str(cfg.get("parallelism", 5)), "--skip-cache"]
    if cond["approach"] == "features":
        return [sys.executable, "-m", "llm_metadata.prompt_eval", "--mode", cond["mode"],
                "--config", cfg["eval_config"], *common]
    if cond["approach"] in ("combined", "scoring"):
        extra = ["--structured-output"] if cond.get("structured_output") else []
        return [sys.executable, "scripts/run_relevance_variant.py", "--variant", cond["approach"],
                "--mode", cond["mode"], *common, *extra]
    raise ValueError(f"Unknown approach {cond['approach']!r}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--config", required=True)
    ap.add_argument("--final", action="store_true", help="Required to spend: the held-out set is run once.")
    ap.add_argument("--check", action="store_true", help="Only compare prompt digests with the config.")
    ap.add_argument("--write-digests", action="store_true", help="Freeze: write the current digests into the config.")
    ap.add_argument("--only", default=None, help="Comma-separated condition names to run (resume after a failure).")
    a = ap.parse_args()

    path = Path(a.config)
    cfg = json.loads(path.read_text())
    now = digests()
    if a.write_digests:
        cfg["prompt_sha256"] = now
        path.write_text(json.dumps(cfg, indent=2) + "\n")
        print("Digests written.")
        return
    frozen = cfg.get("prompt_sha256", {})
    changed = [k for k in now if frozen.get(k) != now[k]]
    if changed:
        sys.exit(f"Prompts changed since the freeze: {', '.join(changed)}. Refusing to run.")
    print("All prompt digests match the frozen config.")
    if a.check:
        return
    if not a.final:
        sys.exit("Add --final: this runs the held-out set, once.")
    only = set(a.only.split(",")) if a.only else None
    for cond in cfg["conditions"]:
        if only and cond["name"] not in only:
            continue
        done_before = sorted(Path("artifacts/runs").glob(f"*_heldout_{cond['name']}.json"))
        if done_before:
            print(f"Skipping {cond['name']}: already run once ({done_before[-1].name}).")
            continue
        cmd = command(cond, cfg)
        print(f"\n=== {cond['name']}: {' '.join(cmd[1:])}", flush=True)
        done = subprocess.run(cmd)
        if done.returncode != 0:
            sys.exit(f"Condition {cond['name']} failed (exit {done.returncode}); fix and resume with --only.")


if __name__ == "__main__":
    main()
