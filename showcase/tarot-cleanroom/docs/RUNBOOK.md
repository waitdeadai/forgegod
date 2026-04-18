# Tarot Harness Runbook

This is the execution contract for building Tarot entirely with ForgeGod.

## Harness

Use the current research-backed split:

- `planner = minimax:MiniMax-M2.7-highspeed`
- `researcher = minimax:MiniMax-M2.7-highspeed`
- `coder = minimax:MiniMax-M2.7-highspeed`
- `reviewer = openai-codex:gpt-5.4`
- `sentinel = openai-codex:gpt-5.4`
- `escalation = openai-codex:gpt-5.4`
- `taste = openai-codex:gpt-5.4`
- `profile = max_effort`
- `subagents = enabled`
- `hive = enabled`

## Build Rules

- every meaningful architecture or dependency choice requires 2026 research first
- every story must leave the app runnable
- every public claim must be documented
- every visual pass must be checked on phone widths
- every milestone must update docs, not just code
- this showcase must visibly use ForgeGod brand colors and symbolism
- every story should survive Codex adversarial review plus taste review
- if the harness gets stuck or receives a weak review, rerun current-year research before trying blind retries

## Recommended Build Sequence

### Phase 1: Skeleton

- create new app from zero
- wire TypeScript, lint, Vitest, Playwright
- land initial route structure and deployment

### Phase 2: Time Window Engine

- implement timezone config
- implement open/closed computation
- expose `/api/status`
- cover edge cases with unit tests

### Phase 3: Reading Engine

- define typed card content
- implement three-card spread logic
- expose `/api/reading`
- test duplicate prevention and closed-state rejection

### Phase 4: Design System and UI

- test `awesome-design-md` as a reference workflow
- keep repo-local Tarot `DESIGN.md` as the final source of truth
- implement landing
- implement countdown and closed-state
- implement reading ritual flow
- mobile polish and OG metadata

### Phase 5: Production Hardening

- E2E against production build
- mobile viewport coverage
- no horizontal overflow
- verify performance and layout stability

## Required Commands Per Milestone

At minimum:

```bash
npm run lint
npm run test
npm run test:e2e
npm run build
```

When Playwright is used, follow the Next.js guidance and prefer running against
the production build.

## ForgeGod Workflow

Recommended command sequence:

```bash
forgegod research "2026 best practices for a mobile-first tarot ritual app on Next.js App Router with Vercel deployment, deterministic local content, and time-window access control" --depth sota
forgegod audit run
forgegod recon "Build the definitive ForgeGod tarot showcase from zero using docs/PRD.md, docs/ARCHITECTURE.md, DESIGN.md, and taste.md. Use MiniMax M2.7 highspeed for planning/coding and Codex as adversarial reviewer."
forgegod hive --prd .forgegod/prd.json --workers 2 --subagents
```

Recommended DESIGN.md workflow:

```bash
forgegod design list --query vercel
forgegod design pull vercel --path <scratch-dir>
```

Use that preset as a structural reference only. The Tarot app itself should use
its own ForgeGod-branded `DESIGN.md`.

When the backlog is stable:

```bash
forgegod loop --prd .forgegod/prd.json
```

## Review Contract

Codex must explicitly review:

- schedule correctness
- timezone edge cases
- mobile UX
- visual regressions
- whether the build actually reads as ForgeGod-branded
- route security assumptions
- test sufficiency

## Documentation Contract

Any time the app evolves, update:

- PRD if behavior changes
- architecture if structure changes
- design doc if the visual language changes
- stories if the order or scope changes
