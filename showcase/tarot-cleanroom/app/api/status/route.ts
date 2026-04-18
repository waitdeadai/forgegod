/**
 * app/api/status/route.ts
 *
 * Returns the current ritual-window schedule status.
 * Server-authoritative: computation uses the canonical timezone from lib/timezone.ts.
 */

import { NextResponse } from "next/server";
import { getScheduleStatus } from "@/lib/time-windows";
import { TIMEZONE } from "@/lib/timezone";
import type { StatusResponse } from "@/lib/schemas";

export async function GET(): Promise<NextResponse<StatusResponse>> {
  const status = getScheduleStatus(undefined, TIMEZONE);
  return NextResponse.json(status);
}
