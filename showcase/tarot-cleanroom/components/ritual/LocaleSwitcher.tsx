import Link from "next/link";
import {
  type Locale,
  getMessages,
  localizedPath,
  locales,
} from "@/lib/i18n";

export default function LocaleSwitcher({
  currentLocale,
  pathname,
}: {
  currentLocale: Locale;
  pathname: "/" | "/reading";
}) {
  const copy = getMessages(currentLocale).nav;

  return (
    <nav
      className="locale-switcher"
      aria-label={copy.languageLabel}
    >
      {locales.map((locale) => {
        const label =
          locale === "en" ? copy.english : copy.spanish;
        const active = locale === currentLocale;

        return (
          <Link
            key={locale}
            href={localizedPath(locale, pathname)}
            hrefLang={locale}
            locale={false}
            className={[
              "locale-switcher__link",
              active ? "locale-switcher__link--active" : "",
            ].join(" ")}
            aria-current={active ? "true" : undefined}
          >
            {label}
          </Link>
        );
      })}
    </nav>
  );
}
