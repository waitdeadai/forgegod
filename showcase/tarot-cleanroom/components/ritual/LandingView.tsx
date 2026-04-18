import Link from "next/link";
import LocaleSwitcher from "./LocaleSwitcher";
import StatusGate from "./StatusGate";
import TarotEmblem from "./TarotEmblem";
import type { Locale, TarotMessages } from "@/lib/i18n";

export default function LandingView({
  locale,
  messages,
}: {
  locale: Locale;
  messages: TarotMessages;
}) {
  const readingHref = `/${locale}/reading`;

  return (
    <main className="landing">
      <div className="landing__topbar container">
        <LocaleSwitcher currentLocale={locale} pathname="/" />
      </div>

      <div className="landing__emblem" aria-hidden="true">
        <div className="landing__logo">
          <TarotEmblem size={48} />
        </div>
      </div>

      <section className="hero container">
        <div className="hero__eyebrow">
          <span className="hero__label">{messages.landing.eyebrow}</span>
        </div>
        <h1 className="hero__title">
          <span className="hero__title-main">{messages.landing.titleMain}</span>
          <span className="hero__title-time">{messages.landing.titleTime}</span>
        </h1>
        <p className="hero__description">{messages.landing.description}</p>
        <div className="hero__cta">
          <Link href={readingHref} className="btn btn--primary btn--glow">
            {messages.landing.enterReading}
          </Link>
          <span className="hero__cta-note">{messages.landing.ctaNote}</span>
        </div>
      </section>

      <section className="status-section container">
        <StatusGate
          locale={locale}
          messages={{
            status: messages.status,
            countdown: messages.countdown,
          }}
        />
      </section>

      <section className="explain container">
        <h2 className="explain__title">{messages.landing.explainTitle}</h2>
        <ol className="explain__steps">
          {messages.landing.steps.map((step) => (
            <li key={step.number} className="explain__step">
              <span className="explain__step-num">{step.number}</span>
              <div>
                <strong>{step.title}</strong> - {step.body}
              </div>
            </li>
          ))}
        </ol>
      </section>

      <footer className="landing__footer">
        <p className="landing__footer-text">
          <span className="landing__footer-brand">{messages.landing.footerLead}</span>
          <span className="landing__footer-sep" aria-hidden="true">
            {" "}
            -{" "}
          </span>
          {messages.landing.footerTail}
        </p>
      </footer>

      <style>{`
        .landing__topbar {
          display: flex;
          justify-content: flex-end;
          padding-top: var(--space-6);
        }

        .landing__emblem {
          display: flex;
          justify-content: center;
          padding-top: var(--space-8);
          padding-bottom: var(--space-4);
        }

        .landing__logo {
          animation: emblem-pulse 4s ease-in-out infinite;
        }

        @keyframes emblem-pulse {
          0%, 100% { opacity: 0.7; }
          50% { opacity: 1; }
        }

        @media (prefers-reduced-motion: reduce) {
          .landing__logo { animation: none; opacity: 0.85; }
        }

        .hero {
          padding-top: var(--space-4);
          padding-bottom: var(--space-8);
          text-align: center;
        }

        .hero__eyebrow {
          margin-bottom: var(--space-3);
        }

        .hero__label {
          font-family: var(--font-mono);
          font-size: 0.6875rem;
          font-weight: 500;
          color: var(--color-cyan);
          letter-spacing: 0.18em;
          text-transform: uppercase;
        }

        .hero__title {
          display: flex;
          flex-direction: column;
          align-items: center;
          margin-bottom: var(--space-4);
        }

        .hero__title-main {
          font-family: var(--font-display);
          font-size: clamp(3rem, 15vw, 5.5rem);
          font-weight: 800;
          color: var(--color-white);
          line-height: 1;
          letter-spacing: -0.04em;
        }

        .hero__title-time {
          font-family: var(--font-mono);
          font-size: clamp(1rem, 5vw, 1.5rem);
          font-weight: 400;
          color: var(--color-cyan);
          letter-spacing: 0.3em;
          margin-top: var(--space-1);
        }

        .hero__description {
          font-size: 1rem;
          color: var(--color-muted);
          max-width: 34ch;
          margin: 0 auto var(--space-8);
          line-height: 1.7;
        }

        .hero__cta {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: var(--space-3);
        }

        .hero__cta-note {
          font-family: var(--font-mono);
          font-size: 0.6875rem;
          color: var(--color-muted);
          letter-spacing: 0.05em;
        }

        .status-section {
          margin-bottom: var(--space-12);
        }

        .status-card {
          display: flex;
          align-items: flex-start;
          gap: var(--space-4);
          padding: var(--space-6);
          border-radius: 12px;
        }

        .status-card__indicator {
          width: 12px;
          height: 12px;
          border-radius: 50%;
          flex-shrink: 0;
          margin-top: 4px;
        }

        .status-card__indicator--open {
          background: var(--color-cyan);
          box-shadow: 0 0 10px rgba(68, 217, 243, 0.8);
          animation: pulse-cyan 2s ease-in-out infinite;
        }

        .status-card__indicator--closed {
          background: var(--color-gate-closed);
        }

        .status-card__indicator--loading {
          background: var(--color-muted);
          animation: pulse-muted 1.5s ease-in-out infinite;
        }

        .status-card__indicator--error {
          background: #f87171;
        }

        @keyframes pulse-cyan {
          0%, 100% { box-shadow: 0 0 6px rgba(68, 217, 243, 0.6); }
          50% { box-shadow: 0 0 16px rgba(68, 217, 243, 1); }
        }

        @keyframes pulse-muted {
          0%, 100% { opacity: 0.4; }
          50% { opacity: 1; }
        }

        @media (prefers-reduced-motion: reduce) {
          .status-card__indicator--open { animation: none; box-shadow: 0 0 10px rgba(68, 217, 243, 0.6); }
          .status-card__indicator--loading { animation: none; opacity: 0.5; }
        }

        .status-card__body {
          flex: 1;
        }

        .status-card__label {
          font-family: var(--font-mono);
          font-size: 0.6875rem;
          font-weight: 500;
          color: var(--color-muted);
          letter-spacing: 0.12em;
          text-transform: uppercase;
          margin-bottom: var(--space-1);
        }

        .status-card__value {
          font-family: var(--font-display);
          font-size: 1.125rem;
          font-weight: 700;
          color: var(--color-white);
          display: flex;
          align-items: center;
          gap: var(--space-2);
        }

        .status-card__value--skeleton {
          color: var(--color-muted);
          font-weight: 400;
          font-family: var(--font-body);
        }

        .status-card__sub {
          font-size: 0.875rem;
          color: var(--color-muted);
          margin-top: var(--space-1);
        }

        .status-card__dot {
          display: inline-block;
          width: 8px;
          height: 8px;
          border-radius: 50%;
          flex-shrink: 0;
        }

        .status-card__dot--open {
          background: var(--color-cyan);
          box-shadow: 0 0 6px rgba(68, 217, 243, 0.8);
        }

        .status-card__dot--closed {
          background: var(--color-gate-closed);
        }

        .status-card__countdown {
          margin-top: var(--space-3);
        }

        .status-card__actions {
          margin-top: var(--space-4);
        }

        .status-card--open {
          border-color: rgba(68, 217, 243, 0.2);
        }

        .status-card--closed {
          border-color: var(--color-surface-alt);
        }

        .status-card--error {
          border-color: rgba(248, 113, 113, 0.3);
        }

        .explain {
          padding-bottom: var(--space-16);
        }

        .explain__title {
          font-size: 0.75rem;
          font-family: var(--font-mono);
          font-weight: 500;
          color: var(--color-muted);
          letter-spacing: 0.15em;
          text-transform: uppercase;
          margin-bottom: var(--space-6);
        }

        .explain__steps {
          list-style: none;
          display: flex;
          flex-direction: column;
          gap: var(--space-6);
        }

        .explain__step {
          display: flex;
          gap: var(--space-4);
        }

        .explain__step-num {
          font-family: var(--font-mono);
          font-size: 0.75rem;
          font-weight: 500;
          color: var(--color-cyan);
          letter-spacing: 0.1em;
          flex-shrink: 0;
          padding-top: 2px;
        }

        .explain__step > div {
          color: var(--color-muted);
          font-size: 0.9375rem;
          line-height: 1.6;
        }

        .explain__step > div strong {
          color: var(--color-white);
          font-weight: 500;
        }

        .landing__footer {
          padding: var(--space-8) 0;
          text-align: center;
          border-top: 1px solid var(--color-surface-alt);
        }

        .landing__footer-text {
          font-family: var(--font-mono);
          font-size: 0.6875rem;
          color: var(--color-muted);
          letter-spacing: 0.08em;
        }

        .landing__footer-brand {
          color: var(--color-cyan);
        }

        @media (max-width: 374px) {
          .hero__title-main {
            font-size: 2.5rem;
          }

          .hero__description {
            font-size: 0.875rem;
          }

          .status-card {
            padding: var(--space-4);
          }
        }
      `}</style>
    </main>
  );
}
