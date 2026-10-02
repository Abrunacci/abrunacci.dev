"""Sending through Resend's HTTP API, with a key that can only send.

https://resend.com/docs/api-reference/emails/send-email
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import httpx

RESEND_URL = "https://api.resend.com/emails"
TIMEOUT_SECONDS = 10.0


@dataclass(frozen=True, slots=True)
class Mail:
    subject: str
    text: str
    reply_to: str | None = None


class SendError(Exception):
    """Resend did not accept the mail. The message has to be kept some other way."""


class Mailer(Protocol):
    async def send(self, mail: Mail) -> None: ...


class ResendMailer:
    def __init__(self, client: httpx.AsyncClient, api_key: str, sender: str, to: str) -> None:
        self._client = client
        self._api_key = api_key
        self._sender = sender
        self._to = to

    async def send(self, mail: Mail) -> None:
        payload: dict[str, object] = {
            "from": self._sender,
            "to": [self._to],
            "subject": mail.subject,
            "text": mail.text,
        }
        if mail.reply_to:
            payload["reply_to"] = mail.reply_to
        try:
            response = await self._client.post(
                RESEND_URL,
                json=payload,
                headers={"Authorization": f"Bearer {self._api_key}"},
                timeout=TIMEOUT_SECONDS,
            )
        except httpx.HTTPError as error:
            raise SendError(f"Resend did not answer: {type(error).__name__}") from error
        if response.is_error:
            # Resend's error body names the problem (a bad sender, a key without access); it
            # never echoes the key.
            raise SendError(f"Resend answered {response.status_code}: {response.text[:300]}")
