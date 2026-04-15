# ForgeGod Deep Research Agent — Run This

**Purpose:** Research how to make ForgeGod the best open-source autonomous coding engine in the world. Produce a model-agnostic deep research agent spec + concrete implementation plan.

**Research model:** Use your most capable model (Claude 4 Opus, Gemini 2.5 Pro, or GPT-5). Use MiniMax M2.7 for parallel speed lookups.

**Output:** A complete `forgegod-oss/deepresearch/RESEARCH_REPORT.md` + a drop-in research agent system prompt + integration spec.

---

## ForgeGod Context (read this first)

### Current Architecture

```
PRD.json stories
  → RalphLoop picks TODO stories (deps satisfied)
    → PLANNER (MiniMax M2.7-highspeed)
      → decomposes story into steps
      → outputs plan with checkpoints
    → CODER (MiniMax M2.7-highspeed)
      → implements plan
      → must show ≥2 drafts + verification evidence (EffortGate)
    → REVIEWER (Z.AI GLM-5 adversarial)
      → approves → story done
      → rejects → feedback to CODER, loop
  → repeat
```

**23 registered tools, 633 tests, lint clean, build passes**

**Key files to know:**
- `forgegod/loop.py` — RalphLoop, `_get_ready_stories()`, `_tick()`
- `forgegod/agents/planner.py` — story decomposition
- `forgegod/agents/coder.py` — implementation
- `forgegod/agents/reviewer.py` — adversarial gate
- `forgegod/agents/taste.py` — EffortGate
- `forgegod/agents/effort.py` — effort scoring
- `forgegod/router.py` — 10-provider routing
- `forgegod/config.py` — MiniMax, Z.AI, model configs
- `forgegod/skills/audit-agent/` — pre-story audit skill

**Providers:** minimax (M2.7), zai (glm-5), openai (gpt-5.4-mini), anthropic (claude-opus-4), openai-codex (gpt-5.4), ollama (qwen-2.5-14b), deepseek, gemini, kimi, openrouter

---

## Phase 1: Read the ForgeGod Code (do this first)

Before researching anything, read these files to ground yourself:

1. `forgegod/agents/planner.py` — what does the planner do today?
2. `forgegod/loop.py` — how does RalphLoop work?
3. `forgegod/agents/taste.py` + `forgegod/agents/effort.py` — how does EffortGate work?
4. `forgegod/config.py` — what models are configured?
5. `forgegod/skills/audit-agent/SKILL.md` — what does audit-agent do?

Then answer:
- What planning strategy does the planner use now?
- What is the biggest gap between what it does and what top engines do?

---

## Phase 2: Research These 5 Areas

### Area A: Planning & Task Decomposition

**Search queries:**
- `SWE-agent task decomposition architecture 2026`
- `Devin autonomous coding planning architecture`
- `Claude Code task planning implementation`
- `MetaGPT ChatDev multi-agent planning`
- `hierarchical task networks LLM coding agent`

**For each finding:**
- What technique is used?
- Source URL + date verified
- How would it fit into ForgeGod's planner?

### Area B: Self-Correction & Reflection Patterns

**Search queries:**
- `Reflexion LLM self-correction arXiv 2026`
- `Self-Refine iterative improvement coding`
- `CRITIC LLM self-verification`
- `DEFT coding agent self-testing`
- `coding agent self-debug 2026 patterns`

### Area C: Quality Gates & Verification-First

**Search queries:**
- `test-driven development LLM coding 2026`
- `LLM-as-judge coding quality`
- `adversarial coding agent reviewer architecture`
- `EffortGate autonomous coding`
- `SWE-bench high scoring agent patterns`

### Area D: Benchmark Intelligence

**Search queries:**
- `SWE-bench leaderboard 2026`
- `BFCL Berkeley Function Calling Leaderboard 2026`
- `LiveCodeBench v4 coding agent`
- `HumanEval++ 2026 coding benchmarks`
- `autonomous coding agent benchmark comparison 2026`

### Area E: Model-Specific Performance

