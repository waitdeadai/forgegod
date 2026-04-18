import type { Metadata, Viewport } from "next";
import { Analytics } from "@vercel/analytics/next";
import { SpeedInsights } from "@vercel/speed-insights/next";
import { DM_Sans, JetBrains_Mono, Syne } from "next/font/google";
import { notFound } from "next/navigation";
import "../globals.css";
import EmbedResizeBridge from "@/components/ritual/EmbedResizeBridge";
import {
  defaultLocale,
  getMessages,
  isLocale,
  localizedPath,
  locales,
  siteUrl,
} from "@/lib/i18n";

const dmSans = DM_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "700"],
  style: ["normal", "italic"],
  variable: "--font-dm-sans",
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-jetbrains-mono",
  display: "swap",
});

const syne = Syne({
  subsets: ["latin"],
  weight: ["600", "700", "800"],
  variable: "--font-syne",
  display: "swap",
});

export async function generateStaticParams() {
  return locales.map((locale) => ({ locale }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}): Promise<Metadata> {
  const { locale } = await params;

  if (!isLocale(locale)) {
    notFound();
  }

  const messages = getMessages(locale);
  const url = new URL(localizedPath(locale, "/"), siteUrl);

  return {
    metadataBase: new URL(siteUrl),
    title: {
      default: messages.metadata.title,
      template: messages.metadata.titleTemplate,
    },
    description: messages.metadata.description,
    alternates: {
      canonical: url.pathname,
      languages: {
        en: localizedPath("en", "/"),
        es: localizedPath("es", "/"),
        "x-default": localizedPath(defaultLocale, "/"),
      },
    },
    openGraph: {
      type: "website",
      locale: locale === "es" ? "es_AR" : "en_US",
      url: url.pathname,
      siteName: messages.metadata.siteName,
      title: messages.metadata.title,
      description: messages.metadata.description,
    },
    twitter: {
      card: "summary_large_image",
      title: messages.metadata.title,
      description: messages.metadata.description,
      creator: "@forgegod",
    },
    icons: {
      icon: "/icon.svg",
      shortcut: "/icon.svg",
      apple: "/icon.svg",
    },
    robots: {
      index: true,
      follow: true,
    },
  };
}

export const viewport: Viewport = {
  themeColor: "#0c0c0c",
  width: "device-width",
  initialScale: 1,
  maximumScale: 5,
};

export default async function LocaleLayout({
  children,
  params,
}: Readonly<{
  children: React.ReactNode;
  params: Promise<{ locale: string }>;
}>) {
  const { locale } = await params;
  const enableObservability =
    process.env.VERCEL === "1" ||
    process.env.NEXT_PUBLIC_ENABLE_VERCEL_OBSERVABILITY === "true";

  if (!isLocale(locale)) {
    notFound();
  }

  return (
    <html
      lang={locale}
      className={`${dmSans.variable} ${jetbrainsMono.variable} ${syne.variable}`}
    >
      <body>
        <EmbedResizeBridge />
        {children}
        {enableObservability ? (
          <>
            <Analytics />
            <SpeedInsights />
          </>
        ) : null}
      </body>
    </html>
  );
}
