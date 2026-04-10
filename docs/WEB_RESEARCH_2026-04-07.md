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

## Harness Research Addendum - GLM Coding Plan + Codex Adversary

Verified on `2026-04-08` before designing a stronger ForgeGod harness for
agentic product builds:

- OpenAI's help material says Codex on supported ChatGPT plans can run in the
  terminal, edit files, execute tests, work in parallel, and operate in
  isolated sandboxes. That reinforces using Codex as the review/adversary layer
  instead of forcing it into the primary builder role:
  - https://help.openai.com/en/articles/11369540-using-codex-with-your-chatgpt-plan
- OpenAI's harness-engineering article explicitly argues that stronger
  scaffolding, PR-sized loops, clean repo docs, and agent-review cycles produce
  the gains. That fits a `GLM builder + Codex adversary` split better than
  symmetric multi-agent redundancy:
  - https://openai.com/index/harness-engineering/
- OpenAI's Codex use-case docs also position Codex strongly for PR review and
  front-end iteration with visual checks:
  - https://developers.openai.com/codex/use-cases
- Z.AI's DevPack docs position `glm-5.1` as a coding-agent model and expose the
  coding endpoint separately from the general OpenAI-compatible endpoint:
  - https://docs.z.ai/devpack/using5.1
  - https://docs.z.ai/api-reference/introduction
- Z.AI's FAQ says Coding Plan quota is only for coding tools designated or
  recognized by Z.AI and should not be assumed for arbitrary apps/bots/websites
  through direct API use:
  - https://docs.z.ai/devpack/faq
- There is still strong evidence that this pattern is used in real coding tools:
  OpenClaw's official provider docs explicitly support Coding Plan choices like
  `zai-coding-global` and `glm-5.1`, and Z.AI documents multiple supported tool
  integrations across OpenClaw, OpenCode, Cline, Crush, Cursor, Goose, and
  "other tools" OpenAI-compatible flows:
  - https://docs.openclaw.ai/providers/zai
  - https://docs.z.ai/devpack/tool/openclaw
  - https://docs.z.ai/devpack/tool/opencode
  - https://docs.z.ai/devpack/tool/cline
  - https://docs.z.ai/devpack/tool/crush
  - https://docs.z.ai/devpack/tool/cursor
  - https://docs.z.ai/devpack/tool/goose
  - https://docs.z.ai/devpack/quick-start

Operational conclusion for ForgeGod: the best research-backed harness today is
`glm-5.1` as planner/researcher/coder and `openai-codex:gpt-5.4` as
reviewer/sentinel/escalation. If ForgeGod users choose to wire
`ZAI_CODING_API_KEY` into this harness, the implementation should be treated as
an experimental, at-your-own-risk mode rather than marketed as a guaranteed
provider-sanctioned billing path.

## Origin Baseline Addendum - claw-code

Verified on `2026-04-08` before the next ForgeGod harness pass:

- The public `claw-code` repo presents itself as the canonical public `claw`
  harness implementation and centers `USAGE.md`, `PARITY.md`,
  `PHILOSOPHY.md`, and container-oriented runtime docs as the operational map:
  - https://github.com/ultraworkers/claw-code
  - https://raw.githubusercontent.com/ultraworkers/claw-code/main/USAGE.md
  - https://raw.githubusercontent.com/ultraworkers/claw-code/main/PARITY.md
  - https://raw.githubusercontent.com/ultraworkers/claw-code/main/PHILOSOPHY.md
- `claw-code` makes doctor/preflight a first-class product surface. Its usage
  guide says to run `/doctor` before prompts or automation, which supports
  keeping setup and sandbox diagnostics in the main CLI rather than as a
  hidden support path:
  - https://raw.githubusercontent.com/ultraworkers/claw-code/main/USAGE.md
- `claw-code` exposes explicit permission modes and tool allowlists
  (`read-only`, `workspace-write`, `danger-full-access`, plus
  `--allowedTools`). That is a stronger user-facing permission model than
  ForgeGod currently exposes:
  - https://raw.githubusercontent.com/ultraworkers/claw-code/main/USAGE.md
