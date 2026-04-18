/**
 * lib/schemas.ts
 *
 * Shared TypeScript types for the API layer.
 * TarotCard and Reading come from the content layer / reading engine.
 */

import type { TarotCard } from "@/lib/tarot-content";
import type { Reading } from "@/lib/reading-engine";
export type { TarotCard, Reading };

export type { Suit, Position } from "@/lib/reading-engine";
export type { TimeWindow, ScheduleStatus } from "@/lib/time-windows";

/** API response envelope */
export interface ApiResponse<T> {
  data: T;
  ok: boolean;
  error?: string;
}

/** /api/status response */
export type StatusResponse = {
  isOpen: boolean;
  now: string;
  timezone: string;
  currentWindow: { label: string; start: string; end: string } | null;
  nextOpenAt: string | null;
  nextCloseAt: string | null;
};

/** /api/reading response — discriminated by isOpen */
export interface ReadingOpenResponse {
  isOpen: true;
  reading: {
    spread: Array<{
      position: { position: "past" | "present" | "future"; label: string; description: string };
      card: TarotCard;
      isReversed: boolean;
    }>;
    drawnAt: string;
  };
}

export interface ReadingClosedResponse {
  isOpen: false;
  status: StatusResponse;
}

export type ReadingResponse = ReadingOpenResponse | ReadingClosedResponse;
