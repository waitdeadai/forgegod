# ForgeGod Mock Parity Harness

Verified on `2026-04-08`.

## Purpose

This is ForgeGod's deterministic local harness for validating core agent
behavior without depending on live providers. It is inspired by the role that
`claw-code` assigns to its mock parity harness, but it is native to ForgeGod's
Python runtime and focuses on ForgeGod's current weak points:

- tool roundtrips
- workspace boundaries
- shell roundtrips
- completion gating
- reviewer gating
- acceptance-criteria review policy

## Why this exists

ForgeGod already has:

- unit tests
- stress tests
- build verification
- live-provider smoke tests

What it did not have was a small deterministic harness that proves the harness
itself does what it claims in a local, repeatable way. That gap matters because
ForgeGod's current objective is not to hand-finish showcase apps, but to become
a stronger harness than the repo lineage it came from.

This document covers the internal scripted-runtime layer. For the end-to-end
CLI layer that drives `forgegod run` against a deterministic local
OpenAI-compatible endpoint, see
[CLI_MOCK_PARITY_HARNESS_2026-04-08.md](CLI_MOCK_PARITY_HARNESS_2026-04-08.md).

## Current scenario manifest

Canonical manifest:

- [mock_parity_scenarios.json](mock_parity_scenarios.json)

Current scenarios:

1. `read_file_roundtrip`
2. `grep_roundtrip`
3. `write_file_allowed`
4. `write_file_denied`
5. `multi_tool_turn_roundtrip`
6. `bash_stdout_roundtrip`
7. `completion_gate_roundtrip`
8. `tool_scope_roundtrip`
9. `reviewer_blocks_cli_completion`
10. `acceptance_criteria_force_review`

## Run

```bash
python scripts/run_mock_parity_harness.py
```

Direct pytest execution also works:

```bash
python -m pytest -q tests/test_mock_parity_harness.py tests/test_cli_run.py tests/test_reviewer.py
```

## Design notes

- The harness is local and deterministic.
- It does not require OpenAI, Z.AI, or any network provider.
- Agent-turn scenarios use a scripted router that returns fixed model outputs.
- Tool execution is real: files, grep, repo map, shell, and git diff run
  through the real ForgeGod runtime surface.
- The purpose is to validate harness semantics, not model quality.

## What this still does not prove

- live-provider correctness
- cost/performance under real model latency
- strict Docker sandbox behavior end to end
- showcase-product completion

Those remain separate layers. This harness is the deterministic core layer.
