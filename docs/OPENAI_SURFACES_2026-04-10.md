# OpenAI Surfaces - 2026-04-10

This note documents how ForgeGod treats OpenAI in 2026.

## Why this exists

OpenAI now exposes two distinct ways to use frontier coding models:

- OpenAI API access
- ChatGPT/Codex subscription access

ForgeGod should not blur those together. Users need to understand what they
have connected, what gets billed where, and how the harness will split roles.

## Official source grounding

Verified on 2026-04-10:

- OpenAI model docs support GPT-5.4 and GPT-5.4-mini as current API surfaces:
  https://developers.openai.com/api/docs/models
- OpenAI Codex best practices stress planning, repo context, and parallel work:
  https://developers.openai.com/codex/learn/best-practices
- OpenAI Help says Codex is included on supported ChatGPT plans and runs as a
  separate ChatGPT/Codex surface:
  https://help.openai.com/en/articles/11369540-using-codex-with-your-chatgpt-plan
- OpenAI Help also states that ChatGPT plans and API usage are billed
  separately:
  https://help.openai.com/en/articles/8156019

Inference from those sources:

- It is legitimate to treat OpenAI API and Codex subscription as separate
  harness surfaces inside ForgeGod.
- A hybrid harness is sensible when the user has both surfaces connected,
  because it keeps builder and reviewer roles split while staying inside one
  vendor family.

## Surface modes

ForgeGod now exposes four OpenAI surface modes:

- `auto`
  - Keep provider-agnostic routing.
  - OpenAI may still be selected if it is the best available path.
- `api-only`
  - Restrict OpenAI routing to direct API-backed models.
  - ForgeGod uses GPT-5.4 or GPT-5.4-mini only.
- `codex-only`
  - Restrict OpenAI routing to the ChatGPT/Codex subscription surface.
  - ForgeGod uses `openai-codex:gpt-5.4` for every role that stays inside
    OpenAI.
- `api+codex`
  - Use OpenAI API for builder-style roles and Codex for review-style roles.
  - This is the recommended explicit OpenAI-only adversarial setup when both
    auth surfaces are ready.

## Effective fallback behavior

The configured surface is the user's intent. The effective surface is what
ForgeGod can actually run with the auth surfaces that are ready right now.

Examples:

- Requested `api+codex`, but only API key is ready -> effective `api-only`
- Requested `api+codex`, but only Codex login is ready -> effective `codex-only`
- Requested `api-only`, but only Codex login is ready -> effective `codex-only`
- Requested `codex-only`, but only API key is ready -> effective `api-only`

ForgeGod now surfaces both:

- requested OpenAI surface
- effective OpenAI surface

That behavior is available in:

- `forgegod init`
- onboarding wizard
- `forgegod auth sync`
- `forgegod auth explain`

## Recommended role mapping

### `api+codex` with `adversarial`

- `planner = openai:gpt-5.4`
- `coder = openai:gpt-5.4-mini`
- `reviewer = openai-codex:gpt-5.4`
- `sentinel = openai:gpt-5.4`
- `escalation = openai:gpt-5.4`
- `researcher = openai:gpt-5.4-mini`

### `api-only` with `adversarial`

- `planner = openai:gpt-5.4`
- `coder = openai:gpt-5.4-mini`
- `reviewer = openai:gpt-5.4`
- `sentinel = openai:gpt-5.4`
- `escalation = openai:gpt-5.4`
- `researcher = openai:gpt-5.4-mini`

### `codex-only`

- `planner = openai-codex:gpt-5.4`
- `coder = openai-codex:gpt-5.4`
- `reviewer = openai-codex:gpt-5.4`
- `sentinel = openai-codex:gpt-5.4`
- `escalation = openai-codex:gpt-5.4`
- `researcher = openai-codex:gpt-5.4`

## Commands

Inspect before writing config:

```bash
forgegod auth explain --profile adversarial --prefer-provider openai --openai-surface api+codex
```

Write the recommended hybrid setup:

```bash
forgegod auth sync --profile adversarial --prefer-provider openai --openai-surface api+codex
```

Force API-only:

```bash
forgegod auth sync --profile adversarial --openai-surface api-only
```

Force Codex-only:

```bash
forgegod auth sync --profile adversarial --openai-surface codex-only
```

Release-grade matrix:

```bash
forgegod evals --matrix openai-surfaces
```

That matrix compares:

- `adversarial`
- `single-model`
- `auto`
- `api-only`
- `codex-only`
- `api+codex`

with split scores for:

- `ux`
- `safety`
- `workflow`
- `verification`

## Current status

As of 2026-04-10:

- This OpenAI surface model is implemented in ForgeGod config, onboarding, and
  CLI.
- The behavior is covered by deterministic unit and CLI tests.
- It is a harness clarity upgrade, not a claim that OpenAI is automatically the
  best default for every repository.
