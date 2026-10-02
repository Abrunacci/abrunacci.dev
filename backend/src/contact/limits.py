"""The two limits, both in memory: per sender and per day.

Memory is enough for one container, but it starts empty after every deploy, rollback or reboot:
each sender's count starts again, and so does the day's. The worst that does is let one more
day's quota through on a day with a deploy.
"""

from __future__ import annotations

from collections import OrderedDict, deque
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

SENDS_PER_WINDOW = 5
WINDOW_SECONDS = 60 * 60
"""Five messages an hour from one address (or IPv6 /64)."""

MAX_TRACKED_SENDERS = 10_000
"""Bounds the memory a flood of addresses can take: the least recent ones are forgotten."""

MAILS_PER_DAY = 20

LOCAL_TIME = timezone(timedelta(hours=-3), "ART")
"""The day resets at midnight in Argentina (no daylight saving time)."""


@dataclass
class SenderLimit:
    _sends: OrderedDict[str, deque[float]] = field(default_factory=OrderedDict)

    def allow(self, key: str, now: float) -> bool:
        """Count one message from ``key``, unless it already sent its quota in the window."""
        sends = self._sends.pop(key, None) or deque()
        while sends and now - sends[0] >= WINDOW_SECONDS:
            sends.popleft()
        allowed = len(sends) < SENDS_PER_WINDOW
        if allowed:
            sends.append(now)
        # Most recent last, so the oldest is the first to go.
        self._sends[key] = sends
        while len(self._sends) > MAX_TRACKED_SENDERS:
            self._sends.popitem(last=False)
        return allowed


@dataclass
class DailyCap:
    """At most ``MAILS_PER_DAY`` messages mailed per local day, and one notice when it is hit."""

    _day: date | None = None
    _sent: int = 0
    _notice_sent: bool = False

    def reserve(self, now: float) -> bool:
        """Take one of today's slots. Give it back with ``release`` if the mail fails."""
        self._roll(now)
        if self._sent >= MAILS_PER_DAY:
            return False
        self._sent += 1
        return True

    def release(self, now: float) -> None:
        self._roll(now)
        self._sent = max(0, self._sent - 1)

    def notice_due(self, now: float) -> bool:
        self._roll(now)
        return not self._notice_sent

    def notice_sent(self, now: float) -> None:
        self._roll(now)
        self._notice_sent = True

    def _roll(self, now: float) -> None:
        today = datetime.fromtimestamp(now, LOCAL_TIME).date()
        if today != self._day:
            self._day, self._sent, self._notice_sent = today, 0, False
