# Obsidian Integration Plan 2026-04-17

## Verdict

Yes, Obsidian is worth integrating into ForgeGod, but not as the primary runtime memory backend.

The current ForgeGod memory system is already stronger for autonomous runtime use:

- SQLite-backed structured memory
- FTS5 retrieval
- hybrid ranking with relevance, importance, and recency
- explicit episodic, semantic, procedural, graph, and error-solution tiers
- LLM-assisted memory extraction via `MemoryAgent`

Obsidian should therefore be added as an optional knowledge surface:

- human-readable memory projection
- research notebook
- decision log
- pattern library
- operator dashboard
- optional ingest source for planning and research

It should not replace `forgegod/memory.py` as the authoritative hot-path memory layer.

## Why This Is the SOTA 2026 Direction

The key shift is that Obsidian now has first-party surfaces that materially reduce integration risk:

1. Obsidian CLI is now an official product surface for scripting, automation, and integration with external tools.
2. Obsidian Headless exists for sync without the desktop app, aimed at automation and agent workflows.
3. Bases gives a native structured view over frontmatter properties, which is ideal for research briefs, task dashboards, and memory projections.
4. The official plugin API remains available when deeper UX is needed, but official docs explicitly warn to keep plugins lightweight and safe.

That changes the recommendation from older community-plugin-heavy approaches.

In 2026, the strongest architecture is:

- ForgeGod runtime memory stays in SQLite
- ForgeGod exports stable knowledge to Markdown plus frontmatter inside an Obsidian vault
- ForgeGod optionally reads curated notes back in
- ForgeGod optionally uses official Obsidian CLI for search, open, create, append, and property operations
- ForgeGod only uses a custom Obsidian plugin if official CLI plus vault files are insufficient

## Research Findings

### 1. Obsidian CLI is now a first-party automation surface

Official docs state that Obsidian CLI lets you control Obsidian from the terminal for scripting, automation, and integration with external tools. It supports both direct commands and an interactive TUI. It requires the desktop app to be installed and running, and it exposes commands for:

- reading files
- creating files
- appending content
- setting properties
- searching
- tags
- tasks
- plugin reload
- screenshots
- developer tools
- Bases queries with JSON, CSV, TSV, Markdown, and path output

This is enough to justify a native ForgeGod adapter layer instead of treating Obsidian as a blind folder.

Sources:

- https://obsidian.md/help/cli

### 2. Obsidian Headless exists for non-desktop automation, but it is not the default path

Official docs describe Obsidian Headless as a standalone client for Obsidian services and specifically mention agentic tools, CI, and automated workflows. It is strongest for sync and remote automation, but it is still open beta and tied to Obsidian services and subscription-backed sync.

This makes Headless useful for later server-side or hive-adjacent workflows, but not the default first implementation for ForgeGod.

Sources:

- https://help.obsidian.md/headless
- https://help.obsidian.md/sync/headless

### 3. Obsidian is Markdown-first and file-system-friendly

Official help states that Obsidian stores notes as plain text Markdown files in a vault and automatically refreshes external changes. This is important because it means ForgeGod can safely generate and maintain vault content directly through file IO, without building a plugin first.

Official docs also note that Obsidian maintains a metadata cache and can rebuild it if needed, which is relevant for high-write automation.

Sources:

- https://help.obsidian.md/data-storage

### 4. Properties plus Bases are a strong structured layer

Official docs state that:

- note properties are YAML frontmatter
- property values are intended to be small and machine-readable
- Bases can query frontmatter-backed note data and render structured views
- Bases queries can also be accessed from the CLI

This is highly relevant for ForgeGod because it means we can expose memory summaries, research notes, model experiments, and design rules as structured notes without inventing a custom knowledge UI.

Sources:

- https://obsidian.md/help/properties
- https://obsidian.md/help/bases/syntax
- https://obsidian.md/help/cli

### 5. Search and wikilinks give us a low-friction ingest layer

Official docs confirm:

- search supports path, content, tag, line, and block filters
- internal links support wikilinks and Markdown links
- Obsidian can automatically update internal links after rename

That makes a curated ingest path viable: ForgeGod can read selected note sets and reconstruct a scoped knowledge pack for planning or research, while human operators maintain notes naturally in Obsidian.

Sources:

