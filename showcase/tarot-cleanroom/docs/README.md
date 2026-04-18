# Tarot Cleanroom

This directory is the cleanroom benchmark for the definitive ForgeGod tarot showcase.

Rules:

- zero reuse of implementation code from the previous tarot build
- product code must be generated and refined through ForgeGod, not by hand
- every major architecture or dependency choice must be research-backed with 2026 sources
- the final app must be good enough to replace the current public showcase on the ForgeGod site

Harness target:

- `planner = minimax:MiniMax-M2.7-highspeed`
- `researcher = minimax:MiniMax-M2.7-highspeed`
- `coder = minimax:MiniMax-M2.7-highspeed`
- `reviewer = openai-codex:gpt-5.4`
- `sentinel = openai-codex:gpt-5.4`
- `escalation = openai-codex:gpt-5.4`
- `taste = openai-codex:gpt-5.4`
- `profile = max_effort`
- `hive + subagents = enabled`

Key 2026 research facts used for this run:

- MiniMax documents `MiniMax-M2.7-highspeed` as an OpenAI-compatible model with a 204,800 token context window and higher output speed than standard M2.7.
- MiniMax documents direct integration with coding tools through OpenAI-compatible and Anthropic-compatible surfaces.
- OpenAI documents Codex CLI/App as a local agentic coding surface on Windows, macOS, and Linux, with ChatGPT-account sign-in supported.
- Next.js App Router officially supports code-generated `opengraph-image.tsx` for production metadata and sharing surfaces.

Primary sources:

- https://platform.minimaxi.com/docs/api-reference/text-openai-api
- https://platform.minimaxi.com/docs/guides/text-ai-coding-tools
- https://platform.minimaxi.com/docs/release-notes/models
- https://platform.minimaxi.com/docs/token-plan/minimax-cli
- https://developers.openai.com/codex/quickstart
- https://developers.openai.com/codex/config-reference
- https://nextjs.org/docs/app/api-reference/file-conventions/metadata/opengraph-image
