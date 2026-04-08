# Security Policy

## Reporting Vulnerabilities

**Do NOT file public GitHub issues for security vulnerabilities.**

Report security issues to: **security@waitdead.com**

We will acknowledge receipt within 48 hours and aim to provide a fix within 7 days for critical issues.

## Scope

ForgeGod executes shell commands, reads/writes files, and sends code to LLM APIs. Security issues in scope include:

- Command injection or sandbox bypass
- Path traversal allowing access outside project directory
- Secret/credential exposure to LLM context
- Prompt injection via project files (rules.md, AGENTS.md)
- MCP server compromise vectors
- Authentication bypass or API key exposure

## Security Model

ForgeGod uses two different execution models:

- `standard` mode runs on the host with guardrails
- `strict` mode requires a real Docker sandbox backend

ForgeGod implements defense-in-depth:

1. **Real strict sandbox** - `strict` mode runs commands in a Docker container with `--network none`, `--read-only`, `--cap-drop ALL`, `no-new-privileges`, and a workspace bind mount
2. **Standard-mode shell policy** - `standard` mode blocks dangerous command patterns and shell operators such as chaining, pipes, redirection, and command substitution
3. **Isolated process dirs** - Host-local guarded execution scopes `HOME`, temp, cache, and config directories under `.forgegod/sandbox`
4. **Secret redaction** - API keys and tokens are stripped from tool output before entering LLM context
5. **Workspace scoping** - Agent-driven filesystem and shell execution stay within the active workspace root, and configured `blocked_paths` are enforced
6. **Generated-code validation** - Dangerous generated code is flagged on writes and edits; `strict` mode blocks suspicious writes
7. **Prompt-injection detection** - Project rules and file content are scanned for prompt-injection patterns
8. **Budget limits** - Cost controls prevent runaway API spend
9. **Killswitch** - Create `.forgegod/KILLSWITCH` to immediately halt the autonomous loop

## Known Limitations

- ForgeGod sends file contents and code to third-party LLM APIs. Do not use on repositories containing secrets or proprietary code without appropriate safeguards.
- `strict` mode depends on a usable local Docker daemon and a pre-pulled sandbox image. If those prerequisites are missing, strict execution is blocked.
- ForgeGod now includes a strict-sandbox doctor check and a non-technical setup guide in [docs/STRICT_SANDBOX_SETUP.md](docs/STRICT_SANDBOX_SETUP.md). Prefer that path over disabling `strict` for convenience.
- ForgeGod still does not provide microVM isolation, custom seccomp profiles, or a stronger backend than the local Docker Engine.
- `standard` mode is still a host-local guardrailed workflow, not a locked-down profile. Suspicious generated code is blocked only in `strict` mode.
- MCP server connections spawn external processes. Only connect to trusted MCP servers.
- Project rules files (`.forgegod/rules.md`, `AGENTS.md`) are injected into the system prompt. Cloning untrusted repositories may result in prompt injection.

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | Yes       |
