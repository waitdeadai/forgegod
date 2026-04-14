# Taste — Smoothrevenue.com

> Design standard for smoothrevenue.com — inspired by Linear, Vercel, Stripe Radar.

## 1. Visual Theme & Atmosphere

**Dark institutional elegance.** Inspired by Linear, Vercel, Stripe Radar. NOT "AI startup hype" — corporate, serious, trustworthy. Glassmorphism 2.0 refined (not amateur), over sophisticated dark background.

Every pixel signals: "these people have done this 100 times at enterprise scale."

**Mood**: dark, premium, mature, technical, corporate authority

## 2. Reference Benchmarks

- https://linear.app — dark minimal, bento grids, precision typography
- https://vercel.com — institutional clarity, monospace accents, confident whitespace
- https://stripe.com — copy authority, zero hedging, metric-driven

## 3. Color Palette

| Token | Hex | Role |
|-------|-----|------|
| `--bg-base` | `#0a0a0b` | Page background (near-black) |
| `--bg-surface` | `#111114` | Cards, elevated surfaces |
| `--bg-elevated` | `#18181c` | Modals, dropdowns |
| `--border` | `#1e1e24` | Subtle glass edges |
| `--border-glow` | `rgba(255,107,53,0.3)` | Orange hover glow on cards |
| `--text-primary` | `#f0f0f5` | Headings, primary text |
| `--text-secondary` | `#8b8b99` | Body text, muted |
| `--text-tertiary` | `#55555f` | Captions, disabled |
| `--accent-orange` | `#ff6b35` | Primary CTAs, highlights |
| `--accent-orange-dim` | `rgba(255,107,53,0.12)` | Orange glow fills |
| `--accent-blue` | `#3b82f6` | Secondary actions, links |
| `--success` | `#22c55e` | Positive indicators |
| `--error` | `#ef4444` | Error states |

## 4. Typography

- **Headings**: Sora (geometric sans — NOT Poppins)
  - Weights: 400, 500, 600, 700
  - Optical sizing: `font-optical-sizing: auto`
- **Body**: Inter (best body font for B2B SaaS — NOT Lora)
  - Weights: 400, 500, 600
  - Optical sizing: yes
- **Mono**: JetBrains Mono (code, technical labels)
  - Weight: 400, 500

**Scale** (fluid, clamp-based):
- `--text-xs`: clamp(0.75rem, 0.7rem + 0.25vw, 0.875rem)
- `--text-sm`: clamp(0.875rem, 0.8rem + 0.35vw, 1rem)
- `--text-base`: clamp(1rem, 0.9rem + 0.5vw, 1.125rem)
- `--text-lg`: clamp(1.125rem, 1rem + 0.6vw, 1.25rem)
- `--text-xl`: clamp(1.25rem, 1.1rem + 0.75vw, 1.5rem)
- `--text-2xl`: clamp(1.5rem, 1.2rem + 1.5vw, 2rem)
- `--text-3xl`: clamp(2rem, 1.5rem + 2.5vw, 3rem)
- `--text-4xl`: clamp(2.5rem, 1.8rem + 3.5vw, 4rem)
- `--text-5xl`: clamp(3rem, 2rem + 5vw, 5.5rem)

**FORBIDDEN**: Poppins, Lora, generic system fonts

## 5. Component Standards

### Button — Primary
- Background: `var(--accent-orange)`, white text, `border-radius: 8px`
- Hover: `filter: brightness(1.1)`, `box-shadow: 0 8px 32px rgba(255,107,53,0.3)`
- Active: `transform: scale(0.98)`
- Disabled: `opacity: 0.5`, `cursor: not-allowed`
- Loading: spinner icon replaces text

### Button — Ghost
- Transparent, `border: 1px solid var(--border)`, white text
- Hover: `bg: rgba(255,255,255,0.05)`

### Glass Card
- Background: `rgba(17,17,20,0.85)`, `backdrop-filter: blur(20px)`
- Border: `1px solid var(--border)`, `border-radius: 16px`
- Box-shadow: `0 4px 24px rgba(0,0,0,0.4)`
- Hover: border → `var(--border-glow)`, `translateY(-2px)`, enhanced shadow

### Form Input
- Background: `var(--bg-elevated)`, `border: 1px solid var(--border)`, `border-radius: 8px`
- Focus: border → `var(--accent-orange)`, `box-shadow: 0 0 0 3px var(--accent-orange-dim)`
- Error: border → `var(--error)`, error message below in red
- Placeholder: `var(--text-tertiary)`

### Accordion
- `<details>` element with custom chevron (Lucide ChevronDown SVG)
- Chevron rotates 180° when open (CSS transform)
- Content: `max-height: 0` → `max-height: 500px` transition, 300ms ease
- Border-bottom between items

