import { getCollection, type CollectionEntry } from "astro:content";
import source from "../../content/profile.json";
import de from "../../content/de/profile.json";
import { defaultLocale, type Locale } from "./ui";

/**
 * Content in a given language.
 *
 * A translation carries only words. Everything that is the same in every
 * language — the email, the links, the images, a slide's colour, the order of
 * the case studies — is read from the English files, so it cannot drift
 * between two copies.
 */

// content/de/profile.json holds only the fields that change with the
// language; the rest of the profile comes from content/profile.json.
const profiles = { en: {}, de } satisfies Record<Locale, Partial<typeof source>>;

export function getProfile(locale: Locale) {
  return { ...source, ...profiles[locale] };
}

/**
 * The "Get an AI summary of me" link: the engine's URL, which ends at `q=`,
 * with the prompt written in the reader's language appended.
 *
 * This encodes everything outside RFC 3986's unreserved set — stricter than
 * encodeURIComponent, which leaves ( ) ! ' * alone. The engines accept either;
 * this form is the one the English links were first published with, so moving
 * the prompt out of them into plain text left their hrefs unchanged.
 */
export function aiSummaryUrl(engineUrl: string, prompt: string): string {
  const encoded = encodeURIComponent(prompt).replace(
    /[!'()*]/g,
    (c) => `%${c.charCodeAt(0).toString(16).toUpperCase()}`,
  );
  return engineUrl + encoded;
}

export interface CaseStudyView {
  /** Frontmatter, with the translated fields laid over the English ones. */
  data: CollectionEntry<"caseStudies">["data"];
  /** The entry whose markdown body is rendered. */
  body: CollectionEntry<"caseStudies"> | CollectionEntry<"caseStudyTranslations">;
  /** The language the words are actually in, which is English wherever a
   *  translation is still missing. */
  lang: Locale;
}

export async function getCaseStudies(locale: Locale): Promise<CaseStudyView[]> {
  const originals = (await getCollection("caseStudies")).sort(
    (a, b) => a.data.order - b.data.order,
  );
  if (locale === defaultLocale) {
    return originals.map((entry) => ({ data: entry.data, body: entry, lang: locale }));
  }

  // Translation ids carry their path: de/case-studies/<id of the original>.
  const prefix = `${locale}/case-studies/`;
  const translations = new Map(
    (await getCollection("caseStudyTranslations"))
      .filter((entry) => entry.id.startsWith(prefix))
      .map((entry) => [entry.id.slice(prefix.length), entry]),
  );

  // A translation whose original was renamed or removed would otherwise just
  // stop appearing, silently.
  for (const id of translations.keys()) {
    if (!originals.some((entry) => entry.id === id)) {
      throw new Error(
        `content/${prefix}${id}.md translates a case study that does not exist in content/case-studies/`,
      );
    }
  }

  return originals.map((entry) => {
    const translation = translations.get(entry.id);
    if (!translation) {
      // Not fatal: a new case study can go live in English before it is
      // translated, and this page shows it in English until then.
      console.warn(`[i18n] no ${locale} translation for ${entry.id}; showing it in English`);
      return { data: entry.data, body: entry, lang: defaultLocale };
    }
    return {
      data: { ...entry.data, ...translation.data },
      body: translation,
      lang: locale,
    };
  });
}
