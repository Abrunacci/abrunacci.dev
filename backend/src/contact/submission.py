"""What the form sends, read from the raw body and checked field by field.

The HTML form has the same ``required`` and ``maxlength`` rules, so a person only sees these
errors if the browser skipped them; the server checks anyway.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import parse_qs

from contact.turnstile import RESPONSE_FIELD

MAX_BODY_BYTES = 32 * 1024
"""Every field at its maximum, percent-encoded, fits several times over."""

NAME_MAX = 100
EMAIL_MAX = 254
MESSAGE_MAX = 5000

HONEYPOT_FIELD = "website"
"""Hidden from people (and from screen readers); bots fill in anything that looks like a field."""

TOKEN_FIELD = "opened"

# Deliberately loose: one @, something on each side, a dot in the domain, no spaces. Whether the
# address really exists only shows when the reply bounces.
_EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


@dataclass(frozen=True, slots=True)
class Submission:
    name: str
    email: str
    message: str
    honeypot: str
    token: str
    turnstile: str
    """The token Cloudflare's widget put in the form; empty when it did not run."""
    errors: dict[str, str] = field(default_factory=dict)
    """Field name to the sentence shown under it. Empty when every field is valid."""


def parse(body: bytes) -> Submission:
    fields = parse_qs(body.decode("utf-8", errors="replace"), keep_blank_values=True)

    def value(name: str) -> str:
        values = fields.get(name)
        return values[0] if values else ""

    # One line each: no line breaks can reach the mail's headers.
    name = " ".join(value("name").split())
    email = value("email").strip()
    message = value("message").replace("\r\n", "\n").strip()

    errors = {}
    if not name:
        errors["name"] = "Enter your name."
    elif len(name) > NAME_MAX:
        errors["name"] = f"Keep the name under {NAME_MAX} characters."
    if not email:
        errors["email"] = "Enter your email address, so I can reply."
    elif len(email) > EMAIL_MAX or not _EMAIL.fullmatch(email):
        errors["email"] = "Enter a valid email address, like name@company.com."
    if not message:
        errors["message"] = "Write a message."
    elif len(message) > MESSAGE_MAX:
        errors["message"] = f"Keep the message under {MESSAGE_MAX:,} characters."

    return Submission(
        name=name,
        email=email,
        message=message,
        honeypot=value(HONEYPOT_FIELD),
        token=value(TOKEN_FIELD),
        turnstile=value(RESPONSE_FIELD),
        errors=errors,
    )
