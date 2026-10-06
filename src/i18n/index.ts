/** The texts of a language. No i18n library: one object per language, picked here. */

import { en } from "./en.ts";
import { es } from "./es.ts";
import type { Language } from "./language.ts";
import type { Texts } from "./texts.ts";

const TEXTS: Readonly<Record<Language, Texts>> = { en, es };

export function textsFor(language: Language): Texts {
  return TEXTS[language];
}
