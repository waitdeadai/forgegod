# ForgeGod Mascot Research Notes

Date verified: 2026-04-08

## Source-backed direction

- The All Contributors specification says open source projects should include a visible contributors section in a prominent project surface, typically the README, and that contributors should be recognized across contribution categories rather than only code.
  Source: https://allcontributors.org/en/specification/

- The All Contributors emoji key explicitly defines `design` as a first-class contribution category covering UI/UX, branding, and visuals.
  Source: https://allcontributors.org/en/emoji-key/

- Google's current image metadata guidance recommends using `ImageObject` structured data with `creator` and/or `creditText` when you want published images to carry attribution metadata.
  Source: https://developers.google.com/search/docs/appearance/structured-data/image-license-metadata

## Decisions applied in this pass

- Adopt the user-supplied PNG by Matias Mesa as the official ForgeGod mascot source of truth.
- Keep WAITDEAD as the software author and maintainer while crediting Matias Mesa as the mascot creator in visible repo surfaces and site metadata.
- Publish contributor credit in both the README and a top-level `CONTRIBUTORS.md` file so the first design collaboration is visible without hunting through commit history.
- Add structured image credit to the website for the official mascot asset rather than relying only on plain text.

## Implementation notes

- `docs/mascot.png` now matches the approved 2026 mascot artwork from Matias Mesa.
- `docs/mascot.webp`, `docs/mascot-192.webp`, `docs/mascot.svg`, `docs/og-image.png`, and `docs/og-image.webp` were regenerated from that approved source.
- `README.md`, `README.es.md`, `CONTRIBUTING.md`, `CONTRIBUTORS.md`, and `docs/index.html` now carry explicit contributor credit for the mascot design.
