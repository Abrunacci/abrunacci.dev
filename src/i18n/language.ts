/**
 * The page's languages. Each one has its own URL, with the same page in it: English at the
 * root, the others under their code. Nothing picks one for the visitor; the selector at the top
 * links between them.
 */

export const LANGUAGES = ["en", "es"] as const;

export type Language = (typeof LANGUAGES)[number];

/** The one at the root, and the one search engines offer when none matches (x-default). */
export const DEFAULT_LANGUAGE: Language = "en";

/** Each language by its own name, as the selector reads it out whatever the page's language. */
export const LANGUAGE_NAMES: Readonly<Record<Language, string>> = {
  en: "English",
  es: "Español",
};

/** The page's path in a language: "/" or "/es/". Always with the trailing slash. */
export function pathFor(language: Language): string {
  return language === DEFAULT_LANGUAGE ? "/" : `/${language}/`;
}

/** The contact form (served by backend/) in a language. */
export function contactFormFor(language: Language): string {
  return language === DEFAULT_LANGUAGE ? "/contact" : `/contact?lang=${language}`;
}
