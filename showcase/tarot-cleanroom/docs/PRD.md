# Tarot 3:33 PRD

## Product Summary

Tarot 3:33 is a ritualized tarot web app that only opens during configured
windows. Outside those windows, visitors see the next opening time and a
beautiful waiting state. During open windows, they can complete a guided tarot
reading for free.

This is a ForgeGod showcase product. It exists to prove that ForgeGod can build
and ship a polished, real-world app from zero.

## Design Direction

This is a ForgeGod showcase product. The visual language is **ForgeGod's own brand**:
- **Primary accent**: `#44d9f3` (ForgeGod CYAN — logo mark, key elements, CTAs)
- **Background**: `#0c0c0c` (near-black)
- **Surface**: `#141414`
- **Display font**: "Syne" — geometric, futuristic sans-serif (Google Fonts)
- **Body font**: "DM Sans" — clean modern sans-serif
- **Mono font**: "JetBrains Mono" — timestamps, technical values
- **Gate open**: `#44d9f3` cyan with glow pulse
- **Gate closed**: `#737373` muted gray
- The product must feel like a precision ForgeGod artifact — geometric, minimal, dark
- NO mystical purple, NO gold accents, NO Playfair Display, NO occult aesthetic
- See `docs/DESIGN.md` for the complete design specification

## v1 Goals

- Ship a mobile-first tarot experience with strong visual identity.
- Enforce opening windows correctly and consistently.
- Offer one excellent free reading flow instead of many weak ones.
- Make the product feel launch-ready even without payments.
- Keep the stack simple enough that ForgeGod can build it end-to-end under the
  current harness.

## v1 Non-Goals

- payments
- subscriptions
- user accounts
- saved reading history in the cloud
- notifications
- AI-generated runtime readings
- marketplaces, admin backoffice, or CMS

## Core User Stories

### 1. Closed-state visitor

As a visitor, when the ritual window is closed, I want to understand:

- that the app is currently closed
- when it opens next
- what the experience is
- that the site is intentional, not broken

### 2. Open-state visitor

As a visitor, when the window is open, I want to:

- enter the reading flow immediately
- feel a sense of ritual and progression
- get a complete reading without needing an account

### 3. Mobile visitor

As a phone user, I want the product to feel native-quality:

- readable typography
- no horizontal scroll
- clear touch targets
- elegant animation that does not break usability

## v1 Feature Set

### Public landing

- hero section
- live open/closed status
- next opening countdown
- explanation of how the reading works
- strong mobile-first CTA

### Reading flow

v1 ships one spread only:

- `Past / Present / Future` three-card reading

Reading flow:

1. intro / ritual step
2. shuffle / reveal interaction
3. three card reveal
4. meaning view
5. reflection / closing state

### Schedule logic

- app is governed by a canonical timezone
- open windows are config-driven
- closed routes never expose the actual reading flow

### Content system

- tarot deck content lives locally in typed content files
- each card has:
  - name
  - suit / major arcana info
  - upright meaning
  - reversed meaning or v1 policy to disable reversals
  - short interpretation snippets per position

### SEO / sharing

- metadata
- OG image support
- sitemap / robots

## v1 Product Decisions

### Free first

Keep the first version fully free. The goal is to prove:

- the experience
- the harness
- the quality bar

before adding billing complexity.

### No runtime AI in v1

Do not call models from the app at runtime in the first release.

Reason:

- cheaper
- simpler
- more deterministic
- easier to test
- better for first production showcase

### Config beats magic for time windows

The user-facing idea is mystical; the implementation should be explicit.

v1 uses a schedule config file as the source of truth for windows instead of
embedding clever but opaque time-generation logic.

## Acceptance Criteria

- open/closed status is correct for the configured timezone
- closed users cannot access the reading route by URL alone
- open users can finish the full reading without auth
- the app works at `320px` width without horizontal scroll
- all primary controls are at least `44x44` CSS px
- unit and E2E tests cover the schedule engine and the main reading journey
- the app is deployable to Vercel without manual server setup

## v2 Hooks, But Not Now

The codebase should leave clean seams for later:

- paid readings
- Mercado Pago / Lemon Squeezy / crypto
- waitlist / reminders
- AI oracle mode
- saved reading history
