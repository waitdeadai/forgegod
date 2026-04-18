"use client";

import { useEffect } from "react";

const EMBED_MESSAGE_TYPE = "forgegod:showcase-height";

function isAllowedParentOrigin(origin: string): boolean {
  try {
    const url = new URL(origin);

    if (url.protocol !== "https:") {
      return false;
    }

    if (url.hostname === "forgegod.com" || url.hostname === "www.forgegod.com") {
      return true;
    }

    return url.hostname.endsWith(".vercel.app") && url.hostname.startsWith("forgegod-");
  } catch {
    return false;
  }
}

function getParentOrigin(): string | null {
  if (!document.referrer) {
    return null;
  }

  try {
    const origin = new URL(document.referrer).origin;
    return isAllowedParentOrigin(origin) ? origin : null;
  } catch {
    return null;
  }
}

function getDocumentHeight(): number {
  const body = document.body;
  const html = document.documentElement;

  return Math.max(
    body?.scrollHeight ?? 0,
    body?.offsetHeight ?? 0,
    html?.clientHeight ?? 0,
    html?.scrollHeight ?? 0,
    html?.offsetHeight ?? 0,
  );
}

export default function EmbedResizeBridge() {
  useEffect(() => {
    if (window.parent === window) {
      return;
    }

    const parentOrigin = getParentOrigin();

    if (!parentOrigin) {
      return;
    }

    document.documentElement.classList.add("is-embedded");
    document.body.classList.add("is-embedded");

    let rafId = 0;

    const publishHeight = () => {
      cancelAnimationFrame(rafId);
      rafId = window.requestAnimationFrame(() => {
        window.parent.postMessage(
          {
            type: EMBED_MESSAGE_TYPE,
            height: getDocumentHeight(),
            path: window.location.pathname,
          },
          parentOrigin,
        );
      });
    };

    const resizeObserver = new ResizeObserver(() => {
      publishHeight();
    });

    resizeObserver.observe(document.documentElement);
    resizeObserver.observe(document.body);

    const mutationObserver = new MutationObserver(() => {
      publishHeight();
    });

    mutationObserver.observe(document.body, {
      attributes: true,
      childList: true,
      subtree: true,
      characterData: true,
    });

    window.addEventListener("load", publishHeight);
    window.addEventListener("resize", publishHeight);
    window.addEventListener("orientationchange", publishHeight);

    publishHeight();

    return () => {
      cancelAnimationFrame(rafId);
      resizeObserver.disconnect();
      mutationObserver.disconnect();
      window.removeEventListener("load", publishHeight);
      window.removeEventListener("resize", publishHeight);
      window.removeEventListener("orientationchange", publishHeight);
      document.documentElement.classList.remove("is-embedded");
      document.body.classList.remove("is-embedded");
    };
  }, []);

  return null;
}
