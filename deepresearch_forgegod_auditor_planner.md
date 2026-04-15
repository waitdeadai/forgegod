# Deep Research: ForgeGod Auditor & Planner Enhancement

## Objective

Make ForgeGod the best open-source autonomous coding engine in the world by building a world-class **research agent** that continuously improves the **auditor** and **planner** subsystems using current 2026 data, patterns, and benchmarks from primary sources.

---

## Context: What ForgeGod Is

ForgeGod (`forgegod-oss`, `https://github.com/waitdeadai/forgegod`) is an **autonomous coding harness** — a Python package that orchestrates multi-model agents to implement features from a `prd.json` story manifest.

**Current architecture (as of 2026-04-15):**
- **Provider matrix**: 10 route surfaces — ollama, openai, openai-codex, anthropic, openrouter, gemini, deepseek, kimi, zai, minimax
- **Default harness**: MiniMax M2.7 High Speed (coder) + Z.AI GLM-5 (adversarial reviewer)
- **Ralph Loop**: The autonomous story-execution loop — reads `prd.json`, picks `TODO` stories, runs coder+reviewer per story, enforces EffortGate (≥2 drafts + verification evidence)
- **audit-agent**: First-class skill that runs before any story planning; produces `.forgegod/AUDIT.md` via 11-step protocol
- **23 registered tools** in the agent tool registry
- **Tests**: 633 passing, lint clean, build passes

**Core loop flow:**
```
RalphLoop._get_ready_stories()  → picks stories with status="todo" and deps satisfied
  → spawn coder agent (MiniMax M2.7)
    → draft implementation
    → EffortGate enforces: ≥2 drafts + verification evidence
    → reviewer agent (Z.AI GLM-5 adversarial)
      → reject → loop back to coder with feedback
      → approve → story marked done
  → repeat until all done
```

**Key files:**
- `forgegod/loop.py` — RalphLoop implementation
- `forgegod/router.py` — model routing (10 providers)
- `forgegod/benchmark.py` — model detection + cost tracking
- `forgegod/doctor.py` — auth verification
- `forgegod/config.py` — MiniMax/Z.AI config structs
- `forgegod/agents/taste.py` — taste agent (quality gate)
- `forgegod/agents/effort.py` — EffortGate logic
- `.forgegod/skills/audit-agent/SKILL.md` — audit-agent skill definition

---

## The Problem: Auditor & Planner Are The Bottleneck

The auditor and planner are the **highest-leverage subsystems** in any coding engine. If they are wrong, every downstream story is wrong.

**Current weaknesses identified:**
1. **Audit-agent** only triggers on first entry or >20 commits — it doesn't run continuously as the codebase evolves
2. **RalphLoop** picks `TODO` stories but has no dynamic reprioritization based on codebase state
3. **Planner** has no access to live competitive intelligence — it doesn't know what Claude Code, Copilot, or Aider are doing differently
4. **No learning loop** — past story outcomes don't inform future story planning
5. **No cost-awareness** in story sizing — stories can be oversized and burn budget without verification
6. **Provider selection for planner/coder/reviewer is static** — not dynamically optimized per story complexity
7. **Subagent briefs are inconsistent** — planning quality varies by model quality

---

## Research Agent Mission

You are the **ForgeGod Research Agent**. Your job is to deeply research, synthesize, and propose concrete improvements to the auditor and planner subsystems.

**You are model-agnostic.** You can use any model for research. Your output is a **research report + implementation plan** that engineers (human or agent) can execute.

**Your constraints:**
- Source primary sources: official docs, GitHub repos, arXiv papers, published benchmarks
- No blogspam or vendor marketing
- All claims must have citations with URLs and verification dates
- Focus on 2026 patterns — LLMs, coding agents, multi-agent orchestration, autonomous coding

---

## Research Areas

### 1. Auditor Subsystem Enhancement

**Focus:** How do the best coding engines (Claude Code, Copilot, Aider, Claude Engineer, Devin, SWE-agent, etc.) perform continuous codebase awareness?

**Specific questions to answer:**
- How does Claude Code maintain codebase context over long sessions? What is its context management strategy?
- What does SWE-bench reveal about autonomous agent architecture? What patterns distinguish high-scoring agents from low-scoring ones?
- How do agents like Devin, Opus 4, and Claude Code handle **planning with incomplete context**? What fail-safe patterns exist?
- What is the current SOTA for **codebase indexing** — how do agents efficiently retrieve relevant code without full context reload?
- What approaches exist for **continuous audit** vs one-shot audit? Which architectures support audit-as-you-go?
- What does the literature say about **self-correcting agents** — how do agents detect their own errors without external verification?

