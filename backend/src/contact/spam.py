"""Which messages look like spam. They are still mailed, with a mark in the subject.

A founder may well paste their product's URL and their LinkedIn, so one or two links are normal.
What gives spam away is many links, a link where the name goes, or link markup (HTML or BBCode)
that only makes sense to a forum or a bot.
"""

from __future__ import annotations

import re

SUBJECT_MARK = "[posible spam]"

MAX_LINKS = 2
"""More links than this in the message marks it."""

_LINK = re.compile(r"https?://|www\.", re.IGNORECASE)
_LINK_MARKUP = re.compile(r"<a\s[^>]*href|\[url[=\]]", re.IGNORECASE)


def reasons(name: str, message: str) -> list[str]:
    """Why the message looks like spam, in words for the mail; empty if it does not."""
    found = []
    links = len(_LINK.findall(message))
    if links > MAX_LINKS:
        found.append(f"{links} links in the message")
    if _LINK.search(name):
        found.append("a link in the name")
    if _LINK_MARKUP.search(message):
        found.append("link markup (HTML or BBCode)")
    return found
