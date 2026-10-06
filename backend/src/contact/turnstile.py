"""Cloudflare Turnstile: whether the browser that sent the form passed Cloudflare's check.

The form page runs Cloudflare's widget, which puts a token in the ``cf-turnstile-response``
field. The token is checked here, once, with siteverify:
https://developers.cloudflare.com/turnstile/get-started/server-side-validation/

Three outcomes:

- ``PASSED``: Cloudflare says yes.
- ``FAILED``: Cloudflare says no, or the form came without a token. The message is discarded.
- ``UNAVAILABLE``: no usable answer (a timeout, a network error, a 5xx, an ``internal-error``, a
  body that is not what siteverify sends) or Cloudflare says the secret is wrong. The message is
  mailed anyway, marked, since the other traps still apply and a bot cannot make Cloudflare
  fail. A wrong secret counts here too: it would otherwise discard every message in silence.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

import httpx

SITEVERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
TIMEOUT_SECONDS = 5.0

RESPONSE_FIELD = "cf-turnstile-response"
"""The hidden field the widget adds to the form."""

TOKEN_MAX = 2048
"""Cloudflare's limit for a token; anything longer is not one."""

_OUR_PROBLEM = {"missing-input-secret", "invalid-input-secret", "internal-error"}
"""Error codes that say nothing about the visitor."""


class Verdict(Enum):
    PASSED = "passed"
    FAILED = "failed"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class Result:
    verdict: Verdict
    detail: str = ""
    """Cloudflare's error codes, or what went wrong reaching it. Never the token."""


class Verifier(Protocol):
    async def verify(self, token: str) -> Result: ...


class Siteverify:
    def __init__(self, client: httpx.AsyncClient, secret: str) -> None:
        self._client = client
        self._secret = secret

    async def verify(self, token: str) -> Result:
        if not token:
            return Result(Verdict.FAILED, "missing-input-response")
        if len(token) > TOKEN_MAX:
            return Result(Verdict.FAILED, "invalid-input-response")
        try:
            response = await self._client.post(
                SITEVERIFY_URL,
                data={"secret": self._secret, "response": token},
                timeout=TIMEOUT_SECONDS,
            )
        except httpx.HTTPError as error:
            return Result(Verdict.UNAVAILABLE, type(error).__name__)
        if response.status_code >= 500:
            return Result(Verdict.UNAVAILABLE, f"siteverify answered {response.status_code}")
        try:
            body = response.json()
        except ValueError:
            body = None
        if not isinstance(body, dict) or not isinstance(body.get("success"), bool):
            return Result(Verdict.UNAVAILABLE, f"siteverify answered {response.status_code}")
        if body["success"]:
            return Result(Verdict.PASSED)
        codes = body.get("error-codes")
        codes = [c for c in codes if isinstance(c, str)] if isinstance(codes, list) else []
        detail = ",".join(codes)
        if _OUR_PROBLEM & set(codes):
            return Result(Verdict.UNAVAILABLE, detail)
        return Result(Verdict.FAILED, detail)
