# ForgeGod Operations

This document is the current system of record for day-to-day work in this repository. It is intentionally more reliable than the marketing copy in `README.md`, `README.es.md`, `BENCHMARKS.md`, and `docs/index.html`.

## Policy

- ForgeGod targets SOTA 2026 or beyond for coding-agent architecture, safety, benchmarking, and developer workflow quality.
- The repository objective is to make ForgeGod the strongest harness possible in the current year, not to hand-finish showcase products outside the harness.
- Before changing architecture or task loops, audit the relevant subsystem end to end first. Do not patch blind.
- Before committing meaningful changes, do extensive current-year research with primary or official sources and build a concrete understanding of both ForgeGod and the subsystem being changed.
- `https://github.com/ultraworkers/claw-code` is the historical origin baseline. ForgeGod should understand that lineage and exceed it on architecture, workflow reliability, and harness quality.
- The currently preferred cost-effective harness pairing is `openai-codex` plus `zai:glm-5.1`, but ForgeGod should stay provider-agnostic because the best pairing can change quickly.
- Default to maximum effort. For harness changes, do not stop at the first passing check; expand audit, verification, and documentation until the result is defensible and reproducible.
- Rule 8: when a real harness blocker appears, do fresh current-year web research before spending hours brute-forcing locally. Prefer official docs and proven cases from the relevant ecosystem, then encode the working pattern into ForgeGod so the fix is repeatable.
- That target is only credible when backed by current primary or official 2026 sources and confirmed by local repo evidence such as passing tests, reproducible benchmarks, or documented verification steps.
- If the repo falls short of that bar, document the gap explicitly rather than silently implying frontier quality.

## Verified Baseline (2026-04-10)

- OS: `Windows-11-10.0.26200-SP0`
- Python: `3.13.5`
- Package version: `forgegod 0.1.0`
- Registered tools: `23`
- Provider families: `8`
- Route surfaces present in `forgegod/router.py`: `9`
- Tests collected: `553`
- Git remote audited: `https://github.com/waitdeadai/forgegod.git`

## Verification Commands

| Command | Observed result on 2026-04-10 |
|:--------|:------------------------------|
| `python -m pytest -m "not stress" -q` | `468 passed, 1 skipped, 84 deselected in 153.89s` |
| `python -m pytest tests/stress/test_stress_budget.py::TestRapidCostRecording::test_1000_rapid_writes -q` | passes in `0.07s` |
| `python scripts/run_stress_tests.py --markdown` | `84 passed in 137.62s` |
| `python -m pytest tests -q` | `552 passed, 1 skipped in 235.36s` |
| `python -m pytest --collect-only -q` | `553 tests collected` |
| `python -m forgegod evals --output .forgegod/evals/smoke_report.json --traces-dir .forgegod/evals/smoke_traces` | `10/10 passing, score=1.000` |
| `python -m forgegod evals --matrix openai-surfaces --output .forgegod/evals/openai_surface_matrix.json --traces-dir .forgegod/evals/openai_surface_matrix_traces` | `8/8 rows passing, score=1.000` |
| `python -m ruff check forgegod tests scripts` | passes |
| `python -m build` | passes; builds sdist and wheel |
| `python scripts/smoke_glm_codex_harness.py` | passes; `zai:glm-5.1` planner + `openai-codex:gpt-5.4` reviewer |
| `python scripts/run_mock_parity_harness.py` | `10 passed` |
| `python scripts/run_cli_mock_parity_harness.py` | `12 passed` |
| `FORGEGOD_RUN_DOCKER_STRICT_TESTS=1 python -m pytest tests/test_strict_sandbox_integration.py -q -rs` | `1 passed` |
| `python -m forgegod --version` | launches and reports `F O R G E G O D v0.1.0` |

## Current Reality Check

- `forgegod loop` is safer than the previous audited baseline: auto-commit and auto-push are now opt-in config flags, not default behavior.
- The benchmark runner no longer calls `Agent(..., project_dir=...)`; that constructor path is fixed, and quoted validation commands are parsed safely.
- Parallel loop execution now runs through `WorktreePool` instead of a shared workspace, scopes worker agents to their assigned worktree, requires at least one git commit before `--workers > 1`, and can patch newly created files back into the main workspace.
- The public `git_worktree_create` tool now matches that same runtime contract, so worktree behavior is no longer split between two different implementations.
- ForgeGod now exposes native auth management in the ForgeGod CLI itself: `forgegod auth status`, `forgegod auth login openai-codex`, and `forgegod auth sync`.
- ForgeGod CLI now has a shared branded console surface in cyan/white/yellow instead of separate utilitarian consoles across onboarding, doctor, and status views.
- `forgegod run` and `forgegod loop` now narrate progress in plain language through runtime events instead of leaking successful transport chatter as the main user-facing output.
- Running plain `forgegod` in a real terminal now opens a natural-language
  session by default, so the primary UX no longer requires `forgegod run "..."`.
  `forgegod run` remains the deterministic scripted path for CI, automation,
  and copy-paste one-shots.
