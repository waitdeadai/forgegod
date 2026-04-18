# Tarot Cleanroom Research Notes — 2026-04-18

## Scope

Research-backed decisions for moving the showcase from a monolingual prototype to a production-grade bilingual release surface.

## Primary sources

- Next.js App Router internationalization guide:
  https://nextjs.org/docs/app/guides/internationalization
- Next.js metadata and OG file conventions:
  https://nextjs.org/docs/app/getting-started/metadata-and-og-images
- Next.js not-found file convention:
  https://nextjs.org/docs/app/api-reference/file-conventions/not-found
- Next.js loading file convention:
  https://nextjs.org/docs/app/api-reference/file-conventions/loading
- Vercel Web Analytics docs:
  https://vercel.com/docs/analytics/
- Vercel Speed Insights docs:
  https://vercel.com/docs/speed-insights/
- web.dev Core Web Vitals workflow:
  https://web.dev/articles/vitals-tools

## Decisions

1. Locale routing uses path prefixes (`/en`, `/es`) rather than client-only state.
   Reason:
   Next.js App Router guidance recommends locale-aware routing with a top-level locale segment and redirecting missing prefixes based on user preference.

2. Locale copy is centralized in typed dictionaries instead of scattered component literals.
   Reason:
   This keeps metadata, UI copy, and route chrome in sync and prevents translation drift.

3. Launch surfaces are implemented with App Router file conventions rather than ad-hoc `<head>` wiring.
   Reason:
   Next.js file conventions for metadata, OG images, robots, sitemap, loading, and not-found are the current stable path.

4. Observability is wired but gated off outside Vercel.
   Reason:
   The Vercel analytics packages load platform-hosted scripts that 404 in local `next start`, so local and CI validation should not fail on observability bootstrap.

5. Core Web Vitals remain a release gate.
   Target:
   - LCP <= 2.5s
   - INP <= 200ms
   - CLS <= 0.1
   - healthy TTFB on Vercel deployment

## Current limitation

The bilingual shell is production-grade, but tarot card meanings still come from the canonical English content deck. Full bilingual deck content is a separate content-localization tranche.
