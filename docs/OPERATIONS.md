# ForgeGod Operations

This document is the current system of record for day-to-day work in this repository. It is intentionally more reliable than the marketing copy in `README.md`, `README.es.md`, `BENCHMARKS.md`, and `docs/index.html`.

## Policy

- ForgeGod targets SOTA 2026 or beyond for coding-agent architecture, safety, benchmarking, and developer workflow quality.
- That target is only credible when backed by current primary or official 2026 sources and confirmed by local repo evidence such as passing tests, reproducible benchmarks, or documented verification steps.
- If the repo falls short of that bar, document the gap explicitly rather than silently implying frontier quality.

## Verified Baseline (2026-04-08)

- OS: `Windows-11-10.0.26200-SP0`
- Python: `3.13.5`
- Package version: `forgegod 0.1.0`
- Registered tools: `23`
- Provider code paths present in `forgegod/router.py`: `8`
- Tests collected: `439`
- Git remote audited: `https://github.com/waitdeadai/forgegod.git`

## Verification Commands

| Command | Observed result on 2026-04-08 |
|:--------|:------------------------------|
| `python -m pytest -m "not stress" -q` | `355 passed, 84 deselected in 14.90s` |
| `python -m pytest tests/stress/test_stress_budget.py::TestRapidCostRecording::test_1000_rapid_writes -q` | passes in `0.07s` |
| `python scripts/run_stress_tests.py --markdown` | `84 passed in 68.09s` |
| `python -m pytest tests -q` | `439 passed in 75.82s` |
| `python -m pytest --collect-only -q` | `439 tests collected in 0.36s` |
| `python -m ruff check forgegod tests` | passes |
| `python -m build` | passes; builds sdist and wheel |
| `python -m forgegod --version` | launches and reports `F O R G E G O D v0.1.0` |

## Current Reality Check

- `forgegod loop` is safer than the previous audited baseline: auto-commit and auto-push are now opt-in config flags, not default behavior.
- The benchmark runner no longer calls `Agent(..., project_dir=...)`; that constructor path is fixed, and quoted validation commands are parsed safely.
- Worktree support now scopes worker agents to their assigned worktree by rebasing `config.project_dir` per worker.
- Filesystem tools are repository-scoped under agent execution. Paths that escape the active workspace root are rejected, and configured `blocked_paths` are enforced.
- Security configuration is now materially wired through the tool layer: shell execution honors `sandbox_mode`, `sandbox_backend`, and `sandbox_image`; outputs honor `redact_secrets`; command execution can be audited; and rules loading respects `max_rules_file_chars`.
- Standard mode remains a host-local guarded workflow: isolated process dirs, workspace scoping, blocked shell operators, and command policy checks.
- Strict mode now requires a real Docker sandbox backend. Commands run in a no-network, read-only-root container with the workspace bind-mounted, or they are blocked if Docker/image prerequisites are missing.
- Strict mode also blocks suspicious generated-code writes and edits.
- ForgeGod now ships `forgegod design`, which imports `DESIGN.md` presets from `awesome-design-md`, and the agent automatically injects local `DESIGN.md` into frontend tasks.
- ForgeGod now ships `forgegod contribute`, which reads `CONTRIBUTING.md`/repo rules, can discover approachable GitHub issues, and can plan or execute contribution-sized work in a target repository.
- The benchmark file is historical, not a current green-build signal.
- Based on the local verified baseline, the shipped CI workflow should now be green again: lint passes, the full test tree passes, stress passes, and build passes.

## Safe Workflow

1. Run `git status --short` before touching anything.
2. Do deep 2026 research before committing any change. Use primary or official sources when possible, and log links plus the verification date if the change affects architecture, dependencies, security, benchmarks, model strategy, workflows, or public claims.
3. Read [AGENTS.md](../AGENTS.md) and the dated audit before changing loop, worktree, filesystem, or security behavior.
4. Use the smallest verification command that proves the change.
5. If runtime behavior changes, update this file and the dated audit in the same commit.
6. If public-facing claims, providers, versions, benchmark numbers, or security posture change, update `docs/index.html` and verify the live site in the same workstream.
7. Avoid trusting the website bundle in `docs/index.html` for operational truth. It is a static marketing artifact.

## Documentation Map

- [AGENTS.md](../AGENTS.md): short repo-local instructions for coding agents
- [CLAUDE.md](../CLAUDE.md): Claude Code compatibility entrypoint
- [CONVENTIONS.md](../CONVENTIONS.md): Aider and generic agent conventions
- [docs/AUDIT_2026-04-07.md](AUDIT_2026-04-07.md): code audit, findings, and remediation order
- [docs/WEB_RESEARCH_2026-04-07.md](WEB_RESEARCH_2026-04-07.md): external 2026 research that informed the doc structure and safety notes

## Recommended Next Work

1. Add a stronger strict backend, such as Docker Sandboxes or another microVM/syscall-confined runtime, so ForgeGod is not limited to container isolation.
2. Add lifecycle tooling for strict sandbox images and Docker readiness checks in onboarding/doctor flows.
3. Regenerate benchmark claims now that the benchmark path is fixed and the current stress suite is green, or keep benchmark docs explicitly historical.
4. Add explicit tests for worktree isolation and loop auto-commit flag behavior so those guarantees stay locked in.
