# AGENTS.md
Scope: entire repository.

This file is the repo-local operating contract for coding agents working on ForgeGod.

## Trust Order
- Trust code and tests first.
- Treat [docs/OPERATIONS.md](docs/OPERATIONS.md) as the current system of record.
- Use [docs/AUDIT_2026-04-07.md](docs/AUDIT_2026-04-07.md) for the dated defect list and verification baseline.
- Treat `README.md`, `README.es.md`, `BENCHMARKS.md`, and `docs/index.html` as secondary sources. They contain marketing and historical content.

## Verified Baseline (2026-04-08)
- Package version: `forgegod 0.1.0`
- Registered tools: `23`
- Provider code paths: `7` (`openai`, `anthropic`, `gemini`, `ollama`, `openrouter`, `deepseek`, `kimi`)
- Tests collected: `421`
- Core suite: `python -m pytest -m "not stress" -q` -> `337 passed, 84 deselected`
- Full suite: `python -m pytest tests -q` -> `421 passed`
- Stress suite: `python scripts/run_stress_tests.py --markdown` -> `84 passed`
- Lint status: `python -m ruff check forgegod tests` -> passes
- Build status: `python -m build` passes

## High-Risk Runtime Facts
- `forgegod loop` no longer auto-commits or auto-pushes by default. Those behaviors are now opt-in via `loop.auto_commit_success` and `loop.auto_push_success`.
- Agent runtime is workspace-scoped. Under agent execution, filesystem, shell, git, skills, and MCP stdio startup resolve against `config.project_dir.parent`, and filesystem tools reject paths that escape that root.
- Parallel worktree mode now scopes each worker agent to its assigned worktree by rebasing `config.project_dir` for that worker.
- Security config is now materially enforced: `sandbox_mode`, `sandbox_backend`, `sandbox_image`, `blocked_paths`, `audit_commands`, `redact_secrets`, and `max_rules_file_chars` are wired into runtime paths. Standard mode stays local with guardrails; strict mode uses a real Docker sandbox backend or blocks execution if no backend is available.
- Generated-code validation runs on writes and edits. In `strict` mode it blocks suspicious writes; in `standard` mode it remains advisory.
- Residual risk remains because ForgeGod does not yet provide microVM/syscall-level isolation, and strict mode depends on a usable local Docker backend plus a pre-pulled sandbox image.

## Working Rules
- Run `git status --short` before editing and do not revert user-owned local changes.
- Before committing any change, do deep 2026 research relevant to that change. Prefer primary or official sources, verify that the guidance is current, and record the links plus the verification date in repo docs when the change affects architecture, dependencies, security, benchmarks, model strategy, workflows, or public claims.
- ForgeGod aims for SOTA 2026 or beyond. Treat that as an engineering standard, not a marketing slogan: new architecture, safety, benchmark, or workflow changes should move the repo toward frontier practice, or clearly justify why a more conservative choice is better.
- Prefer small patches and rerun the smallest relevant verification command after each change.
- If you change runtime behavior, update `docs/OPERATIONS.md` and the dated audit doc in the same patch.
- If you change public-facing claims, provider counts, versions, benchmark numbers, security posture, or capability copy, update `docs/index.html` and verify the live site in the same workstream.
- Do not describe a change as SOTA, state-of-the-art, or beyond-SOTA unless both conditions are true: the design is backed by current 2026 sources and the repo proves it locally with passing tests or benchmarks.
- If README-style claims drift again, correct the docs or add a dated audit note instead of leaving silent mismatches.

## Standard Commands
- `python -m pytest -m "not stress" -q`
- `python -m pytest tests/stress -x -vv`
- `python -m ruff check forgegod tests`
- `python -m build`
- `python -m forgegod --version`

## Start Here
- [docs/OPERATIONS.md](docs/OPERATIONS.md)
- [docs/AUDIT_2026-04-07.md](docs/AUDIT_2026-04-07.md)
- [docs/WEB_RESEARCH_2026-04-07.md](docs/WEB_RESEARCH_2026-04-07.md)
