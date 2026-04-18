# Tarot Showcase

This repository is a clean restart of the ForgeGod Tarot showcase.

Purpose:
- benchmark ForgeGod on a full product build
- keep the implementation independent from the archived legacy Tarot code
- use the current ForgeGod harness: `zai:glm-5.1` for planning/building and `openai-codex:gpt-5.4` for review/escalation
- ship a bilingual `en` / `es` ritual showcase with real launch surfaces

Source of truth:
- `docs/PRD.md`
- `docs/ARCHITECTURE.md`
- `docs/STORIES.md`
- `DESIGN.md`
- `docs/WEB_RESEARCH_2026-04-18_I18N_PRODUCTIZATION.md`

Important implementation notes:
- English remains the canonical tarot deck source.
- Spanish card copy is generated as a reproducible overlay in `content/locales/es-deck.json`.
- Regenerate the Spanish overlay with `npm run generate:es-deck` after setting `MINIMAX_API_KEY`.

The archived legacy implementation remains outside this repo path as:
- `../tarot_legacy_2026-04-08`
