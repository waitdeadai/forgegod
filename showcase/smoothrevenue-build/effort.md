# Effort — Smoothrevenue.com Build

> Process integrity standard for building smoothrevenue.com — an elite Claude Partner implementation firm marketing site.

## 1. Process Philosophy

Thorough execution is non-negotiable. Every story requires: research before code, minimum 2 drafts, explicit verification evidence (test output, lint output, browser check), and iterative refinement.

The first draft is never the best draft. Speed is secondary to correctness. We build enterprise-grade marketing sites — not prototypes. Single-pass completion is a shortcut. "Good enough" is not good enough.

Every agent MUST:
1. Research the target aesthetic and comparable sites before writing code
2. Produce a first draft and review it critically
3. Produce a second draft incorporating improvements
4. Show verification evidence before claiming done

## 2. Verification Requirements

Every story must produce verification evidence before claiming done:

- `ruff check .` — output showing 0 errors
- Browser console check — 0 errors
- All external resources (fonts, CDN) return HTTP 200
- No placeholder content ("Lorem ipsum", "TODO", "FIXME", "placeholder")
- All form fields are functional with proper validation
- i18n toggle works — all visible text changes when toggled
- Responsive at 375px (mobile), 768px (tablet), 1440px (desktop)
- All links navigate to valid pages or anchors
- WCAG 2.1 AA: 4.5:1 contrast ratio, keyboard navigation works

## 3. Iteration Standards

- **Minimum drafts per task**: 2 (thorough mode)
- **Maximum single-pass completion**: NEVER — single-pass is a shortcut
- **Review cycles before accept**: 2
- **Research MUST precede implementation**: YES
- **Always verify**: YES
- **No shortcuts**: YES

## 4. Forbidden Shortcuts

The following are BLOCKED and will trigger REDO:

- **Single-pass language**: "Done.", "Complete.", "All set.", "Finished."
- **Good enough language**: "good enough", "should work", "looks good", "probably correct"
- **Skipped verification**: "tests can be added later", "no need to verify", "skip lint"
- **Placeholder code**: "// TODO", "FIXME", "placeholder", "stub"
- **Hedging language**: "might work", "probably fine", "should be fine", "we believe"
- **Generic copy**: "We help companies..." without specifics, "seamless", "holistic", "best-in-class"
- **Assumptions**: "assuming correctness", "assume it works"

## 5. Effort Levels

| Level | Min Drafts | Always Verify | No Shortcuts |
|-------|-----------|---------------|--------------|
| efficient | 1 | false | false |
| thorough | 2 | true | true |
| exhaustive | 3 | true | true |
| perfectionist | 4 | true | true |

**Default: thorough**
