"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { track } from "@vercel/analytics";
import CountdownTimer from "./CountdownTimer";
import LocaleSwitcher from "./LocaleSwitcher";
import TarotEmblem from "./TarotEmblem";
import type { Locale, TarotMessages } from "@/lib/i18n";
import { localizeCard } from "@/lib/localized-tarot";
import type { TarotCard as CanonicalTarotCard } from "@/lib/tarot-content";

type TarotCard = CanonicalTarotCard;

interface SpreadEntry {
  position: { position: "past" | "present" | "future"; label: string; description: string };
  card: TarotCard;
  isReversed: boolean;
}

interface ReadingData {
  spread: SpreadEntry[];
  drawnAt: string;
}

interface StatusData {
  isOpen: boolean;
  now: string;
  timezone: string;
  currentWindow: { label: string; start: string; end: string } | null;
  nextOpenAt: string | null;
  nextCloseAt: string | null;
}

type OpenResponse = { isOpen: true; reading: ReadingData };
type ClosedResponse = { isOpen: false; status: StatusData };
type ReadingResponse = OpenResponse | ClosedResponse;
type Phase = "loading" | "intro" | "reveal" | "meaning" | "closing";

function RitualHeader({
  locale,
  title,
  eyebrow,
}: {
  locale: Locale;
  title: string;
  eyebrow: string;
}) {
  return (
    <header className="reading-header surface">
      <div className="reading-header__brand">
        <div className="reading-header__emblem">
          <TarotEmblem size={28} />
        </div>
        <div>
          <p className="reading-header__eyebrow">{eyebrow}</p>
          <p className="reading-header__title">{title}</p>
        </div>
      </div>
      <LocaleSwitcher currentLocale={locale} pathname="/reading" />
    </header>
  );
}

function ClosedGate({
  status,
  locale,
  messages,
}: {
  status: StatusData;
  locale: Locale;
  messages: TarotMessages;
}) {
  return (
    <main className="reading-page">
      <div className="container">
        <RitualHeader
          locale={locale}
          title={messages.metadata.siteName}
          eyebrow={messages.reading.headerEyebrow}
        />
        <div className="reading-closed">
          <TarotEmblem size={56} />
          <div className="reading-closed__badge">{messages.reading.closedBadge}</div>
          <h1 className="reading-closed__title">{messages.reading.closedTitle}</h1>
          <p className="reading-closed__body">{messages.reading.closedBody}</p>
          {status.nextOpenAt && (
            <div className="reading-closed__countdown">
              <p className="reading-closed__countdown-label">
                {messages.reading.nextOpeningIn}
              </p>
              <CountdownTimer
                targetIso={status.nextOpenAt}
                onComplete={messages.countdown.opening}
                labels={{
                  ariaPrefix: messages.countdown.ariaPrefix,
                  day: messages.countdown.units.day,
                  hour: messages.countdown.units.hour,
                  minute: messages.countdown.units.minute,
                  second: messages.countdown.units.second,
                }}
              />
            </div>
          )}
          <Link href={`/${locale}`} className="btn btn--secondary">
            {messages.reading.returnToLanding}
          </Link>
        </div>
      </div>
    </main>
  );
}

function ErrorState({
  locale,
  messages,
}: {
  locale: Locale;
  messages: TarotMessages;
}) {
  return (
    <main className="reading-page">
      <div className="container">
        <RitualHeader
          locale={locale}
          title={messages.metadata.siteName}
          eyebrow={messages.reading.headerEyebrow}
        />
        <div className="reading-error">
          <TarotEmblem size={48} />
          <h1 className="reading-error__title">{messages.reading.unableToBegin}</h1>
          <p className="reading-error__body">{messages.reading.errorBody}</p>
          <Link href={`/${locale}`} className="btn btn--secondary">
            {messages.reading.returnToLanding}
          </Link>
        </div>
      </div>
    </main>
  );
}

function LoadingSkeleton({ messages }: { messages: TarotMessages }) {
  return (
    <div className="reading-loading" aria-busy="true" aria-label={messages.reading.loading}>
      <TarotEmblem size={40} />
      <p className="reading-loading__text">{messages.reading.loading}</p>
    </div>
  );
}

