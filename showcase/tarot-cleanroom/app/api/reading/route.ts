/**
 * app/api/reading/route.ts
 *
 * Returns a complete three-card reading if the gate is open;
 * a closed-status response otherwise.
 *
 * Server-authoritative: schedule uses canonical timezone from lib/timezone.ts.
 * Determinism: reading is seeded from server secret + anonymous cookie ID
 * + current ritual window start epoch.
 */

import { NextRequest, NextResponse } from "next/server";
import { getScheduleStatus, getConcreteWindows, isTestOverrideEnabled, TEST_EPOCH_MS } from "@/lib/time-windows";
import { TIMEZONE } from "@/lib/timezone";
import { getAnonymousId } from "@/lib/identity";
import { drawReading } from "@/lib/reading-engine";
import type { ReadingResponse } from "@/lib/schemas";

/** Extract lowercase header map from the incoming request. */
function headerMap(request: NextRequest): Record<string, string> {
  const out: Record<string, string> = {};
  request.headers.forEach((value, key) => {
    out[key.toLowerCase()] = value;
  });
  return out;
}

export async function GET(request: NextRequest): Promise<NextResponse<ReadingResponse>> {
  const headers = headerMap(request);
  const status = getScheduleStatus(undefined, TIMEZONE, new Date(), headers);

  if (!status.isOpen) {
    return NextResponse.json({
      isOpen: false,
      status,
    });
  }

  // Gate is open — draw a deterministic reading
  const anonymousId = await getAnonymousId();

  // Use the current window already computed by getScheduleStatus
  const currentWindow = status.currentWindow;
  if (!currentWindow) {
    // Safety net: window just closed between status check and draw
    return NextResponse.json({
      isOpen: false,
      status,
    });
  }

  // When the test override is active (x-test-open header with
  // TAROT_ENABLE_TEST_OVERRIDES=true), use the fixed TEST_EPOCH_MS so that
  // repeated requests in the same session always produce the same spread.
  // Otherwise derive the real window start epoch from the current concrete window.
  let windowStartEpoch: number;
  if (isTestOverrideEnabled(headers)) {
    windowStartEpoch = TEST_EPOCH_MS;
  } else {
    windowStartEpoch = deriveCurrentWindowStartEpoch(
      currentWindow,
      new Date(status.now),
      TIMEZONE,
    );
  }

  const reading = drawReading({
    anonymousId,
    windowStartEpoch,
  });

  return NextResponse.json({
    isOpen: true,
    reading,
  });
}

/**
 * Derive the concrete UTC start epoch for the window that is active
 * at `now` in the given timezone.
 *
 * We reconstruct this by finding the concrete window candidate that
 * contains `now` and returning its start epoch.
 */
function deriveCurrentWindowStartEpoch(
  window: { label: string; start: string; end: string },
  now: Date,
  tz: string,
): number {
  const candidates = getConcreteWindows(
    [{ label: window.label, start: window.start, end: window.end }],
    now,
    tz,
  );
  const ts = now.getTime();
  for (const cw of candidates) {
    if (ts >= cw.startDate.getTime() && ts < cw.endDate.getTime()) {
      return cw.startDate.getTime();
    }
  }
  // Fallback: should never be reached for an open window
  return now.getTime();
}
