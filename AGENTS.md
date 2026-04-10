# AGENTS.md
Scope: entire repository.

This file is the repo-local operating contract for coding agents working on ForgeGod.

## Trust Order
- Trust code and tests first.
- Treat [docs/OPERATIONS.md](docs/OPERATIONS.md) as the current system of record.
- Use [docs/AUDIT_2026-04-07.md](docs/AUDIT_2026-04-07.md) for the dated defect list and verification baseline.
- Treat `README.md`, `README.es.md`, `BENCHMARKS.md`, and `docs/index.html` as secondary sources. They contain marketing and historical content.

## Verified Baseline (2026-04-09)
- Package version: `forgegod 0.1.0`
- Registered tools: `23`
- Provider families: `8`
- Native auth surfaces: `2` (`openai-codex` via ChatGPT/Codex login, `zai` via Coding Plan/API key)
- Route surfaces: `9` (`ollama`, `openai`, `openai-codex`, `anthropic`, `openrouter`, `gemini`, `deepseek`, `kimi`, `zai`)
- Tests collected: `521`
- Core suite: `python -m pytest -m "not stress" -q` -> `436 passed, 1 skipped, 84 deselected`
- Full suite: `python -m pytest tests -q` -> `520 passed, 1 skipped`
- Stress suite: `python scripts/run_stress_tests.py --markdown` -> `84 passed`
- Lint status: `python -m ruff check forgegod tests scripts` -> passes
- Build status: `python -m build` passes

## High-Risk Runtime Facts
- `forgegod loop` no longer auto-commits or auto-pushes by default. Those behaviors are now opt-in via `loop.auto_commit_success` and `loop.auto_push_success`.
- Agent runtime is workspace-scoped. Under agent execution, filesystem, shell, git, skills, and MCP stdio startup resolve against `config.project_dir.parent`, and filesystem tools reject paths that escape that root.
- Parallel worktree mode now scopes each worker agent to its assigned worktree by rebasing `config.project_dir` for that worker, and it now fails fast unless the repo has at least one commit available for isolated worktrees.
- Parallel worktree patch-back now handles newly created files, so worker-created files can be reviewed and applied back into the main workspace instead of disappearing from `git diff HEAD`.
- The `git_worktree_create` tool now follows the same contract as the main loop/worktree runtime: it requires at least one commit and uses a single-step `git worktree add -b ...` flow instead of a stale branch-plus-HEAD split path.
- Security config is now materially enforced: `sandbox_mode`, `sandbox_backend`, `sandbox_image`, `blocked_paths`, `audit_commands`, `redact_secrets`, and `max_rules_file_chars` are wired into runtime paths. Standard mode stays local with guardrails; strict mode uses a real Docker sandbox backend or blocks execution if no backend is available.
- ForgeGod now supports native subscription-backed OpenAI access inside the ForgeGod CLI through `forgegod auth login openai-codex` and `forgegod auth sync`. Z.AI's Coding Plan path is also first-class via `ZAI_CODING_API_KEY`.
- `forgegod init`, onboarding, and `forgegod auth sync` now write auth-aware model defaults so planner/reviewer/adversary flows can run without hand-editing `config.toml` when the user has OpenAI Codex or Z.AI but no OpenAI API key.
- OpenAI Codex subscription routing is verified for planner/reviewer/adversary workflows. Coder-loop use is available, but it remains experimental and should be benchmarked per repo before making it the default remote coder.
- HTTP client initialization now degrades cleanly when optional HTTP/2 extras
  are absent. ForgeGod logs once and falls back to HTTP/1.1 instead of failing
  the router or CI on environments that install plain `httpx` without `h2`.
- Implementation-task completion is no longer trusted just because the model
  stopped calling tools. The local harness now requires post-edit verification
  evidence plus a reviewed final diff before accepting completion, and stories
  with acceptance criteria force reviewer coverage by default.
