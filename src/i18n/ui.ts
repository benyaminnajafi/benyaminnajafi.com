/**
 * The languages the site is published in, and the words that belong to the
 * page rather than to the content — labels, headings, accessible names.
 *
 * English is the source. It lives at the root of the site and of content/;
 * every other language is a translation under its own prefix, /de/ and
 * content/de/. The list must match i18n.locales in astro.config.mjs.
 */
export const locales = ["en", "de"] as const;
export type Locale = (typeof locales)[number];
export const defaultLocale = "en" satisfies Locale;

/** Astro.currentLocale is typed as any string; this narrows it. */
export function localeOf(value: string | undefined): Locale {
  return locales.find((locale) => locale === value) ?? defaultLocale;
}

export const ui = {
  en: {
    caseStudies: "Selected Case Studies",
    updated: "Updated",
    backToTop: "Back to Top",
    aiSummary: "Get an AI summary of me",
    cv: "CV",
    role: "Role",
    expertise: "Expertise",
    industry: "Industry",
    themeToggle: "theme switcher",
    carousel: (title: string, count: number) => `${title} — ${count} slides`,
    slide: (n: number, count: number) => `Slide ${n} of ${count}`,
    slideAlt: (title: string, n: number) => `${title} — slide ${n}`,
    notFound: "Page not found",
    notFoundDescription: "This page does not exist.",
    goHome: "Go home",
    dateLocale: "en-US",
  },
  de: {
    caseStudies: "Ausgewählte Case Studies",
    updated: "Aktualisiert",
    backToTop: "Nach oben",
    aiSummary: "KI-Zusammenfassung über mich",
    // The CV is an English document, so the label says so before the click.
    cv: "Lebenslauf (EN)",
    role: "Rolle",
    expertise: "Schwerpunkt",
    industry: "Branche",
    themeToggle: "Farbschema wechseln",
    carousel: (title: string, count: number) => `${title} – ${count} Bilder`,
    slide: (n: number, count: number) => `Bild ${n} von ${count}`,
    slideAlt: (title: string, n: number) => `${title} – Bild ${n}`,
    notFound: "Seite nicht gefunden",
    notFoundDescription: "Diese Seite existiert nicht.",
    goHome: "Zur Startseite",
    // Austrian German, since that is who the translation is for. It only
    // shows in January, which Austria writes as "Jänner".
    dateLocale: "de-AT",
  },
} satisfies Record<Locale, Record<string, unknown>>;

/**
 * A calendar date, written out the way the locale writes it.
 *
 * content/profile.json stores the date as YYYY-MM-DD so that one value serves
 * every language. It is read as UTC and formatted as UTC, or a build on a
 * machine west of Greenwich would print the day before.
 */
export function formatDate(iso: string, locale: Locale): string {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(iso)) {
    throw new Error(`expected a date like 2026-08-10, got ${JSON.stringify(iso)}`);
  }
  return new Intl.DateTimeFormat(ui[locale].dateLocale, {
    dateStyle: "long",
    timeZone: "UTC",
  }).format(new Date(`${iso}T00:00:00Z`));
}