function TarotCardDisplay({
  entry,
  revealed,
  messages,
  locale,
}: {
  entry: SpreadEntry;
  revealed: boolean;
  messages: TarotMessages;
  locale: Locale;
}) {
  const card = localizeCard(entry.card, locale);
  const meaning = entry.isReversed
    ? card.reversedMeaning
    : card.uprightMeaning;
  const positionCopy = messages.reading.positions[entry.position.position];
  const suitLabel =
    messages.reading.suitLabels[card.suit] ?? card.suit;

  return (
    <article
      className={`card-slot ${revealed ? "card-slot--revealed" : "card-slot--hidden"}`}
      aria-label={`${positionCopy.label}: ${card.name}${entry.isReversed ? ` (${messages.reading.reversed})` : ""}`}
    >
      <div className="card-slot__card">
        <div className="card-slot__card-inner">
          <div className="card-slot__back" aria-label={messages.reading.cardBackLabel}>
            <TarotEmblem size={32} />
            <div className="card-slot__back-pattern" />
          </div>
          <div className="card-slot__front">
            <header className="card-slot__header">
              <span className="card-slot__position-label">{positionCopy.label}</span>
              {entry.isReversed && (
                <span className="card-slot__reversed-badge">
                  {messages.reading.reversed}
                </span>
              )}
            </header>
            <h3 className="card-slot__name">{card.name}</h3>
            <p className="card-slot__suit">
              {suitLabel} - {positionCopy.description}
            </p>
            <div className="card-slot__divider" />
            <p className="card-slot__meaning">{meaning}</p>
            {card.keywords.length > 0 && (
              <div className="card-slot__keywords">
                {card.keywords.slice(0, 4).map((keyword) => (
                  <span key={keyword} className="card-slot__keyword">
                    {keyword}
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </article>
  );
}

const PHASE_ORDER = ["intro", "reveal", "meaning", "closing"] as const;

function OpenReading({
  reading,
  locale,
  messages,
}: {
  reading: ReadingData;
  locale: Locale;
  messages: TarotMessages;
}) {
  const [phase, setPhase] = useState<Phase>("intro");
  const [revealedCount, setRevealedCount] = useState(0);

  const formatter = useMemo(
    () =>
      new Intl.DateTimeFormat(locale, {
        hour: "2-digit",
        minute: "2-digit",
      }),
    [locale],
  );

  const currentIdx = PHASE_ORDER.indexOf(phase as (typeof PHASE_ORDER)[number]);

  const isRevealed = (index: number) => {
    if (phase === "intro") return false;
    if (phase === "reveal") return revealedCount > index;
    return true;
  };

  const advanceToReveal = useCallback(() => {
    track("tarot_reveal_started", { locale });
    setPhase("reveal");
    reading.spread.forEach((_, index) => {
      setTimeout(() => setRevealedCount(index + 1), 600 + index * 800);
    });
    setTimeout(
      () => setPhase("meaning"),
      600 + reading.spread.length * 800 + 400,
    );
  }, [locale, reading.spread]);

  const advanceToClosing = useCallback(() => {
    track("tarot_ritual_completed", { locale });
    setPhase("closing");
  }, [locale]);

  return (
    <main className="reading-page">
      <div className="container">
        <RitualHeader
          locale={locale}
          title={messages.metadata.siteName}
          eyebrow={messages.reading.headerEyebrow}
        />
        <div className="reading-flow">
          <div
            className="reading-flow__progress"
            role="list"
            aria-label={messages.reading.phaseAriaLabel}
          >
            {PHASE_ORDER.map((phaseKey, index) => {
              const done = index < currentIdx;
              const active = index === currentIdx;
              return (
                <span
                  key={phaseKey}
                  role="listitem"
                  aria-label={messages.reading.phases[phaseKey]}
                  aria-current={active ? "step" : undefined}
                  className={[
                    "reading-flow__step",
                    done ? "reading-flow__step--done" : "",
                    active ? "reading-flow__step--active" : "",
                  ].join(" ")}
                >
                  {done ? "✓" : index + 1}
                </span>
              );
            })}
          </div>

          {phase === "intro" && (
            <div className="reading-phase reading-phase--intro reading-phase--surface surface">
              <TarotEmblem size={64} />
              <h1 className="reading-phase__title">{messages.reading.introTitle}</h1>
              <p className="reading-phase__body">{messages.reading.introBody}</p>
              <p className="reading-phase__sub">
                {messages.reading.introSubPrefix} {formatter.format(new Date(reading.drawnAt))}
              </p>
              <button
                className="btn btn--primary btn--glow btn--large"
                onClick={advanceToReveal}
                autoFocus
              >
                {messages.reading.revealCards}
              </button>
            </div>
          )}

          {phase === "reveal" && (
            <div className="reading-phase reading-phase--reveal">
              <p className="reading-phase__context">{messages.reading.revealContext}</p>
              <div className="reading-spread reading-spread--ritual">
                {reading.spread.map((entry, index) => (
                  <TarotCardDisplay
                    key={entry.card.id}
                    entry={entry}
                    revealed={isRevealed(index)}
                    messages={messages}
                    locale={locale}
                  />
                ))}
              </div>
            </div>
          )}

          {phase === "meaning" && (
            <div className="reading-phase reading-phase--meaning">
              <h2 className="reading-phase__title">{messages.reading.spreadTitle}</h2>
              <div className="reading-spread reading-spread--ritual">
                {reading.spread.map((entry) => (
                  <TarotCardDisplay
                    key={entry.card.id}
                    entry={entry}
                    revealed={true}
                    messages={messages}
                    locale={locale}
                  />
                ))}
              </div>
              <button
                className="btn btn--secondary btn--large"
                onClick={advanceToClosing}
              >
                {messages.reading.closeRitual}
              </button>
            </div>
          )}

          {phase === "closing" && (
            <div className="reading-phase reading-phase--closing reading-phase--surface surface">
              <TarotEmblem size={56} />
              <h2 className="reading-phase__title">{messages.reading.completeTitle}</h2>
              <p className="reading-phase__body">{messages.reading.completeBody}</p>
              <Link href={`/${locale}`} className="btn btn--secondary">
                {messages.reading.returnToLanding}
              </Link>
            </div>
          )}
        </div>
      </div>
    </main>
  );
}

export default function ReadingExperience({
  locale,
  messages,
}: {
  locale: Locale;
  messages: TarotMessages;
}) {
  const [response, setResponse] = useState<ReadingResponse | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    fetch("/api/reading")
      .then((result) => result.json())
      .then((data: ReadingResponse) => setResponse(data))
      .catch(() => setError(true));
  }, []);

  if (error) {
    return <ErrorState locale={locale} messages={messages} />;
  }

  if (!response) {
    return (
      <main className="reading-page">
        <div className="container">
          <RitualHeader
            locale={locale}
            title={messages.metadata.siteName}
            eyebrow={messages.reading.headerEyebrow}
          />
          <LoadingSkeleton messages={messages} />
        </div>
      </main>
    );
  }

  if (!response.isOpen) {
    return <ClosedGate status={response.status} locale={locale} messages={messages} />;
  }

  return <OpenReading reading={response.reading} locale={locale} messages={messages} />;
}
