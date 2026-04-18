import { describe, expect, it } from "vitest";
import { TAROT_DECK } from "@/lib/tarot-content";
import { localizeCard } from "@/lib/localized-tarot";

describe("localized tarot overlay", () => {
  it("returns canonical cards unchanged for english", () => {
    const card = TAROT_DECK[0]!;
    expect(localizeCard(card, "en")).toEqual(card);
  });

  it("applies spanish translations for overlay-backed cards", () => {
    const fool = TAROT_DECK.find((card) => card.id === "the-fool")!;
    const localized = localizeCard(fool, "es");

    expect(localized.name).toBe("El Loco");
    expect(localized.uprightMeaning).toMatch(/salto de fe/i);
    expect(localized.keywords[0]).toBe("comienzos");
  });
});
