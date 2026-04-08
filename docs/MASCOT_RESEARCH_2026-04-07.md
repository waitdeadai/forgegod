# ForgeGod Mascot Research Notes

Date verified: 2026-04-07

## Source-backed direction

- Adobe's mascot design guidance says a mascot should have its own personality, should be designed with multiple use cases in mind, and usually works as a supplementary brand asset rather than the only logo. It also recommends vector-ready simplification for scalability.
  Source: https://www.adobe.com/my_en/creativecloud/design/discover/mascot-logo-design.html

- Adobe Express' 2026 design trends emphasize organic and imperfect design plus a warm, personal visual style. That supports moving away from overly sterile pixel minimalism toward a more human, character-led mark.
  Source: https://www.adobe.com/express/learn/blog/design-trends-2026

## Decisions applied in this pass

- Keep the cyan pyramid, halo, and white `1` as the non-negotiable identity anchors.
- Treat the detailed illustrated mascot as the primary expressive brand asset for web, social cards, and repo presentation.
- Keep the CLI banner and SVG as simplified companions, not literal attempts to reproduce the full illustration.
- Preserve strong silhouette legibility so the mascot still works at icon sizes.
- Avoid direct resemblance to well-known triangle mascots by keeping ForgeGod's distinct halo, circuitry body, centered eye treatment, and numeric pupil.

## Implementation notes

- `docs/mascot.png` and derived web assets now use the user-supplied 2026 reference direction as the base.
- `docs/og-image.png` and `docs/og-image.webp` were regenerated to match the updated mascot.
- `docs/mascot.svg` was refreshed to align with the illustrated mascot instead of the old minimal placeholder.
