/**
 * tests/unit/reading-engine.test.ts
 *
 * Unit tests for lib/reading-engine.ts
 * Coverage: deterministic seed, unique three-card draw, spread structure.
 */

import { describe, it, expect } from "vitest";
import {
  buildSeedMaterial,
  computeSeed,
  createMulberry32,
  seededShuffle,
  drawReading,
  isValidSpread,
  SPREAD,
} from "@/lib/reading-engine";

const TEST_SECRET = "test-tarot-secret-3x33-for-unit-tests-only";

describe("reading-engine: seed utilities", () => {
  describe("buildSeedMaterial", () => {
    it("concatenates secret, anonymousId, and windowStartEpoch", () => {
      const material = buildSeedMaterial("user-abc", 1700000000000);
      expect(material).toContain(TEST_SECRET);
      expect(material).toContain("user-abc");
      expect(material).toContain("1700000000000");
    });

    it("produces different material for different anonymousIds", () => {
      const a = buildSeedMaterial("user-a", 1700000000000);
      const b = buildSeedMaterial("user-b", 1700000000000);
      expect(a).not.toBe(b);
    });

    it("produces different material for different window epochs", () => {
      const a = buildSeedMaterial("user-abc", 1700000000000);
      const b = buildSeedMaterial("user-abc", 1700000001000);
      expect(a).not.toBe(b);
    });
  });

  describe("computeSeed", () => {
    it("is a valid positive uint32", () => {
      const seed = computeSeed("test-material");
      expect(seed).toBeGreaterThanOrEqual(0);
      expect(seed).toBeLessThanOrEqual(0xffffffff);
      expect(Number.isInteger(seed)).toBe(true);
    });

    it("same material always yields same seed (determinism)", () => {
      const material = "consistent-test-material";
      const s1 = computeSeed(material);
      const s2 = computeSeed(material);
      expect(s1).toBe(s2);
    });

    it("different material yields different seed", () => {
      const s1 = computeSeed("material-one");
      const s2 = computeSeed("material-two");
      expect(s1).not.toBe(s2);
    });
  });

  describe("createMulberry32", () => {
    it("returns numbers in [0, 1)", () => {
      const prng = createMulberry32(12345);
      for (let i = 0; i < 100; i++) {
        const n = prng();
        expect(n).toBeGreaterThanOrEqual(0);
        expect(n).toBeLessThan(1);
      }
    });

    it("is deterministic: same seed yields same sequence", () => {
      const prng1 = createMulberry32(99999);
      const prng2 = createMulberry32(99999);
      for (let i = 0; i < 50; i++) {
        expect(prng1()).toBe(prng2());
      }
    });

    it("different seeds yield different sequences", () => {
      const prng1 = createMulberry32(11111);
      const prng2 = createMulberry32(22222);
      let differ = false;
      for (let i = 0; i < 50; i++) {
        if (prng1() !== prng2()) {
          differ = true;
          break;
        }
      }
      expect(differ).toBe(true);
    });
  });

  describe("seededShuffle", () => {
    it("does not mutate the original array", () => {
      const original = [1, 2, 3, 4, 5];
      const prng = createMulberry32(42);
      seededShuffle(original, prng);
      expect(original).toEqual([1, 2, 3, 4, 5]);
    });

    it("returns an array of the same length", () => {
      const original = [1, 2, 3, 4, 5];
      const prng = createMulberry32(42);
      const result = seededShuffle(original, prng);
      expect(result).toHaveLength(original.length);
    });

    it("contains all original elements", () => {
      const original = [1, 2, 3, 4, 5];
      const prng = createMulberry32(42);
      const result = seededShuffle(original, prng);
      expect([...result].sort()).toEqual([1, 2, 3, 4, 5]);
    });

    it("is deterministic: same seed yields same shuffle", () => {
      const original = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];
      const r1 = seededShuffle(original, createMulberry32(77777));
      const r2 = seededShuffle(original, createMulberry32(77777));
      expect(r1).toEqual(r2);
    });
  });
});

