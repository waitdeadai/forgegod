# ForgeGod

**Multi-model autonomous coding engine. Local + Cloud. 24/7.**

ForgeGod orchestrates OpenAI models + local LLMs (Qwen via Ollama) for continuous autonomous coding. It combines multi-model routing, Reflexion code generation, 24/7 autonomous loops, cost-aware budgets, and self-improving strategies into a single CLI.

## Features

- **Multi-model auto-routing** — Cloud (OpenAI, Anthropic, OpenRouter) + Local (Ollama/Qwen) with circuit breaker and fallback chains
- **Ralph Loop** — 24/7 autonomous coding from a PRD. Progress in git, not LLM context. Fresh agent per story.
- **Reflexion Coder** — 3-attempt code generation with escalating models and AST validation
- **SICA** — Self-Improving Coding Agent: modifies its own strategy based on outcomes (6 safety layers)
- **Cost-aware budgets** — normal/throttle/local-only/halt modes, auto-triggered by spend
- **Parallel worktrees** — Multiple stories at once via git worktrees
- **Cross-session memory** — Principles + causal graph learned from outcomes
- **MCP support** — Connect to 5,800+ Model Context Protocol servers
- **16 built-in tools** — File ops, shell, git, grep, glob, MCP

## Install

```bash
pip install forgegod
```

Or from source:

```bash
git clone https://github.com/waitdead/forgegod.git
cd forgegod
pip install -e ".[dev]"
```

## Quickstart

```bash
# Initialize project
forgegod init

# Single-shot task
forgegod run "Add a /health endpoint to server.py with uptime and version info"

# Plan a project (generates PRD)
forgegod plan "Build a REST API for a todo app with auth, CRUD, and tests"

# 24/7 autonomous loop from PRD
forgegod loop --prd .forgegod/prd.json

# Check cost
forgegod cost

# View status
forgegod status
```

## Configuration

ForgeGod uses TOML config files with 3-level priority:

1. Environment variables (`FORGEGOD_*`)
2. Project config (`.forgegod/config.toml`)
3. Global config (`~/.forgegod/config.toml`)

```toml
[models]
planner = "openai:gpt-4o-mini"
coder = "ollama:qwen3-coder-next"
reviewer = "openai:o4-mini"
sentinel = "openai:gpt-4o"
escalation = "openai:gpt-4o"

[budget]
daily_limit_usd = 5.00
mode = "normal"  # normal | throttle | local-only | halt

[loop]
max_iterations = 100
context_rotation_pct = 80
gutter_detection = true
parallel_workers = 2

[ollama]
host = "http://localhost:11434"
model = "qwen3-coder-next"
```

### Environment Variables

```bash
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."     # Optional
export OPENROUTER_API_KEY="sk-or-..."     # Optional
export FORGEGOD_BUDGET_DAILY_LIMIT_USD=10
export FORGEGOD_BUDGET_MODE=throttle
```

## Architecture

```
forgegod/
├── cli.py          # Typer CLI (init, run, loop, plan, review, cost, status)
├── config.py       # TOML config + env vars
├── router.py       # Multi-provider LLM router + circuit breaker
├── agent.py        # Core agent loop (tools + context compression)
├── coder.py        # Reflexion code generation (3 attempts, model escalation)
├── loop.py         # Ralph loop (24/7 autonomous coding)
├── planner.py      # Task decomposition → PRD
├── reviewer.py     # Frontier model quality gate
├── sica.py         # Self-improving strategy modification
├── memory.py       # Cross-session learning (principles, causal graph)
├── budget.py       # SQLite cost tracking + budget modes
├── worktree.py     # Parallel git worktree workers
├── tui.py          # Rich terminal dashboard
├── models.py       # Pydantic v2 data models
└── tools/
    ├── filesystem.py  # read, write, edit (fuzzy match), glob, grep, repo_map
    ├── shell.py       # bash (command denylist + secret redaction)
    ├── git.py         # git status, diff, commit, worktrees
    ├── mcp.py         # MCP server client
    └── skills.py      # on-demand skill loading (OpenClaw pattern)
```

## How the Ralph Loop Works

1. **Read PRD** — Pick highest priority TODO story
2. **Spawn agent** — Fresh context per story (progress is in git, not LLM memory)
3. **Execute** — Agent uses tools to implement the story
4. **Validate** — Check tests, lint, syntax
5. **Commit or retry** — If pass: commit + mark done. If fail: retry (up to 3x)
6. **Rotate** — Move to next story. Context is always fresh.
7. **Killswitch** — Create `.forgegod/KILLSWITCH` file to stop

## Budget Modes

| Mode | Behavior | Trigger |
|------|----------|---------|
| `normal` | Use all configured models | Default |
| `throttle` | Prefer local, cloud for review only | 80% of daily limit |
| `local-only` | Ollama only, $0 operation | Manual |
| `halt` | Stop all LLM calls | 100% of daily limit |

## Security

ForgeGod implements defense-in-depth security:

- **Command denylist** — Destructive shell commands (`rm -rf /`, `curl | sh`, `sudo`) are blocked
- **Secret redaction** — API keys and tokens are stripped from tool output before entering LLM context
- **Prompt injection detection** — Project rules files are scanned for injection patterns
- **Budget limits** — Cost controls prevent runaway API spend
- **Killswitch** — Create `.forgegod/KILLSWITCH` to immediately halt autonomous loops

> **Warning**: ForgeGod executes shell commands and modifies files on your system. Review all changes before committing. The autonomous loop mode (`forgegod loop`) can make many changes without human review — start with `--max 5` to verify behavior.

> **Warning**: ForgeGod sends code and file contents to third-party LLM APIs (OpenAI, Anthropic, etc.). Do not use on repositories containing secrets, credentials, or proprietary code without appropriate safeguards.

See [SECURITY.md](SECURITY.md) for the full security policy and vulnerability reporting.

```toml
# .forgegod/config.toml — security section
[security]
sandbox_mode = "standard"  # permissive | standard | strict
redact_secrets = true
audit_commands = true
```

## Supported Models

| Provider | Models | Setup |
|----------|--------|-------|
| OpenAI | gpt-4o, gpt-4o-mini, o3, o4-mini | `OPENAI_API_KEY` |
| Ollama | qwen3-coder-next, devstral, any | `ollama serve` |
| Anthropic | claude-sonnet-4-6, claude-opus-4-6 | `ANTHROPIC_API_KEY` |
| OpenRouter | Any model | `OPENROUTER_API_KEY` |

## License

Apache 2.0 — see [LICENSE](LICENSE).

---

Built by [WAITDEAD](https://waitdead.com). Powered by the techniques from OpenClaw, Hermes, and SOTA 2026 coding agent research.
