# ForgeGod Deep Research Agent — Build Your Own Research Agent

**Goal:** Using this document as your sole context, research how to make ForgeGod the world's best open-source autonomous coding engine. Produce: (1) a model-agnostic deep research agent spec, (2) an enhanced planner system prompt, (3) a competitive analysis, (4) prioritized implementation recommendations.

**Output location:** Save as `forgegod-oss/deepresearch/RESEARCH_REPORT_2026.md`

**Research model:** Use Claude 4 Opus, Gemini 2.5 Pro, or GPT-5 for synthesis. Use MiniMax M2.7 for parallel URL lookups.

---

# PART 0: FORGEGOD ARCHITECTURE (read first — this is your entire context)

## What ForgeGod Is

ForgeGod is an **autonomous multi-model coding harness** — a Python package that reads a `prd.json` story manifest and implements features automatically by orchestrating multiple LLM agents through a coder → reviewer loop.

**Repo:** `https://github.com/waitdeadai/forgegod`
**Package:** `forgegod 0.1.0`, Python 3.13+
**Tests:** 633 passing, lint clean, build passes
**GitHub stars:** [check current at repo page]

---

## Core Loop Flow

```
PRD.json (stories with: id, title, description, status=TODO, depends_on=[], acceptance_criteria=[], files_touched=[])
  │
  ▼
RalphLoop._get_ready_stories()
  → filters: status=="TODO" AND all depends_on are "done"
  │
  ▼
For each story:
  │
  ▼
  PLANNER (MiniMax M2.7-highspeed by default)
    → reads story description + acceptance criteria
    → outputs: step-by-step plan with checkpoints
    → model configurable via [models] planner = "minimax:MiniMax-M2.7-highspeed"
    │
    ▼
  CODER (MiniMax M2.7-highspeed)
    → implements plan
    → produces draft N
    → must produce ≥2 drafts before reviewer fires
    │
    ▼
  EFFORT GATE (taste.py + effort.py)
    → checks: ≥2 drafts? verification evidence present?
    → if fail → reject back to CODER with effort feedback
    │
    ▼
  REVIEWER (Z.AI GLM-5 adversarial by default)
    → reviews code diff against acceptance criteria
    → if reject → feedback to CODER, loop again
    → if approve → story marked status="done"
```

---

## Key Files (read these before researching)

| File | Purpose |
|------|---------|
| `forgegod/loop.py` | RalphLoop — `_get_ready_stories()`, `_tick()`, story state machine |
| `forgegod/agents/planner.py` | Planner agent — decomposes story into implementation steps |
| `forgegod/agents/coder.py` | Coder agent — produces drafts of implementation |
| `forgegod/agents/reviewer.py` | Reviewer agent — adversarial quality gate |
| `forgegod/agents/taste.py` | EffortGate — enforces ≥2 drafts + verification evidence |
| `forgegod/agents/effort.py` | Effort scoring — tracks draft count, effort level |
| `forgegod/router.py` | Model routing — `_call_minimax()`, `_call_zai()`, `_call_openai()` etc. |
| `forgegod/config.py` | Config structs — `MiniMaxConfig`, `ZAIConfig`, `ForgeGodConfig` |
| `forgegod/benchmark.py` | `detect_available_models()` — finds all configured providers |
| `forgegod/doctor.py` | `forgegod doctor` — auth verification for all providers |
| `forgegod/skills/audit-agent/SKILL.md` | Audit skill — pre-story codebase audit (11-step protocol) |

---

## Provider Matrix

| Provider | Model | Default Role | Auth |
|----------|-------|-------------|------|
| minimax | M2.7-highspeed | coder, planner | `MINIMAX_API_KEY` |
| zai | glm-5 | adversarial reviewer | `ZAI_CODING_API_KEY` |
| openai | gpt-5.4-mini | fallback coder | `OPENAI_API_KEY` |
| anthropic | claude-opus-4 | high-complexity | `ANTHROPIC_API_KEY` |
| openai-codex | gpt-5.4 | optional reviewer | ChatGPT/Codex subscription |
| ollama | qwen-2.5-14b | local fallback | local |
| deepseek | deepseek-chat | cost-efficient | `DEEPSEEK_API_KEY` |
| gemini | gemini-3-flash | fast research | `GEMINI_API_KEY` |
| kimi | kimi-chat | multilingual | `KIMI_API_KEY` |
| openrouter | various | experimental | `OPENROUTER_API_KEY` |

