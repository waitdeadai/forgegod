"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import TarotEmblem from "@/components/ritual/TarotEmblem";
import { defaultLocale, getMessages, isLocale } from "@/lib/i18n";

export default function LocaleNotFound() {
  const params = useParams<{ locale: string }>();
  const locale =
    params?.locale && isLocale(params.locale) ? params.locale : defaultLocale;
  const messages = getMessages(locale);

  return (
    <main className="reading-page">
      <div className="container">
        <div className="route-not-found">
          <TarotEmblem size={52} />
          <span className="route-not-found__eyebrow">{messages.notFound.eyebrow}</span>
          <h1 className="route-not-found__title">{messages.notFound.title}</h1>
          <p className="route-not-found__body">{messages.notFound.body}</p>
          <Link href={`/${locale}`} className="btn btn--secondary">
            {messages.notFound.home}
          </Link>
        </div>
      </div>
    </main>
  );
}
