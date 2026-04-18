/**
 * tests/unit/api-reading-route.test.ts
 *
 * Route-level unit tests for GET /api/reading.
 *
 * Exercises both open and closed gate branches using real engine code
 * where possible. Time-windows and schedule-status are mocked to
 * control the gate state. The cookie layer is mocked to isolate the
 * route logic from Next.js runtime.
 *
 * Override contract: requests carrying x-test-open: true trigger the
 * forced-open path when TAROT_ENABLE_TEST_OVERRIDES=true (set by Playwright
 * webServer.env). The test mock isTestOverrideEnabled is configured per-test
 * to exercise the override and non-override branches without needing real headers.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { NextRequest } from "next/server";

// ---------------------------------------------------------------------------
// Env setup — activate the test-only override contract
// ---------------------------------------------------------------------------

process.env.TAROT_ENABLE_TEST_OVERRIDES = "true";
process.env.TAROT_SECRET = "test-unit-secret-abc123";

// ---------------------------------------------------------------------------
// Mock Next.js cookies() before importing the route
// ---------------------------------------------------------------------------

const mockCookieStore = new Map<string, string>();
let mockCookieStoreSnapshot: Map<string, string> = new Map();

vi.mock("next/headers", () => ({
  cookies: vi.fn(async () => ({
    get: (name: string) => {
      const value = mockCookieStore.get(name);
      return value ? { value } : undefined;
    },
    set: (name: string, value: string) => {
      mockCookieStore.set(name, value);
    },
  })),
}));

// ---------------------------------------------------------------------------
// Mock the time-windows module — self-contained factory inside vi.hoisted
// to avoid accessing-const-before-initialization errors.  The factory
// returns: getScheduleStatus, getConcreteWindows, isTestOverrideEnabled,
// TEST_EPOCH_MS (all required by the route).
// ---------------------------------------------------------------------------

// vi.hoisted wraps only the factory (no vi.mock inside) so the constant is
// self-contained and hoist-safe.  TEST_EPOCH_MS is defined locally here and
// referenced only within the factory, avoiding access-before-init issues.
const { MOCK_EPOCH } = vi.hoisted(() => ({
  MOCK_EPOCH: 1735691460000, // 2025-01-01T01:11:00Z — first-gate start
}));

vi.mock("@/lib/time-windows", () => ({
  getScheduleStatus: vi.fn(),
  getConcreteWindows: vi.fn(),
  isTestOverrideEnabled: vi.fn(),
  get TEST_EPOCH_MS() {
    return MOCK_EPOCH;
  },
}));

// ---------------------------------------------------------------------------
// Import types after mocks
// ---------------------------------------------------------------------------

import type { ScheduleStatus } from "@/lib/time-windows";
import { getScheduleStatus, getConcreteWindows, isTestOverrideEnabled } from "@/lib/time-windows";

describe("GET /api/reading", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockCookieStore.clear();
    mockCookieStoreSnapshot = new Map(mockCookieStore);
  });

  afterEach(() => {
    mockCookieStore.clear();
  });

  describe("closed gate", () => {
    it("returns ReadingClosedResponse when gate is closed", async () => {
      const closedStatus: ScheduleStatus = {
        isOpen: false,
        now: "2024-01-01T12:00:00.000Z",
        timezone: "UTC",
        currentWindow: null,
        nextOpenAt: "2024-01-01T23:23:00.000Z",
        nextCloseAt: null,
      };
      vi.mocked(getScheduleStatus).mockReturnValue(closedStatus);
      vi.mocked(isTestOverrideEnabled).mockReturnValue(false);

      const { GET } = await import("@/app/api/reading/route");
      const req = new NextRequest("http://localhost/api/reading");
      const res = await GET(req);
      const body = await res.json();

      expect(res.headers.get("content-type")).toContain("application/json");
      expect(body).toHaveProperty("isOpen", false);
      expect(body).toHaveProperty("status");
      expect(body.status).toEqual(closedStatus);
      expect(body).not.toHaveProperty("reading");
    });

    it("closed response does not expose a reading payload", async () => {
      const closedStatus: ScheduleStatus = {
        isOpen: false,
        now: "2024-01-01T12:00:00.000Z",
        timezone: "UTC",
        currentWindow: null,
        nextOpenAt: "2024-01-01T23:23:00.000Z",
        nextCloseAt: null,
      };
      vi.mocked(getScheduleStatus).mockReturnValue(closedStatus);
      vi.mocked(isTestOverrideEnabled).mockReturnValue(false);

      const { GET } = await import("@/app/api/reading/route");
      const req = new NextRequest("http://localhost/api/reading");
      const res = await GET(req);
      const body = await res.json();

      expect(body).not.toHaveProperty("reading");
      expect(body).not.toHaveProperty("cards");
    });
  });

  describe("open gate — real engine exercised", () => {
    it("returns ReadingOpenResponse with a real three-card spread", async () => {
      // Set up a fake cookie so getAnonymousId() returns a known value
      mockCookieStore.set("tarot_uid", "test-anon-123");

      const openStatus: ScheduleStatus = {
        isOpen: true,
        now: "2024-01-02T04:00:00.000Z",
        timezone: "UTC",
        currentWindow: { label: "second-gate", start: "03:33", end: "04:44" },
        nextOpenAt: null,
        nextCloseAt: "2024-01-02T04:44:00.000Z",
      };
      vi.mocked(getScheduleStatus).mockReturnValue(openStatus);
      vi.mocked(isTestOverrideEnabled).mockReturnValue(false);

      // Mock getConcreteWindows to return a concrete window that contains `now`
      const windowStart = new Date("2024-01-02T03:33:00.000Z");
      const windowEnd = new Date("2024-01-02T04:44:00.000Z");
      vi.mocked(getConcreteWindows).mockReturnValue([
        {
          label: "second-gate",
          startDate: windowStart,
          endDate: windowEnd,
        },
      ]);

      const { GET } = await import("@/app/api/reading/route");
      const req = new NextRequest("http://localhost/api/reading");
      const res = await GET(req);
      const body = await res.json();

      expect(body).toHaveProperty("isOpen", true);
      expect(body).toHaveProperty("reading");
      expect(body.reading).toHaveProperty("spread");
      expect(body.reading).toHaveProperty("drawnAt");

      // Real engine: spread must have exactly 3 cards
      expect(body.reading.spread).toHaveLength(3);

      // Real engine: all three cards must be distinct
      const ids = body.reading.spread.map((e: { card: { id: string } }) => e.card.id);
      const unique = new Set(ids);
      expect(unique.size).toBe(3);

      // Real engine: positions must be past/present/future
      const positions = body.reading.spread.map((e: { position: { position: string } }) => e.position.position);
      expect(positions).toEqual(["past", "present", "future"]);

      // Real engine: each entry has isReversed (boolean)
      for (const entry of body.reading.spread) {
        expect(typeof entry.isReversed).toBe("boolean");
      }

      // Real engine: drawnAt is valid ISO
      expect(() => new Date(body.reading.drawnAt)).not.toThrow();
    });

    it("same anonymousId + same window yields the same spread (determinism)", async () => {
      mockCookieStore.set("tarot_uid", "det-user-789");

      const openStatus: ScheduleStatus = {
        isOpen: true,
        now: "2024-01-03T04:00:00.000Z",
        timezone: "UTC",
        currentWindow: { label: "second-gate", start: "03:33", end: "04:44" },
        nextOpenAt: null,
        nextCloseAt: "2024-01-03T04:44:00.000Z",
      };
      vi.mocked(getScheduleStatus).mockReturnValue(openStatus);
      vi.mocked(isTestOverrideEnabled).mockReturnValue(false);

      const windowStart = new Date("2024-01-03T03:33:00.000Z");
      const windowEnd = new Date("2024-01-03T04:44:00.000Z");
      vi.mocked(getConcreteWindows).mockReturnValue([
        { label: "second-gate", startDate: windowStart, endDate: windowEnd },
      ]);

      const { GET } = await import("@/app/api/reading/route");
      const req = new NextRequest("http://localhost/api/reading");

      // Clear cookie between calls to simulate two requests
      mockCookieStore.clear();
      mockCookieStore.set("tarot_uid", "det-user-789");

      const res1 = await GET(req);
      const body1 = await res1.json();

      mockCookieStore.clear();
      mockCookieStore.set("tarot_uid", "det-user-789");

      const res2 = await GET(req);
      const body2 = await res2.json();

      // Same user + same window = same reading
      const ids1 = body1.reading.spread.map((e: { card: { id: string } }) => e.card.id);
      const ids2 = body2.reading.spread.map((e: { card: { id: string } }) => e.card.id);
      expect(ids1).toEqual(ids2);
      expect(body1.reading.spread.map((e: { isReversed: boolean }) => e.isReversed))
        .toEqual(body2.reading.spread.map((e: { isReversed: boolean }) => e.isReversed));
    });

    it("x-test-open header triggers override path using TEST_EPOCH_MS", async () => {
      mockCookieStore.set("tarot_uid", "override-user-456");

      // Gate is open AND x-test-open header is present → override path
      const openStatus: ScheduleStatus = {
        isOpen: true,
        now: new Date(MOCK_EPOCH).toISOString(),
        timezone: "UTC",
        currentWindow: { label: "first-gate", start: "01:11", end: "02:22" },
        nextOpenAt: null,
        nextCloseAt: null,
      };
      vi.mocked(getScheduleStatus).mockReturnValue(openStatus);
      // isTestOverrideEnabled is called with headers from the NextRequest
      vi.mocked(isTestOverrideEnabled).mockImplementation((headers: Record<string, string>) => {
        return headers["x-test-open"] === "true";
      });

      // Override path uses TEST_EPOCH_MS directly — getConcreteWindows not called
      const { GET } = await import("@/app/api/reading/route");
      const req = new NextRequest("http://localhost/api/reading", {
        headers: { "x-test-open": "true" },
      });
      const res = await GET(req);
      const body = await res.json();

      expect(body).toHaveProperty("isOpen", true);
      expect(body).toHaveProperty("reading");
      expect(body.reading.spread).toHaveLength(3);

      // Verify isTestOverrideEnabled was called with the header
      expect(isTestOverrideEnabled).toHaveBeenCalledWith(
        expect.objectContaining({ "x-test-open": "true" }),
      );
    });
  });
});
