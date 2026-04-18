/**
 * lib/timezone.ts
 *
 * Timezone utilities for server-authoritative schedule computation.
 *
 * Phase 1 note: returns UTC-based values only. Full timezone-aware
 * scheduling will be implemented in Phase 2 using a proper
 * offset-based approach (not string formatting → Date reconstruction).
 *
 * Key invariant: never reconstruct a Date from formatted wall-clock parts
 * by parsing them as local time — that reinterprets the target timezone
 * as the host timezone and produces wrong instants on non-UTC hosts.
 */

export const TIMEZONE = process.env.TAROT_TIMEZONE ?? "UTC";

/**
 * Get the current UTC instant as an ISO string.
 * Use this as the server-authoritative "now".
 */
export function utcNow(): string {
  return new Date().toISOString();
}

/**
 * Get the current UTC instant as a Date.
 */
export function utcNowDate(): Date {
  return new Date();
}

/**
 * Format a date in a given IANA timezone, returning "HH:MM" in 24h.
 * Uses Intl.DateTimeFormat which is safe because it never reconstructs
 * a Date from wall-clock parts.
 */
export function formatTimeInZone(date: Date, timezone: string): string {
  try {
    return new Intl.DateTimeFormat("en-GB", {
      timeZone: timezone,
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    }).format(date);
  } catch {
    return "00:00";
  }
}