- ForgeGod now exposes `forgegod permissions` so users can inspect the effective
  permission mode, blocked tools, and allowlist override without reading code.
- ForgeGod now also supports approval overrides on top of static permission
  modes: `deny`, `prompt`, and `approve`.
- Prompt approval is intentionally serialized. `forgegod loop --approval-mode prompt`
  only supports `--workers 1`, and `WorktreePool` rejects prompt approval unless
  `max_workers=1` and a callback is supplied.
- ForgeGod now has two deterministic parity layers: the local agent/runtime
  harness plus a CLI mock parity harness that drives `forgegod run` against a
  local OpenAI-compatible endpoint.
- That CLI mock parity harness now also covers `strict` sandbox behavior at the
  product surface: allowed strict-mode bash execution routes through the real
  sandbox interface, and missing strict backends surface back to the model/CLI
  as deterministic failures instead of opaque hangs.
- ForgeGod now also ships an opt-in real-Docker strict integration test. It is
  skipped by default, but when `FORGEGOD_RUN_DOCKER_STRICT_TESTS=1` and Docker
  is ready, the suite proves a real strict backend roundtrip without monkeypatching.
- ForgeGod now has an explicit deterministic-memory switch for harness work.
  `memory.enabled` and `memory.extraction_enabled` let parity and benchmark
  runs isolate loop execution without hidden post-task model calls.
- If a repo root contains `DESIGN.md`, ForgeGod now injects it into the agent prompt as the frontend design source of truth.
- ForgeGod now ships `forgegod design` for importing `DESIGN.md` presets and `forgegod contribute` for contribution-aware planning/autonomous work that reads `CONTRIBUTING.md` plus repo rules.
- Generated-code validation runs on writes and edits. In `strict` mode it blocks suspicious writes; in `standard` mode it remains advisory.
- Strict Node/Next bootstrap now keeps the workspace itself on a bind mount but mounts `node_modules` into a named Docker volume, including on first-run bootstrap commands like `create-next-app`, so ForgeGod is less likely to poison a Windows bind mount with dependency trees.
- The strict sandbox dependency stamp now treats the Docker volume as the real source of truth instead of host-side `node_modules`, which avoids false "deps are ready" assumptions after stale host leftovers or volume cleanup.
- Agent execution now sees the same checked-in repo docs that planning does. `docs/README.md`, `docs/PRD.md`, `docs/STORIES.md`, `docs/ARCHITECTURE.md`, and `docs/RUNBOOK.md` are injected in bounded form so execution loops are less likely to drift away from repo-defined intent.
- Residual risk remains because ForgeGod does not yet provide microVM/syscall-level isolation, and strict mode depends on a usable local Docker backend plus a pre-pulled sandbox image.

## Working Rules
- Your primary objective in the current year is to make ForgeGod the strongest harness possible for autonomous coding work. In 2026, that means aiming to be the strongest harness on the market, not merely a good demo.
- Before making architecture or loop changes, audit the full relevant architecture first. Do not patch blind.
- Before committing meaningful changes, do extensive current-year research with primary or official sources and build a complete understanding of both the repo and the specific subsystem being changed.
- Treat `https://github.com/ultraworkers/claw-code` as the origin baseline that ForgeGod must understand and exceed. Compare against it explicitly when auditing architecture, workflow, and harness behavior.
- The current preferred cost-effective harness is `openai-codex` plus `zai:glm-5.1`, but the architecture should remain provider-agnostic because that best pair can change quickly.
- Do not solve showcase products manually outside ForgeGod as a substitute for harness quality. The product is the benchmark; the harness is the thing being improved.
- Rule 7: default to maximum effort. For harness changes, do not stop at the first passing check; expand audit, verification, and documentation until the change is defensible, reproducible, and hard to fake.
- Rule 8: when the harness hits a real blocker, do fresh current-year web research before grinding locally for hours. Prefer official docs and proven real-world cases, then encode what works into ForgeGod so the fix is repeatable.
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
