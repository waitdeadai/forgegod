import { ImageResponse } from "next/og";
import { defaultLocale, getMessages, isLocale } from "@/lib/i18n";

export const size = {
  width: 1200,
  height: 630,
};

export const contentType = "image/png";

export default async function OpenGraphImage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale: rawLocale } = await params;
  const locale = isLocale(rawLocale) ? rawLocale : defaultLocale;
  const messages = getMessages(locale);

  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          background:
            "radial-gradient(circle at top, rgba(68,217,243,0.25), transparent 44%), linear-gradient(180deg, #08090c 0%, #0f1118 100%)",
          color: "#f5f7fb",
          padding: "64px",
          fontFamily: "sans-serif",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <div
            style={{
              display: "flex",
              gap: "14px",
              alignItems: "center",
              fontSize: 28,
              letterSpacing: "0.2em",
              textTransform: "uppercase",
              color: "#44d9f3",
            }}
          >
            <span>{messages.og.eyebrow}</span>
          </div>
          <div
            style={{
              width: 110,
              height: 110,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              borderRadius: "999px",
              border: "1px solid rgba(68,217,243,0.35)",
              boxShadow: "0 0 40px rgba(68,217,243,0.16)",
            }}
          >
            <div
              style={{
                width: 72,
                height: 72,
                border: "1px solid rgba(68,217,243,0.45)",
                clipPath: "polygon(50% 0%, 100% 100%, 0% 100%)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "#44d9f3",
                fontSize: 38,
                fontWeight: 800,
              }}
            >
              1
            </div>
          </div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
          <div
            style={{
              fontSize: 96,
              fontWeight: 800,
              lineHeight: 0.92,
              letterSpacing: "-0.06em",
            }}
          >
            {messages.og.headline}
          </div>
          <div
            style={{
              maxWidth: 820,
              fontSize: 30,
              lineHeight: 1.35,
              color: "#b8c0cc",
            }}
          >
            {messages.og.subline}
          </div>
        </div>

        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            fontSize: 22,
            color: "#ffe17b",
            letterSpacing: "0.08em",
            textTransform: "uppercase",
          }}
        >
          <span>{locale.toUpperCase()}</span>
          <span>forgegod</span>
        </div>
      </div>
    ),
    size,
  );
}
