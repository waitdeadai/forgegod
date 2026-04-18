/**
 * lib/time-windows.ts
 *
 * Phase 2 — Timezone-aware schedule computation for Tarot 3:33.
 *
 * Uses date-fns v4 + @date-fns/tz (official timezone companion).
 *
 * Algorithm:
 *  1. Derive the canonical local date in the configured IANA timezone using TZDate.
 *  2. Materialize candidate concrete windows for yesterday, today, and tomorrow
 *     in that timezone — covers all overnight spans.
 *  3. Construct local wall-clock instants using TZDate.tz() (official API).
 *  4. Compare by epoch milliseconds with half-open [start, end) semantics.
 *
 * Interval semantics: half-open [start, end). A window at "23:23–00:00"
 * is active at 23:59 local but closed at 00:00 local exactly.
 */

import { addDays } from "date-fns";
import { TZDate } from "@date-fns/tz";

export interface TimeWindow {
  label: string;
  /** "HH:MM" in 24-hour local time within the configured timezone */
  start: string;
  /** "HH:MM" in 24-hour local time (may be before start = overnight) */
  end: string;
}

export interface ScheduleStatus {
  isOpen: boolean;
  now: string;                 // ISO timestamp (UTC)
  timezone: string;            // IANA timezone name
  currentWindow: TimeWindow | null;
  nextOpenAt: string | null;  // ISO timestamp (UTC) — next window start
  nextCloseAt: string | null; // ISO timestamp (UTC) — current window end
}

/** Canonical ritual windows — HH:MM in the configured IANA timezone */
export const DEFAULT_WINDOWS: TimeWindow[] = [
  { label: "night-gate",   start: "23:23", end: "00:00" },
  { label: "first-gate",   start: "01:11", end: "02:22" },
  { label: "second-gate",  start: "03:33", end: "04:44" },
];

export const DEFAULT_TIMEZONE = "UTC";

/**
 * Fixed epoch used when the test-only override is active (x-test-open header
 * with TAROT_ENABLE_TEST_OVERRIDES=true). The value is 2025-01-01T01:11:00Z —
 * the start of the "first-gate" window (01:11–02:22 UTC) on a known arbitrary
 * date — so that repeated requests in the same test session produce the same
 * deterministic spread.
 */
export const TEST_EPOCH_MS = 1735691460000; // 2025-01-01T01:11:00Z

/**
 * Check whether the test override is enabled via the x-test-open header.
 * Requires both:
 *   1. TAROT_ENABLE_TEST_OVERRIDES=true (set by Playwright webServer env)
 *   2. x-test-open: true header on the request
 *
 * This is defence-in-depth: the header alone cannot force the gate without
 * the env flag, so closed-path E2E tests that omit the header are safe.
 */
