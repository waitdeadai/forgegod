/**
 * lib/seed.ts
 *
 * Re-exports seed utilities from reading-engine for backwards compatibility.
 * The deterministic seed logic lives in lib/reading-engine.ts.
 */

export {
  buildSeedMaterial,
  computeSeed,
  createMulberry32,
  seededShuffle,
} from "@/lib/reading-engine";