## 6. Spatial System

- Base unit: 4px
- Section padding: clamp(64px, 8vw, 128px) vertical
- Card padding: clamp(24px, 3vw, 40px)
- Grid: 12 columns, clamp(16px, 2vw, 24px) gutter
- Max content width: 1280px
- Border radius (cards): 16px
- Border radius (buttons): 8px
- Border radius (inputs): 8px

## 7. Motion Philosophy

- Scroll-triggered: `opacity: 0; transform: translateY(20px)` → `opacity: 1; transform: translateY(0)`
  - Duration: 500ms, `cubic-bezier(0.22, 1, 0.36, 1)`, staggered 80ms between items
- Hover: 200ms `ease-out`, `translateY(-2px)` + enhanced shadow
- Page load: staggered fade-in sections, 100ms delay between
- Focus states: 150ms transition on `box-shadow`
- `prefers-reduced-motion`: all animations disabled when set

**FORBIDDEN**: parallax scrolling, blob animations, particle backgrounds, gradient animations

## 8. Visual Assets

- Icons: Lucide icons (inline SVG, 24px default)
- Images: NO generic stock photos — abstract geometric patterns or data visualizations only
- Decorative: subtle dot grid patterns (opacity 0.03), thin geometric lines
- Favicon: geometric SVG — orange diamond or "SR" monogram
- NO emoji in UI

## 9. Copy Voice

Confident, direct, no hedging. Technical authority without being cold. Results-oriented: specific metrics, timelines, guarantees. Objection handling: address enterprise fears head-on.

### Approved Copy
- "The Execution Layer for Claude at Enterprise Scale"
- "We implement. We operationalize. We deliver revenue from AI investments."
- "95% of AI pilots fail. We engineer for the other 5%."
- "Schedule an Architecture Review" (NOT "Contact Us")

### Forbidden Copy
- "Magic", "revolutionary", "disruptive"
- "Best-in-class" (say WHAT is best-in-class)
- "Seamless", "holistic" (corporate meaningless)
- Generic: "We help companies..." (be specific — say which companies and what specifically)
- Hedging: "we believe", "we think", "we feel"

## 10. Non-Negotiables (Hard Rules)

- NO Tailwind, no Bootstrap, no generic CSS frameworks — pure CSS custom properties
- NO generic stock photos — abstract geometric patterns or data visualizations only
- NO emoji in UI — use Lucide inline SVGs
- NO parallax scrolling, blob animations, particle backgrounds, gradient animations
- All icons: Lucide inline SVGs (copy SVG paths directly, no CDN)
- All text content: specific, not generic marketing copy
- i18n: EN/ES toggle, ALL visible text must change when toggled
- Fonts: Google Fonts only (Sora + Inter + JetBrains Mono)

## 11. Layout & Structure

### Navigation (Sticky)
```
[Logo: "smoothrevenue"] ————————— [Services | Methodology | Case Studies | FAQ] ————————— [EN/ES toggle] [Schedule Review]
```
- Sticky with `backdrop-filter: blur(12px)` + `bg: rgba(10,10,11,0.85)` on scroll
- Mobile: hamburger → full-screen overlay drawer
- Active section: orange underline indicator

### Hero Section (100vh)
- H1: "The Execution Layer for Claude at Enterprise Scale"
- H2: "We implement. We operationalize. We deliver revenue from your AI investments."
- Dual CTA: "Schedule Architecture Review" (orange) + "View Case Studies" (ghost)
- Trust badges: Claude Partner Network (SVG) + AWS Partner + Google Cloud AI Partner
- Background: extremely subtle animated dot grid (opacity 0.04)

### Services Matrix (Bento Grid)
6 cards in asymmetric bento layout:
1. AI Readiness Assessment — "Know where you stand before you commit budget."
2. RAG Architecture & Knowledge Systems — "Turn institutional knowledge into competitive advantage."
3. Legacy Code Modernization — "From technical debt to technical leverage."
4. Agentic Workflow Orchestration — "Autonomous execution at enterprise scale."
5. Defensive AI Security — "Protect your AI systems from prompt injection and model extraction."
6. MLOps & Governance — "Production-grade monitoring, fine-tuning, and compliance."

### Lead Capture Form (10 fields, all required)
1. Company name
2. Industry (dropdown)
3. Company size (dropdown)
4. AI maturity (1-5 visual scale)
5. Innovation budget range (dropdown)
6. Primary use case (textarea, 200 char min)
7. Decision timeline (dropdown)
8. Work email (required, validated)
9. Phone (optional)

### i18n
- JavaScript object with EN/ES strings, `data-i18n` attributes
- Language toggle stores preference in `localStorage` as `lang`
- Default: detect from `navigator.language`, fallback to EN