- `claw-code` also maintains a deterministic mock parity harness with scripted
  scenarios for tool roundtrips, permission denials, and bash flows. That is a
  stronger reproducibility story than ForgeGod's current mix of unit tests,
  stress tests, and live-provider smoke checks:
  - https://raw.githubusercontent.com/ultraworkers/claw-code/main/PARITY.md
  - https://raw.githubusercontent.com/ultraworkers/claw-code/main/rust/MOCK_PARITY_HARNESS.md
- At the same time, `claw-code` keeps a simpler routing story based on a small
  provider matrix and model-prefix selection, while ForgeGod already has a
  broader provider and auth matrix:
  - https://raw.githubusercontent.com/ultraworkers/claw-code/main/USAGE.md

Operational conclusion for ForgeGod: ForgeGod already exceeds `claw-code` in
provider breadth, native auth surfaces, PRD-loop orchestration, and memory
architecture. The remaining delta is now narrower and more specific:
interactive approval behavior in broader loop/worktree contexts and deeper
end-to-end harness coverage. The repo no longer needs generic "better
permissions" rhetoric; it needs the next layer of reproducible proof.

## Harness Research Addendum - OpenAI-Compatible Mock Endpoints

Verified on `2026-04-08` before extending ForgeGod's deterministic harness:

- OpenAI's external-model guide explicitly supports evaluating a custom model
  endpoint that implements OpenAI-compatible chat completions. That is strong
  current-year evidence that a local OpenAI-compatible endpoint is a legitimate
  harness target for deterministic verification, not a hack:
  - https://platform.openai.com/docs/guides/evals?api-mode=responses#run-an-evaluation-on-an-external-model
- `claw-code`'s usage guide also exposes `OPENAI_BASE_URL` for local
  OpenAI-compatible providers and pairs that with deterministic parity work.
  That makes configurable endpoint routing part of the lineage baseline rather
  than an invented ForgeGod detour:
  - https://raw.githubusercontent.com/ultraworkers/claw-code/main/USAGE.md
- Z.AI's official docs continue to document an OpenAI-compatible API surface,
  and the OpenClaw integration page shows the Coding Plan being wired into a
  real agent product through explicit provider setup plus model selection:
  - https://docs.z.ai/api-reference/introduction
  - https://docs.z.ai/devpack/tool/openclaw

Operational conclusion for ForgeGod: adding configurable OpenAI-compatible
endpoint routing and a local CLI mock parity harness is aligned with both
current official guidance and the `claw-code` baseline. The safer product
direction is to make this an explicit, documented harness surface instead of
leaving deterministic end-to-end testing to monkeypatch-heavy unit tests.

## Git Worktree Addendum - Parallel Isolation Contract

Verified on `2026-04-08` before tightening ForgeGod's worktree contract:

- The official Git worktree manual documents `git worktree add -b <new-branch> <path>`
  as the direct one-step way to create and check out a new branch into a new
  worktree, and notes that `-b` defaults its base commit to `HEAD`:
  - https://git-scm.com/docs/git-worktree.html
- The same manual also explains that omitted commit-ish behavior changes when a
  repository has no valid branches yet; Git can fall back to unborn-branch
  convenience behavior in that state:
  - https://git-scm.com/docs/git-worktree.html

Operational conclusion for ForgeGod: the harness should not rely on Git's
unborn-branch convenience path for autonomous parallel coding because ForgeGod
reviews and patches worker output against `HEAD`. Requiring at least one commit
before parallel workers start is the cleaner and more reproducible contract.

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

## Runtime Research Addendum - Strict Docker Sandbox + Node/Next Bootstrap

Verified on `2026-04-09` before tightening ForgeGod's strict Node/web path:

- OpenAI's harness-engineering writeup is explicit that when agents fail,
  the right move is usually to add missing capability, structure, or feedback
  loops to the harness rather than hand-finishing the product outside it:
  - https://openai.com/index/harness-engineering/
- That same article also argues that repo docs should be the system of record
  and that agent legibility matters. That supports injecting bounded repo docs
  into execution-time context instead of limiting that treatment to planning:
  - https://openai.com/index/harness-engineering/
