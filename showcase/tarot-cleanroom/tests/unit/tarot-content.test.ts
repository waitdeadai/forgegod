/**
 * tests/unit/tarot-content.test.ts
 *
 * Unit tests for lib/tarot-content.ts
 * Validates deck integrity: 78 cards, unique IDs, correct suit counts.
 */

import { describe, it, expect } from "vitest";
import {
  TAROT_DECK,
  MAJOR_ARCANA,
  MINOR_ARCANA,
  DECK_SIZE,
} from "@/lib/tarot-content";
import { TarotCardSchema } from "@/content/tarot/deck";

describe("tarot-content deck integrity", () => {
  describe("DECK_SIZE", () => {
    it("must be exactly 78 cards", () => {
      expect(DECK_SIZE).toBe(78);
    });
  });

  describe("TAROT_DECK", () => {
    it("has exactly 78 entries", () => {
      expect(TAROT_DECK).toHaveLength(78);
    });

    it("all cards have a non-empty id", () => {
      for (const card of TAROT_DECK) {
        expect(card.id).toBeTruthy();
        expect(typeof card.id).toBe("string");
        expect(card.id.length).toBeGreaterThan(0);
      }
    });

    it("all card IDs are unique", () => {
      const ids = TAROT_DECK.map((c) => c.id);
      const unique = new Set(ids);
      expect(unique.size).toBe(ids.length);
    });

    it("all cards have required fields", () => {
      for (const card of TAROT_DECK) {
        expect(card).toHaveProperty("id");
        expect(card).toHaveProperty("name");
        expect(card).toHaveProperty("suit");
        expect(card).toHaveProperty("arcanaIndex");
        expect(card).toHaveProperty("uprightMeaning");
        expect(card).toHaveProperty("reversedMeaning");
        expect(card).toHaveProperty("keywords");
        expect(card).toHaveProperty("symbolism");
      }
    });

    it("no card has an empty upright or reversed meaning", () => {
      for (const card of TAROT_DECK) {
        expect(card.uprightMeaning.length).toBeGreaterThan(0);
        expect(card.reversedMeaning.length).toBeGreaterThan(0);
      }
    });
  });

  describe("MAJOR_ARCANA", () => {
    it("has exactly 22 cards", () => {
      expect(MAJOR_ARCANA).toHaveLength(22);
    });

    it("all major arcana cards have suit 'major'", () => {
      for (const card of MAJOR_ARCANA) {
        expect(card.suit).toBe("major");
      }
    });

    it("major arcana indices range from 0 to 21", () => {
      const indices = MAJOR_ARCANA.map((c) => c.arcanaIndex).sort((a, b) => a - b);
      expect(indices[0]).toBe(0);
      expect(indices[indices.length - 1]).toBe(21);
      expect(indices).toHaveLength(22);
    });
  });

  describe("MINOR_ARCANA", () => {
    it("has exactly 56 cards", () => {
      expect(MINOR_ARCANA).toHaveLength(56);
    });

    it("no minor arcana card has suit 'major'", () => {
      for (const card of MINOR_ARCANA) {
        expect(card.suit).not.toBe("major");
      }
    });

    it("all minor arcana cards belong to wands, cups, swords, or pentacles", () => {
      const validSuits = new Set(["wands", "cups", "swords", "pentacles"]);
      for (const card of MINOR_ARCANA) {
        expect(validSuits.has(card.suit)).toBe(true);
      }
    });

    it("each minor suit has exactly 14 cards (Ace through King)", () => {
      const bySuit: Record<string, number> = {};
      for (const card of MINOR_ARCANA) {
        bySuit[card.suit] = (bySuit[card.suit] ?? 0) + 1;
      }
      for (const suit of ["wands", "cups", "swords", "pentacles"]) {
        expect(bySuit[suit]).toBe(14);
      }
    });
  });

  describe("keywords and symbolism normalization from raw JSON", () => {
    /**
     * Regression: raw JSON cards with omitted `keywords` and `symbolism`
     * must be accepted and normalized to concrete `[]` arrays.
     * This mirrors what happens when loadAndValidate parses a real JSON shard.
     */
    it("normalizes missing keywords to []", () => {
      const rawCard = {
        id: "test-normalize-keywords",
        name: "Test Card",
        suit: "major",
        arcanaIndex: 0,
        uprightMeaning: "Test upright.",
        reversedMeaning: "Test reversed.",
        // keywords intentionally omitted
        symbolism: ["test-symbol"],
      };
      const parsed = TarotCardSchema.parse(rawCard);
      expect(parsed.keywords).toEqual([]);
    });

    it("normalizes missing symbolism to []", () => {
      const rawCard = {
        id: "test-normalize-symbolism",
        name: "Test Card",
        suit: "major",
        arcanaIndex: 0,
        uprightMeaning: "Test upright.",
        reversedMeaning: "Test reversed.",
        keywords: ["test-keyword"],
        // symbolism intentionally omitted
      };
      const parsed = TarotCardSchema.parse(rawCard);
      expect(parsed.symbolism).toEqual([]);
    });

    it("normalizes both missing keywords and symbolism to []", () => {
      const rawCard = {
        id: "test-normalize-both",
        name: "Test Card",
        suit: "major",
        arcanaIndex: 0,
        uprightMeaning: "Test upright.",
        reversedMeaning: "Test reversed.",
        // both keywords and symbolism intentionally omitted
      };
      const parsed = TarotCardSchema.parse(rawCard);
      expect(parsed.keywords).toEqual([]);
      expect(parsed.symbolism).toEqual([]);
    });

    it("preserves explicitly provided keywords and symbolism", () => {
      const rawCard = {
        id: "test-preserve",
        name: "Test Card",
        suit: "major",
        arcanaIndex: 0,
        uprightMeaning: "Test upright.",
        reversedMeaning: "Test reversed.",
        keywords: ["courage", "action"],
        symbolism: ["sun", "mountain"],
      };
      const parsed = TarotCardSchema.parse(rawCard);
      expect(parsed.keywords).toEqual(["courage", "action"]);
      expect(parsed.symbolism).toEqual(["sun", "mountain"]);
    });
  });

  describe("suit completeness", () => {
    it("major arcana are all from the major suit", () => {
      expect(MAJOR_ARCANA.every((c) => c.suit === "major")).toBe(true);
    });

    it("minor arcana contain no major-suit cards", () => {
      expect(MINOR_ARCANA.some((c) => c.suit === "major")).toBe(false);
    });

    it("the union of major and minor arcana equals the full deck", () => {
      const majorIds = new Set(MAJOR_ARCANA.map((c) => c.id));
      const minorIds = new Set(MINOR_ARCANA.map((c) => c.id));
      // No overlap
      let overlap = 0;
      for (const id of majorIds) {
        if (minorIds.has(id)) overlap++;
      }
      expect(overlap).toBe(0);
      // Total = 78
      expect(majorIds.size + minorIds.size).toBe(78);
    });
  });
});
