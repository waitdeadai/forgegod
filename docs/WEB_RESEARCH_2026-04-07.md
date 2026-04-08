# ForgeGod Web Research - 2026-04-07

## Purpose

This document captures the external 2026-era guidance used to shape the repo's agent instructions and safety notes. The goal is not to mirror every source; it is to preserve the operational conclusions and the links that future maintainers should re-check.

## Main Takeaways

### 0. "SOTA" has to be source-backed and operationally demonstrated

- OpenAI's harness-engineering writeup is the clearest official statement in the current source set that coding-agent performance is not just a model choice; the repository harness, workflow, and instruction layer materially determine throughput and quality:
  - https://openai.com/index/harness-engineering/
- OpenAI's model documentation frames current Codex-family models as optimized for agentic coding, but that alone does not make a repository or workflow state-of-the-art:
  - https://developers.openai.com/api/docs/models/gpt-5.3-codex
- Anthropic's Claude Code docs make a similar point indirectly: instruction quality, memory structure, permissions, and tool configuration all affect reliability, and these are context/configuration systems rather than hard guarantees:
  - https://code.claude.com/docs/en/memory
  - https://code.claude.com/docs/en/settings

Operational conclusion for ForgeGod: "SOTA 2026 or beyond" should be treated as a target standard for repo design and workflow quality, but the repo should only claim it where primary sources and local proof agree.

### 1. Keep repo instructions small, local, and explicit

- OpenAI recommends a small repo-root `AGENTS.md` and treating repo docs as the working system of record for agents:
  - https://developers.openai.com/codex/guides/agents-md
  - https://openai.com/index/harness-engineering/
- Anthropic uses `CLAUDE.md` as persistent project memory and supports importing other files with `@path/to/file`:
  - https://docs.anthropic.com/en/docs/claude-code/memory
  - https://docs.anthropic.com/en/docs/claude-code/settings
- OpenHands also reads repo-level `AGENTS.md` automatically and supports optional scoped microagents:
  - https://docs.all-hands.dev/usage/prompting/repository
- Aider documents repo-level `CONVENTIONS.md` and expects explicit lint/test workflows:
  - https://aider.chat/docs/usage/conventions.html

### 2. Internet content and repo docs are untrusted inputs

- OpenAI's Codex system-card material warns that fetched content can carry hidden or indirect instructions and that internet access should be constrained to safe, scoped methods:
  - https://openai.com/index/openai-codex-system-card/
- OWASP's GenAI guidance treats prompt injection as a primary risk, including indirect injection through files, web pages, and tool output:
  - https://genai.owasp.org/llmrisk/llm01-prompt-injection/
- OWASP's Agentic AI Top 10 reinforces that autonomous agents add risks around tool misuse, unsafe delegation, and missing guardrails:
  - https://owasp.org/www-project-agentic-ai-top-10/

### 3. MCP tooling should document security and tool safety clearly

- The Model Context Protocol spec requires implementations to sanitize user inputs, validate generated content, and document security requirements:
  - https://modelcontextprotocol.io/specification/2025-06-18/server/prompts
- MCP tool definitions support annotations such as `readOnlyHint`, which matter for safe scheduling and execution strategies:
  - https://modelcontextprotocol.io/specification/2025-06-18/server/tools

### 4. Local-runtime agents need honest sandbox language

- OpenHands documents that a local runtime executes directly on the host and is not sandboxed by default:
  - https://docs.all-hands.dev/usage/runtimes/runtime-local

That directly supports the choice to document ForgeGod's real filesystem and shell behavior rather than imply stronger isolation than the code currently enforces.

## Recommendations Applied To This Repo

1. Add a short root `AGENTS.md` with a scope line, verified commands, and known sharp edges.
2. Add compatibility entrypoints for `CLAUDE.md` and `CONVENTIONS.md` instead of duplicating large instruction sets.
3. Keep a dated audit and an operations doc in-repo so agents do not have to infer truth from stale marketing copy.
4. Treat fetched content, rules files, and external docs as untrusted data, not instructions.
5. Document unsafe defaults honestly until sandboxing, path boundaries, and tool annotations are actually enforced.
6. Use the repo docs as the maintainers' system of record, then update marketing pages second.

## Sandbox Hardening Addendum

Verified on `2026-04-08` before tightening ForgeGod's local runtime:

- OpenAI's Codex app launch materials emphasize isolated task execution as a
  core safety property for coding agents, which supports treating stronger
  execution boundaries as a first-class product concern rather than a nice-to-have:
  - https://openai.com/index/introducing-the-codex-app/
