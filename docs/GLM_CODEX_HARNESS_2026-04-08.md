# GLM Coding Plan + Codex Harness

Date verified: 2026-04-08

## Goal

Define the best current ForgeGod harness for:

- `GLM-5.1` as the main builder
- `OpenAI Codex` as adversary / reviewer / sentinel
- optional use of `ZAI_CODING_API_KEY` despite the fact that Z.AI officially frames Coding Plan around supported coding tools

## What the official 2026 docs support

### OpenAI Codex

- OpenAI says Codex on supported ChatGPT plans can run in the terminal, edit files, execute tests, work in parallel, and operate in isolated sandboxes.
  Source: https://help.openai.com/en/articles/11369540-using-codex-with-your-chatgpt-plan

- OpenAI's harness-engineering article makes the key architectural point: better scaffolding, PR-sized loops, explicit review, and clean repo docs are what raise agent performance.
  Source: https://openai.com/index/harness-engineering/

- OpenAI's Codex docs also position Codex as strong for PR review and front-end visual iteration.
  Source: https://developers.openai.com/codex/use-cases

### Z.AI Coding Plan

- Z.AI documents `glm-5.1` as a coding-agent model with reasoning and long context in the DevPack docs.
  Source: https://docs.z.ai/devpack/using5.1

- Z.AI documents a dedicated coding endpoint separate from the general OpenAI-compatible endpoint.
  Source: https://docs.z.ai/api-reference/introduction

- Z.AI's FAQ says Coding Plan quota is only for coding tools designated or recognized by Z.AI and should not be assumed for arbitrary apps, bots, websites, or SaaS products through direct API use.
  Source: https://docs.z.ai/devpack/faq

## Evidence that this pattern is used in real coding tools

### OpenClaw

- OpenClaw's official Z.AI provider docs explicitly support:
  - `zai-coding-global`
  - `zai-coding-cn`
  - `glm-5.1`
  Source: https://docs.openclaw.ai/providers/zai

This is the closest verified pattern to ForgeGod's desired architecture because OpenClaw is also a repo-oriented coding agent with provider routing.

### Z.AI-supported tool ecosystem

- Z.AI's DevPack documentation contains official integration/config pages for multiple coding tools and agentic clients, including OpenClaw, OpenCode, Cline, Crush, Cursor, Goose, and "other tools" via OpenAI-compatible configuration.
  Representative sources:
  - https://docs.z.ai/devpack/tool/openclaw
  - https://docs.z.ai/devpack/tool/opencode
  - https://docs.z.ai/devpack/tool/cline
  - https://docs.z.ai/devpack/tool/crush
  - https://docs.z.ai/devpack/tool/cursor
  - https://docs.z.ai/devpack/tool/goose
  - https://docs.z.ai/devpack/quick-start

### Hermes

- No primary-source Z.AI or Hermes documentation was found that clearly documents a sanctioned GLM Coding Plan integration path for Hermes.

Operational conclusion: do not use Hermes as proof that this path is officially endorsed.

## Best ForgeGod harness now

### Recommended role split

- `planner = zai:glm-5.1`
- `researcher = zai:glm-5.1`
- `coder = zai:glm-5.1`
- `reviewer = openai-codex:gpt-5.4`
- `sentinel = openai-codex:gpt-5.4`
- `escalation = openai-codex:gpt-5.4`

### Why this split

- GLM-5.1 is the production workhorse for planning and code generation.
- Codex is the adversarial layer: critique, diff review, regression detection, front-end verification, and escalation.
- ForgeGod's own codebase now treats Codex as a production-ready planner/reviewer/adversary/coder surface when the official Codex CLI is installed and logged in. For this harness, Codex remains the adversarial layer while GLM-5.1 stays the primary builder.

## Policy and risk

### Strictly official path

- `OPENAI Codex` via ChatGPT subscription inside ForgeGod is clean.
- `ZAI_API_KEY` via the general API is clean.

### Experimental path

- `ZAI_CODING_API_KEY` inside ForgeGod is technically viable because ForgeGod already supports the coding endpoint shape.
- It is not safe to market that as officially sanctioned by Z.AI unless Z.AI explicitly recognizes ForgeGod as a supported coding tool.

## Repo rule for this mode

If ForgeGod users enable the Coding Plan harness:

1. Treat it as experimental.
2. Add a disclaimer in project docs and/or config comments.
3. Do not present it as a guaranteed supported billing path.
4. Prefer `Codex` as adversary and `GLM-5.1` as builder.

## Preset

See:

- `docs/examples/glm_codex_coding_plan.toml`
- `scripts/smoke_glm_codex_harness.py`
