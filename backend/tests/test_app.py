"""The whole flow through HTTP, with a fake mailer, a fake Cloudflare and a clock the test moves.

The fake Cloudflare answers like siteverify does for Cloudflare's test secret keys:
https://developers.cloudflare.com/turnstile/troubleshooting/testing/
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import parse_qs

import httpx
import pytest
from fastapi.testclient import TestClient

from contact.app import create_app
from contact.limits import LOCAL_TIME, MAILS_PER_DAY, SENDS_PER_WINDOW
from contact.mailer import Mail, SendError
from contact.settings import Settings
from contact.turnstile import SITEVERIFY_URL, Siteverify

# Cloudflare's test keys. The test site keys make the widget hand over DUMMY_TOKEN, which only
# the test secret keys accept.
PASSES = "1x0000000000000000000000000000000AA"
FAILS = "2x0000000000000000000000000000000AA"
SPENT = "3x0000000000000000000000000000000AA"
SITE_KEY = "1x00000000000000000000AA"
DUMMY_TOKEN = "XXXX.DUMMY.TOKEN.XXXX"

SETTINGS = Settings(
    resend_api_key="re_test",
    form_secret=b"f" * 64,
    mail_from="abrunacci.dev <contact@mail.abrunacci.dev>",
    mail_to="hello@abrunacci.dev",
    turnstile_site_key=SITE_KEY,
    turnstile_secret_key=PASSES,
)
GOOD = {"name": "Ada Lovelace", "email": "ada@example.com", "message": "Let's talk.", "website": ""}


@dataclass
class FakeMailer:
    sent: list[Mail] = field(default_factory=list)
    failing: bool = False
    error: str = "Resend answered 500: down"

    async def send(self, mail: Mail) -> None:
        if self.failing:
            raise SendError(self.error)
        self.sent.append(mail)


@dataclass
class FakeCloudflare:
    """siteverify, answering by secret key as Cloudflare does for its test keys."""

    calls: list[dict[str, list[str]]] = field(default_factory=list)
    down: Exception | None = None
    """Raised instead of answering: Cloudflare unreachable."""
    answer: httpx.Response | None = None
    """Sent instead of the usual answer."""

    def __call__(self, request: httpx.Request) -> httpx.Response:
        assert str(request.url) == SITEVERIFY_URL
        fields = parse_qs(request.content.decode())
        self.calls.append(fields)
        if self.down:
            raise self.down
        if self.answer:
            return self.answer
        codes = {
            FAILS: ["invalid-input-response"],
            SPENT: ["timeout-or-duplicate"],
        }.get(fields["secret"][0], ["invalid-input-secret"])
        if fields["secret"][0] == PASSES:
            return httpx.Response(200, json={"success": True, "error-codes": []})
        return httpx.Response(200, json={"success": False, "error-codes": codes})


@dataclass
class Clock:
    now: float = 1_800_000_000.0

    def __call__(self) -> float:
        return self.now


@dataclass
class Form:
    client: TestClient
    mailer: FakeMailer
    clock: Clock
    cloudflare: FakeCloudflare

    def open(self) -> str:
        page = self.client.get("/contact")
        assert page.status_code == 200
        match = re.search(r'name="opened" value="([^"]+)"', page.text)
        assert match
        return match.group(1)

    def send(self, wait: float = 10, **fields: str) -> tuple[int, str, str]:
        """Open the form, wait, post it. Returns the status, location and body."""
        token = self.open()
        self.clock.now += wait
        response = self.client.post(
            "/api/contact",
            data={"opened": token, "cf-turnstile-response": DUMMY_TOKEN, **GOOD, **fields},
            follow_redirects=False,
        )
        return response.status_code, response.headers.get("location", ""), response.text


@pytest.fixture
def secret_key() -> str:
    """The Turnstile secret the app runs with; a test overrides it with parametrize."""
    return PASSES


@pytest.fixture
def form(secret_key: str) -> Iterator[Form]:
    mailer, clock, cloudflare = FakeMailer(), Clock(), FakeCloudflare()
    verifier = Siteverify(httpx.AsyncClient(transport=httpx.MockTransport(cloudflare)), secret_key)
    with TestClient(create_app(SETTINGS, mailer, clock, verifier)) as client:
        yield Form(client, mailer, clock, cloudflare)


def events(caplog: pytest.LogCaptureFixture) -> list[dict[str, object]]:
    return [json.loads(r.getMessage()) for r in caplog.records if r.name == "contact"]


@pytest.fixture(autouse=True)
def _capture(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level("INFO", logger="contact")
    # The app's own handler stops propagation; let pytest see the records.
    logging.getLogger("contact").propagate = True


SENT = "/contact?status=sent"


def assert_no_form_content(event: dict[str, object]) -> None:
    assert not {"name", "email", "message", "sender"} & event.keys()
    logged = json.dumps(event)
    for value in GOOD.values():
        assert not value or value not in logged


def test_health(form: Form) -> None:
    assert form.client.get("/api/health").json() == {"status": "ok"}


def test_the_form_page(form: Form) -> None:
    page = form.client.get("/contact")
    assert page.headers["cache-control"] == "no-store"
    assert 'action="/api/contact"' in page.text
    assert 'name="website"' in page.text
    assert 'maxlength="5000"' in page.text


def test_the_form_page_runs_turnstile(form: Form) -> None:
    page = form.client.get("/contact")
    csp = page.headers["content-security-policy"]
    assert "script-src 'self' https://challenges.cloudflare.com;" in csp
    assert "frame-src https://challenges.cloudflare.com;" in csp
    assert "default-src 'none';" in csp
    assert f'data-sitekey="{SITE_KEY}"' in page.text
    assert 'data-appearance="interaction-only"' in page.text
    assert '<script src="/api/static/form.js" defer></script>' in page.text
    assert 'type="submit" disabled>' in page.text
    script = form.client.get("/api/static/form.js")
    assert script.status_code == 200
    assert "turnstileReady" in script.text
    assert "challenges.cloudflare.com/turnstile/v0/api.js" in script.text


def test_without_javascript_the_address_replaces_the_form(form: Form) -> None:
    page = form.client.get("/contact").text
    noscript = page[page.index("<noscript>") : page.index("</noscript>")]
    assert ".form { display: none; }" in noscript
    assert (
        'id="alternative" hidden>You can also write to me directly at '
        '<a href="mailto:hello@abrunacci.dev">hello@abrunacci.dev</a>.</p>'
    ) in page


def test_the_confirmation_page(form: Form) -> None:
    page = form.client.get(SENT)
    assert page.status_code == 200
    assert "Thanks, I got your message" in page.text


def test_a_good_message_is_mailed(form: Form, caplog: pytest.LogCaptureFixture) -> None:
    assert form.send() == (303, SENT, "")
    [mail] = form.mailer.sent
    assert mail.subject == "[abrunacci.dev] Ada Lovelace"
    assert mail.reply_to == "ada@example.com"
    assert "Let's talk." in mail.text
    assert "Turnstile" not in mail.text
    [call] = form.cloudflare.calls
    assert call == {"secret": [PASSES], "response": [DUMMY_TOKEN]}
    [event] = events(caplog)
    assert event.keys() == {"event", "id", "time", "length"}
    assert event["event"] == "sent"
    assert event["length"] == len("Let's talk.")


def test_possible_spam_is_mailed_with_a_mark(form: Form) -> None:
    form.send(message="https://a.example https://b.example https://c.example")
    [mail] = form.mailer.sent
    assert mail.subject == "[abrunacci.dev] [posible spam] Ada Lovelace"
    assert "3 links in the message" in mail.text


@pytest.mark.parametrize(
    ("fields", "wait", "reason"),
    [
        ({"website": "https://spam.example"}, 10, "honeypot"),
        ({}, 1, "too_fast"),
        ({}, 25 * 60 * 60, "expired_token"),
    ],
)
def test_bots_get_the_same_confirmation(
    form: Form,
    caplog: pytest.LogCaptureFixture,
    fields: dict[str, str],
    wait: float,
    reason: str,
) -> None:
    assert form.send(wait, **fields) == (303, SENT, "")
    assert form.mailer.sent == []
    [event] = events(caplog)
    assert event["event"] == "discarded"
    assert event["reason"] == reason
    assert_no_form_content(event)


def test_bots_caught_before_turnstile_cost_no_call(form: Form) -> None:
    form.send(website="https://spam.example")
    form.send(wait=1)
    assert form.cloudflare.calls == []


@pytest.mark.parametrize(
    ("secret_key", "fields", "reason"),
    [
        (PASSES, {"cf-turnstile-response": ""}, "turnstile: missing-input-response"),
        (PASSES, {"cf-turnstile-response": "x" * 2049}, "turnstile: invalid-input-response"),
        (FAILS, {}, "turnstile: invalid-input-response"),
        (SPENT, {}, "turnstile: timeout-or-duplicate"),
    ],
)
def test_turnstile_says_no(
    form: Form, caplog: pytest.LogCaptureFixture, fields: dict[str, str], reason: str
) -> None:
    assert form.send(10, **fields) == (303, SENT, "")
    assert form.mailer.sent == []
    [event] = events(caplog)
    assert (event["event"], event["reason"]) == ("discarded", reason)
    assert_no_form_content(event)


@pytest.mark.parametrize(
    ("down", "answer", "detail"),
    [
        (httpx.ReadTimeout("slow"), None, "ReadTimeout"),
        (httpx.ConnectError("refused"), None, "ConnectError"),
        (None, httpx.Response(502, text="Bad gateway"), "siteverify answered 502"),
        (None, httpx.Response(200, text="<html>"), "siteverify answered 200"),
        (None, httpx.Response(200, json={"error-codes": []}), "siteverify answered 200"),
        (
            None,
            httpx.Response(200, json={"success": False, "error-codes": ["internal-error"]}),
            "internal-error",
        ),
    ],
)
def test_without_an_answer_from_cloudflare_it_is_mailed_marked(
    form: Form,
    caplog: pytest.LogCaptureFixture,
    down: Exception | None,
    answer: httpx.Response | None,
    detail: str,
) -> None:
    form.cloudflare.down, form.cloudflare.answer = down, answer
    assert form.send() == (303, SENT, "")
    [mail] = form.mailer.sent
    assert mail.subject == "[abrunacci.dev] [sin verificar] Ada Lovelace"
    assert f"Not checked by Turnstile: no usable answer from Cloudflare ({detail})." in mail.text
    [event] = events(caplog)
    assert (event["event"], event["reason"]) == ("sent", f"turnstile_unavailable: {detail}")


@pytest.mark.parametrize("secret_key", ["not-the-real-secret"])
def test_a_wrong_secret_marks_every_message_instead_of_dropping_it(form: Form) -> None:
    form.send()
    [mail] = form.mailer.sent
    assert mail.subject == "[abrunacci.dev] [sin verificar] Ada Lovelace"
    assert "(invalid-input-secret)" in mail.text


def test_unchecked_and_possible_spam(form: Form) -> None:
    form.cloudflare.down = httpx.ReadTimeout("slow")
    form.send(message="https://a.example https://b.example https://c.example")
    [mail] = form.mailer.sent
    assert mail.subject == "[abrunacci.dev] [sin verificar] [posible spam] Ada Lovelace"


def test_a_forged_token(form: Form, caplog: pytest.LogCaptureFixture) -> None:
    response = form.client.post(
        "/api/contact", data={"opened": "1800000000.abc", **GOOD}, follow_redirects=False
    )
    assert response.headers["location"] == SENT
    assert events(caplog)[0]["reason"] == "invalid_token"


def test_a_huge_body_is_discarded(form: Form, caplog: pytest.LogCaptureFixture) -> None:
    response = form.client.post(
        "/api/contact", data={"message": "x" * 40_000}, follow_redirects=False
    )
    assert response.headers["location"] == SENT
    [event] = events(caplog)
    assert event.keys() == {"event", "id", "time", "reason"}
    assert (event["event"], event["reason"]) == ("discarded", "too_large")


def test_errors_show_the_form_again_with_the_text(form: Form) -> None:
    status, _, body = form.send(email="not-an-address", message="My <b>text</b>")
    assert status == 400
    assert "Enter a valid email address" in body
    assert 'aria-invalid="true"' in body
    assert "My &lt;b&gt;text&lt;/b&gt;" in body
    assert form.mailer.sent == []


def test_fixing_a_typo_right_away_is_not_too_fast(form: Form) -> None:
    status, _, body = form.send(email="ada@")
    assert status == 400
    token = re.search(r'name="opened" value="([^"]+)"', body)
    assert token
    response = form.client.post(
        "/api/contact",
        data={"opened": token.group(1), "cf-turnstile-response": DUMMY_TOKEN, **GOOD},
        follow_redirects=False,
    )
    assert response.headers["location"] == SENT
    assert len(form.mailer.sent) == 1


def test_the_per_sender_limit(form: Form, caplog: pytest.LogCaptureFixture) -> None:
    for _ in range(SENDS_PER_WINDOW + 1):
        form.send()
    assert len(form.mailer.sent) == SENDS_PER_WINDOW
    assert events(caplog)[-1]["reason"] == "sender_limit"


def test_past_the_daily_limit_messages_are_turned_away(
    form: Form, caplog: pytest.LogCaptureFixture
) -> None:
    form.clock.now = datetime(2026, 10, 2, tzinfo=LOCAL_TIME).timestamp()
    for i in range(MAILS_PER_DAY + 2):
        # Within the same day, an hour apart so the per-sender limit stays out of the way.
        form.clock.now += 3600
        status, location, body = form.send(message=f"Message {i}")
        if i < MAILS_PER_DAY:
            assert (status, location) == (303, SENT)
        else:
            assert status == 429
            assert "limit for today" in body
            assert f"Message {i}" in body
    mailed = [m for m in form.mailer.sent if "Daily limit" not in m.subject]
    notices = [m for m in form.mailer.sent if "Daily limit" in m.subject]
    over = [e for e in events(caplog) if e["event"] == "daily_limit"]
    assert len(mailed) == MAILS_PER_DAY
    assert len(notices) == 1
    assert len(over) == 2
    for event in events(caplog):
        assert_no_form_content(event)


def test_send_failure_keeps_the_text_on_the_page(
    form: Form, caplog: pytest.LogCaptureFixture
) -> None:
    form.mailer.failing = True
    status, _, body = form.send()
    assert status == 503
    assert "could not be sent right now" in body
    assert "Let&#39;s talk." in body
    [event] = events(caplog)
    assert event.keys() == {"event", "id", "time", "length", "reason"}
    assert event["event"] == "send_failed"
    assert event["time"] == "2027-01-15T08:00:10+00:00"
    assert event["length"] == len("Let's talk.")
    assert event["reason"] == "Resend answered 500: down"


def test_send_failure_logs_no_personal_data(form: Form, caplog: pytest.LogCaptureFixture) -> None:
    form.mailer.failing = True
    form.mailer.error = "Resend answered 422: Ada Lovelace <ada@example.com> is not valid"
    form.send()
    [event] = events(caplog)
    assert event["reason"] == "Resend answered 422: <name> <<email>> is not valid"
    assert_no_form_content(event)


def test_the_post_address_opened_by_hand(form: Form) -> None:
    response = form.client.get("/api/contact", follow_redirects=False)
    assert response.headers["location"] == "/contact"


def test_the_font_is_served(form: Form) -> None:
    response = form.client.get("/api/static/inter-latin-wght-normal-5.3.0.woff2")
    assert response.status_code == 200
    assert response.content[:4] == b"wOF2"
