# Tarot Architecture

## Recommended Stack

- `Next.js 16` App Router
- `TypeScript` strict mode
- server-first rendering
- `Vitest` + React Testing Library for logic/unit coverage
- `Playwright` for E2E and mobile coverage
- deploy on `Vercel`

## Why this stack

- It is directly supported by current official docs.
- It matches the Vercel deployment path already used by ForgeGod.
- It minimizes bespoke infrastructure.
- It gives us clean conventions for metadata, OG images, route handlers, and
  testing.

## Architectural Principles

### 1. Server-authoritative schedule

The current open/closed state must be computed on the server from:

- canonical timezone
- current server time
- schedule config

The client can render countdown UX, but it cannot be the source of truth.

### 2. Route handlers for business logic

Use route handlers for:

- `/api/status`
- `/api/reading`

Do not put the core ritual/schedule rules into `proxy.ts`.

### 3. Static tarot content

Tarot card copy should live in repo content files, not a DB, in v1.

Benefits:

- free
- deterministic
- easy to diff
- easy to test
- good for ForgeGod loops

### 4. Minimal client state

Use client state only where interaction needs it:

- countdown UI
- reveal transitions
- selected cards in-session

Avoid turning the app into a client-heavy SPA for no reason.

## Proposed App Structure

```text
tarot/
  app/
    (marketing)/
      page.tsx
      about/page.tsx
    reading/
      page.tsx
      loading.tsx
      error.tsx
    api/
      status/route.ts
      reading/route.ts
    opengraph-image.tsx
    layout.tsx
    manifest.ts
    robots.ts
    sitemap.ts
  components/
    ritual/
    layout/
    cards/
    motion/
  content/
    tarot/
      major-arcana.json
      minor-arcana.json
  lib/
    time-windows.ts
    tarot-deck.ts
    reading-engine.ts
    timezone.ts
    schemas.ts
  tests/
    unit/
    e2e/
```

## Core Modules

### `lib/time-windows.ts`

Responsibilities:

- parse schedule config
- determine current open/closed state
- compute next opening and closing
- serialize status for UI/API

This module needs the highest test coverage.

### `lib/reading-engine.ts`

Responsibilities:

- produce a valid three-card spread
- prevent duplicate cards in a single draw
- attach position labels
- combine with content layer

### `app/api/status/route.ts`

Returns:

- `isOpen`
- `now`
- `timezone`
- `nextOpenAt`
- `nextCloseAt`
- current window label

### `app/api/reading/route.ts`

If closed:

- returns a closed-state response

If open:

- returns a complete reading payload

No login, no persistence, no payment checks in v1.

## Schedule Model

Use an explicit config file. Example:

```ts
export const windows = [
  { label: "night-gate", start: "23:23", end: "00:00" },
  { label: "first-gate", start: "01:11", end: "02:22" },
  { label: "second-gate", start: "03:33", end: "04:44" },
]
```

Important:

- overnight windows must be supported
- timezone must be explicit
- schedule logic must not depend on local browser time

## Mobile and Performance Constraints

- no horizontal overflow at `320px`
- reserve card/media dimensions to avoid layout shift
- keep the first route lightweight
- optimize for good `LCP`, `CLS`, and `INP`

## Security / Stability

Even without payments, the app should still include:

- schema validation for route input/output
- no secret leakage to the client
- no dependence on client time for access control
- stable fallback UI for closed state and API failure

## Why no database in v1

There is no user auth, billing, or persistent state requirement yet.

Adding a DB now increases:

- ops complexity
- migration surface
- ForgeGod work surface
- testing scope

without improving the first milestone.
