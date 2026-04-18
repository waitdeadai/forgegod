"use client";

import { useParams } from "next/navigation";
import TarotEmblem from "@/components/ritual/TarotEmblem";
import { defaultLocale, getMessages, isLocale } from "@/lib/i18n";

export default function LocaleLoading() {
  const params = useParams<{ locale: string }>();
  const locale =
    params?.locale && isLocale(params.locale) ? params.locale : defaultLocale;
  const messages = getMessages(locale);

  return (
    <main className="reading-page">
      <div className="container">
        <div className="route-loading">
          <TarotEmblem size={44} />
          <p className="route-loading__title">{messages.loading.title}</p>
          <p className="route-loading__body">{messages.loading.body}</p>
        </div>
      </div>
    </main>
  );
}
