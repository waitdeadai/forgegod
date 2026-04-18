/**
 * lib/reading-engine.ts
 *
 * Deterministic three-card tarot reading engine.
 *
 * Responsibilities:
 * - produce a valid three-card spread from the full 78-card deck
 * - prevent duplicate cards in a single draw (enforced by seeded shuffle)
 * - attach position labels (past / present / future)
 * - combine with the content layer
 * - determinism: same {anonymousId, ritualWindowStartEpoch} always yields same spread
 */

import { createHmac } from "node:crypto";
import { TAROT_DECK } from "@/lib/tarot-content";
import type { TarotCard } from "@/lib/tarot-content";

// ---------------------------------------------------------------------------
// Types (re-exported for consumers)
// ---------------------------------------------------------------------------

export type { Suit, TarotCard } from "@/lib/tarot-content";

export type Position = "past" | "present" | "future";

export interface SpreadPosition {
  position: Position;
  label: string;
  description: string;
}

export interface Reading {
  spread: Array<{
    position: SpreadPosition;
    card: TarotCard;
    isReversed: boolean;
  }>;
  drawnAt: string; // ISO timestamp
}

/** Standard three-card past/present/future spread */
export const SPREAD: SpreadPosition[] = [
  {
    position: "past",
    label: "Past",
    description: "What has led you here",
  },
  {
    position: "present",
    label: "Present",
    description: "What is unfolding now",
  },
  {
    position: "future",
    label: "Future",
    description: "What approaches on the horizon",
  },
];

// ---------------------------------------------------------------------------
// Deterministic seed utilities
// ---------------------------------------------------------------------------

/**
 * Build the canonical seed material string.
 * Concatenates server secret + anonymous ID + window start epoch (ms).
 */
export function buildSeedMaterial(
  anonymousId: string,
  windowStartEpoch: number,
): string {
  const secret = getServerSecret();
  return `${secret}:${anonymousId}:${windowStartEpoch}`;
}

/**
 * Derive a uint32 seed from seed material using HMAC-SHA256.
 * Throws if TAROT_SECRET is not set (fail-fast, no hardcoded fallback).
 */
export function computeSeed(seedMaterial: string): number {
  const secret = getServerSecret();
  const hmac = createHmac("sha256", secret);
  hmac.update(seedMaterial);
  const digest = hmac.digest();
  return digest.readUInt32BE(0);
}

/**
 * Mulberry32 PRNG — fast, seedable, period 2^32.
 * Returns [0, 1) floats from a uint32 seed.
 */
export function createMulberry32(seed: number): () => number {
  return function mulberry32(): number {
    let t = (seed += 0x6d2b79f5);
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/**
 * Fisher-Yates shuffle using a seeded PRNG.
 * Returns a new shuffled copy; does not mutate the input array.
 */
export function seededShuffle<T>(array: readonly T[], prng: () => number): T[] {
  const result = [...array];
  for (let i = result.length - 1; i > 0; i--) {
    const j = Math.floor(prng() * (i + 1));
    [result[i], result[j]] = [result[j]!, result[i]!];
  }
  return result;
}

/**
 * Fail-fast: server secret must be set.
 * Playwright webServer.env provides TAROT_SECRET so E2E tests always have it.
 * Throws with a clear message so misconfiguration is never silent.
 */
function getServerSecret(): string {
  const secret = process.env.TAROT_SECRET;
  if (!secret) {
    throw new Error(
      "tarot-engine: TAROT_SECRET environment variable is not set. " +
        "Set it to a secure random string unique per deployment.",
    );
  }
  return secret;
}

// ---------------------------------------------------------------------------
// Reading generation
// ---------------------------------------------------------------------------

export interface DrawReadingOptions {
  /** Anonymous user ID (from cookie helper) */
  anonymousId: string;
  /** Unix epoch ms of the current ritual window start */
  windowStartEpoch: number;
}

/**
 * Draw a deterministic three-card spread.
 *
 * Determinism: same inputs always produce the same shuffled deck,
 * therefore the same three drawn cards in the same order.
 *
 * @param opts.anonymousId  - stable per-user identifier
 * @param opts.windowStartEpoch - epoch ms of the active ritual window start
 */
export function drawReading(opts: DrawReadingOptions): Reading {
  const seedMaterial = buildSeedMaterial(opts.anonymousId, opts.windowStartEpoch);
  const seed = computeSeed(seedMaterial);
  const prng = createMulberry32(seed);

  // Shuffle the full deck deterministically
  const shuffled = seededShuffle(TAROT_DECK, prng);

  // Draw the first three cards — uniqueness guaranteed by shuffle
  const drawn = shuffled.slice(0, 3);

  // Assign each card to a spread position
  const spread = drawn.map((card, i) => ({
    position: SPREAD[i]!,
    // Half of cards are reversed based on PRNG draw
    isReversed: prng() < 0.5,
    card,
  }));

  return {
    spread,
    drawnAt: new Date().toISOString(),
  };
}

/**
 * Validate that no two cards in a spread share the same id.
 * Used by tests to assert uniqueness guarantees.
 */
export function isValidSpread(spread: Reading["spread"]): boolean {
  const ids = spread.map((entry) => entry.card.id);
  return ids.length === new Set(ids).size;
}
