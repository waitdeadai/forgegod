<p align="center">
  <a href="README.md"><img src="https://img.shields.io/badge/lang-en-blue.svg" alt="English"></a>
  <a href="README.es.md"><img src="https://img.shields.io/badge/lang-es-yellow.svg" alt="Español"></a>
</p>

<p align="center">
  <img src="docs/mascot.png" alt="ForgeGod" width="120" />
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
</p>

<p align="center">
  <code>16 built-in tools</code> &bull; <code>4 LLM providers</code> &bull; <code>5-tier memory</code> &bull; <code>24/7 autonomous</code> &bull; <code>$0 local mode</code>
</p>

---

ForgeGod orchestrates multiple LLMs (OpenAI, Anthropic, Ollama, OpenRouter) into a single autonomous coding engine. It routes tasks to the right model, runs 24/7 from a PRD, learns from every outcome, and self-improves its own strategy. Run it locally for $0 with Ollama, or use cloud models when you need them.

```bash
pip install forgegod
```

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
| Parallel git worktrees | subagents | - | - | - | **yes** |

### The Moat: Harness > Model

A [22-point SWE-bench swing](https://www.cognition.ai/blog/swe-bench-devin) comes from harness engineering, not model upgrades. ForgeGod is the harness:

- **Ralph Loop** — 24/7 coding from a PRD. Progress lives in git, not LLM context. Fresh agent per story. No context rot.
- **5-Tier Memory** — Episodic (what happened) + Semantic (what I know) + Procedural (how I do things) + Graph (how things connect) + Error-Solutions (what fixes what). Memories decay, consolidate, and reinforce automatically.
- **Reflexion Coder** — 3-attempt code gen with escalating models: local (free) → cloud (cheap) → frontier (when it matters). AST validation at every step.
- **SICA** — Self-Improving Coding Agent. Modifies its own prompts, model routing, and strategy based on outcomes. 6 safety layers prevent drift.
- **Budget Modes** — `normal` → `throttle` → `local-only` → `halt`. Auto-triggered by spend. Run forever on Ollama for $0.

## Getting Started (No Coding Required)

You don't need to be a developer to use ForgeGod. If you can describe what you want in plain English, ForgeGod writes the code.

### Option A: Free Local Mode ($0)

1. Install Ollama: https://ollama.com/download
2. Pull a model: `ollama pull qwen3.5:9b`
3. Install ForgeGod: `pip install forgegod`
4. Run: `forgegod init` (interactive wizard guides you)
5. Try it: `forgegod run "Create a simple website with a contact form"`

### Option B: Cloud Mode (faster, ~$0.01/task)

1. Get an OpenAI key: https://platform.openai.com/api-keys
2. Install ForgeGod: `pip install forgegod`
3. Run: `forgegod init` → paste your key when prompted
4. Try it: `forgegod run "Build a REST API with user authentication"`

### Something not working?

Run `forgegod doctor` — it checks your setup and tells you exactly what to fix.

## Quickstart

```bash
# Install
pip install forgegod

# Initialize a project
forgegod init

# Single task
forgegod run "Add a /health endpoint to server.py with uptime and version info"

# Plan a project → generates PRD
forgegod plan "Build a REST API for a todo app with auth, CRUD, and tests"

# 24/7 autonomous loop from PRD
forgegod loop --prd .forgegod/prd.json

# Check what it learned
forgegod memory

# View cost breakdown
forgegod cost

# Benchmark your models
forgegod benchmark

# Health check
forgegod doctor
```

### Zero-Config Start

ForgeGod auto-detects your environment on first run:

1. Finds API keys in env vars (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`)
2. Checks if Ollama is running locally
3. Detects your project language, test framework, and linter
4. Picks the best model for each role based on what's available
5. Creates `.forgegod/config.toml` with sensible defaults

No manual setup required. Just run `forgegod init` and go.

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
3. **Execute** — Agent uses 16 tools to implement the story
4. **Validate** — Tests, lint, syntax, frontier review
5. **Commit or retry** — Pass: commit + mark done. Fail: retry up to 3x with model escalation
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

Memories **decay** without reinforcement (30-day half-life), **consolidate** automatically (merge similar, prune weak), and are **injected** into every prompt as a Memory Spine ranked by relevance + recency + importance.

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

## Configuration

ForgeGod uses TOML config with 3-level priority: env vars > project > global.

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

[security]
sandbox_mode = "standard"    # permissive | standard | strict
redact_secrets = true
audit_commands = true
```

### Environment Variables

```bash
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."     # Optional
export OPENROUTER_API_KEY="sk-or-..."     # Optional
export FORGEGOD_BUDGET_DAILY_LIMIT_USD=10
```

## Supported Models

| Provider | Models | Cost | Setup |
|:---------|:-------|:-----|:------|
| **Ollama** | qwen3-coder-next, devstral, any | **$0** | `ollama serve` |
| OpenAI | gpt-4o, gpt-4o-mini, o3, o4-mini | $$ | `OPENAI_API_KEY` |
| Anthropic | claude-sonnet-4-6, claude-opus-4-6 | $$$ | `ANTHROPIC_API_KEY` |
| OpenRouter | 200+ models | varies | `OPENROUTER_API_KEY` |

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
├── router.py       # Multi-provider LLM router + circuit breaker + Thompson sampling
├── agent.py        # Core agent loop (tools + context compression + sub-agents)
├── coder.py        # Reflexion code generation (3 attempts, model escalation, GOAP)
├── loop.py         # Ralph loop (24/7 autonomous coding from PRD)
├── planner.py      # Task decomposition → PRD
├── reviewer.py     # Frontier model quality gate (sample-based)
├── sica.py         # Self-improving strategy modification (6 safety layers)
├── memory.py       # 5-tier cognitive memory (episodic/semantic/procedural/graph/errors)
├── budget.py       # SQLite cost tracking + auto budget modes
├── worktree.py     # Parallel git worktree workers
├── tui.py          # Rich terminal dashboard
├── benchmark.py    # Model benchmarking engine (12 tasks, 4 tiers, composite scoring)
├── onboarding.py   # Interactive setup wizard for new users
├── doctor.py       # Installation health check (6 diagnostic checks)
├── i18n.py         # Translation strings (English + Spanish es-419)
├── models.py       # Pydantic v2 data models
└── tools/
    ├── filesystem.py  # read, write, edit (fuzzy match), glob, grep, repo_map
    ├── shell.py       # bash (command denylist + secret redaction)
    ├── git.py         # git status, diff, commit, worktrees
    ├── mcp.py         # MCP server client (5,800+ servers)
    └── skills.py      # On-demand skill loading
```

## Security

Defense-in-depth, not security theater:

- **Command denylist** — 13 dangerous patterns blocked (`rm -rf /`, `curl | sh`, `sudo`, fork bombs)
- **Secret redaction** — 11 patterns strip API keys from tool output before LLM context
- **Prompt injection detection** — Rules files scanned for injection patterns before loading
- **Budget limits** — Cost controls prevent runaway API spend
- **Killswitch** — Create `.forgegod/KILLSWITCH` to immediately halt autonomous loops
- **Sensitive file protection** — `.env`, credentials files get warnings + automatic redaction

> **Warning**: ForgeGod executes shell commands and modifies files. Review changes before committing. Start autonomous mode with `--max 5` to verify behavior.

See [SECURITY.md](SECURITY.md) for the full policy and vulnerability reporting.

## Contributing

We welcome contributions. See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

- Bug reports and feature requests: [GitHub Issues](https://github.com/waitdeadai/forgegod/issues)
- Questions and discussion: [GitHub Discussions](https://github.com/waitdeadai/forgegod/discussions)

## License

Apache 2.0 — see [LICENSE](LICENSE).

---

<p align="center">
  Built by <a href="https://waitdead.com">WAITDEAD</a> &bull; Powered by techniques from OpenClaw, Hermes, and SOTA 2026 coding agent research.
</p>
