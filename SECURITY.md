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

ForgeGod operates with the same permissions as your user account. It implements defense-in-depth:

1. **Command denylist** — Destructive shell commands are blocked by default
2. **Secret redaction** — API keys and tokens are stripped from tool output before entering LLM context
3. **Path awareness** — Sensitive file patterns (.env, credentials) trigger warnings
4. **Budget limits** — Cost controls prevent runaway API spend
5. **Killswitch** — Create `.forgegod/KILLSWITCH` to immediately halt the autonomous loop

## Known Limitations

- ForgeGod sends file contents and code to third-party LLM APIs. Do not use on repositories containing secrets or proprietary code without appropriate safeguards.
- The command denylist is pattern-based and can be bypassed by determined users or creative LLM outputs. It is a safety net, not a security boundary.
- MCP server connections spawn external processes. Only connect to trusted MCP servers.
- Project rules files (.forgegod/rules.md, AGENTS.md) are injected into the system prompt. Cloning untrusted repositories may result in prompt injection.

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | Yes       |
