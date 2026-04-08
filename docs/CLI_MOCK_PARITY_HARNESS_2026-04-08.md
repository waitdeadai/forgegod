# ForgeGod CLI Mock Parity Harness

Verified on `2026-04-08`.

## Purpose

This is the end-to-end CLI layer of ForgeGod's parity harness. Unlike the
internal scripted-agent harness, this layer drives the real `forgegod run`
and `forgegod loop` commands against a deterministic local OpenAI-compatible
endpoint.

It exists to prove these product-level claims locally and repeatably:

- ForgeGod CLI can drive a real OpenAI-compatible provider path without live vendors
- tool calls roundtrip through the router, agent, and CLI surfaces correctly
- completion gates still hold at the CLI layer
- permission-denied write tasks fail fast instead of spinning to max turns
- PRD-driven loop execution is reproducible without live providers
- isolated parallel worktree execution is reproducible without live providers
- strict sandbox behavior is visible and deterministic at the CLI layer

## Why this matters

`claw-code` treats mock parity as a first-class harness surface, not just a
collection of unit tests. ForgeGod now has two layers:

1. `docs/MOCK_PARITY_HARNESS_2026-04-08.md` for local deterministic agent/runtime semantics
2. this CLI harness for end-to-end product behavior through a mock provider

That split is deliberate. It lets ForgeGod prove harness behavior without
paying provider costs or depending on external uptime.

## Scenarios

Canonical manifest:

- [cli_mock_parity_scenarios.json](cli_mock_parity_scenarios.json)

Current scenarios:

1. `cli_read_file_roundtrip`
2. `cli_write_file_allowed`
3. `cli_write_file_denied`
4. `cli_completion_gate_roundtrip`
5. `cli_tool_result_turn_capture`
6. `cli_prompt_approval_allows_write`
7. `cli_prompt_approval_denies_write`
8. `cli_loop_story_success`
9. `cli_loop_story_denied`
10. `cli_loop_parallel_worktree_success`
11. `cli_strict_bash_roundtrip`
12. `cli_strict_backend_blocked`

## Run

```bash
python scripts/run_cli_mock_parity_harness.py
```

Direct pytest execution also works:

```bash
python -m pytest -q tests/test_cli_mock_parity.py
```

If you want to inspect the mock endpoint directly:

```bash
python scripts/mock_openai_service.py --scenario cli_read_file_roundtrip
```

## Design notes

- The endpoint is local and deterministic.
- The provider path is genuinely OpenAI-compatible HTTP, not a monkeypatched router.
- The harness uses real ForgeGod CLI commands, config loading, tool execution,
  permission enforcement, and completion semantics.
- Loop scenarios use repo-local config switches such as `memory.enabled` and
  `memory.extraction_enabled` so deterministic parity runs do not get polluted
  by hidden post-task memory-model calls.
- The parallel loop scenario proves the real product path now goes through
  isolated git worktrees, not a shared workspace, and it requires a repo with
  at least one commit so Git has a valid base for `worktree add`.
- Strict-mode scenarios prove two different things without needing a live
  Docker engine in every test environment:
  the CLI must route allowed commands through the real sandbox interface, and
  missing strict backends must surface back through the product as explicit
  failures instead of opaque max-turn loops.
- The mock service captures request payloads so tests can assert that tool
  results are actually sent back to the model.

## What this still does not prove

- live-provider correctness
- subscription auth behavior for Codex or Z.AI Coding Plan
- real Docker-engine backend health end to end
- showcase-product completion quality

Those remain separate layers. This harness is the repeatable product-CLI layer.