**Resources to examine:**
- `https://github.com/princeton-nlp/SWE-agent` — architecture, tool use, reconstruction
- `https://github.com/CLAUDE-DEV/Claude-Dev` — long-horizon agent patterns
- `https://github.com/sWE-E/coodex` — Claude Code open-source exploration
- `https://github.com/ultraworkers/claw-code` — ForgeGod's origin baseline
- arXiv papers on coding agents (search: "SWE-agent", "Devin", "autonomous coding agent 2026")
- Anthropic's published Claude Code architecture notes
- GitHub topics: `autonomous-coding`, `ai-coding-agent`, `llm-software-engineering`

**Output:** Concrete proposal for `.forgegod/skills/audit-agent/SKILL.md` improvements + `forgegod/agents/audit.py` new capabilities.

---

### 2. Planner Subsystem Enhancement

**Focus:** How do top coding engines plan story decomposition, dependency management, and effort estimation?

**Specific questions to answer:**
- How does Claude Code's **task decomposition** work? How does it break complex features into verifiable sub-tasks?
- What planning strategies do the best autonomous coding engines use? (hierarchical task networks, linear task chains, graph-based dependencies)
- How do agents handle **story sizing** — how do they estimate effort and budget for a PRD story before committing?
- What role does **verification-first** planning play in reducing rework? (e.g., writing tests before implementation)
- How do multi-model harnesses (like ForgeGod's MiniMax coder + Z.AI reviewer) optimize **role specialization**?
- What is the SOTA for **adversarial coding** — how does a reviewer agent differ from a coder agent architecturally?
- How do agents handle **dependency conflicts** between stories? What ordering strategies minimize integration surprises?
- What cost-estimation models exist for LLM token usage per story type? How do production harnesses budget?

**Resources to examine:**
- `https://github.com/anthropics/claude-code` — official Claude Code repo
- `https://github.com/openai/devin` — Devin architecture discussions
- `https://github.com/aider-ai/aider` — Aider's chat-to-code architecture
- ForgeGod's own `prd.json` story structure — analyze the dependency chain patterns
- Papers: "SWE-bench: Can Large Language Models Resolve Real-World GitHub Issues?" and sequels
- Papers: "CodeAgent", "AgentCoder", "MagiCoder" — search for these

**Output:** Concrete proposal for `forgegod/agents/planner.py` new strategies + story sizing model.

---

### 3. Multi-Agent Orchestration Patterns

**Focus:** What are the 2026 best practices for multi-agent coding harnesses?

**Specific questions to answer:**
- What role architectures work best for coder + reviewer + planner? (e.g., specialist vs generalist, adversarial vs collaborative)
- How do production harnesses handle **agent consensus** — when coder and reviewer disagree, what decides?
- What is the role of **memory** between agent turns? How do top harnesses maintain working memory vs long-term memory?
- How do **reflection** patterns (Reflexion, Self-Refine, etc.) work in multi-agent coding loops?
- What is the optimal **turn budget** per story? How do top engines prevent infinite loops?
- How does **provider diversity** (multi-model) improve or complicate harness reliability?
- What safety patterns exist for autonomous coding loops — how do you prevent budget exhaustion, infinite loops, and goal drift?

**Resources to examine:**
- Reflexion paper (arXiv) — language agent reflection
- Self-Refine paper — iterative self-improvement
- `https://github.com/strong-io/llm-agent-zoo` — agent patterns collection
- Papers: "A Survey on Large Language Model-Based Autonomous Agents" (2025-2026)
- Papers: "ChatDev", "MetaGPT", "SoftwareAgent" — multi-agent software engineering

**Output:** Architecture recommendations for `forgegod/agents/` subsystem refactors.

---

### 4. Benchmarking & Measurement

**Focus:** How do you measure whether ForgeGod is actually improving?

**Specific questions to answer:**
- What benchmarks exist for coding agent quality? (SWE-bench, BFCL, LiveCodeBench, HumanEval, etc.)
- Which benchmark best predicts **real-world autonomous coding performance**?
- How do you build a **local harness eval** that doesn't require external API calls?
- What metrics should ForgeGod track per story? (time-to-complete, cost-per-story, revision count, reviewer rejection rate)
- How do you measure **auditor quality** — does running audit-agent actually prevent downstream bugs?
- How do you measure **planner quality** — do stories sized by the planner actually complete within estimated effort?
- What is the SOTA for **harness self-evaluation** — can a harness evaluate its own performance?

**Output:** Proposed metrics + `forgegod/evals/` framework additions.

---

### 5. Competitive Landscape (2026 Q1-Q2)

**Focus:** Where does ForgeGod stand vs competitors, and what can be borrowed?

**Specific questions to answer:**
- What are the top 10 open-source autonomous coding engines in 2026? (list with GitHub stars, last commit, key differentiators)
- What does Claude Code do that ForgeGod doesn't?
- What does OpenAI's Copilot Next / Copilot Workspace do architecturally?
- What is the current state of **openai-codex** integration — is it production-ready for autonomous coding?
- What is the current state of **MiniMax M2.7** for coding tasks — are there published benchmarks?
- What is the current state of **Z.AI GLM-5** for code review — any public benchmarks?
- What emerging models (Gemini 3, GPT-5, Claude 4) are relevant for coding harnesses in 2026?

**Resources to examine:**
- `https://github.com/topics/autonomous-coding-agent`
- `https://github.com/topics/ai-coding-assistant`
- GitHub trending repos in `software-development` / `artificial-intelligence`
- `https://aider.chat/docs/benchmarks.html` — Aider benchmarks
- LiveCodeBench, SWE-bench leaderboards

**Output:** Competitive analysis table + `docs/COMPETITORS.md` draft.

---

## Deliverable Format

Produce a single research report at `forgegod-oss/deepresearch/auditor_planner_research_2026.md` with this structure:

```markdown
# ForgeGod Auditor & Planner — Research Report 2026

**Generated:** YYYY-MM-DD
**Research agent model:** [model used]
**Sources:** [count] primary sources consulted

## Executive Summary
[3-5 bullets: most important findings]

## 1. Auditor Subsystem — Findings & Proposals
### Current State
[What ForgeGod audit-agent does today]

### Research Findings
[What top engines do — with citations]

### Proposed Improvements
[Numbered proposals with specific file/targets]
- Proposal 1: [title] → files to change: [list]
- Proposal 2: ...

## 2. Planner Subsystem — Findings & Proposals
[Same structure]

## 3. Multi-Agent Orchestration — Findings & Proposals
[Same structure]

## 4. Benchmarking — Findings & Proposals
[Same structure]

## 5. Competitive Landscape
[Analysis table]

## Priority Implementation Roadmap
[Ranked by impact × feasibility]

## Verified Sources
- [Source 1](url) — verified YYYY-MM-DD
- [Source 2](url) — verified YYYY-MM-DD
- ...
```

---

## How to Run This Research

1. **Use a research-capable model** — Gemini 2.5 Pro, Claude 4 Opus, or GPT-5 for the deep synthesis. Use MiniMax M2.7 for speed on intermediate lookups.
2. **Search extensively** — use WebSearch and WebFetch to pull from primary sources, not summaries
3. **Verify URLs** — every claim needs a citation. Check that URLs are live and content matches the claim.
4. **Cross-reference** — compare what ForgeGod docs say vs what competitors actually do
5. **Focus on actionable** — proposals must name specific files and functions to change
6. **Apply Karpathy Simplicity** — prefer minimal architectural changes that produce maximal impact

---

## Quality Bar

- Minimum 30 primary sources cited (official docs, GitHub repos, arXiv papers)
- No vendor marketing or unverified blog posts as sources
- All code examples must be syntactically valid Python
- All proposals must be traceable to a specific file in `forgegod-oss/`
- Research report must be comprehensive enough that a human or agent could implement the top-3 proposals without additional research

---

## Start Research Now

Begin with:
1. WebSearch for "SWE-agent architecture 2026" + "Claude Code autonomous coding architecture"
2. WebFetch the GitHub repos of top competitors (SWE-agent, Aider, Claude-Dev)
3. Search arXiv for recent papers on "autonomous coding agent" and "LLM software engineering"
4. Check GitHub trending for `autonomous-coding-agent` topic
5. Fetch ForgeGod's current audit-agent SKILL.md and loop.py to ensure research is grounded in actual code

Then synthesize into the report format above.
