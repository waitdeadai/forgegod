import { notFound } from "next/navigation";
import LandingView from "@/components/ritual/LandingView";
import { getMessages, isLocale } from "@/lib/i18n";

export default async function LocaleLandingPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;

  if (!isLocale(locale)) {
    notFound();
  }

  const messages = getMessages(locale);
  return <LandingView locale={locale} messages={messages} />;
}
