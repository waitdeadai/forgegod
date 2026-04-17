# ForgeGod x OpenClaw x Hermes Research

Date: 2026-04-17

## Question

What is the SOTA 2026 way to let ForgeGod power chat-driven coding from OpenClaw and Hermes without rebuilding Telegram/WhatsApp inside ForgeGod?

## Conclusion

Do not rebuild the messaging gateway in ForgeGod.

Use ForgeGod as a callable coding engine surface, and integrate it with the chat runtimes that already own:

- channel adapters
- session routing
- chat delivery
- approval flows
- gateway security boundaries

That means:

1. Hermes: first-party ForgeGod skill now, MCP server later if we want tool-native invocation.
2. OpenClaw: first-party skill plus CLI-backend config now, ACP/native harness later if we want persistent external harness sessions with thread binding and richer runtime controls.
3. Stable bridge surface first: machine-friendly `forgegod bridge chat` with session ids, JSON output, optional system prompt input, and repo-local transcript continuity.

## Why this is the right split

### OpenClaw already owns the messaging control plane

OpenClaw documents that one long-lived Gateway owns all messaging surfaces, while control-plane clients connect to the Gateway over WebSocket. It is already the correct host for Telegram/WhatsApp routing and delivery, not ForgeGod.

Source:

- https://docs.openclaw.ai/concepts/architecture

### OpenClaw has two separate extension paths

OpenClaw explicitly separates:

- CLI backends for conservative external CLI execution
- ACP agents for full external harness sessions with session controls and bindings

The docs are explicit that CLI backends are a safety-net style text path, while ACP agents are the deeper external harness path.

Sources:

- https://docs.openclaw.ai/gateway/cli-backends
- https://docs.openclaw.ai/tools/acp-agents
- https://docs.openclaw.ai/plugins/sdk-agent-harness

### OpenClaw skills are lightweight and workspace-local

OpenClaw skills are just workspace directories with `SKILL.md`, and the docs recommend them for concise, testable workflow instructions. That makes them the fastest low-risk entrypoint for ForgeGod delegation.

Source:

- https://docs.openclaw.ai/tools/creating-skills

### Hermes prefers skills first for external CLIs

Hermes explicitly says to make something a skill when the capability is instructions plus shell commands and existing tools, including wrapping an external CLI.

That matches ForgeGod today.

Sources:

- https://hermes-agent.nousresearch.com/docs/developer-guide/creating-skills/
- https://hermes-agent.nousresearch.com/docs/user-guide/features/hooks/

### Hermes also has a strong MCP surface

Hermes can consume stdio or HTTP MCP servers with filtered exposure and safe env handling. That makes a future ForgeGod MCP server reasonable, but it is not required for the first production-worthy integration.

Source:

- https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp/

## Recommended rollout

### Phase 1: stable bridge surface

Ship a machine-friendly ForgeGod bridge:

- `forgegod bridge chat`
- stable `--session-id`
- `--format text|json`
- `--system-prompt`
- optional attached file/image paths
- repo-local transcript continuity

This is the interoperability contract.

### Phase 2: installable agent assets

Ship first-party exports:

- Hermes skill scaffold
- OpenClaw skill scaffold
- OpenClaw CLI backend config snippet

This is enough to let Telegram/WhatsApp/Discord sessions delegate coding into ForgeGod today through those runtimes.

### Phase 3: deeper native runtime path

If adoption justifies it, build:

- an OpenClaw ACP/native harness plugin for ForgeGod
- optionally a ForgeGod MCP server for Hermes and other MCP-native clients

That is the path for richer session semantics, tool streaming, and long-lived external harness work.

## What not to do

- Do not bolt Telegram or WhatsApp adapters directly into ForgeGod.
- Do not duplicate OpenClaw/Hermes gateway auth, pairing, or delivery logic.
- Do not rely on prompt-only “use ForgeGod” patterns without a stable CLI bridge contract.
- Do not claim full ACP-native integration before ForgeGod actually owns session resume and external runtime event streaming.
