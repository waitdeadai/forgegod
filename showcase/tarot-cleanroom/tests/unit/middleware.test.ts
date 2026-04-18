import { describe, expect, it } from "vitest";
import { NextRequest } from "next/server";
import middleware from "@/middleware";
import { localeCookieName } from "@/lib/i18n";

describe("locale middleware", () => {
  it("redirects root requests to the preferred locale", () => {
    const request = new NextRequest("http://localhost/", {
      headers: { "accept-language": "es-AR,es;q=0.9,en;q=0.8" },
    });

    const response = middleware(request);

    expect(response.status).toBe(307);
    expect(response.headers.get("location")).toBe("http://localhost/es");
  });

  it("redirects unprefixed routes", () => {
    const request = new NextRequest("http://localhost/reading", {
      headers: { "accept-language": "en-US,en;q=0.9" },
    });

    const response = middleware(request);

    expect(response.status).toBe(307);
    expect(response.headers.get("location")).toBe("http://localhost/en/reading");
  });

  it("passes through locale-prefixed routes and refreshes the cookie", () => {
    const request = new NextRequest("http://localhost/es/reading");

    const response = middleware(request);

    expect(response.headers.get("x-middleware-next")).toBe("1");
    expect(response.cookies.get(localeCookieName)?.value).toBe("es");
  });
});