- Docker's bind-mount docs explain that bind mounts can obscure existing
  container data. That is a concrete reason not to treat host-mounted
  `node_modules` as a stable dependency store inside strict containers:
  - https://docs.docker.com/engine/storage/bind-mounts/
- Docker's volume docs position named volumes as the persistent mechanism for
  container-managed data. That supports storing `node_modules` in a named
  volume instead of on a Windows bind mount:
  - https://docs.docker.com/engine/storage/volumes/
- Next.js documents `create-next-app` as the official bootstrap path, with
  flags such as `--app`, `--use-npm`, `--empty`, `--disable-git`, and
  `--agents-md`, and it notes that the CLI creates the project and installs
  the dependencies. That supports letting ForgeGod prefer the official
  bootstrap flow instead of improvising a scaffold from scratch:
  - https://nextjs.org/docs/app/api-reference/cli/create-next-app
- Playwright's Docker docs say the container image includes browsers and
  system dependencies, but the Playwright package itself still needs to be
  installed separately. That supports allowing a narrow network exception for
  browser/bootstrap install steps while keeping normal strict commands offline:
  - https://playwright.dev/docs/docker
- OpenHands documents a Docker-based runtime as the way to run the agent
  locally, which supports ForgeGod treating container-backed execution as the
  baseline for real local isolation rather than a niche add-on:
  - https://docs.openhands.dev/openhands/usage/run-openhands/local-setup

Operational conclusion for ForgeGod:

- Keep the workspace on a bind mount so file edits stay visible to the host.
- Keep `node_modules` off the host bind mount and inside a named Docker volume.
- Allow network only for a narrow bootstrap surface such as package installs
  and browser downloads; keep normal strict commands on `--network none`.
- Treat the Docker volume plus manifest hash as the dependency readiness
  signal, not host-side `node_modules`.
- Give the execution agent the checked-in repo docs so it follows the same
  source-of-truth artifacts that planning already uses.

## CLI UX Addendum - claw-code, Crush, and Claude Code

Verified on `2026-04-09` before refining ForgeGod's user-facing CLI layer:

- `claw-code` keeps operational trust high by making doctor/preflight, explicit
  permission flags, and parity coverage part of the main CLI contract instead
  of hiding them as support docs:
  - https://github.com/ultraworkers/claw-code
  - https://raw.githubusercontent.com/ultraworkers/claw-code/main/USAGE.md
  - https://raw.githubusercontent.com/ultraworkers/claw-code/main/PARITY.md
- `crush` positions the CLI itself as the product surface: multiple providers,
  polished terminal UX, conversational entrypoints, and a user-facing workflow
  that feels like a tool, not a debug log:
  - https://github.com/charmbracelet/crush
  - https://raw.githubusercontent.com/charmbracelet/crush/main/README.md
- Claude Code's interactive-mode and CLI docs reinforce two important UX
  patterns: users work in natural language, and the CLI should expose
  configurable interaction surfaces instead of raw transport details:
  - https://code.claude.com/docs/en/interactive-mode
  - https://code.claude.com/docs/en/cli-reference
  - https://code.claude.com/docs/en/settings

Operational conclusion for ForgeGod:

- Keep doctor, permissions, and auth setup as first-class CLI surfaces.
- Suppress successful HTTP transport chatter from the main UX path and narrate
  work in plain language at the task/story level instead.
- Use one shared branded console surface so onboarding, doctor, status, run,
  and loop feel like the same product.
- Guide provider setup inside ForgeGod: detect what is already linked,
  recommend a path, explain where secrets are stored, and avoid sending users
  straight to manual shell edits when the CLI can own the flow safely.

## What Future Maintainers Should Re-Check

- Whether OpenAI, Anthropic, OpenHands, and Aider still use the same file conventions.
- Whether newer MCP specs add stricter tool-safety metadata that ForgeGod should adopt.
- Whether OWASP prompt-injection guidance has changed in a way that should affect rule loading, tool redaction, or web-research behavior.
- Whether ForgeGod's security claims in README match the actual runtime by the time of the next release.