- https://obsidian.md/help/plugins/search
- https://help.obsidian.md/Linking%20notes%20and%20files/Internal%20links
- https://help.obsidian.md/settings

### 6. If a plugin is ever built, it must stay thin

Official developer docs explicitly warn against developing plugins in a main vault and note that plugins affect startup time. They recommend minimizing `onload` work and deferring file event handling until layout is ready.

This means ForgeGod should not start with a heavyweight plugin that scans the vault or manages memory itself. If we ever build one, it should be a thin UX layer on top of ForgeGod-managed files and commands.

Sources:

- https://docs.obsidian.md/Plugins/Getting%20started/Build%20a%20plugin
- https://docs.obsidian.md/plugins/guides/load-time

### 7. Secrets do not belong in synced notes

Official developer docs provide a secret storage surface for plugins. For ForgeGod, the main implication is that API keys, auth tokens, or live provider credentials must never be written into notes, frontmatter, or synced vault content.

Sources:

- https://docs.obsidian.md/plugins/guides/secret-storage

## Repo Reality Check

ForgeGod already has the right primitives to benefit from Obsidian without architectural inversion:

- `forgegod/memory.py` already provides structured recall and consolidation
- `forgegod/memory_agent.py` already extracts reusable learnings after tasks
- `forgegod/researcher.py` already synthesizes source-grounded research outputs
- `forgegod/planner.py` already creates structured planning artifacts
- `forgegod/hive.py` and `forgegod/subagents.py` already create parallel outputs that need human-readable aggregation

What ForgeGod lacks is not memory quality. It lacks a polished operator-facing knowledge surface.

Obsidian solves that well.

## Recommended Integration Model

### Decision

Use Obsidian as an optional projection plus ingestion layer, not as the source of truth for runtime memory.

### Layering

1. Runtime memory layer
   - remains SQLite in `forgegod/memory.py`
   - still powers fast recall and hot-path prompting

2. Knowledge projection layer
   - exports selected research, patterns, decisions, and postmortems to an Obsidian vault as Markdown plus frontmatter

3. Knowledge ingestion layer
   - reads selected Obsidian notes back into ForgeGod before planning or research
   - only for curated folders or note types

4. Optional app bridge
   - if official Obsidian CLI is available, use it for open, search, property, and base queries
   - otherwise fall back to direct file IO

5. Optional server sync layer
   - use Obsidian Headless only for subscription-backed remote automation later

## What Not To Do

These are anti-patterns:

1. Do not replace ForgeGod memory with Markdown files.
2. Do not write every low-confidence runtime memory into Obsidian.
3. Do not let all hive workers write to the vault concurrently.
4. Do not store secrets, tokens, provider config, or chain-of-thought-like raw internals in notes.
5. Do not start with a heavy custom Obsidian plugin.
6. Do not sync the same vault from multiple conflicting mechanisms by default.
7. Do not make Obsidian mandatory for ForgeGod core functionality.

## Best Architecture

### A. New ForgeGod module: `forgegod/obsidian.py`

Responsibility:

- detect vault availability
- validate vault path
- detect CLI availability
- read and write notes
- map ForgeGod artifacts to Obsidian note schemas
- optionally use CLI when present

Suggested public surface:

- `ObsidianAdapter`
- `ObsidianVaultConfig`
- `write_note()`
- `append_note()`
- `set_properties()`
- `search_notes()`
- `read_note()`
- `export_memory_projection()`
- `export_research_brief()`
- `export_story_postmortem()`
- `ingest_curated_notes()`

### B. Config additions

Add a new config section:

```toml
[obsidian]
enabled = false
vault_path = ""
mode = "projection"
cli_command = "obsidian"
headless_command = "ob"
use_cli_when_available = true
write_strategy = "file-io"
link_style = "wikilink"
export_root = "ForgeGod"
ingest_enabled = false
ingest_folders = ["ForgeGod/Research", "ForgeGod/Patterns", "ForgeGod/Decisions"]
ingest_max_notes = 25
project_stable_memories_only = true
min_confidence = 0.65
generate_bases = true
```

Recommended modes:

- `projection`: export only
- `projection+ingest`: export plus curated readback
- `bridge`: use CLI features when available
- `disabled`

### C. New CLI commands

Add a top-level `forgegod obsidian` group:

