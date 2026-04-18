import { NextRequest, NextResponse } from "next/server";
import {
  defaultLocale,
  getPreferredLocale,
  isLocale,
  localeCookieName,
  locales,
} from "@/lib/i18n";

function shouldBypass(pathname: string): boolean {
  return (
    pathname.startsWith("/api") ||
    pathname.startsWith("/_next") ||
    pathname.startsWith("/favicon") ||
    pathname.startsWith("/robots.txt") ||
    pathname.startsWith("/sitemap.xml") ||
    pathname.startsWith("/manifest.webmanifest") ||
    /\.[a-z0-9]+$/i.test(pathname)
  );
}

function detectLocale(request: NextRequest) {
  const cookieLocale = request.cookies.get(localeCookieName)?.value;
  if (cookieLocale && isLocale(cookieLocale)) {
    return cookieLocale;
  }

  return getPreferredLocale(request.headers.get("accept-language"));
}

export default function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  if (shouldBypass(pathname)) {
    return NextResponse.next();
  }

  const pathLocale = locales.find(
    (locale) => pathname === `/${locale}` || pathname.startsWith(`/${locale}/`),
  );

  if (pathLocale) {
    const response = NextResponse.next();
    response.cookies.set(localeCookieName, pathLocale, {
      path: "/",
      sameSite: "lax",
      maxAge: 60 * 60 * 24 * 365,
    });
    return response;
  }

  const locale = detectLocale(request) ?? defaultLocale;
  const redirected = request.nextUrl.clone();
  redirected.pathname =
    pathname === "/" ? `/${locale}` : `/${locale}${pathname}`;

  return NextResponse.redirect(redirected);
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|.*\\..*).*)"],
};
