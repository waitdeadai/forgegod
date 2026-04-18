import { notFound } from "next/navigation";
import ReadingExperience from "@/components/ritual/ReadingExperience";
import { getMessages, isLocale } from "@/lib/i18n";

export default async function LocaleReadingPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;

  if (!isLocale(locale)) {
    notFound();
  }

  const messages = getMessages(locale);
  return <ReadingExperience locale={locale} messages={messages} />;
}
