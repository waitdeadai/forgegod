<p align="center">
  <a href="README.md"><img src="https://img.shields.io/badge/lang-en-blue.svg" alt="English"></a>
  <a href="README.es.md"><img src="https://img.shields.io/badge/lang-es-yellow.svg" alt="Español"></a>
</p>

<p align="center">
  <img src="docs/mascot.png" alt="ForgeGod official mascot" width="120" />
</p>

<p align="center">
  <sub>Official mascot design by <a href="https://www.linkedin.com/in/matt-mesa/">Matias Mesa</a>.</sub>
</p>

<h1 align="center">ForgeGod</h1>

<p align="center">
  <strong>The coding agent that runs 24/7, learns from its mistakes, and costs $0 when you want it to.</strong>
</p>

<p align="center">
  <a href="https://pypi.org/project/forgegod/"><img src="https://img.shields.io/pypi/v/forgegod?color=00e5ff&style=flat-square" alt="PyPI"></a>
  <a href="https://github.com/waitdeadai/forgegod/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-Apache%202.0-00e5ff?style=flat-square" alt="License"></a>
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/python-3.11+-00e5ff?style=flat-square" alt="Python 3.11+"></a>
  <a href="https://github.com/waitdeadai/forgegod/actions"><img src="https://img.shields.io/github/actions/workflow/status/waitdeadai/forgegod/ci.yml?style=flat-square&color=00e5ff" alt="CI"></a>
  <a href="https://forgegod.com"><img src="https://img.shields.io/badge/site-forgegod.com-00e5ff?style=flat-square" alt="Website"></a>
  <a href="docs/AUDIT_2026-04-07.md"><img src="https://img.shields.io/badge/audit-2026.04.07-00e5ff?style=flat-square" alt="Audit"></a>
</p>

<p align="center">
  <code>23 built-in tools</code> &bull; <code>8 LLM providers</code> &bull; <code>5-tier memory</code> &bull; <code>24/7 autonomous</code> &bull; <code>$0 local mode</code>
</p>

---

ForgeGod orchestrates multiple LLMs (OpenAI, Anthropic, Google Gemini, Ollama, OpenRouter, DeepSeek, Kimi via Moonshot, and Z.AI GLM) into a single autonomous coding engine. It routes tasks to the right model, runs 24/7 from a PRD, learns from every outcome, and self-improves its own strategy. Run it locally for $0 with Ollama, use cloud API keys when you need them, or connect native OpenAI Codex subscription auth and Z.AI Coding Plan inside the ForgeGod CLI.

```bash
pip install forgegod
```

> Audit note (re-verified 2026-04-09): the verified baseline now includes `23` registered tools, `8` provider families, `9` route surfaces, `525` collected tests, `440` non-stress tests passing by default plus `1` opt-in Docker strict integration test, `84/84` stress tests passing, green lint, and a green build. `forgegod loop` no longer auto-commits or auto-pushes by default. Read [docs/AUDIT_2026-04-07.md](docs/AUDIT_2026-04-07.md), [docs/OPERATIONS.md](docs/OPERATIONS.md), and [docs/WEB_RESEARCH_2026-04-07.md](docs/WEB_RESEARCH_2026-04-07.md) before making runtime changes.

## What Makes ForgeGod Different

Every other coding CLI uses **one model at a time** and **resets to zero** each session. ForgeGod doesn't.

| Capability | Claude Code | Codex CLI | Aider | Cursor | **ForgeGod** |
|:-----------|:----------:|:---------:|:-----:|:------:|:------------:|
| Multi-model auto-routing | - | - | manual | - | **yes** |
| Local + cloud hybrid | - | basic | basic | - | **native** |
| 24/7 autonomous loops | - | - | - | - | **yes** |
| Cross-session memory | basic | - | - | removed | **5-tier** |
| Self-improving strategy | - | - | - | - | **yes (SICA)** |
| Cost-aware budget modes | - | - | - | - | **yes** |
| Reflexion code generation | - | - | - | - | **3-attempt** |
| Parallel git worktrees | subagents | - | - | - | **experimental** |
| Stress tested + benchmarked | - | - | - | - | **[audited baseline](docs/AUDIT_2026-04-07.md)** |

