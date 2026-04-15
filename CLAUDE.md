# Claude Code Memory

@AGENTS.md
@docs/OPERATIONS.md

## Karpathy-Inspired Coding Principles

Four principles to reduce common LLM coding mistakes (derived from Andrej Karpathy's observations on LLM coding pitfalls).

**Tradeoff:** These bias toward caution over speed. For trivial tasks (typos, obvious one-liners), use judgment — not every change needs full rigor.

### 1. Think Before Coding
- **Don't assume. Don't hide confusion. Surface tradeoffs.**
- State assumptions explicitly — if uncertain, ask rather than guess.
- Present multiple interpretations — don't pick silently when ambiguity exists.
- Push back when warranted — if a simpler approach exists, say so.
- Stop when confused — name what's unclear and ask.

### 2. Simplicity First
- **Minimum code that solves the problem. Nothing speculative.**
- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If 200 lines could be 50, rewrite it.

**Test:** Would a senior engineer say this is overcomplicated? If yes, simplify.

### 3. Surgical Changes
- **Touch only what you must. Clean up only your own mess.**
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it — don't delete it.
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

**Test:** Every changed line should trace directly to the user's request.

### 4. Goal-Driven Execution
- **Define success criteria. Loop until verified.**
- Transform tasks into verifiable goals:
  - "Add validation" → "Write tests for invalid inputs, then make them pass"
  - "Fix the bug" → "Write a test that reproduces it, then make it pass"
  - "Refactor X" → "Ensure tests pass before and after"
- For multi-step tasks, state a brief plan before starting:
  ```
  1. [Step] → verify: [check]
  2. [Step] → verify: [check]
  ```
- Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

**How to know it's working:** Fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, clarifying questions come before implementation.
