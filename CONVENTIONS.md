# ForgeGod Conventions

Primary repo instructions live in [AGENTS.md](AGENTS.md).

Before finalizing changes:
- Check `git status --short`.
- Do deep 2026 research before committing changes that affect architecture, dependencies, security, benchmarks, model strategy, workflows, or public claims. Record sources and dates in repo docs.
- Aim for SOTA 2026 or beyond, but only claim it when the design is source-backed and the repo proves it locally.
- Trust [docs/OPERATIONS.md](docs/OPERATIONS.md) and [docs/AUDIT_2026-04-07.md](docs/AUDIT_2026-04-07.md) over historical marketing copy.
- When public-facing claims, providers, versions, benchmark numbers, or security posture change, update `docs/index.html` and verify the deployed site as part of the same change.
- Run the smallest relevant verification command:
  - `python -m pytest -m "not stress" -q`
  - `python -m ruff check forgegod tests`
  - `python -m build`
