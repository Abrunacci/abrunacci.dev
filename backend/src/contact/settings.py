"""Settings from the environment, checked once at startup.

The server's values come from infra's projects.yml: ``RESEND_API_KEY`` and ``MAIL_TO`` are
secrets the admin sets, ``FORM_SECRET`` one the playbook generates, the rest are public ``env``
(see docs/deploy.md). A missing or unusable value stops the app from starting, with a message
that names the variable and never its value.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

MIN_SECRET_LENGTH = 32
"""infra generates 64 hex characters; anything this short was typed by hand by mistake."""

DEFAULT_SUBJECT_PREFIX = "[abrunacci.dev]"
DEFAULT_SITE_URL = "https://abrunacci.dev"


class SettingsError(Exception):
    """A required variable is missing, or one has a value the app cannot use."""


@dataclass(frozen=True, slots=True)
class Settings:
    resend_api_key: str = field(repr=False)
    form_secret: bytes = field(repr=False)
    """Signs the time the form was opened. It must survive restarts: a new one invalidates
    every form that is open at that moment."""
    mail_from: str
    """The sender, on the domain verified in Resend: ``Name <address@mail.abrunacci.dev>``."""
    mail_to: str
    subject_prefix: str = DEFAULT_SUBJECT_PREFIX
    site_url: str = DEFAULT_SITE_URL
    trusted_proxy: str = ""
    """Container name of the reverse proxy (Caddy). Only a request whose connection comes from
    it may say who the visitor is, in ``X-Forwarded-For``. Empty: the header is never read."""

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> Settings:
        secret = _required(env, "FORM_SECRET")
        if len(secret) < MIN_SECRET_LENGTH:
            raise SettingsError(f"FORM_SECRET must be at least {MIN_SECRET_LENGTH} characters long")
        return cls(
            resend_api_key=_required(env, "RESEND_API_KEY"),
            form_secret=secret.encode(),
            mail_from=_required(env, "MAIL_FROM"),
            mail_to=_required(env, "MAIL_TO"),
            subject_prefix=env.get("MAIL_SUBJECT_PREFIX", "").strip() or DEFAULT_SUBJECT_PREFIX,
            site_url=(env.get("SITE_URL", "").strip() or DEFAULT_SITE_URL).rstrip("/"),
            trusted_proxy=env.get("TRUSTED_PROXY", "").strip(),
        )


def _required(env: Mapping[str, str], name: str) -> str:
    value = env.get(name, "").strip()
    if not value:
        raise SettingsError(f"{name} is not set")
    return value
