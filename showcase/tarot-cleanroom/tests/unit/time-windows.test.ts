/**
 * tests/unit/time-windows.test.ts
 *
 * Unit tests for lib/time-windows.ts
 * Coverage: getScheduleStatus, window-edge cases, overnight windows, UTC + non-UTC timezones.
 *
 * Semantic contract (half-open [start, end)):
 *   - A window "23:23-00:00" is OPEN at 23:59 and CLOSED at exactly 00:00.
 *   - nextCloseAt < nextOpenAt when currently open (close of current < start of next).
 *   - After 2024-01-01T23:50:00Z, next opening is first-gate at 2024-01-02T01:11:00Z.
 */

import { describe, it, expect } from "vitest";
import {
  getScheduleStatus,
  getCurrentWindow,
  getNextWindowStart,
  getNextWindowClose,
  DEFAULT_WINDOWS,
  DEFAULT_TIMEZONE,
} from "@/lib/time-windows";

describe("time-windows", () => {
  describe("getCurrentWindow", () => {
    it("returns null when before any window", () => {
      const d = new Date("2024-01-01T00:00:00Z");
      expect(getCurrentWindow(DEFAULT_WINDOWS, d)).toBeNull();
    });

    it("returns night-gate during the overnight window", () => {
      const d = new Date("2024-01-01T23:50:00Z");
      const w = getCurrentWindow(DEFAULT_WINDOWS, d);
      expect(w?.label).toBe("night-gate");
    });

    it("returns first-gate during its window", () => {
      const d = new Date("2024-01-01T01:30:00Z");
      const w = getCurrentWindow(DEFAULT_WINDOWS, d);
      expect(w?.label).toBe("first-gate");
    });

    it("returns second-gate during its window", () => {
      const d = new Date("2024-01-01T04:00:00Z");
      const w = getCurrentWindow(DEFAULT_WINDOWS, d);
      expect(w?.label).toBe("second-gate");
    });

    it("returns null just after a window closes", () => {
      const d = new Date("2024-01-01T00:01:00Z");
      expect(getCurrentWindow(DEFAULT_WINDOWS, d)).toBeNull();
    });

    it("returns null between windows", () => {
      const d = new Date("2024-01-01T03:00:00Z");
      expect(getCurrentWindow(DEFAULT_WINDOWS, d)).toBeNull();
    });

    it("handles edge at exact window start (inclusive)", () => {
      const d = new Date("2024-01-01T01:11:00Z");
      const w = getCurrentWindow(DEFAULT_WINDOWS, d);
      expect(w?.label).toBe("first-gate");
    });

    it("handles edge at exact window end (exclusive, closed)", () => {
      const d = new Date("2024-01-01T02:22:00Z");
      expect(getCurrentWindow(DEFAULT_WINDOWS, d)).toBeNull();
    });

    it("overnight window is open at 23:59 (just before midnight)", () => {
      const d = new Date("2024-01-02T23:59:00Z");
      const w = getCurrentWindow(DEFAULT_WINDOWS, d);
      expect(w?.label).toBe("night-gate");
    });

    it("overnight window is closed at exactly midnight (endExclusive)", () => {
      const d = new Date("2024-01-03T00:00:00Z");
      expect(getCurrentWindow(DEFAULT_WINDOWS, d)).toBeNull();
    });
  });

  describe("getNextWindowStart", () => {
    it("returns today's night-gate when called before it", () => {
      const d = new Date("2024-01-01T20:00:00Z");
      const next = getNextWindowStart(DEFAULT_WINDOWS, d);
      expect(next?.getUTCHours()).toBe(23);
      expect(next?.getUTCMinutes()).toBe(23);
      expect(next?.getUTCDate()).toBe(1);
    });

    it("returns first-gate (01:11 UTC Jan 2) after 23:50 UTC Jan 1", () => {
      // Critical required semantic: after night-gate, next opening is first-gate,
      // NOT tomorrow's night-gate (23:23 Jan 2 would be ~22h later).
      // After 2024-01-01T23:50:00Z the night-gate closes at 2024-01-02T00:00:00Z
      // and first-gate opens at 2024-01-02T01:11:00Z.
      const d = new Date("2024-01-01T23:50:00Z");
      const next = getNextWindowStart(DEFAULT_WINDOWS, d);
      expect(next?.getUTCFullYear()).toBe(2024);
      expect(next?.getUTCMonth()).toBe(0); // January
      expect(next?.getUTCDate()).toBe(2);  // Jan 2
      expect(next?.getUTCHours()).toBe(1);
      expect(next?.getUTCMinutes()).toBe(11);
    });

    it("returns night-gate when called after morning windows before night-gate", () => {
      const d = new Date("2024-01-01T05:00:00Z");
      const next = getNextWindowStart(DEFAULT_WINDOWS, d);
      expect(next?.getUTCHours()).toBe(23);
      expect(next?.getUTCMinutes()).toBe(23);
      expect(next?.getUTCDate()).toBe(1);
    });

    it("returns first-gate after night-gate closes at midnight", () => {
      const d = new Date("2024-01-02T00:01:00Z");
      const next = getNextWindowStart(DEFAULT_WINDOWS, d);
      expect(next?.getUTCHours()).toBe(1);
      expect(next?.getUTCMinutes()).toBe(11);
      expect(next?.getUTCDate()).toBe(2);
    });

    it("handles non-UTC timezone America/New_York", () => {
      // 2024-01-01T06:00:00Z = 01:00 EST Jan 1 — before first-gate 01:11 EST
      // first-gate 01:11 EST = 06:11 UTC Jan 1 (same calendar day in EST)
      const windows = [{ label: "ny-gate", start: "01:11", end: "02:22" }];
      const d = new Date("2024-01-01T06:00:00Z");
      const next = getNextWindowStart(windows, d, "America/New_York");
      expect(next?.getUTCHours()).toBe(6);
      expect(next?.getUTCMinutes()).toBe(11);
      expect(next?.getUTCDate()).toBe(1);
    });

    it("handles non-UTC timezone Asia/Tokyo", () => {
      // 2024-01-01T14:00:00Z = 23:00 JST Jan 1 — before night-gate 23:23 JST
      // night-gate 23:23 JST Jan 1 = 14:23 UTC Jan 1
      const windows = [{ label: "tokyo-night", start: "23:23", end: "00:00" }];
      const d = new Date("2024-01-01T14:00:00Z");
      const next = getNextWindowStart(windows, d, "Asia/Tokyo");
      expect(next?.getUTCHours()).toBe(14);
      expect(next?.getUTCMinutes()).toBe(23);
      expect(next?.getUTCDate()).toBe(1);
    });
  });

  describe("getScheduleStatus", () => {
    it("returns isOpen: true during a window", () => {
      const d = new Date("2024-01-01T01:30:00Z");
      const status = getScheduleStatus(DEFAULT_WINDOWS, DEFAULT_TIMEZONE, d);
      expect(status.isOpen).toBe(true);
      expect(status.currentWindow?.label).toBe("first-gate");
    });

    it("returns isOpen: false between windows", () => {
      const d = new Date("2024-01-01T03:00:00Z");
      const status = getScheduleStatus(DEFAULT_WINDOWS, DEFAULT_TIMEZONE, d);
      expect(status.isOpen).toBe(false);
      expect(status.currentWindow).toBeNull();
    });

    it("populates nextOpenAt ISO string when closed", () => {
      const d = new Date("2024-01-01T03:00:00Z");
      const status = getScheduleStatus(DEFAULT_WINDOWS, DEFAULT_TIMEZONE, d);
      expect(typeof status.nextOpenAt).toBe("string");
      expect(status.nextOpenAt).toContain("T");
    });

    it("populates nextCloseAt when open", () => {
      const d = new Date("2024-01-01T01:30:00Z");
      const status = getScheduleStatus(DEFAULT_WINDOWS, DEFAULT_TIMEZONE, d);
      expect(typeof status.nextCloseAt).toBe("string");
      expect(status.nextCloseAt).toContain("T");
    });

    it("nextCloseAt is BEFORE nextOpenAt when open (current ends before next opens)", () => {
      // At 01:30 UTC inside first-gate: close=02:22 UTC, next open=03:33 UTC
      // nextCloseAt (02:22) < nextOpenAt (03:33) — invariant while open
      const d = new Date("2024-01-01T01:30:00Z");
      const status = getScheduleStatus(DEFAULT_WINDOWS, DEFAULT_TIMEZONE, d);
      if (status.nextOpenAt && status.nextCloseAt) {
        expect(new Date(status.nextCloseAt).getTime()).toBeLessThan(
          new Date(status.nextOpenAt).getTime(),
        );
      }
    });

    it("respects custom windows array", () => {
      const customWindows = [{ label: "test-gate", start: "12:00", end: "13:00" }];
      const inside = new Date("2024-01-01T12:30:00Z");
      const insideStatus = getScheduleStatus(customWindows, DEFAULT_TIMEZONE, inside);
      expect(insideStatus.isOpen).toBe(true);
      expect(insideStatus.currentWindow?.label).toBe("test-gate");

      const outside = new Date("2024-01-01T14:00:00Z");
      const outsideStatus = getScheduleStatus(customWindows, DEFAULT_TIMEZONE, outside);
      expect(outsideStatus.isOpen).toBe(false);
    });

    it("uses UTC timezone", () => {
      const d = new Date("2024-01-01T00:00:00Z");
      const status = getScheduleStatus(DEFAULT_WINDOWS, DEFAULT_TIMEZONE, d);
      expect(status.timezone).toBe("UTC");
    });
  });

  describe("overnight window boundary", () => {
    it("night-gate is open at 23:59 UTC (just before midnight)", () => {
      const d = new Date("2024-01-01T23:59:00Z");
      const status = getScheduleStatus(DEFAULT_WINDOWS, DEFAULT_TIMEZONE, d);
      expect(status.isOpen).toBe(true);
      expect(status.currentWindow?.label).toBe("night-gate");
    });

    it("night-gate is CLOSED at exactly 00:00 UTC (endExclusive)", () => {
      // A window "23:23-00:00" ends at exactly 00:00 — half-open [start, end).
      // At exactly 00:00:00.000Z the window is closed.
      const d = new Date("2024-01-02T00:00:00Z");
      const status = getScheduleStatus(DEFAULT_WINDOWS, DEFAULT_TIMEZONE, d);
      expect(status.isOpen).toBe(false);
    });

    it("night-gate is closed at 00:01 UTC", () => {
      const d = new Date("2024-01-02T00:01:00Z");
      const status = getScheduleStatus(DEFAULT_WINDOWS, DEFAULT_TIMEZONE, d);
      expect(status.isOpen).toBe(false);
    });
  });
});
