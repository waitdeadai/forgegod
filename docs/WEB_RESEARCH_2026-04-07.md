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

## Provider Research Addendum - Z.AI / GLM

Verified on `2026-04-08` before adding a new provider path:

- Z.AI's API introduction documents an OpenAI-compatible API surface, which
  makes a direct ForgeGod provider integration worthwhile instead of routing it
  through a third-party aggregator:
  - https://docs.z.ai/api-reference/introduction
- Z Code's configuration docs explicitly distinguish between Z.AI, the GLM
  Coding Plan, and generic OpenAI-compatible providers. That supports making the
  Coding Plan endpoint a first-class config path instead of forcing users to
  hand-edit a custom provider:
  - https://zcode.z.ai/docs/configuration
- Z.AI's tool-calling docs show current GLM models exposing tool/function
  calling and reasoning content in the chat-completions family, which is the
  key compatibility point ForgeGod needs for agent loops:
  - https://docs.z.ai/guides/capabilities/stream-tool
- Z.AI's pricing docs provide the cost basis for `glm-5.1` and nearby GLM
  models added to ForgeGod's cost table:
  - https://docs.z.ai/guides/overview/pricing
- Z.AI's OpenClaw integration docs explicitly list the Coding Plan-supported
  model set and show `glm-5.1` as the current coding-focused model to target:
  - https://docs.z.ai/devpack/tool/openclaw

Operational conclusion for ForgeGod: add `zai` as a first-class provider with
an explicit Coding Plan path, detect it in onboarding/doctor/benchmark flows,
and treat `glm-5.1` as the default benchmarkable model until repo-local
benchmarks justify a different default.

## Native Auth Addendum - OpenAI Codex + Z.AI Coding Plan

Verified on `2026-04-08` before wiring native subscription-oriented auth into ForgeGod CLI:

- OpenAI's help material states that Codex is available on supported ChatGPT
  plans and can be accessed through the Codex CLI, IDE extension, or Codex in
  ChatGPT. That supports using ChatGPT-backed Codex login as a native auth
  surface inside ForgeGod instead of pretending the only supported OpenAI path
  is API keys:
  - https://help.openai.com/en/articles/11369540-using-codex-with-your-chatgpt-plan
- OpenAI's billing guidance also says API usage and ChatGPT subscriptions are
  billed separately. That supports treating `openai-codex` as a different auth
  and billing surface from `OPENAI_API_KEY`, including zero in-repo cost
  accounting for subscription-backed calls:
  - https://help.openai.com/en/articles/8156019
- OpenClaw's provider docs explicitly treat OpenAI Codex as an auth surface
  distinct from plain OpenAI API keys, which reinforces the design choice to
  model native auth surfaces separately from upstream provider families:
  - https://docs.openclaw.ai/concepts/model-providers
- Z.AI's devpack quick-start docs show a Coding Plan path for external coding
  tools with a dedicated API key and base URL. That supports making
  `ZAI_CODING_API_KEY` first-class instead of forcing users through a generic
  OpenAI-compatible custom endpoint:
  - https://docs.z.ai/devpack/quick-start
  - https://docs.z.ai/devpack/tool/openclaw
- OpenRouter's official docs remain credit/API based rather than a subscription
  auth surface, so it should not be marketed as "native subscription" support
  in ForgeGod today:
  - https://openrouter.ai/docs/api-reference/overview
- Alibaba / Qwen Coding Plan docs currently frame that surface around supported
  coding tools rather than generic autonomous third-party loops. That supports
  delaying any "native subscription" claim there until ForgeGod has a clearly
  sanctioned integration path:
  - https://www.alibabacloud.com/help/en/model-studio/claude-code-coding-plan
  - https://qwen.ai/docs/qwen-code/getting-started

Operational conclusion for ForgeGod: implement native auth now for OpenAI
Codex and Z.AI Coding Plan inside ForgeGod CLI, keep usage inside ForgeGod once
the one-time provider login is complete, and avoid claiming native subscription
support for OpenRouter or Alibaba until there is an official, reproducible path
that fits ForgeGod's autonomous workflow model.

## Workflow Research Addendum - DESIGN.md + Contribution Mode

Verified on `2026-04-08` before adding frontend and contribution workflows:

- VoltAgent's `awesome-design-md` repo documents `DESIGN.md` as a lightweight,
  markdown-native design system file for AI agents and positions it as a drop-in
  repo-root artifact that coding agents can consume directly:
  - https://github.com/VoltAgent/awesome-design-md
- That repository explicitly cites Google Stitch's `DESIGN.md` concept and
  standardizes reusable sections such as palette, typography, components,
  layout, responsive behavior, and agent prompt guidance:
  - https://github.com/VoltAgent/awesome-design-md/blob/main/README.md
  - https://stitch.withgoogle.com/docs/design-md/overview/
- GitHub's own guidance says contributors should look for `good first issue`
  and `help wanted` labels when entering a project:
  - https://docs.github.com/en/communities/setting-up-your-project-for-healthy-contributions/encouraging-helpful-contributions-to-your-project-with-labels?apiVersion=2022-11-28
- GitHub's open-source contribution docs also recommend opening an issue before
  investing major feature work so the approach aligns with maintainer
  expectations:
  - https://docs.github.com/en/get-started/exploring-projects-on-github/finding-ways-to-contribute-to-open-source-on-github

Operational conclusion for ForgeGod: `DESIGN.md` is worth supporting as a
first-class repo artifact for frontend tasks, and a contribution mode should
read `CONTRIBUTING.md`, prefer approachable labels, and avoid treating
"autonomous contribution" as license to bypass maintainer rules.

## What Future Maintainers Should Re-Check

- Whether OpenAI, Anthropic, OpenHands, and Aider still use the same file conventions.
- Whether newer MCP specs add stricter tool-safety metadata that ForgeGod should adopt.
- Whether OWASP prompt-injection guidance has changed in a way that should affect rule loading, tool redaction, or web-research behavior.
- Whether ForgeGod's security claims in README match the actual runtime by the time of the next release.
