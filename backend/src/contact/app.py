"""The HTTP side: the form page, the endpoint it posts to, and the health check.

Every step a message can take ends in the log:

- ``discarded``: a bot trap caught it (honeypot, time trap, per-sender limit). The sender sees
  the same confirmation as everyone else, so a bot cannot tell what stopped it.
- ``held``: today's mail quota is used up. It is accepted and kept in the log, and one notice a
  day says so.
- ``send_failed``: Resend did not take it. The person sees the form again with their text and
  can retry, so the log keeps only the error and what is needed to find the entry (an ID, the
  time, the message's length), never who wrote it or what they wrote.
- ``sent``: mailed.
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

from contact import client_ip, form_token, spam
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

FORM_PATH = "/contact"
"""Where the form page is served. Caddy sends this path, and /api/*, to this container."""

POST_PATH = "/api/contact"
SENT_QUERY = "status=sent"

SEND_FAILED = "Your message could not be sent right now. Please try again in a few minutes."

# No scripts at all. Styles are inline in each page; the font is served from /api/static.
CONTENT_SECURITY_POLICY = (
    "default-src 'none'; style-src 'unsafe-inline'; font-src 'self'; img-src 'self'; "
    "form-action 'self'; base-uri 'none'; frame-ancestors 'none'"
)

log = logging.getLogger("contact")


def create_app(
    settings: Settings | None = None,
    mailer: Mailer | None = None,
    clock: Callable[[], float] = time.time,
) -> FastAPI:
    settings = settings or Settings.from_env(os.environ)
    _configure_logging()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if mailer is not None:
            app.state.mailer = mailer
            yield
            return
        async with httpx.AsyncClient() as client:
            app.state.mailer = ResendMailer(
                client, settings.resend_api_key, settings.mail_from, settings.mail_to
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

    def page(template: str, status: int = 200, **context: Any) -> HTMLResponse:
        html = templates.get_template(template).render(
            site_url=settings.site_url,
            post_path=POST_PATH,
            limits={"name": NAME_MAX, "email": EMAIL_MAX, "message": MESSAGE_MAX},
            honeypot_field=HONEYPOT_FIELD,
            token_field=TOKEN_FIELD,
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
        submission: Submission | None = None, *, status: int = 200, error: str = ""
    ) -> HTMLResponse:
        # A form shown again keeps the token it was sent with: a fresh one would trip the time
        # trap when someone fixes a typo and sends again within seconds.
        token = submission.token if submission else form_token.issue(settings.form_secret, clock())
        return page(
            "form.html",
            status,
            token=token,
            values=submission,
            errors=submission.errors if submission else {},
            error=error,
        )

    def confirmation() -> RedirectResponse:
        # 303: the browser follows with a GET, so reloading the page does not post again.
        return RedirectResponse(f"{FORM_PATH}?{SENT_QUERY}", status_code=303)

    @app.get("/api/health")
    async def health() -> JSONResponse:
        return JSONResponse({"status": "ok"})

    @app.get(FORM_PATH)
    async def show_form(request: Request) -> HTMLResponse:
        if request.url.query == SENT_QUERY:
            return page("sent.html")
        return form_page()

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
            _log("discarded", sender, reason="too_large")
            return confirmation()
        submission = parse(body)

        if submission.honeypot:
            _log("discarded", sender, submission, reason="honeypot")
            return confirmation()
        if problem := form_token.check(settings.form_secret, submission.token, now):
            _log("discarded", sender, submission, reason=problem.value)
            return confirmation()
        if submission.errors:
            return form_page(submission, status=400)
        if not senders.allow(sender, now):
            _log("discarded", sender, submission, reason="sender_limit")
            return confirmation()

        flags = spam.reasons(submission.name, submission.message)
        if not daily.reserve(now):
            _log("held", sender, submission, spam=flags)
            if daily.notice_due(now):
                await _send_notice(request.app.state.mailer, settings, now, daily)
            return confirmation()

        try:
            await request.app.state.mailer.send(_message_mail(settings, submission, flags))
        except SendError as error:
            daily.release(now)
            _log_send_failure(submission, error, now)
            return form_page(submission, status=503, error=SEND_FAILED)
        _log("sent", sender, spam=flags)
        return confirmation()

    return app


async def _read_body(request: Request) -> bytes | None:
    """The body, or ``None`` past ``MAX_BODY_BYTES`` (read no further than that)."""
    body = bytearray()
    async for chunk in request.stream():
        body += chunk
        if len(body) > MAX_BODY_BYTES:
            return None
    return bytes(body)


def _message_mail(settings: Settings, submission: Submission, flags: list[str]) -> Mail:
    subject = f"{settings.subject_prefix} {submission.name}"
    if flags:
        subject = f"{settings.subject_prefix} {spam.SUBJECT_MARK} {submission.name}"
    lines = [f"From: {submission.name} <{submission.email}>", ""]
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
                "It keeps accepting messages, but until midnight (Argentina time) it writes them",
                "to the backend's log instead of mailing them, as entries with",
                '"event": "held". None is lost.',
                "",
                "This notice is sent once a day.",
            ]
        ),
    )
    try:
        await mailer.send(notice)
    except SendError as error:
        # Tried again with the next held message.
        log.error(json.dumps({"event": "notice_failed", "error": str(error)}))
        return
    daily.notice_sent(now)


def _log(event: str, sender: str, submission: Submission | None = None, **extra: Any) -> None:
    entry: dict[str, Any] = {"event": event, "sender": sender, **extra}
    if submission is not None:
        entry |= {"name": submission.name, "email": submission.email, "message": submission.message}
    log.info(json.dumps(entry, ensure_ascii=False))


def _log_send_failure(submission: Submission, error: SendError, now: float) -> None:
    """No personal data: no address, name, email or text. Resend's answer is kept for the cause,
    with the sender's name and email blanked in case it quotes them."""
    reason = str(error)
    for value, placeholder in ((submission.email, "<email>"), (submission.name, "<name>")):
        if value:
            reason = reason.replace(value, placeholder)
    entry = {
        "event": "send_failed",
        "id": uuid.uuid4().hex,
        "time": datetime.fromtimestamp(now, UTC).isoformat(timespec="seconds"),
        "length": len(submission.message),
        "error": reason,
    }
    log.error(json.dumps(entry, ensure_ascii=False))


def _configure_logging() -> None:
    """One JSON object per line on stdout, which the container's log keeps."""
    if log.handlers:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    log.addHandler(handler)
    log.setLevel(logging.INFO)
    log.propagate = False