---

## RalphLoop Story Lifecycle

```python
# States: TODO → IN_PROGRESS → DONE (or ERROR)
# Only TODO stories are picked by _get_ready_stories()
# Story must have all depends_on entries in DONE state

class Story:
    id: str
    title: str
    description: str
    status: str  # "todo" | "in_progress" | "done"
    priority: int
    depends_on: list[str]  # story IDs
    acceptance_criteria: list[str]
    files_touched: list[str]
    iterations: int
    max_iterations: int
    error_log: list[str]
    completed_at: str
```

---

## EffortGate (taste.py + effort.py)

```python
# EffortGate requires:
# 1. ≥2 drafts produced by CODER
# 2. Verification evidence (test output, lint output, or diff)
# 3. If max_effort mode: always_verify enabled, suggestions considered

# effort.py scoring:
# draft_count → base effort
# has_verification → +effort
# reviewer_rejections → tracking
```

---

## Audit-Agent (pre-story)

```
Trigger: before first story OR when >20 commits since last audit
Output: .forgegod/AUDIT.md
Protocol: 11-step codebase audit
Purpose: surface blockers, dead code, architectural drift
```

---

## Config Files

**Project-level:** `showcase/*/.forgegod/config.toml`
```toml
[models]
planner = "minimax:MiniMax-M2.7-highspeed"
coder = "minimax:MiniMax-M2.7-highspeed"
reviewer = "zai:glm-5"

[minimax]
base_url = "https://api.minimaxi.com/v1"
timeout = 120.0

[zai]
timeout = 120.0
base_url = "https://api.z.ai/api/coding/paas/v4"
```

---

# PART 1: YOUR RESEARCH MISSION

## What You Are Building

A **ForgeGod Deep Research Agent** — a model-agnostic agent that:
1. Operates inside ForgeGod (pre-story research) OR standalone (human-initiated)
2. Produces citable, verifiable intelligence from primary sources
3. Feeds research output directly into ForgeGod's planner to produce better plans
4. Works with ANY model that supports function calling

## The Core Problem

