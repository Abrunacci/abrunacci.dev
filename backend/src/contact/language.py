"""The form's languages: the same as the landing's (src/i18n/language.ts in the site)."""

from __future__ import annotations

from typing import Literal, get_args

Language = Literal["en", "es"]

LANGUAGES: tuple[Language, ...] = get_args(Language)

DEFAULT_LANGUAGE: Language = "en"

LANGUAGE_FIELD = "lang"
"""The query parameter that opens the form in a language (``/contact?lang=es``), and the hidden
field that carries it with the message, so its errors and confirmation are in that language."""


def from_parameter(value: str | None) -> Language:
    """The language a parameter names; anything else is the default."""
    for known in LANGUAGES:
        if value == known:
            return known
    return DEFAULT_LANGUAGE
