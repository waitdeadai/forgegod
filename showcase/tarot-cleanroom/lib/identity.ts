/**
 * lib/identity.ts
 *
 * Anonymous user identity for deterministic tarot readings.
 * Uses Next.js cookies with secure HTTP-only semantics.
 * Identity is a random UUID stored in an HttpOnly, Secure, SameSite=Lax cookie.
 * No authentication — purely pseudonymous tracking for seed consistency.
 */

import { cookies } from "next/headers";
import { randomUUID } from "node:crypto";

const COOKIE_NAME = "tarot_uid";
const COOKIE_MAX_AGE = 60 * 60 * 24 * 365; // 1 year in seconds

/**
 * Get the anonymous user ID for the current request.
 * Creates one if it does not exist.
 * Must be called in a server context (route handler, server component).
 */
export async function getAnonymousId(): Promise<string> {
  const cookieStore = await cookies();
  const existing = cookieStore.get(COOKIE_NAME);

  if (existing?.value) {
    return existing.value;
  }

  const id = randomUUID();
  cookieStore.set(COOKIE_NAME, id, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    maxAge: COOKIE_MAX_AGE,
    path: "/",
  });

  return id;
}