ForgeGod's **PLANNER** is the bottleneck. If the planner produces a weak plan, the coder produces weak code. Current planner weaknesses:
- No dynamic story sizing / effort estimation
- No access to live competitive intelligence
- No learning from past story outcomes
- No research phase before planning
- Static provider selection (doesn't match story complexity to model capability)

## Your Deliverables

You must produce ALL of the following:

1. **FINDING-[N] list** (20+ findings from primary research)
2. **Competitive analysis table** (ForgeGod vs SWE-agent vs Aider vs Claude-Dev vs Devin)
3. **Top 5 recommendations** (ranked by Impact × Feasibility)
4. **Deep Research Agent System Prompt** (drop-in, model-agnostic)
5. **Integration spec** (exact files to add/modify in ForgeGod)
6. **Source registry** (20+ sources with verification dates)

---

# PART 2: RESEARCH PROTOCOL

## The 5 Research Areas

### Area A: Planning & Task Decomposition
- SWE-agent task decomposition architecture
- Devin planning architecture
- Claude Code task planning
- MetaGPT / ChatDev multi-agent planning
- Hierarchical task networks (HTN) for LLMs

### Area B: Self-Correction & Reflection
- Reflexion (arXiv) — verbal reinforcement reflection
- Self-Refine — iterative self-improvement
- CRITIC — LLM self-verification
- DEFT — coding agent self-testing
- Self-debug patterns for coding agents

### Area C: Quality Gates & Verification-First
- Test-driven development with LLMs
- LLM-as-Judge patterns
- Adversarial reviewer architectures
- EffortGate-like mechanisms in other harnesses
- SWE-bench high-scoring agent patterns

### Area D: Benchmarks & Measurement
- SWE-bench leaderboard 2026 (what scores highest and why)
- BFCL (Berkeley Function Calling Leaderboard)
- LiveCodeBench v4
- How to build local harness evals without external API calls
- Per-story metrics (time, cost, revision count)

### Area E: Competitive Landscape
- Top 10 open-source coding agents 2026 (GitHub stars + features)
- SWE-agent architecture
- Aider benchmarks + architecture
- Claude-Dev patterns
- claw-code (ForgeGod origin baseline)
- Emerging models: Gemini 3, GPT-5, Claude 4, MiniMax M2.7

## Source Standards

### VALID (use these)
- GitHub repos ≥100 stars, last commit ≤6 months ago
- arXiv papers from 2024-2026
- Official documentation (Anthropic, OpenAI, MiniMax, Z.AI)
- Primary benchmark pages with methodology
- Academic conference papers (NeurIPS, ICML, ICLR, ASE, ICSE)

### INVALID (reject these)
- Blog posts without primary sources
- Vendor marketing pages
- Tutorial sites (Medium, Towards Data Science, etc.)
- Twitter/X posts
- Unverified GitHub gists

### Verification Rule
For every source: fetch the URL, confirm content matches claim, record date fetched. Dead URL = invalid source, find another.

---

# PART 3: OUTPUT SPECIFICATIONS

## OUTPUT 1: FINDING-[N] List (minimum 20 findings)

```
FINDING-[N]: [Descriptive Title]
Source: [URL]
Verified: [YYYY-MM-DD]
Category: [planning | self-correction | quality | benchmark | competitive | model]
Mechanism: [How the technique works — 2-3 sentences]
ForgeGod gap: [Does ForgeGod use this? If not: what file/function needs changing]
Evidence strength: [high | medium | low]
Effort to add: [low | medium | high]
```

## OUTPUT 2: Competitive Analysis Table

Markdown table comparing at minimum:
- ForgeGod
- SWE-agent (princeton-nlp/SWE-agent)
- Aider (aider-ai/aider)
- Claude-Dev
- Devin (openai/devin)
- claw-code (ultraworkers/claw-code)

On these features (10+):
Multi-model harness | Adversarial reviewer | EffortGate | audit-agent | Continuous benchmark | Test-first support | Story sizing | Cost awareness | Self-correction | Provider diversity | CLI tool | Open source

## OUTPUT 3: Top 5 Recommendations

Ranked by Impact × Feasibility × Confidence.

```
RECOMMENDATION-[N]: [Title]
Top finding: [FINDING-N]
Change: [Specific — file + function + what to add/change]
Test: [Specific command or test to verify it works]
Risk: [What could break]
```

## OUTPUT 4: Deep Research Agent System Prompt

A complete, drop-in system prompt for a model-agnostic research agent.

Must include:
- Mission statement
- Research protocol (5-dimension search)
- Source standards (valid/invalid with examples)
- Output format (FINDING-[N] + all 6 outputs)
- Quality gates (how to verify sources, handle contradictions)
- Special directives for ForgeGod integration
- Karpathy Simplicity reminders

The prompt must be model-agnostic (no model-specific features).

## OUTPUT 5: Integration Spec

For each integration option, specify exact files to add or modify:

```
Option A: Pre-story research (inside RalphLoop)
  File to modify: forgegod/agents/planner.py
  Change: add research_agent.research(story) call
  Trigger: stories with complexity > threshold

Option B: CLI command
  File to add: forgegod/agents/researcher.py
  Command: forgegod research "[query]"
  Output: markdown report + sources

Option C: audit-agent hybrid
  File to modify: forgegod/skills/audit-agent/SKILL.md
  Change: add research phase to audit protocol

Skill to add: .forgegod/skills/deep-research/SKILL.md
```

## OUTPUT 6: Source Registry

```
| # | Source | URL | Type | Verified | Key Finding |
|---|--------|-----|------|----------|-------------|
| 1 | SWE-agent | github.com/... | github | YYYY-MM-DD | ... |
[20+ rows]
```

---

# PART 4: FINAL REPORT STRUCTURE

Save your complete output as:

`forgegod-oss/deepresearch/RESEARCH_REPORT_2026.md`

```
# ForgeGod Deep Research Report — 2026

Generated: YYYY-MM-DD
Research model: [what you used]
Total sources: [N]
Quality: [X] URLs verified live

## Executive Summary
[3-5 bullets: most important findings]

## FINDINGS (20+)
[All FINDING-[N] entries grouped by category]

## COMPETITIVE ANALYSIS
[Full comparison table with ForgeGod advantages/gaps marked]

## TOP 5 RECOMMENDATIONS
[Ranked by Impact × Feasibility]

## ENHANCED PLANNER SYSTEM PROMPT
[Full drop-in prompt — paste directly into planner.py]

## DEEP RESEARCH AGENT SYSTEM PROMPT
[Full model-agnostic research agent prompt]

## INTEGRATION SPEC
[Exact file changes for all 3 integration options]

## SOURCE REGISTRY
[Full table of all sources]

## APPENDIX: Research Notes
[Contradictions found, areas needing more research, open questions]
```

---

# PART 5: QUALITY CHECKLIST

Before finishing, confirm all of:

- [ ] Read all 5 key ForgeGod files (planner.py, loop.py, taste.py, effort.py, config.py)
- [ ] 20+ sources found across all 5 research areas
- [ ] Every source URL fetched and confirmed live
- [ ] All 6 outputs produced in full
- [ ] FINDING-[N] format used consistently throughout
- [ ] All 5 recommendations name specific files and functions
- [ ] Enhanced planner prompt is copy-paste ready (no placeholder text)
- [ ] Deep research agent prompt is model-agnostic (no Claude/GPT-specific features)
- [ ] Integration spec names exact file paths and line numbers where possible
- [ ] Source registry has 20+ rows with verification dates
- [ ] Report saved to `forgegod-oss/deepresearch/RESEARCH_REPORT_2026.md`
- [ ] Karpathy Simplicity applied: no bloated proposals, only high-impact changes

---

# PART 6: RESEARCH QUERIES TO RUN

Start your research with these exact searches:

```
WebSearch: "SWE-agent architecture task decomposition 2026"
WebSearch: "Reflexion LLM self-correction arXiv 2026"
WebSearch: "SWE-bench leaderboard 2026 top agents"
WebSearch: "Claude Code autonomous coding architecture 2026"
WebSearch: "Aider vs SWE-agent vs Devin benchmark comparison 2026"
WebSearch: "MetaGPT multi-agent software engineering 2026"
WebSearch: "Self-Refine iterative improvement LLM coding"
WebSearch: "test-driven development LLM coding agent 2026"
WebSearch: "open source autonomous coding agent GitHub 2026 stars"
WebSearch: "LLM task decomposition planning autonomous coding"
WebFetch: github.com/princeton-nlp/SWE-agent (README + architecture)
WebFetch: github.com/aider-ai/aider (benchmarks page)
WebFetch: github.com/CLAUDE-DEV/Claude-Dev
WebFetch: github.com/ultraworkers/claw-code
```

Then expand based on what you find. Cross-reference findings across multiple sources.

---

# PART 7: KARPATHY SIMPLICITY REMINDER

You are being graded on the quality of your recommendations, not the quantity.

- Do NOT propose 20 changes. Propose 3 changes you are most confident will have the biggest impact.
- Every recommendation must be traceable to a specific file and function in ForgeGod.
- Every source must be verifiable — if you can't verify it, don't cite it.
- Prefer changes that are small, targeted, and high-impact over large architectural rewrites.
- The goal is a research agent that makes ForgeGod measurably better, not a perfect research report.

Good research = "add these 3 specific things to these 3 specific files" + "here's how to test it works."

---

# PART 8: HOW TO USE THIS DOCUMENT

1. Copy this entire document into your research model's context
2. The model reads PART 0 (ForgeGod Architecture) first — this is its sole context about ForgeGod
3. The model runs the searches in PART 6 plus its own research
4. The model produces all 6 outputs per PART 3 specifications
5. The model saves the report to `forgegod-oss/deepresearch/RESEARCH_REPORT_2026.md`
6. Extract the enhanced planner prompt → paste into `forgegod/agents/planner.py`
7. Extract the deep research agent prompt → save as `.forgegod/skills/deep-research/SKILL.md`
8. Execute the top recommendations in the integration spec

---

**START RESEARCH NOW. Read PART 0 first. Run PART 6 searches. Produce PART 3 outputs. Save to PART 4 location.**
