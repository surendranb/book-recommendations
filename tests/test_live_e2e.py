# SPDX-License-Identifier: MIT

"""Live OpenLibrary tests + Gutendex fail-soft check + full stdio E2E.
Self-skipping offline."""

import json
import sys

import pytest

from book_recommendations import openlibrary as ol
from book_recommendations import gutendex

live = pytest.mark.live
e2e = pytest.mark.e2e


def _reachable():
    try:
        cards, _ = ol.search_works("islands", limit=2)
        return bool(cards)
    except Exception:
        return False


if not _reachable():
    pytest.skip("OpenLibrary unreachable", allow_module_level=True)


@live
def test_search_works_cards():
    cards, total = ol.search_works("polar exploration", limit=5)
    assert total > 100
    assert len(cards) == 5
    card = cards[0]
    assert card["title"] and card["author"]
    assert card["openlibrary_url"].startswith("https://openlibrary.org/works/")
    assert card["why_picked"].startswith("matched")


@live
def test_blind_date_live():
    picks = ol.blind_date(count=1, seed=7)
    assert picks
    assert picks[0]["title"] and picks[0]["author"]
    assert "blind date" in picks[0]["why_picked"]


@live
def test_gutendex_fail_soft():
    # gutendex.com was unreachable during the build window; both outcomes
    # are valid, never an exception.
    rows = gutendex.fetch_classics(topic="adventure", count=3)
    assert isinstance(rows, list)
    if rows:  # when it IS up, shape must hold
        assert rows[0]["title"] and rows[0]["read_url"]


@e2e
@live
async def test_stdio_session_surface():
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    params = StdioServerParameters(
        command=sys.executable, args=["-m", "book_recommendations"],
        env={"DO_NOT_TRACK": "1", "PATH": "/usr/bin:/bin"})
    async with stdio_client(params) as (reader, writer):
        async with ClientSession(reader, writer) as session:
            await session.initialize()

            tools = await session.list_tools()
            names = {t.name for t in tools.tools}
            assert {"recommend", "blind_date", "free_classics",
                    "skills_list", "skill_read"} <= names

            result = await session.call_tool(
                "recommend", {"topic": "cold war espionage", "count": 2})
            payload = json.loads(result.content[0].text)
            assert len(payload["books"]) == 2
            book = payload["books"][0]
            assert book["title"] and book["author"]
            assert book["openlibrary_url"]

            result = await session.call_tool("blind_date", {"seed": 3})
            payload = json.loads(result.content[0].text)
            assert payload["picks"][0]["why_picked"].startswith("blind date")

            # no-topic nonsense handled honestly:
            result = await session.call_tool(
                "recommend", {"topic": "zzqxjv nonexistograph", "count": 1})
            payload = json.loads(result.content[0].text)
            assert "error" in payload and "INPUT_FIXABLE" in payload["error"]
