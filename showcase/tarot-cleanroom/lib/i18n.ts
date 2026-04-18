export const locales = ["en", "es"] as const;
export type Locale = (typeof locales)[number];

export const defaultLocale: Locale = "en";
export const localeCookieName = "forgegod_tarot_locale";

export const localeLabels: Record<Locale, string> = {
  en: "English",
  es: "Español",
};

export interface TarotMessages {
  metadata: {
    title: string;
    titleTemplate: string;
    description: string;
    siteName: string;
  };
  nav: {
    languageLabel: string;
    english: string;
    spanish: string;
  };
  landing: {
    eyebrow: string;
    titleMain: string;
    titleTime: string;
    description: string;
    enterReading: string;
    ctaNote: string;
    statusOpenCta: string;
    explainTitle: string;
    steps: Array<{
      number: string;
      title: string;
      body: string;
    }>;
    footerLead: string;
    footerTail: string;
  };
  status: {
    label: string;
    checking: string;
    open: string;
    closed: string;
    closingSoon: string;
    closesIn: string;
    nextOpeningIn: string;
    unableToCheck: string;
    enterNow: string;
    opening: string;
  };
    reading: {
      headerEyebrow: string;
      closedBadge: string;
    closedTitle: string;
    closedBody: string;
    nextOpeningIn: string;
    returnToLanding: string;
    unableToBegin: string;
    errorBody: string;
    loading: string;
    introTitle: string;
    introBody: string;
    introSubPrefix: string;
    revealCards: string;
    revealContext: string;
    spreadTitle: string;
    closeRitual: string;
    completeTitle: string;
    completeBody: string;
    phaseAriaLabel: string;
      phases: {
        intro: string;
        reveal: string;
        meaning: string;
        closing: string;
      };
      reversed: string;
      cardBackLabel: string;
      suitLabels: Record<string, string>;
      positions: Record<
        "past" | "present" | "future",
      {
        label: string;
        description: string;
      }
    >;
  };
  countdown: {
    complete: string;
    opening: string;
    ariaPrefix: string;
    units: {
      day: string;
      hour: string;
      minute: string;
      second: string;
    };
  };
  loading: {
    title: string;
    body: string;
  };
  notFound: {
    eyebrow: string;
    title: string;
    body: string;
    home: string;
  };
  og: {
    eyebrow: string;
    headline: string;
    subline: string;
  };
  manifest: {
    name: string;
    shortName: string;
    description: string;
  };
}

