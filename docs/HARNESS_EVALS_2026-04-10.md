# Harness Evals V1 - 2026-04-10

## Why This Exists

ForgeGod already had:

- unit and integration tests
- stress tests
- a coding benchmark runner
- deterministic mock parity harnesses

What it did **not** have was a first-class way to answer this question:

> Did the harness behave correctly as a product surface?

That gap matters because ForgeGod is no longer just a library of helpers. It is
now a user-facing coding harness with:

- conversational root chat
- `run` and `loop` execution surfaces
- permission and approval policies
- strict sandbox paths
- provider and profile routing

Benchmarks answer "which model or route solved a coding task better?"  
Harness evals answer "did ForgeGod itself behave correctly and safely?"

## Research Basis

This plan is grounded in current official guidance and comparable systems:

- OpenAI says harness quality, evals, and traces materially affect agentic
  coding performance:
  - https://openai.com/index/harness-engineering/
- OpenAI's practical guide recommends starting simple, introducing decomposition
  only when justified, and keeping human checkpoints for risky actions:
  - https://cdn.openai.com/business-guides-and-resources/a-practical-guide-to-building-agents.pdf
- OpenAI's evals guidance emphasizes trace-aware grading rather than relying
  only on pass/fail unit tests:
  - https://platform.openai.com/docs/guides/evals
  - https://platform.openai.com/docs/guides/agent-evals
- Docker's security and rootless guidance reinforce that runtime claims should
  be backed by real isolation controls, not just policy prose:
  - https://docs.docker.com/engine/security/
  - https://docs.docker.com/engine/security/rootless/
- OpenHands distinguishes host-local runtimes from stronger isolated runtimes,
  which supports keeping ForgeGod's strict path measurable and honest:
  - https://docs.openhands.dev/openhands/usage/runtimes/runtime-local
  - https://docs.openhands.dev/openhands/usage/runtimes/runloop-runtime
- `claw-code`, `Crush`, and Claude Code are useful comparison points for CLI
  product quality, but they do not remove the need for repo-local ForgeGod evals:
  - https://github.com/ultraworkers/claw-code
  - https://github.com/charmbracelet/crush
  - https://code.claude.com/docs/en/interactive-mode

## Current Repository Gap

As of the 2026-04-10 audit baseline, ForgeGod still had these issues:

1. `BENCHMARKS.md` was explicitly historical, not current release evidence.
2. The repo had no formal harness eval surface for chat UX, approval flows,
   permission denials, or completion-gate discipline.
3. The router and benchmark layers could measure model output and test results,
   but not whether the CLI product surface behaved correctly for a human user.
4. Experimental paths such as Codex coder-loop and worktrees still needed
   stronger evidence before graduation decisions.

## V1 Goal

Ship a deterministic `forgegod evals` command that measures ForgeGod as a
product surface, not just a code generator.

V1 is intentionally narrow:

- deterministic
- mock-backed
- fast enough for local repetition
- focused on CLI behavior and harness policies

It is **not** the final eval system.

## V1 Scope

### Included in V1

- Built-in harness eval manifest
- Custom JSON manifest support
- Per-case trace capture
- Machine-readable JSON report
- Deterministic grading against expectations
- Coverage for:
  - natural-language root chat
  - terse/caveman chat
  - completion gate discipline
  - permission denials
  - prompt approval flow

### Explicitly Out of Scope for V1

- live cloud-provider comparisons
- grader-LLM scoring
- loop/worktree eval suites
- strict Docker backend coverage beyond the existing dedicated tests
- benchmark leaderboard regeneration
- showcase/product generation

## Design Principles

1. Separate harness evals from model benchmarks.
2. Prefer deterministic mock scenarios before live-provider eval noise.
3. Capture traces as artifacts, not just pass/fail summaries.
4. Grade product behavior directly:
   - Was the CLI conversational?
   - Did permissions behave correctly?
   - Did the completion gate hold?
5. Keep manifests simple enough that contributors can add cases without reading
   the entire runtime.

## V1 Architecture

### Core Pieces

- `forgegod/evals.py`
  - manifest loader
  - deterministic runner
  - graders
  - report writer
- `forgegod evals`
  - list cases
  - run selected cases
  - save JSON report
  - save per-case trace artifacts
- built-in case set
  - enough to catch regressions in talking mode and safety UX

### Inputs

Each eval case specifies:

- product surface: `run` or `chat`
- mock scenario
- workspace setup
- permission/approval mode
- terse on/off
- expectations

### Outputs

Each run produces:

- exit status
- scored case results
- per-check pass/fail
- request trace artifact per case
- aggregate report JSON

## Initial Built-In Cases

1. `chat_natural_language_roundtrip`
2. `chat_terse_roundtrip`
3. `run_completion_gate_roundtrip`
4. `run_prompt_approval_allowed`
5. `run_permission_denied`

These are not arbitrary. Together they cover the exact surfaces ForgeGod most
recently hardened.

## Acceptance Criteria for V1

V1 is considered done when all of this is true:

1. `forgegod evals --list` works.
2. `forgegod evals` runs a built-in deterministic manifest.
3. Report JSON is written to `.forgegod/evals/`.
4. Per-case request traces are saved.
5. The suite is covered by automated tests.
6. README, operations docs, audit notes, and website copy stay aligned.

## Recommended Next Phases

### V2

- add loop/worktree eval scenarios
- add opt-in strict Docker eval cases
- add scenario tags for provider surfaces and sandbox tiers

### V3

- add grader-backed trace analysis
- score plan quality, reviewer quality, and verification quality separately
- compare `single-model` vs `adversarial` using the same eval corpus

### V4

- connect eval outcomes to release gates and graduation decisions:
  - worktree graduation
  - Codex coder-loop graduation
  - provider-default changes

## Operational Rule

From this point forward:

- `forgegod benchmark` is for coding/model comparison
- `forgegod evals` is for harness/product behavior

If a regression is in the user-facing harness, it should land in `forgegod evals`
before it is called fixed.
