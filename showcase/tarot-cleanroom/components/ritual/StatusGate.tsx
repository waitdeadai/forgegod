"use client";

import Link from "next/link";
import useSWR from "swr";
import CountdownTimer from "./CountdownTimer";
import type { Locale, TarotMessages } from "@/lib/i18n";

const fetcher = (url: string) => fetch(url).then((r) => r.json());

interface StatusResponse {
  isOpen: boolean;
  now: string;
  timezone: string;
  currentWindow: { label: string; start: string; end: string } | null;
  nextOpenAt: string | null;
  nextCloseAt: string | null;
}

function StatusSkeleton({ copy }: { copy: TarotMessages["status"] }) {
  return (
    <div
      className="status-card surface"
      aria-busy="true"
      aria-label={copy.checking}
    >
      <div className="status-card__indicator status-card__indicator--loading" />
      <div className="status-card__body">
        <p className="status-card__label">{copy.label}</p>
        <p className="status-card__value status-card__value--skeleton">
          {copy.checking}
        </p>
      </div>
    </div>
  );
}

function GateOpen({
  nextCloseAt,
  copy,
  countdown,
  readingHref,
}: {
  nextCloseAt: string | null;
  copy: TarotMessages["status"];
  countdown: TarotMessages["countdown"];
  readingHref: string;
}) {
  return (
    <div className="status-card status-card--open surface">
      <div
        className="status-card__indicator status-card__indicator--open"
        aria-hidden="true"
      />
      <div className="status-card__body">
        <p className="status-card__label">{copy.label}</p>
        <p className="status-card__value">
          <span
            className="status-card__dot status-card__dot--open"
            aria-hidden="true"
          />
          {copy.open} - {copy.closingSoon}
        </p>
        {nextCloseAt ? (
          <div className="status-card__countdown">
            <p className="status-card__sub">{copy.closesIn}</p>
            <CountdownTimer
              targetIso={nextCloseAt}
              onComplete={copy.closed}
              labels={{
                ariaPrefix: copy.closesIn,
                day: countdown.units.day,
                hour: countdown.units.hour,
                minute: countdown.units.minute,
                second: countdown.units.second,
              }}
            />
          </div>
        ) : (
          <p className="status-card__sub">{copy.enterNow}</p>
        )}
        <div className="status-card__actions">
          <Link className="btn btn--primary" href={readingHref}>
            {copy.enterNow}
          </Link>
        </div>
      </div>
    </div>
  );
}

function GateClosed({
  nextOpenAt,
  copy,
  countdown,
}: {
  nextOpenAt: string;
  copy: TarotMessages["status"];
  countdown: TarotMessages["countdown"];
}) {
  return (
    <div className="status-card status-card--closed surface">
      <div
        className="status-card__indicator status-card__indicator--closed"
        aria-hidden="true"
      />
      <div className="status-card__body">
        <p className="status-card__label">{copy.label}</p>
        <p className="status-card__value">
          <span
            className="status-card__dot status-card__dot--closed"
            aria-hidden="true"
          />
          {copy.closed}
        </p>
        <p className="status-card__sub">{copy.nextOpeningIn}</p>
        <div className="status-card__countdown">
          <CountdownTimer
            targetIso={nextOpenAt}
            onComplete={copy.opening}
            labels={{
              ariaPrefix: copy.nextOpeningIn,
              day: countdown.units.day,
              hour: countdown.units.hour,
              minute: countdown.units.minute,
              second: countdown.units.second,
            }}
          />
        </div>
      </div>
    </div>
  );
}

export default function StatusGate({
  locale,
  messages,
}: {
  locale: Locale;
  messages: Pick<TarotMessages, "status" | "countdown">;
}) {
  const { data, error } = useSWR<StatusResponse>("/api/status", fetcher, {
    refreshInterval: 30_000,
    revalidateOnFocus: true,
  });
  const readingHref = `/${locale}/reading`;

  if (error) {
    return (
      <div className="status-card surface status-card--error">
        <div
          className="status-card__indicator status-card__indicator--error"
          aria-hidden="true"
        />
        <div className="status-card__body">
          <p className="status-card__label">{messages.status.label}</p>
          <p className="status-card__value">{messages.status.unableToCheck}</p>
        </div>
      </div>
    );
  }

  if (!data) {
    return <StatusSkeleton copy={messages.status} />;
  }

  if (data.isOpen) {
    return (
      <GateOpen
        nextCloseAt={data.nextCloseAt}
        copy={messages.status}
        countdown={messages.countdown}
        readingHref={readingHref}
      />
    );
  }

  if (data.nextOpenAt) {
    return (
      <GateClosed
        nextOpenAt={data.nextOpenAt}
        copy={messages.status}
        countdown={messages.countdown}
      />
    );
  }

  return (
    <div className="status-card surface status-card--closed">
      <div
        className="status-card__indicator status-card__indicator--closed"
        aria-hidden="true"
      />
      <div className="status-card__body">
        <p className="status-card__label">{messages.status.label}</p>
        <p className="status-card__value">{messages.status.closed}</p>
      </div>
    </div>
  );
}
