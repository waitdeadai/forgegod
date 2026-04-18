/**
 * content/tarot/deck.ts
 *
 * Deterministic TypeScript source of truth for all 78 tarot cards.
 *
 * Content is assembled at module load time from validated repo-local JSON shards.
 * This file is the single integration point for all card data — no other
 * content file is imported directly by the engine layer.
 *
 * Valid shards (all parse cleanly):
 *   - major-arcana.json      → 22 cards (indices 0–21)
 *   - minor-pentacles.json   → 14 cards (Ace–King pentacles)
 *   - minor-swords.json      → 14 cards (Ace–King swords)
 *   - minor-wands.json       → 14 cards (Ace–King wands)
 *   - minor-cups.json        → 14 cards (Ace–King cups)
 *
 * Total: 22 + 14×4 = 78 cards ✓
 */

import { z } from "zod";

import majorArcanaRaw from "@/content/tarot/major-arcana.json";
import minorPentaclesRaw from "@/content/tarot/minor-pentacles.json";
import minorSwordsRaw from "@/content/tarot/minor-swords.json";
import minorWandsRaw from "@/content/tarot/minor-wands.json";
import minorCupsRaw from "@/content/tarot/minor-cups.json";

// ---------------------------------------------------------------------------
// Zod schema — mirrors the invariants enforced in lib/tarot-content.ts
// ---------------------------------------------------------------------------

export const SuitEnum = z.enum(["major", "wands", "cups", "swords", "pentacles"]);
export type Suit = z.infer<typeof SuitEnum>;

export const TarotCardSchema = z.object({
  id: z.string().min(1),
  name: z.string().min(1),
  suit: SuitEnum,
  arcanaIndex: z.number().int().min(0),
  keywords: z.array(z.string()).default([]),
  uprightMeaning: z.string().min(1),
  reversedMeaning: z.string().min(1),
  symbolism: z.array(z.string()).default([]),
});

export type TarotCard = z.infer<typeof TarotCardSchema>;

/** Array schema for a complete deck shard — used to validate each JSON file */
const TarotDeckSchema = z.array(TarotCardSchema);

// ---------------------------------------------------------------------------
// Load and validate each shard
// ---------------------------------------------------------------------------

/**
 * Validate and parse a raw JSON deck shard.
 * Each shard is validated as an array of TarotCards; Zod's `.default([])`
 * on optional fields ensures missing `keywords` and `symbolism` are normalized
 * to concrete `[]` at parse time.
 */
function loadAndValidate(raw: unknown, label: string): TarotCard[] {
  const result = TarotDeckSchema.safeParse(raw);
  if (!result.success) {
    const issues = result.error.issues
      .map((i) => `  [${i.path.join(".")}] ${i.message}`)
      .join("\n");
    throw new Error(`deck: ${label} validation failed\n${issues}`);
  }
  return result.data;
}

const majorArcana = loadAndValidate(majorArcanaRaw, "Major Arcana");
const minorPentacles = loadAndValidate(minorPentaclesRaw, "Minor Pentacles");
const minorSwords = loadAndValidate(minorSwordsRaw, "Minor Swords");
const minorWands = loadAndValidate(minorWandsRaw, "Minor Wands");
const minorCups = loadAndValidate(minorCupsRaw, "Minor Cups");

// ---------------------------------------------------------------------------
// Assemble full deck with build-time invariant checks
// ---------------------------------------------------------------------------

const ALL_CARDS = [
  ...majorArcana,
  ...minorPentacles,
  ...minorSwords,
  ...minorWands,
  ...minorCups,
] as TarotCard[];

// Invariant: exactly 78 cards
if (ALL_CARDS.length !== 78) {
  throw new Error(`deck: must have exactly 78 cards, got ${ALL_CARDS.length}`);
}

// Invariant: all IDs unique
const ids = ALL_CARDS.map((c) => c.id);
if (new Set(ids).size !== ALL_CARDS.length) {
  const dupes = ids.filter((id, i) => ids.indexOf(id) !== i);
  throw new Error(`deck: duplicate card IDs found: ${[...new Set(dupes)].join(", ")}`);
}

// Invariant: Major Arcana exactly 22 cards
if (majorArcana.length !== 22) {
  throw new Error(`deck: Major Arcana must have 22 cards, got ${majorArcana.length}`);
}

// Invariant: Minor Arcana exactly 56 cards (4 suits × 14 ranks)
const minorCount = minorPentacles.length + minorSwords.length + minorWands.length + minorCups.length;
if (minorCount !== 56) {
  throw new Error(`deck: Minor Arcana must have 56 cards, got ${minorCount}`);
}

// Invariant: each minor suit has exactly 14 cards
for (const [suit, cards] of [
  ["pentacles", minorPentacles],
  ["swords", minorSwords],
  ["wands", minorWands],
  ["cups", minorCups],
] as const) {
  if (cards.length !== 14) {
    throw new Error(`deck: ${suit} must have 14 cards, got ${cards.length}`);
  }
}

// ---------------------------------------------------------------------------
// Public exports — these are what lib/tarot-content.ts re-exports
// ---------------------------------------------------------------------------

/** Full 78-card tarot deck, validated at module load */
export const DECK: readonly TarotCard[] = ALL_CARDS;

/** Major Arcana only (22 cards) */
export const MAJOR: readonly TarotCard[] = majorArcana;

/** Minor Arcana only (56 cards, 4 suits × 14 ranks) */
export const MINOR: readonly TarotCard[] = [...minorPentacles, ...minorSwords, ...minorWands, ...minorCups];

/** Total card count — verified to be exactly 78 at module load */
export const DECK_SIZE = ALL_CARDS.length;
