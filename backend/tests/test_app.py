"""The whole flow through HTTP, with a fake mailer and a clock the test moves."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from contact.app import create_app
from contact.limits import LOCAL_TIME, MAILS_PER_DAY, SENDS_PER_WINDOW
from contact.mailer import Mail, SendError
from contact.settings import Settings

SETTINGS = Settings(
    resend_api_key="re_test",
    form_secret=b"f" * 64,
    mail_from="abrunacci.dev <contact@mail.abrunacci.dev>",
    mail_to="hello@abrunacci.dev",
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
class Clock:
    now: float = 1_800_000_000.0

    def __call__(self) -> float:
        return self.now


@dataclass
class Form:
    client: TestClient
    mailer: FakeMailer
    clock: Clock

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
            "/api/contact", data={"opened": token, **GOOD, **fields}, follow_redirects=False
        )
        return response.status_code, response.headers.get("location", ""), response.text


@pytest.fixture
def form() -> Iterator[Form]:
    mailer, clock = FakeMailer(), Clock()
    with TestClient(create_app(SETTINGS, mailer, clock)) as client:
        yield Form(client, mailer, clock)


def events(caplog: pytest.LogCaptureFixture) -> list[dict[str, object]]:
    return [json.loads(r.getMessage()) for r in caplog.records if r.name == "contact"]


@pytest.fixture(autouse=True)
def _capture(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level("INFO", logger="contact")
    # The app's own handler stops propagation; let pytest see the records.
    logging.getLogger("contact").propagate = True


SENT = "/contact?status=sent"


def test_health(form: Form) -> None:
    assert form.client.get("/api/health").json() == {"status": "ok"}


def test_the_form_page(form: Form) -> None:
    page = form.client.get("/contact")
    assert page.headers["cache-control"] == "no-store"
    assert "script-src" not in page.headers["content-security-policy"]
    assert "<script" not in page.text
    assert 'action="/api/contact"' in page.text
    assert 'name="website"' in page.text
    assert 'maxlength="5000"' in page.text


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
    assert events(caplog) == [{"event": "sent", "sender": "unknown", "spam": []}]


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
    # Kept in the log in case a person was caught by mistake.
    assert event["message"] == "Let's talk."


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
    assert events(caplog) == [{"event": "discarded", "sender": "unknown", "reason": "too_large"}]


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
        "/api/contact", data={"opened": token.group(1), **GOOD}, follow_redirects=False
    )
    assert response.headers["location"] == SENT
    assert len(form.mailer.sent) == 1


def test_the_per_sender_limit(form: Form, caplog: pytest.LogCaptureFixture) -> None:
    for _ in range(SENDS_PER_WINDOW + 1):
        form.send()
    assert len(form.mailer.sent) == SENDS_PER_WINDOW
    assert events(caplog)[-1]["reason"] == "sender_limit"


def test_past_the_daily_limit_messages_are_held(
    form: Form, caplog: pytest.LogCaptureFixture
) -> None:
    form.clock.now = datetime(2026, 10, 2, tzinfo=LOCAL_TIME).timestamp()
    for i in range(MAILS_PER_DAY + 2):
        # Within the same day, an hour apart so the per-sender limit stays out of the way.
        form.clock.now += 3600
        assert form.send(message=f"Message {i}")[1] == SENT
    mailed = [m for m in form.mailer.sent if "Daily limit" not in m.subject]
    notices = [m for m in form.mailer.sent if "Daily limit" in m.subject]
    held = [e for e in events(caplog) if e["event"] == "held"]
    assert len(mailed) == MAILS_PER_DAY
    assert len(notices) == 1
    assert [e["message"] for e in held] == [f"Message {i}" for i in (20, 21)]


def test_send_failure_keeps_the_text_on_the_page(
    form: Form, caplog: pytest.LogCaptureFixture
) -> None:
    form.mailer.failing = True
    status, _, body = form.send()
    assert status == 503
    assert "could not be sent right now" in body
    assert "Let&#39;s talk." in body
    [event] = events(caplog)
    assert event.keys() == {"event", "id", "time", "length", "error"}
    assert event["event"] == "send_failed"
    assert event["time"] == "2027-01-15T08:00:10+00:00"
    assert event["length"] == len("Let's talk.")
    assert event["error"] == "Resend answered 500: down"


def test_send_failure_logs_no_personal_data(form: Form, caplog: pytest.LogCaptureFixture) -> None:
    form.mailer.failing = True
    form.mailer.error = "Resend answered 422: Ada Lovelace <ada@example.com> is not valid"
    form.send()
    [event] = events(caplog)
    assert event["error"] == "Resend answered 422: <name> <<email>> is not valid"
    logged = json.dumps(event)
    for value in GOOD.values():
        assert not value or value not in logged


def test_the_post_address_opened_by_hand(form: Form) -> None:
    response = form.client.get("/api/contact", follow_redirects=False)
    assert response.headers["location"] == "/contact"


def test_the_font_is_served(form: Form) -> None:
    response = form.client.get("/api/static/inter-latin-wght-normal-5.3.0.woff2")
    assert response.status_code == 200
    assert response.content[:4] == b"wOF2"