- That same root entrypoint now auto-creates repo-local `.forgegod/config.toml`
  on first use with auth-aware defaults when possible. `forgegod init` is still
  the guided wizard path when the user wants onboarding or explicit profile
  selection up front.
- That conversational root entrypoint now also preserves the same session
  overrides as explicit subcommands, including `--terse`, model overrides,
  review toggles, permission/approval modes, and repeated `--allow-tool`
  values. Humans no longer lose control by choosing the natural-language
  surface over `forgegod run`.
- `forgegod init` onboarding now detects linked providers up front, recommends a setup path, explains repo-local secret storage, and keeps model connection guidance inside ForgeGod CLI instead of pushing users straight into manual shell editing.
- OpenAI Codex subscription routing is now a first-class route surface. It is verified for planner/reviewer/adversary workflows, and `forgegod auth sync` writes auth-aware model defaults so those flows work without manual config edits.
- Z.AI's Coding Plan path is also first-class through `ZAI_CODING_API_KEY`, and `forgegod init` / onboarding / `forgegod auth sync` can wire it into role defaults automatically.
- `forgegod init`, onboarding, and `forgegod auth sync` now also expose a harness profile choice: `adversarial` is the recommended split-model setup, while `single-model` intentionally pins every role to one detected model for users who prefer a simpler loop.
- Those same setup flows now expose `preferred_provider = "openai"` as an explicit bias. In adversarial mode, ForgeGod can now prefer `openai:gpt-5.4` / `openai:gpt-5.4-mini` for API-backed roles while still using `openai-codex:gpt-5.4` as the reviewer when the ChatGPT/Codex subscription surface is linked.
- ForgeGod now also exposes explicit OpenAI surface selection in setup flows: `auto`, `api-only`, `codex-only`, and `api+codex`. `forgegod auth explain` makes the requested surface, the effective detected surface, and the resulting role mapping visible before the user rewrites project defaults.
- Agent completion is now harder to fake locally: implementation tasks must show
  post-edit verification evidence plus a reviewed final diff before the core
  agent loop accepts completion, and `forgegod run --review` now treats
  `revise` / `reject` as blocking verdicts instead of cosmetic output.
- Filesystem tools are repository-scoped under agent execution. Paths that escape the active workspace root are rejected, and configured `blocked_paths` are enforced.
- Security configuration is now materially wired through the tool layer: shell execution honors `sandbox_mode`, `sandbox_backend`, and `sandbox_image`; outputs honor `redact_secrets`; command execution can be audited; and rules loading respects `max_rules_file_chars`.
- Standard mode remains a host-local guarded workflow: isolated process dirs, workspace scoping, blocked shell operators, and command policy checks.
- Strict mode now requires a real Docker sandbox backend. Commands run in a no-network, read-only-root container with the workspace bind-mounted, or they are blocked if Docker/image prerequisites are missing.
- Strict Node/web bootstrap is now less brittle on Windows-style workspaces: ForgeGod mounts `node_modules` as a named Docker volume, including for first-run bootstrap commands, instead of assuming dependency trees should live on the host bind mount.
- ForgeGod now treats that dependency volume, not host-side `node_modules`, as the durable readiness signal for strict Node commands. That avoids stale-host false positives after resets or cleaned Docker volumes.
- `forgegod doctor` now checks strict sandbox readiness directly: Docker CLI, Docker daemon, and the required strict image cache are all surfaced with copy-paste fix steps.
- `forgegod doctor` now also distinguishes "Docker CLI missing" from "Docker daemon not ready", which matters on Windows/Desktop setups where the client is installed but the engine pipe is down.
- Strict mode also blocks suspicious generated-code writes and edits.
- ForgeGod now ships `forgegod design`, which imports `DESIGN.md` presets from `awesome-design-md`, and the agent automatically injects local `DESIGN.md` into frontend tasks.
- ForgeGod now ships `forgegod contribute`, which reads `CONTRIBUTING.md`/repo rules, can discover approachable GitHub issues, and can plan or execute contribution-sized work in a target repository.
- Stories with acceptance criteria now force reviewer coverage by default,
  instead of relying purely on sample-rate review.
- ForgeGod now exposes `forgegod permissions`, which makes the current
  permission mode, blocked tools, and allowlist override inspectable from the
  CLI instead of leaving that policy implicit in code or docs.
- ForgeGod now supports approval modes on top of static permission modes:
  `deny`, `prompt`, and `approve`. The prompt path is wired into `forgegod run`,
  and it is covered by the deterministic CLI mock parity harness.
- Prompt approval is now explicitly serialized across richer execution paths.
  `forgegod loop --approval-mode prompt` only supports `--workers 1`, and
  `WorktreePool` rejects prompt approval unless it runs with one worker and an
  injected approval callback.
- `forgegod loop` now closes its `ModelRouter` cleanly on exit, matching the
  shutdown hygiene that `forgegod run` already had.
- OpenAI direct routing is now configurable through `[openai].base_url`, which
  lets ForgeGod hit deterministic local OpenAI-compatible endpoints for harness
  verification without vendor network calls.
- ForgeGod now has a true CLI mock parity harness, not just unit-level scripted
  routers. `forgegod run` is exercised against a deterministic local
  OpenAI-compatible endpoint, and permission-denied write tasks now fail fast
  instead of spinning to max turns.