**Search queries:**
- `MiniMax M2.7 coding benchmark 2026`
- `Z.AI GLM-5.1 coding performance`
- `Claude 4 Opus coding vs GPT-5 2026`
- `best open source coding agent 2026 comparison`
- `SWE-agent vs Aider vs Claude-Dev benchmark`

---

## Phase 3: Competitive Analysis

**Run these searches:**
- `best open source autonomous coding agent 2026 github stars`
- `autonomous coding engine comparison SWE-bench 2026`
- `forgegod vs claude code vs aider vs swe-agent`

**Fetch these repos:**
- `https://github.com/princeton-nlp/SWE-agent` (README + architecture docs)
- `https://github.com/aider-ai/aider` (benchmarks page)
- `https://github.com/CLAUDE-DEV/Claude-Dev`
- `https://github.com/ultraworkers/claw-code` (ForgeGod origin baseline)
- `https://github.com/anthropics/claude-code`

**Build a comparison table:**
| Feature | ForgeGod | SWE-agent | Aider | Claude-Dev | Devin |
|---------|----------|------------|-------|------------|-------|
| Multi-model harness | ✓ | ? | ? | ? | ? |
| Adversarial reviewer | ✓ | ? | ? | ? | ? |
| EffortGate | ✓ | ? | ? | ? | ? |
| audit-agent | ✓ | ? | ? | ? | ? |
| Continuous benchmark | ✓ | ? | ? | ? | ? |

---

## Phase 4: Synthesize Findings

### FINDING-[N] Template

```
FINDING-[N]: [Descriptive Title]
Source: [URL] (verified YYYY-MM-DD)
Category: [planning | self-correction | quality | benchmark | model | competitive]
Mechanism: [How the technique works — 2-3 sentences]
ForgeGod gap: [Does ForgeGod already use this? If not, what file/function needs changing?]
Evidence strength: [high | medium | low] — based on source quality and citations
Effort to add: [low | medium | high]
```

Produce **20+ findings** across all 5 areas.

---

## Phase 5: Produce These 6 Outputs

### OUTPUT 1: Findings List (20+ findings)

Using the FINDING-[N] template above. Group by category.

### OUTPUT 2: Competitive Analysis Table

Markdown table comparing ForgeGod against 5+ competitors on 10+ features. Mark ForgeGod's advantages in green, gaps in red.

### OUTPUT 3: Top 5 Actionable Recommendations

Ranked by **Impact × Feasibility**:

```
RECOMMENDATION-[N]: [Title]
Top finding: [FINDING-N that motivates this]
Change: [Specific code change — file, function name, what to add/change]
Test: [How to verify it works — specific test or command]
Risk: [What could break]
```

### OUTPUT 4: Deep Research Agent System Prompt

A complete, drop-in system prompt for a model-agnostic research agent:

```markdown
[SYSTEM PROMPT — copy this verbatim]

You are the ForgeGod Deep Research Agent.

You conduct exhaustive research on coding agent architecture, planning,
self-correction, and quality patterns using only primary sources.

Your research feeds directly into ForgeGod's planner and coder to produce
research-backed code that incorporates 2026 SOTA patterns.

## Your Mission
Conduct deep research on [TOPIC] and produce:
1. A findings list (20+ sources, FINDING-[N] format)
2. A competitive analysis
3. Top 5 actionable recommendations
4. An enhanced planner system prompt injection

## Research Standards
VALID SOURCES: GitHub repos ≥100 stars (≤6 months old), arXiv 2024-2026,
  official docs (Anthropic/OpenAI/MiniMax/Z.AI), primary benchmark pages.

INVALID SOURCES: blog posts, vendor marketing, tutorial sites (Medium/TDS),
  Twitter/X posts, unverified gists.

VERIFICATION: Every source must have URL + date fetched. Fetch the URL.
  Confirm the content matches the claim. If dead, find an alternative.

## Output Format

### FINDING-[N]: [Title]
Source: [URL] (verified YYYY-MM-DD)
Category: [planning | self-correction | quality | benchmark | model | competitive]
Mechanism: [2-3 sentences]
ForgeGod gap: [What to change — file + function if missing]
Evidence strength: [high | medium | low]
Effort to add: [low | medium | high]

### Competitive Analysis Table
[Markdown table]

### Top 5 Recommendations
[Ranked by Impact × Feasibility]

### Enhanced Planner Prompt Injection
[Any additions to the planner system prompt based on findings]

[/SYSTEM PROMPT]
```