const messages: Record<Locale, TarotMessages> = {
  en: {
    metadata: {
      title: "Tarot 3:33 - ForgeGod",
      titleTemplate: "%s | Tarot 3:33",
      description:
        "A ritualized tarot experience by ForgeGod. The gate opens at precise moments for a three-card reading.",
      siteName: "Tarot 3:33",
    },
    nav: {
      languageLabel: "Language",
      english: "English",
      spanish: "Spanish",
    },
    landing: {
      eyebrow: "ForgeGod Presents",
      titleMain: "Tarot",
      titleTime: "3:33",
      description:
        "A ritualized tarot experience. The gate opens at precise moments. Enter when the time is right.",
      enterReading: "Enter the Reading",
      ctaNote: "Available during open ritual windows only",
      statusOpenCta: "Enter while the gate is open",
      explainTitle: "How the Ritual Works",
      steps: [
        {
          number: "01",
          title: "The gate opens",
          body: "Tarot 3:33 is only accessible during configured ritual windows.",
        },
        {
          number: "02",
          title: "Draw three cards",
          body: "A Past, Present, Future spread, revealed with ceremony.",
        },
        {
          number: "03",
          title: "Receive your reading",
          body: "Instant interpretation rooted in the major arcana tradition.",
        },
      ],
      footerLead: "ForgeGod",
      footerTail: "Built with precision",
    },
    status: {
      label: "Ritual Gate",
      checking: "Checking schedule...",
      open: "Open",
      closed: "Closed",
      closingSoon: "Closing soon",
      closesIn: "Closes in",
      nextOpeningIn: "Next opening in",
      unableToCheck: "Unable to check status",
      enterNow: "Enter now",
      opening: "Opening...",
    },
    reading: {
      headerEyebrow: "ForgeGod Ritual",
      closedBadge: "Ritual Gate Closed",
      closedTitle: "Not Yet",
      closedBody:
        "Tarot 3:33 opens at precise ritual windows. The gate is currently sealed. Return when the time is right.",
      nextOpeningIn: "Next opening in",
      returnToLanding: "Return to Landing",
      unableToBegin: "Unable to Begin",
      errorBody:
        "Something went wrong. Please return to the landing page and try again.",
      loading: "Preparing your reading...",
      introTitle: "Your Reading Awaits",
      introBody:
        "Three cards will be drawn from the universal deck: Past, Present, and Future. Each holds a reflection of your journey.",
      introSubPrefix: "Drawn at",
      revealCards: "Reveal the Cards",
      revealContext: "The cards speak...",
      spreadTitle: "Your Spread",
      closeRitual: "Close Ritual",
      completeTitle: "Ritual Complete",
      completeBody:
        "The cards have spoken. Carry what resonates. The gate will close when the ritual window ends.",
      phaseAriaLabel: "Ritual phases",
      phases: {
        intro: "Invocation",
        reveal: "Reveal",
        meaning: "Interpretation",
        closing: "Closure",
      },
      reversed: "Reversed",
      cardBackLabel: "ForgeGod tarot card back",
      suitLabels: {
        major: "Major Arcana",
        cups: "Cups",
        swords: "Swords",
        wands: "Wands",
        pentacles: "Pentacles",
      },
      positions: {
        past: {
          label: "Past",
          description: "What has led you here",
        },
        present: {
          label: "Present",
          description: "What is unfolding now",
        },
        future: {
          label: "Future",
          description: "What approaches on the horizon",
        },
      },
    },
    countdown: {
      complete: "Now",
      opening: "Opening...",
      ariaPrefix: "Opens in",
      units: {
        day: "d",
        hour: "h",
        minute: "m",
        second: "s",
      },
    },
    loading: {
      title: "Preparing the gate",
      body: "Loading the ritual surfaces and timing engine.",
    },
    notFound: {
      eyebrow: "Missing route",
      title: "This ritual path does not exist",
      body: "Return to the landing page and re-enter through a valid gate.",
      home: "Return Home",
    },
    og: {
      eyebrow: "ForgeGod Ritual",
      headline: "Tarot 3:33",
      subline: "A bilingual ceremonial tarot showcase built on ForgeGod.",
    },
    manifest: {
      name: "Tarot 3:33 by ForgeGod",
      shortName: "Tarot 3:33",
      description:
        "A bilingual ceremonial tarot showcase built with ForgeGod.",
    },
  },
  es: {
    metadata: {
      title: "Tarot 3:33 - ForgeGod",
      titleTemplate: "%s | Tarot 3:33",
      description:
        "Una experiencia de tarot ritualizada por ForgeGod. La puerta se abre en momentos precisos para una tirada de tres cartas.",
      siteName: "Tarot 3:33",
    },
    nav: {
      languageLabel: "Idioma",
      english: "Inglés",
      spanish: "Español",
    },
    landing: {
      eyebrow: "ForgeGod Presenta",
      titleMain: "Tarot",
      titleTime: "3:33",
      description:
        "Una experiencia de tarot ritualizada. La puerta se abre en momentos precisos. Entra cuando llegue la hora.",
      enterReading: "Entrar a la lectura",
      ctaNote: "Disponible solo durante ventanas rituales abiertas",
      statusOpenCta: "Entrar mientras la puerta está abierta",
      explainTitle: "Cómo funciona el ritual",
      steps: [
        {
          number: "01",
          title: "La puerta se abre",
          body: "Tarot 3:33 solo es accesible durante ventanas rituales configuradas.",
        },
        {
          number: "02",
          title: "Extrae tres cartas",
          body: "Una tirada Pasado, Presente y Futuro revelada con ceremonia.",
        },
        {
          number: "03",
          title: "Recibe tu lectura",
          body: "Interpretación inmediata anclada en la tradición de los arcanos mayores.",
        },
      ],
      footerLead: "ForgeGod",
      footerTail: "Construido con precisión",
    },
    status: {
      label: "Puerta ritual",
      checking: "Verificando horario...",
      open: "Abierta",
      closed: "Cerrada",
      closingSoon: "Cierra pronto",
      closesIn: "Cierra en",
      nextOpeningIn: "Próxima apertura en",
      unableToCheck: "No se pudo verificar el estado",
      enterNow: "Entrar ahora",
      opening: "Abriendo...",
    },
    reading: {
      headerEyebrow: "Ritual ForgeGod",
      closedBadge: "Puerta ritual cerrada",
      closedTitle: "Todavía no",
      closedBody:
        "Tarot 3:33 abre en ventanas rituales precisas. La puerta está sellada por ahora. Vuelve cuando llegue la hora.",
      nextOpeningIn: "Próxima apertura en",
      returnToLanding: "Volver al inicio",
      unableToBegin: "No se pudo iniciar",
      errorBody:
        "Algo salió mal. Vuelve a la página inicial e inténtalo otra vez.",
      loading: "Preparando tu lectura...",
      introTitle: "Tu lectura te espera",
      introBody:
        "Se extraerán tres cartas del mazo universal: Pasado, Presente y Futuro. Cada una refleja una parte de tu recorrido.",
      introSubPrefix: "Extraída a las",
      revealCards: "Revelar las cartas",
      revealContext: "Las cartas hablan...",
      spreadTitle: "Tu tirada",
      closeRitual: "Cerrar ritual",
      completeTitle: "Ritual completo",
      completeBody:
        "Las cartas ya hablaron. Conserva lo que resuene. La puerta se cerrará cuando termine la ventana ritual.",
      phaseAriaLabel: "Fases del ritual",
      phases: {
        intro: "Invocación",
        reveal: "Revelación",
        meaning: "Interpretación",
        closing: "Cierre",
      },
      reversed: "Invertida",
      cardBackLabel: "Dorso de carta tarot ForgeGod",
      suitLabels: {
        major: "Arcanos mayores",
        cups: "Copas",
        swords: "Espadas",
        wands: "Bastos",
        pentacles: "Oros",
      },
      positions: {
        past: {
          label: "Pasado",
          description: "Lo que te trajo hasta aquí",
        },
        present: {
          label: "Presente",
          description: "Lo que se está desplegando ahora",
        },
        future: {
          label: "Futuro",
          description: "Lo que se acerca en el horizonte",
        },
      },
    },
    countdown: {
      complete: "Ahora",
      opening: "Abriendo...",
      ariaPrefix: "Abre en",
      units: {
        day: "d",
        hour: "h",
        minute: "m",
        second: "s",
      },
    },
    loading: {
      title: "Preparando la puerta",
      body: "Cargando las superficies rituales y el motor de tiempos.",
    },
    notFound: {
      eyebrow: "Ruta inexistente",
      title: "Este camino ritual no existe",
      body: "Vuelve al inicio y entra otra vez por una puerta válida.",
      home: "Volver al inicio",
    },
    og: {
      eyebrow: "Ritual ForgeGod",
      headline: "Tarot 3:33",
      subline:
        "Un showcase ceremonial bilingüe de tarot construido sobre ForgeGod.",
    },
    manifest: {
      name: "Tarot 3:33 por ForgeGod",
      shortName: "Tarot 3:33",
      description:
        "Un showcase ceremonial bilingüe de tarot construido con ForgeGod.",
    },
  },
};

