from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def build_config():
    from forgegod.config import ForgeGodConfig

    config = ForgeGodConfig()
    config.models.planner = "zai:glm-5.1"
    config.models.coder = "zai:glm-5.1"
    config.models.reviewer = "openai-codex:gpt-5.4"
    config.models.sentinel = "openai-codex:gpt-5.4"
    config.models.escalation = "openai-codex:gpt-5.4"
    config.models.researcher = "zai:glm-5.1"
    config.review.enabled = True
    config.review.sample_rate = 1
    config.review.always_review_run = True
    config.recon.enabled = True
    config.zai.use_coding_plan = True
    config.project_dir = ROOT / ".forgegod"
    return config


async def main() -> int:
    from forgegod.config import load_config
    from forgegod.native_auth import codex_login_status_sync
    from forgegod.router import ModelRouter

    load_config(ROOT)
    codex_ready, codex_detail = codex_login_status_sync()
    zai_ready = bool(os.environ.get("ZAI_CODING_API_KEY"))

    print("ForgeGod GLM/Codex Harness Smoke")
    print(json.dumps({
        "codex_ready": codex_ready,
        "codex_detail": codex_detail,
        "zai_coding_api_key_present": zai_ready,
    }, indent=2))

    if not codex_ready:
        print("\nCodex is not ready. Run `forgegod auth login openai-codex` first.")
        return 2

    if not zai_ready:
        print("\nZAI_CODING_API_KEY is not set. Export it before running this smoke test.")
        return 3

    router = ModelRouter(build_config())
    try:
        planner_text, planner_usage = await router.call(
            prompt=(
                "Return ONLY valid JSON with keys ok, role, summary. "
                "Set ok=true and role='planner'."
            ),
            role="planner",
            json_mode=True,
            max_tokens=200,
            temperature=0.1,
        )
        reviewer_text, reviewer_usage = await router.call(
            prompt=(
                "Review this tiny plan in one sentence: "
                "Build a deterministic countdown utility with unit tests."
            ),
            role="reviewer",
            json_mode=False,
            max_tokens=120,
            temperature=0.1,
        )
        print("\nPlanner call:")
        print(json.dumps({
            "provider": planner_usage.provider,
            "model": planner_usage.model,
            "cost_usd": planner_usage.cost_usd,
            "response": planner_text,
        }, indent=2))
        print("\nReviewer call:")
        print(json.dumps({
            "provider": reviewer_usage.provider,
            "model": reviewer_usage.model,
            "cost_usd": reviewer_usage.cost_usd,
            "response": reviewer_text,
        }, indent=2))
        return 0
    finally:
        await router.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