### OUTPUT 5: ForgeGod Integration Spec

How to wire the research agent into ForgeGod:

```markdown
## Integration Option A: Pre-Story Research (inside RalphLoop)

Trigger: Before planner fires on stories with complexity > threshold
File to modify: forgegod/agents/planner.py
Change: Add research_agent.research(story) call before planner fires
Output: research brief injected as planner context

## Integration Option B: forgegod research CLI command

File to add: forgegod/agents/researcher.py
Command: forgegod research "[query]"
Output: markdown report to stdout + .forgegod/research_cache/

## Integration Option C: Audit-Research hybrid

File to modify: forgegod/skills/audit-agent/SKILL.md
Change: audit-agent runs research phase after codebase audit
Output: research brief added to AUDIT.md

## Skill to add: .forgegod/skills/deep-research/SKILL.md
[Standard skill YAML with research protocol + output format]
```

### OUTPUT 6: Verified Source Registry

```
| # | Source | URL | Type | Verified | Key Finding |
|---|--------|-----|------|----------|-------------|
| 1 | SWE-agent | github.com/princeton-nlp/SWE-agent | github | YYYY-MM-DD | ... |
[20+ rows]
```

---

## Phase 6: Write the Final Report

Save as `forgegod-oss/deepresearch/RESEARCH_REPORT_2026.md`

```markdown
# ForgeGod Deep Research Report — [TOPIC]

**Generated:** YYYY-MM-DD
**Research model:** [what you used]
**Sources:** [N] primary sources verified
**Quality:** [All/N most] URLs verified live

## Executive Summary
[3-5 bullets: most important findings]

## 1. FINDINGS (20+ findings)
[All FINDING-[N] entries]

## 2. COMPETITIVE ANALYSIS
[Comparison table]

## 3. TOP 5 RECOMMENDATIONS
[Ranked recommendations with specific code changes]

## 4. ENHANCED PLANNER PROMPT
[The full planner prompt injection — ready to paste into planner.py]

## 5. INTEGRATION SPEC
[How to wire this into ForgeGod]

## 6. SOURCE REGISTRY
[The full source table]

## Appendix: Full Research Notes
[Any extra notes, contradictions found, areas needing more research]
```

---

## Quality Checklist

Before finishing, verify:

- [ ] Read all 5 key ForgeGod files before researching
- [ ] 20+ sources found across 5 areas
- [ ] Every source URL fetched and verified live
- [ ] All 6 outputs produced
- [ ] FINDING-[N] format used consistently
- [ ] Recommendations name specific files/functions
- [ ] Enhanced planner prompt is copy-paste ready
- [ ] Integration spec specifies exact file changes
- [ ] Report saved to `deepresearch/RESEARCH_REPORT_2026.md`

---

## How to Run

1. Give this entire document as a prompt to your research model
2. Or copy the sections into your chat one at a time
3. Recommended: Claude 4 Opus or Gemini 2.5 Pro for full research
4. MiniMax M2.7 for parallel URL verification lookups
5. Aim for 20-40 verified sources
6. Save output to `forgegod-oss/deepresearch/RESEARCH_REPORT_2026.md`
7. Copy the enhanced planner prompt into `forgegod/agents/planner.py`

---

## Karpathy Simplicity Reminder

Research is only valuable if it produces change. Prioritize:
1. The 1-2 changes that would have the biggest impact on code quality
2. The specific files and functions to modify
3. How to verify the change works

Don't propose 50 changes. Propose 3 changes you can confidently implement.