- `forgegod obsidian status`
- `forgegod obsidian doctor`
- `forgegod obsidian init --vault <path>`
- `forgegod obsidian export-memory`
- `forgegod obsidian export-research`
- `forgegod obsidian ingest`
- `forgegod obsidian open`
- `forgegod obsidian rebuild-base`

### D. Event model

Obsidian should receive projected outputs from durable lifecycle events:

1. After research completes
   - export a research brief note

2. After planning completes
   - export plan note plus design/risk note

3. After story success or failure
   - export postmortem note

4. After memory consolidation
   - export only durable semantic and procedural patterns above threshold

5. After loop or hive batches
   - export run summary note

### E. Centralized writing only

In hive mode:

- workers do not write to Obsidian directly
- only the coordinator projects outputs to the vault

Reason:

- avoids collisions
- keeps note naming deterministic
- prevents duplicate memory projections
- reduces metadata-cache churn inside Obsidian

## Data Model

### Folder layout

Recommended vault subtree:

```text
ForgeGod/
  Dashboard/
  Research/
  Decisions/
  Patterns/
  Errors/
  Runs/
  Stories/
  Bases/
```

### Frontmatter schema

Use small, atomic properties aligned with Obsidian's property model:

```yaml
type: research
project: forgegod
story_id: t001
status: approved
confidence: 0.84
updated_at: 2026-04-17T12:00:00Z
provider: openai
model: gpt-5.4-mini
tags:
  - forgegod
  - research
  - memory
links:
  - "[[Patterns/SQLite Memory Spine]]"
sources:
  - https://obsidian.md/help/cli
  - https://help.obsidian.md/data-storage
```

Important rule:

- keep frontmatter atomic
- keep large reasoning in body sections
- do not nest complex object graphs in properties unless Bases clearly benefits

### Note types

Recommended note types:

- `research`
- `decision`
- `pattern`
- `error-solution`
- `postmortem`
- `story-summary`
- `run-summary`
- `design-rule`

### Linking style

Default to wikilinks because they are native and compact:

- `[[Patterns/SQLite Memory Spine]]`
- `[[Research/Obsidian Integration 2026-04-17]]`

## How Obsidian Improves ForgeGod

### 1. Better human oversight

ForgeGod currently learns well, but much of that learning is operationally hidden in runtime state and internal files. Obsidian gives operators a readable surface for:

- what ForgeGod learned
- why a plan changed
- what failed repeatedly
- which design rules were promoted to stable patterns

### 2. Better research continuity

Research briefs exported to Obsidian become long-lived project memory for humans and agents. This is useful for:

- revisiting architecture decisions
- comparing provider changes over time
- tracking benchmark assumptions
- keeping research notes portable outside the harness

### 3. Better design and product iteration

Because Obsidian handles Markdown, properties, links, and structured views well, it is strong for:

- product PRDs
- design rules
- showcase postmortems
- roadmap notes
- operator heuristics

### 4. Better explainability for non-coders

This matters for ForgeGod specifically because your project is aiming to be both powerful and legible. Obsidian creates a natural operator-facing layer for people who are not reading raw SQLite tables or internal JSON.

## Where Obsidian Does Not Improve ForgeGod

Obsidian is weak as a hot-path autonomous memory backend because:

- Markdown parsing is slower than structured SQLite retrieval
- concurrency is worse
- deduplication is weaker
- ranking and scoring are not native
- write amplification can become messy
- human edits can destroy runtime invariants

That is why it should remain a projection plus ingestion layer.

## Best Initial Scope

### Phase 1: Projection-only integration

This is the correct first shipping version.

Deliver:

- config for vault path and enable flag
- export notes for research, decisions, patterns, errors, and run summaries
- deterministic naming and frontmatter schema
- optional generation of one or more `.base` files for dashboards
- no plugin required
- no runtime dependency on Obsidian CLI

Why this first:

- low risk
- immediate operator value
- zero architectural inversion
- easy to test

### Phase 2: Curated ingest

Deliver:

- read only selected folders
- parse frontmatter plus body
- summarize relevant notes into a compact context pack before planning or research
- configurable note cap and token budget

Guardrails:

- only ingest notes with matching `type`, `project`, or tags
- only ingest curated folders
- score and summarize before prompt injection

### Phase 3: CLI bridge

Deliver:

- detect official Obsidian CLI
- open notes after export
- search vault via CLI
- query Bases via CLI
- optionally expose an `obsidian_search` or `obsidian_open` tool

