# ForgeGod Web Research - 2026-04-11

## Purpose

Capture the 2026-era external guidance used to justify ForgeGod's new subagent
review pattern and the local hive (multi-process) supervisor/worker design.
This is a reference log for maintainers, not a marketing document.

## Sources and Takeaways

### 1) OpenAI Agents SDK: handoffs and manager-style delegation

- The Agents SDK models handoffs as tool-based delegation and allows filtering
  the history passed to a specialist agent, which aligns with ForgeGod's
  "manager + handoff" orchestration pattern and context filtering choices.
  https://openai.github.io/openai-agents-js/guides/handoffs/

### 2) OpenAI Practical Guide: manager pattern + guardrails

- OpenAI's guide highlights the manager pattern where agents can serve as tools
  for other agents, which supports treating subagents as tool-like analysis
  workers under a central controller.
  https://cdn.openai.com/business-guides-and-resources/a-practical-guide-to-building-agents.pdf
- The same guide describes guardrails as first-class concepts in the Agents SDK
  that can run concurrently and block unsafe output, which supports ForgeGod's
  adversarial review + retry guardrail posture.
  https://cdn.openai.com/business-guides-and-resources/a-practical-guide-to-building-agents.pdf
- The guide splits orchestration into single-agent and multi-agent patterns and
  recommends an incremental approach, reinforcing ForgeGod's hybrid coordinator
  (rules + LLM) and multi-worker scheduling instead of full autonomy at once.
  https://cdn.openai.com/business-guides-and-resources/a-practical-guide-to-building-agents.pdf

### 3) LangGraph Supervisor: hierarchical supervisor/worker pattern

- LangGraph Supervisor describes a hierarchical multi-agent system where a
  single supervisor delegates work to workers that communicate only with the
  supervisor, aligning with ForgeGod's hive coordinator and worker isolation.
  https://changelog.langchain.com/announcements/langgraph-supervisor-a-library-for-hierarchical-multi-agent-systems

### 4) OpenAI Swarm: educational only, Agents SDK is production path

- OpenAI's Swarm repo states it is experimental/educational and recommends
  migrating to the production-ready Agents SDK for real use cases. This
  supports ForgeGod's choice to follow Agents SDK concepts instead of Swarm.
  https://github.com/openai/swarm

## Operational Conclusion For ForgeGod

1. Keep subagents scoped as analysis-only workers with adversarial review
   and a single retry.
2. Keep hive as a supervisor/worker system with tool-like handoffs and
   deterministic dependency checks.
3. Treat guardrails and review as first-class in the runtime, not optional.
4. Avoid Swarm as a production foundation; follow the Agents SDK patterns.
