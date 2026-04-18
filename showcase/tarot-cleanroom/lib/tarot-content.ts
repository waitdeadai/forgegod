/**
 * lib/tarot-content.ts
 *
 * Typed tarot content layer — thin re-export from the deterministic deck source.
 *
 * All 78-card content lives in content/tarot/deck.ts which assembles and validates
 * at module load from clean JSON shards:
 *   - major-arcana.json      → 22 cards
 *   - minor-pentacles.json   → 14 cards
 *   - minor-swords.json      → 14 cards
 *   - minor-wands.json      → 14 cards
 *   - minor-cups.json        → 14 cards
 *
 * This file re-exports the validated deck for consumers (reading-engine, tests).
 */

export {
  DECK as TAROT_DECK,
  MAJOR as MAJOR_ARCANA,
  MINOR as MINOR_ARCANA,
  DECK_SIZE,
  TarotCardSchema,
  SuitEnum,
} from "@/content/tarot/deck";

export type { TarotCard, Suit } from "@/content/tarot/deck";