- That CLI parity harness now covers real `forgegod loop` execution too:
  deterministic single-worker success, deterministic permission-blocked
  failure, and deterministic isolated parallel worktree success are all
  exercised through PRD-driven loop runs against the mock provider.
- The CLI parity harness now also covers `strict` sandbox interactions:
  an allowed strict-mode bash command must route through the real sandbox
  interface, and a missing strict backend must surface back to the model/CLI
  as a deterministic, user-visible failure.
- ForgeGod now also has an environment-gated real Docker strict integration
  test. It is opt-in so the default suite stays portable, but when Docker is
  available it proves a real strict backend roundtrip without monkeypatching.
- ForgeGod now exposes `memory.enabled` and `memory.extraction_enabled` so
  deterministic harnesses and benchmarks can isolate loop behavior without
  hidden post-task memory-model calls.
- ForgeGod now has deterministic CLI coverage for auth-aware provider selection
  in `forgegod auth sync`, including cloud-budget normalization and the Codex
  experimental-coder note.
- ForgeGod now has a first-class deterministic harness eval surface:
  `forgegod evals`. It sits above unit tests and parity harnesses, saves
  per-case trace artifacts, and grades real CLI behavior for chat UX, terse
  mode, approval flows, permission denials, completion-gate discipline,
  loop/worktree behavior, and strict-sandbox interface handling.
- That same surface now also splits scores by `ux`, `safety`, `workflow`, and
  `verification`, and it ships an explicit OpenAI-first matrix:
  `forgegod evals --matrix openai-surfaces`. That matrix compares
  `adversarial` vs `single-model` across `auto`, `api-only`, `codex-only`, and
  `api+codex` routing assumptions without relying on anecdotal local runs.
- Agent execution now sees bounded repo context docs, not just `AGENTS.md` and
  `DESIGN.md`. This aligns execution with checked-in `docs/PRD.md`,
  `docs/STORIES.md`, `docs/ARCHITECTURE.md`, and related source-of-truth docs.
- ForgeGod now degrades cleanly when optional HTTP/2 support is unavailable in
  the host environment. If `httpx` was installed without `h2`, the router logs
  a single warning and reuses HTTP/1.1 clients instead of failing requests and
  collapsing CI on Python 3.11.
- The benchmark file is historical, not a current green-build signal.
- Based on the local verified baseline, including a full rerun on Python 3.11,
  the shipped CI workflow should now be green again: lint passes, the full test
  tree passes, stress passes, and build passes.

## Safe Workflow

1. Run `git status --short` before touching anything.
2. Do deep 2026 research before committing any change. Use primary or official sources when possible, and log links plus the verification date if the change affects architecture, dependencies, security, benchmarks, model strategy, workflows, or public claims.
3. Read [AGENTS.md](../AGENTS.md) and the dated audit before changing loop, worktree, filesystem, or security behavior.
4. Do not compensate for harness weakness by hand-building showcase features outside ForgeGod. Improve the harness until ForgeGod can complete the target itself.
5. Start with the smallest verification command that can fail fast, then widen verification to the maximum relevant evidence before declaring the change done.
6. If runtime behavior changes, update this file and the dated audit in the same commit.
7. If public-facing claims, providers, versions, benchmark numbers, or security posture change, update `docs/index.html` and verify the live site in the same workstream.
8. Avoid trusting the website bundle in `docs/index.html` for operational truth. It is a static marketing artifact.
9. For harness changes, run both deterministic layers when relevant:
   `python scripts/run_mock_parity_harness.py` and `python scripts/run_cli_mock_parity_harness.py`.

## Documentation Map

- [AGENTS.md](../AGENTS.md): short repo-local instructions for coding agents
- [CLAUDE.md](../CLAUDE.md): Claude Code compatibility entrypoint
- [CONVENTIONS.md](../CONVENTIONS.md): Aider and generic agent conventions
- [docs/AUDIT_2026-04-07.md](AUDIT_2026-04-07.md): code audit, findings, and remediation order
- [docs/WEB_RESEARCH_2026-04-07.md](WEB_RESEARCH_2026-04-07.md): external 2026 research that informed the doc structure and safety notes

## Recommended Next Work

1. Add an opt-in real-Docker tier to `forgegod evals` so strict backend coverage can graduate from a separate smoke into a release-gated eval layer when the environment allows it.
2. Add grader-backed trace analysis inside `forgegod evals`, especially for reviewer quality and verification quality, so score splits are not only expectation-driven.
3. Expand the OpenAI matrix from deterministic routing coverage to live API/Codex comparisons when the user has both auth surfaces linked.
4. Add a stronger strict backend, such as Docker Sandboxes or another microVM/syscall-confined runtime, so ForgeGod is not limited to container isolation.
5. Regenerate benchmark claims now that the benchmark path is fixed and the current stress suite is green, or keep benchmark docs explicitly historical.
6. Decide whether OpenAI Codex coder-loop behavior is good enough to graduate from experimental status, using `forgegod evals` plus broader repo-local benchmarks instead of anecdotal runs.
