/**
 * tests/unit/api-status-route.test.ts
 *
 * Route-level unit tests for GET /api/status.
 * Mocks getScheduleStatus to exercise the handler without hitting
 * the Phase 1 closed-stub implementation.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import type { ScheduleStatus } from "@/lib/time-windows";

// Mock the time-windows module before importing the route
vi.mock("@/lib/time-windows", () => ({
  getScheduleStatus: vi.fn(),
}));

// Import after mock is set up
const { getScheduleStatus } = await import("@/lib/time-windows");

describe("GET /api/status", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("returns ScheduleStatus when gate is closed", async () => {
    const closedStatus: ScheduleStatus = {
      isOpen: false,
      now: "2024-01-01T12:00:00.000Z",
      timezone: "UTC",
      currentWindow: null,
      nextOpenAt: "2024-01-01T23:23:00.000Z",
      nextCloseAt: null,
    };
    vi.mocked(getScheduleStatus).mockReturnValue(closedStatus);

    // Dynamically import to pick up the mocked module
    const { GET } = await import("@/app/api/status/route");
    const res = await GET();
    const body = await res.json();

    expect(res.headers.get("content-type")).toContain("application/json");
    expect(body).toEqual(closedStatus);
    expect(body.isOpen).toBe(false);
  });

  it("returns ScheduleStatus when gate is open", async () => {
    const openStatus: ScheduleStatus = {
      isOpen: true,
      now: "2024-01-01T03:00:00.000Z",
      timezone: "UTC",
      currentWindow: { label: "first-gate", start: "01:11", end: "02:22" },
      nextOpenAt: null,
      nextCloseAt: "2024-01-01T02:22:00.000Z",
    };
    vi.mocked(getScheduleStatus).mockReturnValue(openStatus);

    const { GET } = await import("@/app/api/status/route");
    const res = await GET();
    const body = await res.json();

    expect(body).toEqual(openStatus);
    expect(body.isOpen).toBe(true);
  });
});
