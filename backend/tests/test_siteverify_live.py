"""siteverify itself, with Cloudflare's test secret keys and the token its test site keys hand out.

These call Cloudflare, so they need the internet: ``uv run pytest -m "not live"`` skips them.
https://developers.cloudflare.com/turnstile/troubleshooting/testing/
"""

from __future__ import annotations

import asyncio

import httpx
import pytest

from contact.turnstile import Result, Siteverify, Verdict

pytestmark = pytest.mark.live

DUMMY_TOKEN = "XXXX.DUMMY.TOKEN.XXXX"


def verify(secret: str) -> Result:
    async def run() -> Result:
        async with httpx.AsyncClient() as client:
            return await Siteverify(client, secret).verify(DUMMY_TOKEN)

    return asyncio.run(run())


def test_the_passing_secret() -> None:
    assert verify("1x0000000000000000000000000000000AA").verdict is Verdict.PASSED


def test_the_failing_secret() -> None:
    result = verify("2x0000000000000000000000000000000AA")
    assert result.verdict is Verdict.FAILED
    assert result.detail


def test_the_spent_token_secret() -> None:
    assert verify("3x0000000000000000000000000000000AA") == Result(
        Verdict.FAILED, "timeout-or-duplicate"
    )