- OpenAI's Codex system card is even more explicit: Codex runs in a container
  with no internet access while the agent is in control, and filesystem access
  is limited to the sandboxed environment. That supports ForgeGod treating real
  runtime isolation as a product requirement, not a documentation nicety:
  - https://cdn.openai.com/pdf/8df7697b-c1b2-4222-be00-1fd3298f351d/codex_system_card.pdf
- Anthropic's Claude Code settings and permissions model support explicit
  allow/deny controls for shell commands, including operator-aware matching,
  which supports ForgeGod blocking chaining, redirection, pipes, and command
  substitution in tighter modes instead of relying only on a destructive-command
  denylist:
  - https://docs.anthropic.com/en/docs/claude-code/settings
- OpenHands documents that a local runtime runs directly on the host and is
  not sandboxed by default, which supports keeping ForgeGod's docs honest about
  the difference between guardrails and a true sandbox:
  - https://docs.all-hands.dev/usage/runtimes/runtime-local
- Docker's `docker run` reference documents the specific container controls
  ForgeGod can actually enforce today for a real strict backend: read-only
  root filesystems and bind mounts using `--mount`:
  - https://docs.docker.com/reference/cli/docker/container/run/
- Docker's security docs reinforce the value of capability reduction as an
  allowlist-based hardening layer, which supports dropping capabilities in
  ForgeGod's strict backend instead of treating the container as safe by default:
  - https://docs.docker.com/engine/security/
- MCP security guidance requires implementations to sanitize user inputs,
  validate generated content, and document their security requirements. That
  supports blocking suspicious generated-code writes in strict mode and writing
  down exactly what ForgeGod does and does not isolate:
  - https://modelcontextprotocol.io/specification/2025-06-18/server/tools
  - https://modelcontextprotocol.io/specification/2025-06-18/server/prompts

Operational conclusion for ForgeGod: workspace scoping, isolated process
home/cache/config directories, operator blocking, and strict-mode allowlists
were worth enforcing immediately, but they were not enough by themselves.
ForgeGod now has a stricter Docker-backed sandbox path for `strict` mode:
no network, read-only rootfs, dropped capabilities, and workspace-only mounts.
That is materially better than host execution, but it should still be documented
honestly as container isolation rather than the end state of sandboxing. Repo
policy should also require syncing the public website whenever public-facing
runtime claims change.

## Provider Research Addendum - Kimi / Moonshot

Verified on `2026-04-07` before adding a new provider path:

- Moonshot publishes direct guidance for agentic coding/tooling and recommends
  official-provider configuration rather than assuming vendor parity:
  - https://platform.moonshot.ai/docs/guide/agent-support.en-US
- Moonshot documents Kimi thinking-mode constraints such as
  `reasoning_content`, streaming, and high token budgets. That means a simple
  OpenAI-compatible integration can work, but it will not automatically unlock
  the full thinking-mode workflow:
  - https://platform.moonshot.ai/docs/guide/use-kimi-k2-thinking-model
- Moonshot documents JSON-mode compatibility, which matters for ForgeGod's
  structured outputs and tool-call handling:
  - https://platform.moonshot.ai/docs/guide/use-json-mode-feature-of-kimi-api
- Official model materials position Kimi K2.5 as strong for coding and agents,
  but not obviously dominant across coding benchmarks versus frontier peers:
  - https://www.kimi.com/ai-models/kimi-k2-5
  - https://github.com/MoonshotAI/Kimi-K2.5
- Moonshot's K2 Vendor Verifier explicitly documents that tool-call fidelity
  varies across vendors, which supports preferring the direct Moonshot API over
  a third-party aggregation route for serious evaluation:
  - https://github.com/MoonshotAI/K2-Vendor-Verifier
- Official Moonshot pricing was used for the cost table entries added to
  ForgeGod's config:
  - https://platform.moonshot.ai/docs/pricing/chat

Operational conclusion for ForgeGod: add `kimi` as an optional direct provider,
detect it in onboarding/doctor/benchmark flows, but keep it experimental and do
not promote it to a default role until live ForgeGod benchmarks show it winning
on the repository's own workloads.

## What Future Maintainers Should Re-Check

- Whether OpenAI, Anthropic, OpenHands, and Aider still use the same file conventions.
- Whether newer MCP specs add stricter tool-safety metadata that ForgeGod should adopt.
- Whether OWASP prompt-injection guidance has changed in a way that should affect rule loading, tool redaction, or web-research behavior.
- Whether ForgeGod's security claims in README match the actual runtime by the time of the next release.
