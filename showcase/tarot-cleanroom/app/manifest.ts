import type { MetadataRoute } from "next";
import { defaultLocale, getMessages } from "@/lib/i18n";

export default function manifest(): MetadataRoute.Manifest {
  const messages = getMessages(defaultLocale);

  return {
    name: messages.manifest.name,
    short_name: messages.manifest.shortName,
    description: messages.manifest.description,
    start_url: "/en",
    display: "standalone",
    background_color: "#0c0c0c",
    theme_color: "#0c0c0c",
    icons: [
      {
        src: "/icon.svg",
        sizes: "any",
        type: "image/svg+xml",
      },
    ],
  };
}
