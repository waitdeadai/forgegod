import { describe, expect, it } from "vitest";
import {
  getMessages,
  getPreferredLocale,
  localizedPath,
  localeFromPath,
  stripLocale,
} from "@/lib/i18n";

describe("i18n helpers", () => {
  it("prefers spanish from accept-language", () => {
    expect(getPreferredLocale("es-AR,es;q=0.9,en;q=0.8")).toBe("es");
  });

  it("falls back to english for unknown languages", () => {
    expect(getPreferredLocale("fr-FR,fr;q=0.9")).toBe("en");
  });

  it("builds localized paths", () => {
    expect(localizedPath("en", "/")).toBe("/en");
    expect(localizedPath("es", "/reading")).toBe("/es/reading");
  });

  it("strips locale prefixes", () => {
    expect(stripLocale("/en")).toBe("/");
    expect(stripLocale("/es/reading")).toBe("/reading");
  });

  it("extracts locale from pathname", () => {
    expect(localeFromPath("/en/reading")).toBe("en");
    expect(localeFromPath("/es")).toBe("es");
    expect(localeFromPath("/fr")).toBeNull();
  });

  it("returns bilingual message dictionaries", () => {
    expect(getMessages("en").landing.enterReading).toMatch(/Enter/);
    expect(getMessages("es").landing.enterReading).toMatch(/Entrar/);
  });
});