export function isTestOverrideEnabled(headers: Record<string, string>): boolean {
  return (
    process.env.TAROT_ENABLE_TEST_OVERRIDES === "true" &&
    headers["x-test-open"] === "true"
  );
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

function parseHM(hhmm: string): [number, number] {
  const parts = hhmm.split(":").map(Number);
  return [parts[0] ?? 0, parts[1] ?? 0];
}

/**
 * Derive the local calendar date (Y/M/D) from a UTC instant in the given timezone.
 * Uses TZDate to perform the conversion correctly without host-tz dependency.
 */
function toLocalYMD(
  utc: Date,
  tz: string,
): { year: number; month: number; day: number } {
  const local = new TZDate(utc.getTime(), tz) as Date;
  return {
    year: local.getFullYear(),
    month: local.getMonth(),
    day: local.getDate(),
  };
}

/**
 * Convert a local wall-clock time on a given local calendar date to a UTC instant.
 * Uses TZDate.tz() — the official @date-fns/tz constructor for precise
 * local-to-UTC conversion that is independent of the host timezone.
 */
function localTimeToUTC(
  year: number,
  month: number,
  day: number,
  hhmm: string,
  tz: string,
): Date {
  const [h, m] = parseHM(hhmm);
  return TZDate.tz(tz, year, month, day, h, m, 0, 0) as Date;
}

/** Shift a YMD triple by a signed day offset using TZDate arithmetic. */
function shiftYMD(
  year: number,
  month: number,
  day: number,
  offset: number,
  tz: string,
): { year: number; month: number; day: number } {
  const anchor = TZDate.tz(tz, year, month, day, 0, 0, 0, 0) as Date;
  const shifted = addDays(anchor, offset);
  return {
    year: shifted.getFullYear(),
    month: shifted.getMonth(),
    day: shifted.getDate(),
  };
}

// ---------------------------------------------------------------------------
// Concrete window — a resolved [start, end) UTC interval on a specific date
// ---------------------------------------------------------------------------

interface ConcreteWindow {
  label: string;
  startDate: Date;
  endDate: Date;
}

/**
 * Build a concrete window instance on a specific local calendar date.
 * Handles overnight end-times by placing the end on the next calendar day.
 */
function buildConcreteWindow(
  window: TimeWindow,
  year: number,
  month: number,
  day: number,
  tz: string,
): ConcreteWindow {
  const [sh, sm] = parseHM(window.start);
  const [eh, em] = parseHM(window.end);

  const startDate = localTimeToUTC(year, month, day, window.start, tz);

  // Overnight: end time is "before" start time on the same calendar day,
  // so the window ends on the next local calendar day.
  const isOvernight = eh < sh || (eh === sh && em < sm);
  const endYMD = isOvernight ? shiftYMD(year, month, day, 1, tz) : { year, month, day };
  const endDate = localTimeToUTC(endYMD.year, endYMD.month, endYMD.day, window.end, tz);

  return { label: window.label, startDate, endDate };
}

/**
 * All concrete window instances for yesterday, today, and tomorrow (local dates).
 *
 * Materializing THREE consecutive local dates ensures any overnight span that
 * contains `now` will be fully covered. For example, a window 23:23–00:00
 * started yesterday and extends into today — the yesterday instance captures it.
 */
export function getConcreteWindows(
  windows: TimeWindow[],
  utcNow: Date,
  tz: string,
): ConcreteWindow[] {
  const { year, month, day } = toLocalYMD(utcNow, tz);
  const today = { year, month, day };
  const yesterday = shiftYMD(year, month, day, -1, tz);
  const tomorrow = shiftYMD(year, month, day, 1, tz);

  return windows.flatMap((w) => [
    buildConcreteWindow(w, yesterday.year, yesterday.month, yesterday.day, tz),
    buildConcreteWindow(w, today.year, today.month, today.day, tz),
    buildConcreteWindow(w, tomorrow.year, tomorrow.month, tomorrow.day, tz),
  ]);
}

// ---------------------------------------------------------------------------
// Core exports
// ---------------------------------------------------------------------------

/**
 * Find the currently active window, if any, using half-open [start, end) semantics.
 * A window is active when: windowStartEpoch <= nowEpoch < windowEndEpoch.
 */
export function getCurrentWindow(
  windows: TimeWindow[],
  now: Date = new Date(),
  timezone: string = DEFAULT_TIMEZONE,
): TimeWindow | null {
  const candidates = getConcreteWindows(windows, now, timezone);
  const ts = now.getTime();
  for (const cw of candidates) {
    if (ts >= cw.startDate.getTime() && ts < cw.endDate.getTime()) {
      const w = windows.find((w2) => w2.label === cw.label);
      if (w) return w;
    }
  }
  return null;
}

/**
 * Find the next window start instant (UTC), or null if no more windows exist.
 */
export function getNextWindowStart(
  windows: TimeWindow[],
  now: Date = new Date(),
  timezone: string = DEFAULT_TIMEZONE,
): Date | null {
  const ts = now.getTime();
  const candidates = getConcreteWindows(windows, now, timezone);

  let earliest: Date | null = null;
  for (const cw of candidates) {
    if (cw.startDate.getTime() > ts) {
      if (earliest === null || cw.startDate.getTime() < earliest.getTime()) {
        earliest = cw.startDate;
      }
    }
  }
  return earliest;
}

/**
 * Find the next window close instant (UTC) for the window currently open.
 * Returns null if no window is currently open.
 */
export function getNextWindowClose(
  windows: TimeWindow[],
  now: Date = new Date(),
  timezone: string = DEFAULT_TIMEZONE,
): Date | null {
  const current = getCurrentWindow(windows, now, timezone);
  if (!current) return null;

  const ts = now.getTime();
  const candidates = getConcreteWindows(windows, now, timezone);

  for (const cw of candidates) {
    if (
      cw.label === current.label &&
      ts >= cw.startDate.getTime() &&
      ts < cw.endDate.getTime()
    ) {
      return cw.endDate;
    }
  }
  return null;
}

/**
 * Canonical schedule status for the given config and UTC instant.
 * All timestamps are UTC ISO strings; `timezone` is echoed in the response.
 *
 * When the x-test-open request header is present (test env only, gated by
 * TAROT_ENABLE_TEST_OVERRIDES=true), the gate is reported as open using a
 * representative DEFAULT_WINDOWS entry so that E2E tests can exercise the
 * full reading journey deterministically without relying on the real schedule.
 *
 * Closed-path tests that omit the header always hit real schedule logic.
 */
export function getScheduleStatus(
  windows: TimeWindow[] = DEFAULT_WINDOWS,
  timezone: string = DEFAULT_TIMEZONE,
  now: Date = new Date(),
  requestHeaders?: Record<string, string>,
): ScheduleStatus {
  // Test-only: enable deterministic override when BOTH the env flag
  // TAROT_ENABLE_TEST_OVERRIDES=true AND the x-test-open header are present.
  // Use a fixed epoch so the reading engine is deterministic across repeated
  // same-session requests. The TEST_EPOCH_MS lands squarely in first-gate 01:11–02:22 UTC.
  if (isTestOverrideEnabled(requestHeaders ?? {})) {
    const representativeWindow = DEFAULT_WINDOWS[1]!; // first-gate 01:11–02:22
    return {
      isOpen: true,
      now: new Date(TEST_EPOCH_MS).toISOString(),
      timezone,
      currentWindow: representativeWindow,
      nextOpenAt: null,
      nextCloseAt: null,
    };
  }

  const currentWindow = getCurrentWindow(windows, now, timezone);
  const isOpen = currentWindow !== null;

  const nextOpenAt = getNextWindowStart(windows, now, timezone);
  const nextCloseAt = isOpen
    ? getNextWindowClose(windows, now, timezone)
    : null;

  return {
    isOpen,
    now: now.toISOString(),
    timezone,
    currentWindow,
    nextOpenAt: nextOpenAt?.toISOString() ?? null,
    nextCloseAt: nextCloseAt?.toISOString() ?? null,
  };
}
