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

## 100% Context Preservation Rule

**Every task MUST maintain 100% of context from start to finish.** This project runs on the principle that context fragmentation destroys efficiency. To preserve context:

1. **Always spawn a subagent for planning** (`Plan` subagent type) — never plan inline within the main session. A separate subagent with a clean context window builds the plan, then the main agent executes it without cognitive load.

2. **Always spawn a subagent for complex execution** — for uncertain, multi-step, or high-risk changes, delegate the research/investigation work to a subagent and let it report a clean summary back. Do not pollute the main context with debugging loops.

3. **For long workstreams**: spawn one subagent to research + plan (`Plan` type), another subagent to implement (`general-purpose` type), and let each subagent exhaust its task and return a full report. The main session remains clean and authoritative.

4. **Rule of thumb**: if the task is more than 3 tool calls or involves reading more than 2 files, consider spawning a subagent instead of doing it inline.

5. **Subagent memory discipline**: give subagents a precise, self-contained brief. Include: what to investigate, what format to report back in (bullet points preferred, not raw file dumps), and what constraints to respect. Subagents that receive vague prompts produce vague results.

6. **Verification via subagent**: when you need to verify behavior across the full codebase, spawn a focused subagent to audit, test, and report — do not do it inline where the main context will grow stale.

The main session is for orchestration, review, and committing. Never let it get bloated with investigation noise that a subagent could handle better.

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
- Do NOT do multi-step investigation inline — always use a subagent to preserve main session clarity