Why not earlier:

- file IO already solves persistence
- CLI adds convenience, not core correctness

### Phase 4: Optional thin plugin

Only build this if needed for UX.

Potential plugin features:

- live status panel for ForgeGod runs
- command palette actions for opening latest research or postmortem
- render a dashboard note or custom Bases-driven view
- display health warnings when projected notes are stale

Constraints from official docs:

- minimal `onload`
- defer heavy event work until layout ready
- never test inside a primary vault

### Phase 5: Optional Headless sync for remote workflows

Only for advanced users with Obsidian Sync.

Potential uses:

- team-shared research vault
- server-side report generation
- CI snapshot archiving
- hive coordinator pushing summaries to a shared remote vault

This should stay opt-in because Headless is open beta and subscription-dependent.

## Exact Implementation Recommendation For ForgeGod

### Recommended first merge

Implement only this:

1. `forgegod/obsidian.py`
2. `obsidian` config section
3. `forgegod obsidian` CLI group
4. projection from:
   - `Researcher`
   - `Planner`
   - `MemoryAgent`
   - `RalphLoop`
   - `HiveCoordinator`
5. one generated dashboard `.base`

### Do not include in the first merge

Do not include:

- custom plugin
- headless sync
- live bidirectional sync
- arbitrary vault-wide ingestion
- real-time vault watchers

## Suggested File Changes

### New files

- `forgegod/obsidian.py`
- `tests/test_obsidian.py`
- `tests/test_obsidian_cli.py`
- `docs/OBSIDIAN_INTEGRATION_PLAN_2026-04-17.md`

### Existing files likely touched

- `forgegod/config.py`
- `forgegod/cli.py`
- `forgegod/researcher.py`
- `forgegod/planner.py`
- `forgegod/memory_agent.py`
- `forgegod/loop.py`
- `forgegod/hive.py`
- `forgegod/models.py`
- `README.md`
- `README.es.md`

## Suggested Note Templates

### Research note

```md
---
type: research
project: forgegod
status: approved
confidence: 0.86
updated_at: 2026-04-17T12:00:00Z
tags: [forgegod, research, sota]
---

# Obsidian Integration Research

## Summary

## Sources

## Recommended pattern

## Risks

## Follow-up
```

### Pattern note

```md
---
type: pattern
project: forgegod
status: stable
confidence: 0.78
tags: [forgegod, pattern, memory]
---

# SQLite Memory Spine

## Trigger

## Action

## Why it works

## Related notes
- [[Research/Obsidian Integration 2026-04-17]]
```

## Testing Plan

### Unit tests

- path validation
- note rendering
- frontmatter serialization
- wikilink generation
- ingest note parsing
- stable memory threshold filtering

### Integration tests

- export research brief to temporary vault
- export postmortem to temporary vault
- rebuild `.base` file
- ingest curated folder into context pack
- hive coordinator writes only once per completed batch

### Manual verification

- open generated vault in Obsidian
- confirm external file refresh works
- confirm properties display correctly
- confirm Base query works
- confirm note renames preserve internal links

## Risks

### Risk 1: Vault clutter

Mitigation:

- keep everything under `ForgeGod/`
- deterministic filenames
- stable note types only

### Risk 2: Over-exporting noisy memory

Mitigation:

- export only high-confidence or explicitly approved learnings
- keep episodic noise out of Obsidian by default

### Risk 3: Metadata cache churn

Mitigation:

- batch writes
- central writer in hive mode
- no live per-token or per-step logging

### Risk 4: Secret leakage into notes

Mitigation:

- explicit scrubber before export
- never export env vars or provider credentials
- no raw tool transcripts by default

### Risk 5: Plugin complexity

Mitigation:

- defer plugin work
- prefer file IO and official CLI first

## Go / No-Go Decision

Go, with scope control.

The recommended move is:

- yes to Obsidian integration
- yes to projection-first integration
- yes to optional curated ingest
- yes to official CLI support when available
- no to replacing SQLite memory
- no to custom plugin in v1
- no to headless sync in v1

## Recommended Next Step

If you want execution next, the right implementation order is:

1. add config and adapter
2. export research plus pattern notes
3. export loop and hive summaries
4. generate one Base dashboard
5. add curated ingest
6. add official CLI bridge

That order gives maximum operator value with minimum architectural risk.
