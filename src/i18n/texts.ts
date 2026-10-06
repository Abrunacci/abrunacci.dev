/**
 * Everything the page says, as one object per language (`en.ts`, `es.ts`) with this shape, so
 * the build fails when a language is missing a text. Project summaries are in
 * src/data/projects.yaml, one per language.
 */

import type { Language } from "./language.ts";

export interface Texts {
  readonly language: Language;
  /** Open Graph's locale, like "en_US". */
  readonly ogLocale: string;

  /** The browser tab and the search result's title. */
  readonly title: string;
  /** The summary search engines show under the title; it leads with the name. */
  readonly description: string;
  /** The title, description and image of a shared link. */
  readonly share: {
    readonly title: string;
    readonly description: string;
    /** A file in public/, rendered by tools/render-images.sh. */
    readonly image: string;
    readonly imageAlt: string;
  };
  /** The language selector's name. */
  readonly languageGroup: string;

  /** Shown above the name. Empty hides it. */
  readonly availability: string;
  readonly role: string;
  /** The tagline, with the part that matters most marked. */
  readonly tagline: { readonly before: string; readonly mark: string; readonly after: string };
  /** Joined with " · "; the last part does not wrap. */
  readonly location: readonly string[];
  readonly emailMe: string;
  /** Around "GitHub" and "LinkedIn" for screen readers: "GitHub profile", "Perfil de GitHub". */
  readonly profile: { readonly before: string; readonly after: string };
  /** The list of technologies, for screen readers. */
  readonly technologies: string;

  readonly about: {
    readonly eyebrow: string;
    readonly title: string;
    /** One opening sentence, then short points. */
    readonly lead: string;
    readonly points: readonly string[];
  };

  readonly projects: {
    readonly eyebrow: string;
    readonly title: string;
    /** A card's technologies, for screen readers. */
    readonly builtWith: string;
    readonly liveSite: string;
    /** Between "Live site" and the project's title, for screen readers. */
    readonly liveSiteOf: string;
    readonly sourceCode: string;
    /** Between "Source code" and the project's title, for screen readers. */
    readonly sourceCodeOf: string;
  };

  /** Also the contact form's texts in backend/src/contact/texts.py: keep both the same. */
  readonly contact: {
    readonly eyebrow: string;
    readonly title: string;
    readonly text: string;
    readonly button: string;
  };
}
