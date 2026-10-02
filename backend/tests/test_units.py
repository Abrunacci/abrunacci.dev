"""The pieces on their own: token, addresses, limits, spam marks, fields and settings."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import ClassVar

import pytest

from contact import client_ip, form_token, spam
from contact.limits import LOCAL_TIME, MAILS_PER_DAY, SENDS_PER_WINDOW, DailyCap, SenderLimit
from contact.settings import Settings, SettingsError
from contact.submission import MESSAGE_MAX, parse

SECRET = b"s" * 64
OPENED = 1_800_000_000.0


class TestFormToken:
    def test_a_token_sent_after_a_few_seconds_passes(self) -> None:
        token = form_token.issue(SECRET, OPENED)
        assert form_token.check(SECRET, token, OPENED + 3) is None
        assert form_token.check(SECRET, token, OPENED + form_token.MAX_AGE_SECONDS) is None

    def test_too_fast(self) -> None:
        token = form_token.issue(SECRET, OPENED)
        assert form_token.check(SECRET, token, OPENED + 2.9) is form_token.TokenProblem.TOO_FAST

    def test_from_the_future_counts_as_too_fast(self) -> None:
        token = form_token.issue(SECRET, OPENED)
        assert form_token.check(SECRET, token, OPENED - 60) is form_token.TokenProblem.TOO_FAST

    def test_expired(self) -> None:
        token = form_token.issue(SECRET, OPENED)
        later = OPENED + form_token.MAX_AGE_SECONDS + 1
        assert form_token.check(SECRET, token, later) is form_token.TokenProblem.EXPIRED

    @pytest.mark.parametrize(
        "token",
        [
            "",
            "1800000000",
            "1800000000.",
            "1800000000.abc",
            "-5.abc",
            "\uff11\uff18\uff10\uff10.abc",  # fullwidth digits
            "99999999999999999999.abc",
        ],
    )
    def test_malformed(self, token: str) -> None:
        assert form_token.check(SECRET, token, OPENED) is form_token.TokenProblem.INVALID

    def test_another_secret_or_another_time_does_not_match(self) -> None:
        token = form_token.issue(b"x" * 64, OPENED)
        assert form_token.check(SECRET, token, OPENED + 10) is form_token.TokenProblem.INVALID
        signature = form_token.issue(SECRET, OPENED).split(".")[1]
        moved = f"{int(OPENED) - 100}.{signature}"
        assert form_token.check(SECRET, moved, OPENED + 10) is form_token.TokenProblem.INVALID


class TestLimitKey:
    @pytest.mark.parametrize(
        ("address", "key"),
        [
            ("203.0.113.7", "203.0.113.7"),
            ("::ffff:203.0.113.7", "203.0.113.7"),
            ("2001:db8:1:2:aaaa::1", "2001:db8:1:2::/64"),
            ("2001:db8:1:2:ffff:ffff:ffff:ffff", "2001:db8:1:2::/64"),
            ("2001:db8:1:3::1", "2001:db8:1:3::/64"),
            ("testclient", client_ip.UNKNOWN),
            ("", client_ip.UNKNOWN),
        ],
    )
    def test_key(self, address: str, key: str) -> None:
        assert client_ip.limit_key(address) == key


class TestVisitorAddress:
    def run(self, peer: str | None, header: str | None, host: str) -> str:
        proxy = client_ip.TrustedProxy(host)
        return asyncio.run(client_ip.visitor_address(peer, header, proxy))

    def test_the_header_counts_when_the_proxy_sent_it(self) -> None:
        assert self.run("127.0.0.1", "203.0.113.7", "localhost") == "203.0.113.7"

    def test_only_the_entry_the_proxy_added(self) -> None:
        assert self.run("127.0.0.1", "198.51.100.1, 203.0.113.7", "localhost") == "203.0.113.7"

    def test_from_another_peer_the_header_is_ignored(self) -> None:
        assert self.run("192.0.2.50", "203.0.113.7", "localhost") == "192.0.2.50"

    def test_without_a_trusted_proxy_the_header_is_ignored(self) -> None:
        assert self.run("127.0.0.1", "203.0.113.7", "") == "127.0.0.1"

    def test_a_proxy_that_does_not_resolve_is_not_trusted(self) -> None:
        assert self.run("127.0.0.1", "203.0.113.7", "no-such-host.invalid") == "127.0.0.1"

    def test_ipv4_mapped_peer(self) -> None:
        assert self.run("::ffff:127.0.0.1", "203.0.113.7", "localhost") == "203.0.113.7"


class TestSenderLimit:
    def test_a_window_allows_a_few_sends(self) -> None:
        limit = SenderLimit()
        assert all(limit.allow("a", 100 + i) for i in range(SENDS_PER_WINDOW))
        assert not limit.allow("a", 200)
        assert limit.allow("b", 200)

    def test_the_window_slides(self) -> None:
        limit = SenderLimit()
        for i in range(SENDS_PER_WINDOW):
            limit.allow("a", 100 + i)
        assert not limit.allow("a", 100 + 3599)
        assert limit.allow("a", 100 + 3600)

    def test_memory_is_bounded(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("contact.limits.MAX_TRACKED_SENDERS", 3)
        limit = SenderLimit()
        for key in "abcd":
            limit.allow(key, 0)
        assert len(limit._sends) == 3
        assert "a" not in limit._sends


class TestDailyCap:
    def at(self, text: str) -> float:
        return datetime.fromisoformat(text).replace(tzinfo=LOCAL_TIME).timestamp()

    def test_quota_and_reset_at_local_midnight(self) -> None:
        cap = DailyCap()
        morning = self.at("2026-10-02T09:00")
        assert all(cap.reserve(morning) for _ in range(MAILS_PER_DAY))
        assert not cap.reserve(self.at("2026-10-02T23:59"))
        assert cap.reserve(self.at("2026-10-03T00:00"))

    def test_a_failed_send_gives_its_slot_back(self) -> None:
        cap = DailyCap()
        now = self.at("2026-10-02T09:00")
        for _ in range(MAILS_PER_DAY):
            cap.reserve(now)
        cap.release(now)
        assert cap.reserve(now)

    def test_one_notice_a_day(self) -> None:
        cap = DailyCap()
        today = self.at("2026-10-02T09:00")
        assert cap.notice_due(today)
        cap.notice_sent(today)
        assert not cap.notice_due(today)
        assert cap.notice_due(self.at("2026-10-03T09:00"))


class TestSpam:
    def test_a_normal_message(self) -> None:
        message = "We are hiring. See https://example.com and https://linkedin.com/in/me"
        assert spam.reasons("Ada Lovelace", message) == []

    def test_many_links(self) -> None:
        message = "https://a.example http://b.example www.c.example"
        assert spam.reasons("Ada", message) == ["3 links in the message"]

    def test_a_link_in_the_name(self) -> None:
        assert spam.reasons("Cheap SEO www.example.com", "hi") == ["a link in the name"]

    @pytest.mark.parametrize("markup", ['<a href="x">x</a>', "[url=x]x[/url]", "[URL]x[/URL]"])
    def test_link_markup(self, markup: str) -> None:
        assert spam.reasons("Ada", markup) == ["link markup (HTML or BBCode)"]


class TestSubmission:
    def test_fields_are_cleaned(self) -> None:
        body = b"name=+Ada%0D%0ALovelace+&email=+ada%40example.com+&message=Hi%0D%0Athere+&website="
        submission = parse(body)
        assert submission.name == "Ada Lovelace"
        assert submission.email == "ada@example.com"
        assert submission.message == "Hi\nthere"
        assert submission.errors == {}

    def test_missing_and_invalid_fields(self) -> None:
        submission = parse(b"name=&email=not-an-address&message=")
        assert set(submission.errors) == {"name", "email", "message"}

    def test_too_long(self) -> None:
        body = f"name=Ada&email=a%40b.co&message={'x' * (MESSAGE_MAX + 1)}".encode()
        assert set(parse(body).errors) == {"message"}

    def test_invalid_utf8_does_not_crash(self) -> None:
        assert parse(b"name=%ff&email=a%40b.co&message=hi").name == "�"


class TestSettings:
    ENV: ClassVar[dict[str, str]] = {
        "RESEND_API_KEY": "re_test",
        "FORM_SECRET": "f" * 64,
        "MAIL_FROM": "abrunacci.dev <contact@mail.abrunacci.dev>",
        "MAIL_TO": "hello@abrunacci.dev",
    }

    def test_defaults(self) -> None:
        settings = Settings.from_env(self.ENV)
        assert settings.subject_prefix == "[abrunacci.dev]"
        assert settings.site_url == "https://abrunacci.dev"
        assert settings.trusted_proxy == ""

    @pytest.mark.parametrize("name", ["RESEND_API_KEY", "FORM_SECRET", "MAIL_FROM", "MAIL_TO"])
    def test_required(self, name: str) -> None:
        with pytest.raises(SettingsError, match=name):
            Settings.from_env({**self.ENV, name: " "})

    def test_a_short_secret_is_refused(self) -> None:
        with pytest.raises(SettingsError, match="FORM_SECRET"):
            Settings.from_env({**self.ENV, "FORM_SECRET": "short"})

    def test_secrets_stay_out_of_repr(self) -> None:
        text = repr(Settings.from_env(self.ENV))
        assert "re_test" not in text
        assert "f" * 64 not in text