describe("reading-engine: drawReading", () => {
  describe("structure", () => {
    it("returns a Reading with spread and drawnAt", () => {
      const reading = drawReading({
        anonymousId: "test-user",
        windowStartEpoch: Date.now(),
      });
      expect(reading).toHaveProperty("spread");
      expect(reading).toHaveProperty("drawnAt");
    });

    it("spread has exactly 3 entries", () => {
      const reading = drawReading({
        anonymousId: "test-user",
        windowStartEpoch: Date.now(),
      });
      expect(reading.spread).toHaveLength(3);
    });

    it("each spread entry has position, card, and isReversed", () => {
      const reading = drawReading({
        anonymousId: "test-user",
        windowStartEpoch: Date.now(),
      });
      for (const entry of reading.spread) {
        expect(entry).toHaveProperty("position");
        expect(entry).toHaveProperty("card");
        expect(entry).toHaveProperty("isReversed");
        expect(typeof entry.isReversed).toBe("boolean");
      }
    });

    it("spread positions are past, present, future in order", () => {
      const reading = drawReading({
        anonymousId: "test-user",
        windowStartEpoch: Date.now(),
      });
      expect(reading.spread[0]?.position.position).toBe("past");
      expect(reading.spread[1]?.position.position).toBe("present");
      expect(reading.spread[2]?.position.position).toBe("future");
    });

    it("drawnAt is a valid ISO timestamp", () => {
      const reading = drawReading({
        anonymousId: "test-user",
        windowStartEpoch: Date.now(),
      });
      expect(Number.isNaN(Date.parse(reading.drawnAt))).toBe(false);
    });
  });

  describe("determinism", () => {
    it("same anonymousId + same windowStartEpoch yields identical spread", () => {
      const epoch = 1700000000000;
      const user = "det-user-xyz";
      const r1 = drawReading({ anonymousId: user, windowStartEpoch: epoch });
      const r2 = drawReading({ anonymousId: user, windowStartEpoch: epoch });
      expect(r1.spread.map((e) => e.card.id)).toEqual(r2.spread.map((e) => e.card.id));
      expect(r1.spread.map((e) => e.isReversed)).toEqual(r2.spread.map((e) => e.isReversed));
    });

    it("same anonymousId + different windowStartEpoch yields different spread", () => {
      const user = "det-user-xyz";
      const r1 = drawReading({ anonymousId: user, windowStartEpoch: 1700000000000 });
      const r2 = drawReading({ anonymousId: user, windowStartEpoch: 1700000001000 });
      const ids1 = r1.spread.map((e) => e.card.id);
      const ids2 = r2.spread.map((e) => e.card.id);
      // At least one card should differ (extremely high probability)
      expect(ids1).not.toEqual(ids2);
    });

    it("different anonymousId + same windowStartEpoch yields different spread", () => {
      const epoch = 1700000000000;
      const r1 = drawReading({ anonymousId: "user-alpha", windowStartEpoch: epoch });
      const r2 = drawReading({ anonymousId: "user-beta", windowStartEpoch: epoch });
      const ids1 = r1.spread.map((e) => e.card.id);
      const ids2 = r2.spread.map((e) => e.card.id);
      expect(ids1).not.toEqual(ids2);
    });
  });

  describe("uniqueness guarantees", () => {
    it("no two cards in a spread share the same id", () => {
      // Draw many readings to increase confidence
      for (let i = 0; i < 10; i++) {
        const reading = drawReading({
          anonymousId: `uniqueness-test-${i}`,
          windowStartEpoch: 1700000000000 + i,
        });
        expect(isValidSpread(reading.spread)).toBe(true);
      }
    });

    it("all three drawn cards are distinct", () => {
      const reading = drawReading({
        anonymousId: "distinct-check",
        windowStartEpoch: 1700000000000,
      });
      const ids = reading.spread.map((e) => e.card.id);
      const unique = new Set(ids);
      expect(unique.size).toBe(3);
    });
  });
});

describe("reading-engine: SPREAD", () => {
  it("has exactly 3 positions", () => {
    expect(SPREAD).toHaveLength(3);
  });

  it("contains past, present, and future positions", () => {
    const positions = SPREAD.map((s) => s.position);
    expect(positions).toContain("past");
    expect(positions).toContain("present");
    expect(positions).toContain("future");
  });

  it("each spread position has required fields", () => {
    for (const entry of SPREAD) {
      expect(typeof entry.position).toBe("string");
      expect(typeof entry.label).toBe("string");
      expect(typeof entry.description).toBe("string");
    }
  });
});

describe("reading-engine: isValidSpread", () => {
  it("returns true for a valid spread", () => {
    const reading = drawReading({
      anonymousId: "valid-spread-test",
      windowStartEpoch: 1700000000000,
    });
    expect(isValidSpread(reading.spread)).toBe(true);
  });

  it("returns false for spread with duplicate card ids", () => {
    const fakeSpread = [
      { position: SPREAD[0]!, card: { id: "the-fool", name: "Fool", suit: "major" as const, arcanaIndex: 0, uprightMeaning: "", reversedMeaning: "", keywords: [], symbolism: [] }, isReversed: false },
      { position: SPREAD[1]!, card: { id: "the-fool", name: "Fool", suit: "major" as const, arcanaIndex: 0, uprightMeaning: "", reversedMeaning: "", keywords: [], symbolism: [] }, isReversed: false },
    ];
    expect(isValidSpread(fakeSpread)).toBe(false);
  });

  it("returns true for spread with unique card ids", () => {
    const fakeSpread = [
      { position: SPREAD[0]!, card: { id: "the-fool", name: "Fool", suit: "major" as const, arcanaIndex: 0, uprightMeaning: "", reversedMeaning: "", keywords: [], symbolism: [] }, isReversed: false },
      { position: SPREAD[1]!, card: { id: "the-magician", name: "Magician", suit: "major" as const, arcanaIndex: 1, uprightMeaning: "", reversedMeaning: "", keywords: [], symbolism: [] }, isReversed: false },
    ];
    expect(isValidSpread(fakeSpread)).toBe(true);
  });
});
