import type { MetadataRoute } from "next";
import { locales, localizedPath, siteUrl } from "@/lib/i18n";

export default function sitemap(): MetadataRoute.Sitemap {
  const updatedAt = new Date();

  return locales.flatMap((locale) => [
    {
      url: `${siteUrl}${localizedPath(locale, "/")}`,
      lastModified: updatedAt,
      changeFrequency: "weekly",
      priority: 1,
    },
    {
      url: `${siteUrl}${localizedPath(locale, "/reading")}`,
      lastModified: updatedAt,
      changeFrequency: "weekly",
      priority: 0.8,
    },
  ]);
}
