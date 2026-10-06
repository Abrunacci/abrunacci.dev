"""The HTTP side: the form page, the endpoint it posts to, and the health check.

Every step a message can take ends in the log, as one line with the event, its reason, an ID,
the time and the message's length. Never anything from the form: no name, email or text, and
not the visitor's address.

- ``discarded``: a bot trap caught it (honeypot, time trap, per-sender limit, Turnstile). The
  sender sees the same confirmation as everyone else, so a bot cannot tell what stopped it.
- ``daily_limit``: today's mail quota is used up. The person sees the form again with their
  text and is asked to try tomorrow, and one notice a day says so.
- ``send_failed``: Resend did not take it. The person sees the form again with their text and
  can retry.
- ``sent``: mailed. With reason ``turnstile_unavailable`` when Cloudflare could not check it.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
import uuid
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, PackageLoader, select_autoescape

from contact import client_ip, form_token, spam, turnstile
from contact.language import DEFAULT_LANGUAGE, LANGUAGE_FIELD, Language, from_parameter
from contact.limits import MAILS_PER_DAY, DailyCap, SenderLimit
from contact.mailer import Mail, Mailer, ResendMailer, SendError
from contact.settings import Settings
from contact.submission import (
    EMAIL_MAX,
    HONEYPOT_FIELD,
    MAX_BODY_BYTES,
    MESSAGE_MAX,
    NAME_MAX,
    TOKEN_FIELD,
    Submission,
    parse,
)
from contact.texts import TEXTS

FORM_PATH = "/contact"
"""Where the form page is served. Caddy sends this path, and /api/*, to this container."""

POST_PATH = "/api/contact"
SENT_QUERY = "status=sent"
"""With ``&lang=…`` after it when the form was not in the default language."""

CONTACT_ADDRESS = "hello@abrunacci.dev"
"""Offered on the form to whoever cannot use it: without JavaScript, or when Turnstile fails."""

UNVERIFIED_MARK = "[sin verificar]"
"""In the subject of a message that Turnstile could not check."""

# Scripts: the form's own (/api/static/form.js) and Cloudflare's Turnstile, which runs its check
# in an iframe. Styles are inline in each page; the font is served from /api/static.
CONTENT_SECURITY_POLICY = (
    "default-src 'none'; script-src 'self' https://challenges.cloudflare.com; "
    "frame-src https://challenges.cloudflare.com; style-src 'unsafe-inline'; font-src 'self'; "
    "img-src 'self'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'"
)

log = logging.getLogger("contact")


def create_app(
    settings: Settings | None = None,
    mailer: Mailer | None = None,
    clock: Callable[[], float] = time.time,
    verifier: turnstile.Verifier | None = None,
) -> FastAPI:
    settings = settings or Settings.from_env(os.environ)
    _configure_logging()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with httpx.AsyncClient() as client:
            app.state.mailer = mailer or ResendMailer(
                client, settings.resend_api_key, settings.mail_from, settings.mail_to
            )
            app.state.verifier = verifier or turnstile.Siteverify(
                client, settings.turnstile_secret_key
            )
            yield

    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.mount("/api/static", StaticFiles(packages=[("contact", "static")]), name="static")

    templates = Environment(
        loader=PackageLoader("contact"),
        autoescape=select_autoescape(),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    proxy = client_ip.TrustedProxy(settings.trusted_proxy)
    senders = SenderLimit()
    daily = DailyCap()

    def page(template: str, language: Language, status: int = 200, **context: Any) -> HTMLResponse:
        html = templates.get_template(template).render(
            t=TEXTS[language],
            language_field=LANGUAGE_FIELD,
            site_url=settings.site_url,
            post_path=POST_PATH,
            limits={"name": NAME_MAX, "email": EMAIL_MAX, "message": MESSAGE_MAX},
            honeypot_field=HONEYPOT_FIELD,
            token_field=TOKEN_FIELD,
            turnstile_site_key=settings.turnstile_site_key,
            contact_address=CONTACT_ADDRESS,
            **context,
        )
        return HTMLResponse(
            html,
            status_code=status,
            headers={
                # The form carries a fresh token; a cached copy would carry a stale one.
                "Cache-Control": "no-store",
                "Content-Security-Policy": CONTENT_SECURITY_POLICY,
            },
        )

    def form_page(
        language: Language,
        submission: Submission | None = None,
        *,
        status: int = 200,
        error: str = "",
    ) -> HTMLResponse:
        """``error``: a sentence for the whole form, or empty."""
        # A form shown again keeps the token it was sent with: a fresh one would trip the time
        # trap when someone fixes a typo and sends again within seconds.
        token = submission.token if submission else form_token.issue(settings.form_secret, clock())
        return page(
            "form.html",
            language,
            status,
            token=token,
            values=submission,
            errors=submission.errors if submission else {},
            error=error,
        )

    def confirmation(language: Language = DEFAULT_LANGUAGE) -> RedirectResponse:
        # 303: the browser follows with a GET, so reloading the page does not post again.
        query = SENT_QUERY
        if language != DEFAULT_LANGUAGE:
            query += f"&{LANGUAGE_FIELD}={language}"
        return RedirectResponse(f"{FORM_PATH}?{query}", status_code=303)

    @app.get("/api/health")
    async def health() -> JSONResponse:
        return JSONResponse({"status": "ok"})

    @app.get(FORM_PATH)
    async def show_form(request: Request) -> HTMLResponse:
        language = from_parameter(request.query_params.get(LANGUAGE_FIELD))
        if request.query_params.get("status") == "sent":
            return page("sent.html", language)
        return form_page(language)

    @app.get(POST_PATH)
    async def post_path_by_hand() -> RedirectResponse:
        return RedirectResponse(FORM_PATH, status_code=303)

    @app.post(POST_PATH)
    async def receive(request: Request) -> Response:
        now = clock()
        address = await client_ip.visitor_address(
            request.client.host if request.client else None,
            request.headers.get("x-forwarded-for"),
            proxy,
        )
        sender = client_ip.limit_key(address)

        body = await _read_body(request)
        if body is None:
            _log("discarded", now, reason="too_large")
            return confirmation()
        submission = parse(body)

        language = submission.language

        if submission.honeypot:
            _log("discarded", now, submission, reason="honeypot")
            return confirmation(language)
        if problem := form_token.check(settings.form_secret, submission.token, now):
            _log("discarded", now, submission, reason=problem.value)
            return confirmation(language)
        if submission.errors:
            return form_page(language, submission, status=400)
        if not senders.allow(sender, now):
            _log("discarded", now, submission, reason="sender_limit")
            return confirmation(language)
        # After the checks that cost nothing, so a bot they catch costs no call to Cloudflare.
        check = await request.app.state.verifier.verify(submission.turnstile)
        if check.verdict is turnstile.Verdict.FAILED:
            _log("discarded", now, submission, reason=f"turnstile: {check.detail or 'no'}")
            return confirmation(language)
        # Cloudflare gave no usable answer: mailed anyway, marked (see turnstile.py).
        unchecked = check.detail if check.verdict is turnstile.Verdict.UNAVAILABLE else ""

        flags = spam.reasons(submission.name, submission.message)
        if not daily.reserve(now):
            _log("daily_limit", now, submission)
            if daily.notice_due(now):
                await _send_notice(request.app.state.mailer, settings, now, daily)
            return form_page(language, submission, status=429, error=TEXTS[language].daily_limit)

        try:
            await request.app.state.mailer.send(
                _message_mail(settings, submission, flags, unchecked)
            )
        except SendError as error:
            daily.release(now)
            _log("send_failed", now, submission, reason=_without(submission, str(error)))
            return form_page(language, submission, status=503, error=TEXTS[language].send_failed)
        _log("sent", now, submission, reason=unchecked and f"turnstile_unavailable: {unchecked}")
        return confirmation(language)

    return app


async def _read_body(request: Request) -> bytes | None:
    """The body, or ``None`` past ``MAX_BODY_BYTES`` (read no further than that)."""
    body = bytearray()
    async for chunk in request.stream():
        body += chunk
        if len(body) > MAX_BODY_BYTES:
            return None
    return bytes(body)


def _message_mail(
    settings: Settings, submission: Submission, flags: list[str], unchecked: str
) -> Mail:
    """``unchecked``: why Turnstile could not check the message, or empty when it did."""
    marks = [settings.subject_prefix]
    if unchecked:
        marks.append(UNVERIFIED_MARK)
    if flags:
        marks.append(spam.SUBJECT_MARK)
    subject = f"{' '.join(marks)} {submission.name}"
    lines = [f"From: {submission.name} <{submission.email}>", ""]
    if unchecked:
        lines += [f"Not checked by Turnstile: no usable answer from Cloudflare ({unchecked}).", ""]
    if flags:
        lines += [f"Marked as possible spam: {'; '.join(flags)}.", ""]
    lines += [submission.message, "", "--", f"Sent from the contact form of {settings.site_url}"]
    return Mail(subject=subject, text="\n".join(lines), reply_to=submission.email)


async def _send_notice(mailer: Mailer, settings: Settings, now: float, daily: DailyCap) -> None:
    notice = Mail(
        subject=f"{settings.subject_prefix} Daily limit reached: messages held",
        text="\n".join(
            [
                f"The contact form mailed {MAILS_PER_DAY} messages today, its daily limit.",
                "",
                "Until midnight (Argentina time) it turns messages away: the person sees the form",
                "again with their text and is asked to try again tomorrow. The backend's log has",
                'one "daily_limit" entry for each, without its content.',
                "",
                "This notice is sent once a day.",
            ]
        ),
    )
    try:
        await mailer.send(notice)
    except SendError as error:
        # Tried again with the next message past the limit.
        log.error(json.dumps({"event": "notice_failed", "error": str(error)}))
        return
    daily.notice_sent(now)


def _log(event: str, now: float, submission: Submission | None = None, reason: str = "") -> None:
    """One line per outcome, with nothing that identifies the person or repeats what they wrote.

    The ID tells one entry from another; the length is the message's, in characters."""
    entry: dict[str, Any] = {
        "event": event,
        "id": uuid.uuid4().hex,
        "time": datetime.fromtimestamp(now, UTC).isoformat(timespec="seconds"),
    }
    if reason:
        entry["reason"] = reason
    if submission is not None:
        entry["length"] = len(submission.message)
    log.info(json.dumps(entry, ensure_ascii=False))


def _without(submission: Submission, text: str) -> str:
    """``text`` with the sender's name and email blanked, in case Resend's answer quotes them."""
    for value, placeholder in ((submission.email, "<email>"), (submission.name, "<name>")):
        if value:
            text = text.replace(value, placeholder)
    return text


def _configure_logging() -> None:
    """One JSON object per line on stdout, which the container's log keeps."""
    if log.handlers:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    log.addHandler(handler)
    log.setLevel(logging.INFO)
    log.propagate = False
