# ForgeGod CLAUDE.md

> SOTA 2026 configuration for ForgeGod coding-agent development.
> Last updated: 2026-04-12

## Model

**Default: MiniMax 2.7 High Speed** (`minimax:2.7-highspeed`)

This is the operational default for all coding roles. ForgeGod stays provider-agnostic;
the default is a working convention, not a hard architectural constraint.

## Import Repository Contract

@AGENTS.md

This file (`.claude/CLAUDE.md`) provides Claude-Code-specific configuration and
overrides. The repo operating contract lives in `AGENTS.md`, which is imported
above and loaded at every session start.

## ForgeGod-Specific Rules

### Project Type
- **ForgeGod** is a Python coding-harness tool (not TypeScript)
- Package: `forgegod 0.1.0`, Python 3.13+
- 23 registered tools, 10 provider families
- Primary eval surface: `forgegod evals`

### Provider Matrix
```
ollama, openai, openai-codex, anthropic,
openrouter, gemini, deepseek, kimi, zai, minimax
```
Default: `minimax:2.7-highspeed`
Fallback: `openai-codex + zai:glm-5.1`

### Standard Commands
```bash
python -m pytest -m "not stress" -q          # core suite
python -m pytest tests/stress -x -vv            # stress suite
python -m ruff check forgegod tests scripts    # lint
python -m build                                 # build
python -m forgegod --version                   # CLI check
forgegod evals                                  # harness evals
forgegod permissions                            # inspect permission mode
forgegod auth status                            # check provider auth
```

### Verification-First Rule
Every implementation task MUST show verification evidence before declaring done:
- Run tests: `python -m pytest tests/...`
- Run lint: `python -m ruff check forgegod tests`
- For file edits: show `git diff` of the change
- For bug fixes: show a failing test first, then the fix

Do NOT rely on model self-assessment. Use external signals (tests, linters,
`git diff`, or explicit expected output).

### Architecture Audit Rule
Before changing loop, worktree, filesystem, or security behavior:
1. Read the relevant subsystem end-to-end
2. Do deep current-year research (primary/official sources)
3. Log links + verification date in repo docs
This applies to: architecture, dependencies, security, benchmarks, model strategy

### Context Management
- Run `/clear` between unrelated tasks
- Use subagents for investigation to keep main session clean
- Compact aggressively: Claude's context degrades as it fills
- For long sessions: `/compact` with specific focus instruction

### Permission Modes
ForgeGod exposes permission modes as first-class CLI flags:
```
--permission-mode read-only | workspace-write | danger-full-access
--approval-mode deny | prompt | approve
```
Inspect current state: `forgegod permissions`

### Memory
Update memory files after every session:
- `.claude/memory/feedback.md`: lessons learned
- `.claude/memory/project.md`: active context
Do NOT trust memory across machines — auto memory is machine-local.

## SOTA 2026 Patterns (from Claude Code best practices)

1. **Verify-first**: always include test/lint evidence before declaring done
2. **Explore → Plan → Implement**: separate research from execution for uncertain changes
3. **Subagent pattern**: delegate research or parallel work to subagents
4. **Context management**: `/clear` between tasks, compact aggressively
5. **Skills + hooks**: `.claude/rules/` for path-specific rules; `.claude/hooks.json` for deterministic enforcement
6. **CLAUDE.md + AGENTS.md**: CLAUDE.md imports AGENTS.md so both tools read the same repo contract

## Settings Reference

See `.claude/settings.json` for the full Claude Code configuration.

Key overrides in this project:
- `effortLevel: high`
- `alwaysThinkingEnabled: true`
- `showThinkingSummaries: true`
- Sandbox: disabled (use `forgegod loop --sandbox-mode strict` for Docker-backed isolation)

## What NOT to do

- Do NOT patch blind — audit first, then change
- Do NOT trust model self-assessment as the only verification signal
- Do NOT describe a change as SOTA without primary sources + local proof
- Do NOT add features outside the harness — improve the harness until ForgeGod can do it itself
- Do NOT commit without running: `python -m ruff check forgegod tests scripts`
