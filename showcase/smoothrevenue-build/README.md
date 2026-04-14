# Smoothrevenue.com — Three-Agent Build Showcase

This directory contains a **live showcase** of the three-agent system:
- **ForgeGod**: autonomous coding harness
- **effort-agent**: "Did you do the work?" — process integrity gate
- **taste-agent**: "Does it look right?" — adversarial design director

## The Setup

The SmoothRevenue marketing site was deleted from this directory and is being rebuilt from scratch by ForgeGod, gated by effort-agent and taste-agent.

## Files

```
smoothrevenue-build/
├── effort.md              # Process standards (min drafts, no shortcuts, verify)
├── taste.md               # Design standards (colors, typography, copy voice)
├── prd.json               # Story breakdown (15 stories)
├── .forgegod/
│   └── config.toml        # ForgeGod config (effort + taste enabled)
└── README.md             # This file
```

## How to Run

```bash
cd showcase/smoothrevenue-build
python -m forgegod loop --prd prd.json --workers 1
```

ForgeGod will:
1. Read `effort.md` + `taste.md` as source of truth
2. Execute 15 stories from `prd.json`
3. After each story, the built-in **EffortGate** checks for:
   - Minimum 2 drafts completed
   - Verification evidence provided
   - Shortcut language (single-pass, "good enough", etc.)
4. After each story, **TasteAgent** evaluates design adherence
5. REDO/REVISE → ForgeGod iterates; DONE/APPROVE → next story

## Three-Agent Architecture

```
ForgeGod (autonomous coder)
  ├── EffortGate (built-in, regex-based) — "did you do the work?"
  │     └── Blocks story if: <2 drafts, no verification, shortcuts found
  │
  ├── TasteAgent (native Python wrap of taste_agent package) — "does it look right?"
  │     └── REJECT/REVISE if design standards not met
  │
  └── MCP tools available: mcp_connect + mcp_call
        effort-agent MCP server: python -m effort_agent.integration.mcp_server
        taste-agent MCP server: python -m taste_agent.integration.mcp_server
```

## What Gets Shown

- effort-agent verdicts: DONE / REDO / FAIL logged per story
- taste-agent verdicts: APPROVE / REVISE / REJECT with design issues
- ForgeGod iteration: REDO/REVISE triggers actual code revision
- Final quality: generated site vs original hand-crafted spec

## Packages Used

- `effort-agent` (v0.1.0) — Process integrity enforcement
- `taste-agent` (v0.2.0) — Adversarial design evaluation
- `forgegod` (v0.1.0) — Autonomous coding harness

## Expected Outcome

The three-agent system should produce a site matching the original SmoothRevenue spec:
- Dark institutional elegance (Linear/Vercel/Stripe aesthetic)
- 6 service cards in bento grid
- Full i18n EN/ES toggle
- 10-field lead form
- Legal pages
- JSON-LD schema markup
- No Tailwind, no emoji, no generic copy
