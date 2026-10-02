"""The time trap: the form carries the time it was opened, signed by this server.

A person needs more than a few seconds to write a message; a bot that posts the form right away,
or replays an old or made-up value, is discarded. The value is ``<unix seconds>.<signature>`` in
a hidden field: no JavaScript and no cookies.
"""

from __future__ import annotations

import hashlib
import hmac
from enum import StrEnum

MIN_AGE_SECONDS = 3
"""Faster than this is not a person typing."""

MAX_AGE_SECONDS = 24 * 60 * 60
"""Covers writing later the same day; a bot gets a new token with every page it loads anyway."""

_CONTEXT = b"contact-form-opened-at:"
"""Ties the signature to this use, in case the secret is ever reused for something else."""


class TokenProblem(StrEnum):
    INVALID = "invalid_token"
    TOO_FAST = "too_fast"
    EXPIRED = "expired_token"


def issue(secret: bytes, now: float) -> str:
    opened_at = int(now)
    return f"{opened_at}.{_sign(secret, opened_at)}"


def check(secret: bytes, token: str, now: float) -> TokenProblem | None:
    """``None`` when the token is genuine and its age is within the limits."""
    opened_text, dot, signature = token.partition(".")
    if not dot or not opened_text.isascii() or not opened_text.isdigit() or len(opened_text) > 12:
        return TokenProblem.INVALID
    opened_at = int(opened_text)
    if not hmac.compare_digest(signature, _sign(secret, opened_at)):
        return TokenProblem.INVALID
    age = now - opened_at
    # A token from the future (the clock stepped back) counts as too fast too.
    if age < MIN_AGE_SECONDS:
        return TokenProblem.TOO_FAST
    if age > MAX_AGE_SECONDS:
        return TokenProblem.EXPIRED
    return None


def _sign(secret: bytes, opened_at: int) -> str:
    return hmac.new(secret, _CONTEXT + str(opened_at).encode(), hashlib.sha256).hexdigest()