export function isLocale(value: string): value is Locale {
  return locales.includes(value as Locale);
}

export function getMessages(locale: Locale): TarotMessages {
  return messages[locale];
}

export function getPreferredLocale(
  acceptLanguageHeader: string | null | undefined,
): Locale {
  if (!acceptLanguageHeader) {
    return defaultLocale;
  }

  const tokens = acceptLanguageHeader
    .split(",")
    .map((part) => part.trim().toLowerCase())
    .filter(Boolean);

  for (const token of tokens) {
    const [language] = token.split(";");
    const [base] = (language ?? "").split("-");
    if (base === "es") {
      return "es";
    }
    if (base === "en") {
      return "en";
    }
  }

  return defaultLocale;
}

export function localizedPath(locale: Locale, pathname: "/" | "/reading"): string {
  return pathname === "/" ? `/${locale}` : `/${locale}${pathname}`;
}

export function stripLocale(pathname: string): string {
  for (const locale of locales) {
    if (pathname === `/${locale}`) {
      return "/";
    }
    if (pathname.startsWith(`/${locale}/`)) {
      return pathname.slice(locale.length + 1) || "/";
    }
  }
  return pathname || "/";
}

export function localeFromPath(pathname: string): Locale | null {
  const [, maybeLocale] = pathname.split("/");
  return maybeLocale && isLocale(maybeLocale) ? maybeLocale : null;
}

export const siteUrl =
  process.env.NEXT_PUBLIC_SITE_URL?.replace(/\/$/, "") ??
  "https://tarot.forgegod.com";