### The Moat: Harness > Model

Scaffolding adds [~11 points on SWE-bench](https://arxiv.org/abs/2410.06992) — harness engineering matters as much as the model. ForgeGod is the harness:

- **Ralph Loop** — 24/7 coding from a PRD. Progress lives in git, not LLM context. Fresh agent per story. No context rot.
- **5-Tier Memory** — Episodic (what happened) + Semantic (what I know) + Procedural (how I do things) + Graph (how things connect) + Error-Solutions (what fixes what). Memories decay, consolidate, and reinforce automatically.
- **Reflexion Coder** — 3-attempt code gen with escalating models: local (free) → cloud (cheap) → frontier (when it matters). The repo now wires workspace scoping, command auditing, blocked paths, and generated-code warnings into runtime, while the audit tracks the remaining hardening gaps.
- **DESIGN.md Native** — Import a design preset, drop `DESIGN.md` in repo root, and frontend tasks inherit that design language automatically.
- **Natural-Language CLI** — ForgeGod now explains what it is doing in plain language while it works, and the CLI surfaces share the same branded cyan/white/yellow UX instead of raw transport noise.
- **Contribution Mode** — Read `CONTRIBUTING.md`, inspect the repo, surface approachable issues, and plan or execute contribution-sized changes with repo-specific guardrails.
- **SICA** — Self-Improving Coding Agent. Modifies its own prompts, model routing, and strategy based on outcomes. Safety guardrails and audit policy keep that loop honest.
- **Budget Modes** — `normal` → `throttle` → `local-only` → `halt`. Auto-triggered by spend. Run forever on Ollama for $0.

## Getting Started (No Coding Required)

You don't need to be a developer to use ForgeGod. If you can describe what you want in plain English, ForgeGod writes the code.

### Option A: Free Local Mode ($0)

1. Install Ollama: https://ollama.com/download
2. Pull a model: `ollama pull qwen3.5:9b`
3. Install ForgeGod: `pip install forgegod`
4. Run: `forgegod init` (interactive wizard guides you)
5. Try it: `forgegod run "Create a simple website with a contact form"`

### Option B: OpenAI Native Subscription Mode

1. Install ForgeGod: `pip install forgegod`
2. Run: `forgegod auth login openai-codex`
3. Run: `forgegod auth sync`
4. Try it: `forgegod plan "Build a REST API with user authentication"`

ForgeGod stays the entrypoint. It delegates the one-time login to the official Codex auth flow, then keeps day-to-day usage inside ForgeGod CLI.

### Option C: Z.AI Coding Plan Mode

1. Export `ZAI_CODING_API_KEY=...`
2. Install ForgeGod: `pip install forgegod`
3. Run: `forgegod auth sync`
4. Try it: `forgegod run "Build a REST API with user authentication"`

### Recommended Experimental Harness: GLM-5.1 + Codex

For the strongest current subscription-backed setup inside ForgeGod, use:

- `planner = zai:glm-5.1`
- `researcher = zai:glm-5.1`
- `coder = zai:glm-5.1`
- `reviewer = openai-codex:gpt-5.4`
- `sentinel = openai-codex:gpt-5.4`
- `escalation = openai-codex:gpt-5.4`

See [docs/GLM_CODEX_HARNESS_2026-04-08.md](docs/GLM_CODEX_HARNESS_2026-04-08.md),
[docs/examples/glm_codex_coding_plan.toml](docs/examples/glm_codex_coding_plan.toml),
and run `python scripts/smoke_glm_codex_harness.py` before high-stakes use.

This harness is research-backed and works in ForgeGod today. The `ZAI_CODING_API_KEY`
path should still be treated as experimental and at-your-own-risk until Z.AI
explicitly recognizes ForgeGod as a supported coding tool.

### Something not working?

Run `forgegod doctor` — it checks your setup and tells you exactly what to fix.

If you want the real `strict` sandbox, read
[docs/STRICT_SANDBOX_SETUP.md](docs/STRICT_SANDBOX_SETUP.md).
It explains Docker Desktop, the required sandbox image, and the safe fix path
in non-technical terms.

## Quickstart

```bash
# Install
pip install forgegod

# Initialize a project
forgegod init

# Check native auth surfaces
forgegod auth status

# Link ChatGPT-backed OpenAI Codex subscription, then sync config defaults
forgegod auth login openai-codex
forgegod auth sync

# Single task
forgegod run "Add a /health endpoint to server.py with uptime and version info"

# Plan a project → generates PRD
forgegod plan "Build a REST API for a todo app with auth, CRUD, and tests"

# 24/7 autonomous loop from PRD
# Loop defaults: no auto-commit or auto-push unless you explicitly enable those flags
# Parallel workers require a git repo with at least one commit because ForgeGod uses isolated worktrees
forgegod loop --prd .forgegod/prd.json

# Caveman mode — 50-75% token savings with ultra-terse prompts
forgegod run --terse "Add a /health endpoint"

# Check what it learned
forgegod memory

# View cost breakdown
forgegod cost

# Benchmark your models
forgegod benchmark

# Install a DESIGN.md preset for frontend work
forgegod design pull claude

# Plan a contribution against another repo
forgegod contribute https://github.com/owner/repo --goal "Improve tests"

# Health check
forgegod doctor
```

### Zero-Config Start

ForgeGod auto-detects your environment on first run:

1. Finds API keys in env vars (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `OPENROUTER_API_KEY`, `GOOGLE_API_KEY` / `GEMINI_API_KEY`, `DEEPSEEK_API_KEY`, `MOONSHOT_API_KEY`, `ZAI_CODING_API_KEY`, `ZAI_API_KEY`) and detects native OpenAI Codex login state
2. Checks if Ollama is running locally
3. Detects your project language, test framework, and linter
4. Picks auth-aware model defaults for each role based on what's available
5. Creates `.forgegod/config.toml` with sensible defaults

No manual setup required. Just run `forgegod init` and go.

If you add a new provider later, run `forgegod auth sync` to rewrite model defaults from detected auth surfaces.

## How the Ralph Loop Works

```
┌─────────────────────────────────────────────────┐
│                  RALPH LOOP                      │
│                                                  │
│  ┌──────┐   ┌───────┐   ┌─────────┐   ┌─────┐ │
│  │ READ │──▶│ SPAWN │──▶│ EXECUTE │──▶│ VAL │ │
│  │ PRD  │   │ AGENT │   │  STORY  │   │IDATE│ │
│  └──────┘   └───────┘   └─────────┘   └──┬──┘ │
│      ▲                                    │     │
│      │         ┌────────┐    ┌────────┐   │     │
│      └─────────│ROTATE  │◀───│COMMIT  │◀──┘     │
│                │CONTEXT │    │OR RETRY│   pass   │
│                └────────┘    └────────┘          │
│                                                  │
│  Progress is in GIT, not LLM context.           │
│  Fresh agent per story. No context rot.          │
│  Create .forgegod/KILLSWITCH to stop.           │
└─────────────────────────────────────────────────┘
```

1. **Read PRD** — Pick highest-priority TODO story
2. **Spawn agent** — Fresh context (progress is in git, not memory)
3. **Execute** — Agent uses 23 tools to implement the story
4. **Validate** — Tests, lint, syntax, frontier review
5. **Finalize or retry** — Pass: review diff + mark done. Fail: retry up to 3x with model escalation
6. **Rotate** — Next story. Context is always fresh.

## 5-Tier Memory System

ForgeGod has the most advanced memory system of any open-source coding agent:

| Tier | What | How | Retention |
|:-----|:-----|:----|:----------|
| **Episodic** | What happened per task | Full outcome records | 90 days |
| **Semantic** | Extracted principles | Confidence + decay + reinforcement | Indefinite |
| **Procedural** | Code patterns & fix recipes | Success rate tracking | Indefinite |
| **Graph** | Entity relationships + causal edges | Auto-extracted from outcomes | Indefinite |
| **Error-Solution** | Error pattern → fix mapping | Fuzzy match lookup | Indefinite |

Memories **decay** with category-specific half-life (14d debugging → 90d architecture), **consolidate** via O(n*k) category-bucketed comparison, and are **recalled** via FTS5 + Jaccard hybrid retrieval (Reciprocal Rank Fusion). SQLite WAL mode for concurrent access.

```bash
# Check memory health
forgegod memory

# Memory is stored in .forgegod/memory.db (SQLite)
# Global learnings in ~/.forgegod/memory.db (cross-project)
```

## Budget Modes

| Mode | Behavior | Trigger |
|:-----|:---------|:--------|
| `normal` | Use all configured models | Default |
| `throttle` | Prefer local, cloud for review only | 80% of daily limit |
| `local-only` | Ollama only, **$0 operation** | Manual or 95% limit |
| `halt` | Stop all LLM calls | 100% of daily limit |

```bash
# Check spend
forgegod cost

# Override mode
export FORGEGOD_BUDGET_MODE=local-only
```

## Caveman Mode (`--terse`)

Ultra-terse prompts that reduce token usage 50-75% with no accuracy loss for coding tasks. Backed by 2026 research:

- [Mini-SWE-Agent](https://github.com/SWE-agent/mini-swe-agent) — 100 lines, >74% SWE-bench Verified
- [Chain of Draft](https://arxiv.org/abs/2502.18600) — 7.6% tokens, same accuracy
- [CCoT](https://arxiv.org/abs/2401.05618) — 48.7% shorter, negligible impact

```bash
# Add --terse to any command
forgegod run --terse "Build a REST API"
forgegod loop --terse --prd .forgegod/prd.json
forgegod plan --terse "Refactor auth module"

# Or enable globally in config
# .forgegod/config.toml
# [terse]
# enabled = true
```

Caveman mode compresses system prompts (~200 → ~80 tokens), tool descriptions (3-8 words each), and tool output (tracebacks → last frame only). JSON schemas for planner/reviewer stay byte-identical.

## Configuration

ForgeGod uses TOML config with 3-level priority: env vars > project > global.

Fresh `forgegod init` and `forgegod auth sync` write auth-aware defaults. The example below shows the file shape, not the only valid mapping.

```toml
# .forgegod/config.toml

[models]
planner = "openai:gpt-4o-mini"        # Cheap planning
coder = "ollama:qwen3-coder-next"     # Free local coding
reviewer = "openai:o4-mini"           # Quality gate
sentinel = "openai:gpt-4o"            # Frontier sampling
escalation = "openai:gpt-4o"          # Fallback for hard problems

[budget]
daily_limit_usd = 5.00
mode = "normal"

[loop]
max_iterations = 100
parallel_workers = 2
gutter_detection = true

[ollama]
host = "http://localhost:11434"
model = "qwen3-coder-next"

[terse]
enabled = false              # --terse flag or set true here

[security]
sandbox_mode = "standard"    # permissive | standard | strict
sandbox_backend = "auto"     # auto | docker
sandbox_image = "mcr.microsoft.com/devcontainers/python:1-3.13-bookworm"
redact_secrets = true
audit_commands = true
```

### Environment Variables

```bash
export OPENAI_API_KEY="sk-..."
forgegod auth login openai-codex           # Native ChatGPT-backed OpenAI auth
export ANTHROPIC_API_KEY="sk-ant-..."     # Optional
export OPENROUTER_API_KEY="sk-or-..."     # Optional
export GOOGLE_API_KEY="AIza..."           # Optional (Gemini)
export DEEPSEEK_API_KEY="sk-..."          # Optional
export MOONSHOT_API_KEY="sk-..."          # Optional (Kimi / Moonshot)
export ZAI_CODING_API_KEY="..."           # Optional (Z.AI Coding Plan)
export ZAI_API_KEY="..."                  # Optional (Z.AI general API)
export FORGEGOD_BUDGET_DAILY_LIMIT_USD=10
```

## Supported Models

| Provider | Models | Cost | Setup |
|:---------|:-------|:-----|:------|
| **Ollama** | qwen3-coder-next, devstral, any | **$0** | `ollama serve` |
| OpenAI API | gpt-4o, gpt-4o-mini, o3, o4-mini | $$ | `OPENAI_API_KEY` |
| OpenAI Codex subscription | gpt-5.4 via Codex auth surface | Included in supported ChatGPT plans | `forgegod auth login openai-codex` |
| Anthropic | claude-sonnet-4-6, claude-opus-4-6 | $$$ | `ANTHROPIC_API_KEY` |
| Google Gemini | gemini-2.5-pro, gemini-3-flash | $$ | `GOOGLE_API_KEY` |
| DeepSeek | deepseek-chat, deepseek-reasoner | $ | `DEEPSEEK_API_KEY` |
| Kimi (Moonshot direct) | kimi-k2.5, kimi-k2-thinking | $$ | `MOONSHOT_API_KEY` |
| Z.AI / GLM | glm-5.1, glm-5, glm-4.7 | $$ | `ZAI_CODING_API_KEY` or `ZAI_API_KEY` |
| OpenRouter | 200+ models | varies | `OPENROUTER_API_KEY` |

Kimi support uses Moonshot's official OpenAI-compatible API and is currently experimental in ForgeGod. Benchmark it on your workload before making it a default role.
OpenAI Codex subscription support is strongest today for planner/reviewer/adversary flows. It also works as a ForgeGod route surface for coding, but coder-loop use remains experimental and should be benchmarked before you make it the default remote coder.
OpenRouter still uses keys/credits. Alibaba/Qwen Coding Plan is still under evaluation because current official docs scope it to supported coding tools rather than generic autonomous loops.

## Model Leaderboard

Run your own: `forgegod benchmark`

| Model | Composite | Correctness | Quality | Speed | Cost | Self-Repair |
|:------|:---------:|:-----------:|:-------:|:-----:|:----:|:-----------:|
| openai:gpt-4o-mini | 81.5 | 10/12 | 7.4 | 12s avg | $0.08 | 4/4 |
| ollama:qwen3.5:9b | 72.3 | 8/12 | 6.8 | 45s avg | $0.00 | 3/4 |

*Run `forgegod benchmark --update-readme` to refresh with your own results.*

## Architecture

```
forgegod/
├── cli.py          # Typer CLI (init, run, loop, plan, review, cost, memory, status, benchmark, doctor)
├── config.py       # TOML config + env vars + 3-level priority
├── router.py       # Multi-provider LLM router + persistent pool + cascade routing + half-open circuit breaker
├── agent.py        # Core agent loop (tools + context compression + sub-agents)
├── coder.py        # Reflexion code generation (3 attempts, model escalation, GOAP)
├── loop.py         # Ralph loop (24/7 autonomous coding, parallel workers, story timeout)
├── planner.py      # Task decomposition → PRD
├── reviewer.py     # Frontier model quality gate (sample-based)
├── sica.py         # Self-improving strategy modification (guardrails + audit policy)
├── memory.py       # 5-tier cognitive memory (FTS5 + RRF hybrid retrieval, WAL mode)
├── budget.py       # SQLite cost + token tracking, forecasting, auto budget modes
├── worktree.py     # Parallel git worktree workers
├── tui.py          # Rich terminal dashboard
├── terse.py        # Caveman mode — terse prompts, tool compression, savings tracker
���── benchmark.py    # Model benchmarking engine (12 tasks, 4 tiers, composite scoring)
├── onboarding.py   # Interactive setup wizard for new users
├── doctor.py       # Installation health check (6 diagnostic checks)
├── i18n.py         # Translation strings (English + Spanish es-419)
├── models.py       # Pydantic v2 data models
└── tools/
    ├── filesystem.py  # async read/write (aiofiles), atomic writes, fuzzy edit, glob, grep, repo_map
    ├── shell.py       # bash (isolated runtime env + strict command policy + secret redaction)
    ├── git.py         # git status, diff, commit, worktrees
    ├── mcp.py         # MCP server client (5,800+ servers)
    └── skills.py      # On-demand skill loading
```

## Security

Defense-in-depth, not security theater:

- **Real strict sandbox** — `strict` runs inside Docker with no network, read-only rootfs, dropped caps, and workspace-only mounts
- **Standard shell policy** — `standard` keeps the local guardrails: isolated runtime dirs, blocked shell operators, and workspace scoping
- **Secret redaction** — 11 patterns strip API keys from tool output before LLM context
- **Prompt injection detection** — 8 patterns scan for jailbreak/role-override attempts
- **AST code validation** — Detects obfuscated dangerous calls (`getattr(os, 'system')`) that regex misses, and blocks suspicious writes in `strict` mode
- **Workspace-scoped file ops** — file and shell tools reject paths that escape the active workspace root
- **Supply chain defense** — Flags known-abandoned/typosquat packages (python-jose, jeIlyfish, etc.)
- **Canary token system** — Detects if system prompt leaks into tool arguments, with per-session rotation
- **Budget limits** — Cost controls with token tracking + burn-rate forecasting
- **Killswitch** — Create `.forgegod/KILLSWITCH` to immediately halt autonomous loops
- **Sensitive file protection** — `.env`, credentials files get warnings + automatic redaction

> **Warning**: ForgeGod executes shell commands and modifies files. As of the verified 2026-04-08 baseline, `strict` uses a real Docker sandbox backend and blocks if Docker/image prerequisites are missing, while `standard` remains a host-local guarded workflow. Use `forgegod doctor` and [docs/STRICT_SANDBOX_SETUP.md](docs/STRICT_SANDBOX_SETUP.md) instead of weakening the sandbox just to get past setup friction.

## Operational Docs

- [AGENTS.md](AGENTS.md) — repo-local instructions for coding agents
- [docs/OPERATIONS.md](docs/OPERATIONS.md) — current system of record and verified commands
- [docs/AUDIT_2026-04-07.md](docs/AUDIT_2026-04-07.md) — detailed code audit and remediation order
- [docs/WEB_RESEARCH_2026-04-07.md](docs/WEB_RESEARCH_2026-04-07.md) — external guidance used to shape the repo docs

See [SECURITY.md](SECURITY.md) for the full policy and vulnerability reporting.

## Contributing

We welcome contributions. See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

- Bug reports and feature requests: [GitHub Issues](https://github.com/waitdeadai/forgegod/issues)
- Questions and discussion: [GitHub Discussions](https://github.com/waitdeadai/forgegod/discussions)

## Contributors

ForgeGod credits code and non-code work in public.

- [Matias Mesa](https://www.linkedin.com/in/matt-mesa/) - `design` - official ForgeGod mascot system
- [WAITDEAD](https://waitdead.com) - `code`, `infra`, `research`, `projectManagement`, `maintenance`

See [CONTRIBUTORS.md](CONTRIBUTORS.md) for the current contributor list.

## License

Apache 2.0 — see [LICENSE](LICENSE).

---

<p align="center">
  Built by <a href="https://waitdead.com">WAITDEAD</a> &bull; Official mascot design by <a href="https://www.linkedin.com/in/matt-mesa/">Matias Mesa</a> &bull; Powered by techniques from OpenClaw, Hermes, and SOTA 2026 coding agent research.
</p>
