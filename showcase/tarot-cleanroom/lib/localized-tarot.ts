import esDeck from "@/content/locales/es-deck.json";
import type { TarotCard } from "@/lib/tarot-content";
import type { Locale } from "@/lib/i18n";

type TarotOverlay = Record<
  string,
  {
    name: string;
    keywords: string[];
    uprightMeaning: string;
    reversedMeaning: string;
    symbolism: string[];
  }
>;

const overlays: Partial<Record<Locale, TarotOverlay>> = {
  es: esDeck as TarotOverlay,
};

export function localizeCard(card: TarotCard, locale: Locale): TarotCard {
  const overlay = overlays[locale]?.[card.id];
  if (!overlay) {
    return card;
  }

  return {
    ...card,
    name: overlay.name,
    keywords: overlay.keywords,
    uprightMeaning: overlay.uprightMeaning,
    reversedMeaning: overlay.reversedMeaning,
    symbolism: overlay.symbolism,
  };
}
