/**
 * tests/setup.ts
 *
 * Vitest global setup — imports jest-dom matchers
 * and configures the jsdom environment for React testing.
 */

import "@testing-library/jest-dom";

// Set the server secret for deterministic seed testing.
// This must be set before any module that reads process.env.TAROT_SECRET is loaded.
process.env.TAROT_SECRET ??= "test-tarot-secret-3x33-for-unit-tests-only";
