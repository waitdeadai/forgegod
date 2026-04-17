# Web Research 2026-04-17 — Multi-Agent Runtime, Research, and Quality Surfaces

Scope: align ForgeGod's public claims and runtime behavior for `subagents`, `hive`,
the built-in `Researcher`, the optional `TasteAgent` wrapper, and the local
`EffortGate`.

## Primary Sources

1. OpenAI Agents SDK multi-agent guide
   https://openai.github.io/openai-agents-js/guides/multi-agent/

2. OpenAI Agents SDK guardrails guide
   https://openai.github.io/openai-agents-js/guides/guardrails/

3. OpenAI deep research guide
   https://developers.openai.com/api/docs/guides/deep-research

4. OpenAI graders guide
   https://developers.openai.com/api/docs/guides/graders

5. OpenAI trace grading guide
   https://developers.openai.com/api/docs/guides/trace-grading

6. OpenAI practical guide to building agents
   https://cdn.openai.com/business-guides-and-resources/a-practical-guide-to-building-agents.pdf

7. LangGraph supervisor README
   https://github.com/langchain-ai/langgraph-supervisor-py

8. AutoGen stable docs
   https://microsoft.github.io/autogen/stable/

9. OpenAI Swarm README
   https://github.com/openai/swarm

## What The Sources Support

- Manager/supervisor orchestration is the production-safe default when one
  runtime should own the final answer, shared guardrails, and execution budget.
  OpenAI's guide explicitly distinguishes "agents as tools" from handoffs and
  recommends the manager pattern when one agent should keep control.

- Handoffs and tool execution need different safety treatment. OpenAI's
  guardrails guide states that tool guardrails do not automatically cover
  handoffs or built-in execution tools. Inference: ForgeGod should keep
  explicit permission boundaries, reviewer checks, and budget ownership outside
  any future handoff abstraction.

- Research agents should return source-grounded outputs, not generic summaries.
  OpenAI deep research documents inline citations, explicit annotations, and
  visible clickable source references as the expected UX for research output.
  Inference: ForgeGod's `Researcher` should remain source-oriented and its
  public copy should describe current-docs grounding rather than vague "AI
  intuition".

- Quality agents need reproducible criteria. OpenAI graders and trace grading
  emphasize structured grading, tool-call inspection, and trace-level analysis.
  Inference: `TasteAgent` and `EffortGate` should be framed as quality gates
  with explicit verdicts and review evidence, not as magical polish steps.

- Local multi-process hive with a central coordinator matches current
  supervisor-worker guidance. LangGraph's supervisor docs and OpenAI's manager
  pattern both reinforce a central orchestrator plus isolated workers.

- Swarm is not the right production reference. OpenAI's own README labels Swarm
  as experimental/educational and recommends the Agents SDK for production use
  cases.

- Event-driven multi-agent runtimes are still relevant. AutoGen's stable docs
  position event-driven, scalable multi-agent systems as the serious path once
  you move beyond prototypes. Inference: ForgeGod's local hive and worker JSON
  surfaces are directionally correct, but they should stay deterministic and
  auditable.

## Resulting ForgeGod Decisions

- `subagents` are now a live opt-in runtime surface, exposed publicly on
  `forgegod`, `forgegod run`, and `forgegod hive` via `--subagents`.

- ForgeGod keeps `subagents` bounded to read-only analysis. Nested orchestration
  is explicitly disabled inside subagent workers to avoid recursive fan-out.

- `parallelism.py` no longer lies by collapsing every task into
  `RESEARCH_FIRST` whenever `research_before_code` is enabled. Research is now a
  recommendation flag; topology remains `sequential`, `subagents`, `hive`, or
  `research_first` only for architecture-heavy work.

- `TasteAgent` remains an optional wrapper around `taste-agent`, but the result
  mapping is now more defensive so missing fields do not break loop execution.

- `EffortGate` stays honest: it is a local deterministic quality floor today,
  not a half-wired external LLM judge.

- Public copy should say `9 provider families` and `10 route surfaces`, and it
  should describe `hive` plus optional `subagents` without implying autonomous
  capabilities the runtime does not actually expose.
