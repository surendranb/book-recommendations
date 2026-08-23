# SPDX-License-Identifier: MIT

"""Gutendex client — free classics from Project Gutenberg. Keyless.

FAIL-SOFT BY DESIGN: gutendex.com is a community service and can be slow or
unreachable (it was during this repo's own build window). Every failure
returns [] — the free_classics tool then says so honestly and points at
OpenLibrary's read_now links instead. Never an error bubble.
"""

import requests

GUTENDEX_URL = "https://gutendex.com/books"
USER_AGENT = "book-recommendations/0.1.0 (MCP server; +https://github.com/surendranb/book-recommendations)"
TIMEOUT = 8.0


def fetch_classics(topic=None, count=5):
    """Public-domain books matching a topic, with read-now URLs.
    Returns [] on any failure (fail-soft)."""
    params = {"mime_type": "text/html"}
    if topic:
        params["topic"] = topic
    try:
        resp = requests.get(GUTENDEX_URL, params=params, timeout=TIMEOUT,
                            headers={"User-Agent": USER_AGENT})
        resp.raise_for_status()
        results = resp.json().get("results", [])
    except Exception:
        return []
    out = []
    for b in results[:max(1, min(int(count), 20))]:
        formats = b.get("formats") or {}
        read_url = formats.get("text/html; charset=utf-8") \
            or formats.get("text/html") \
            or next((u for f, u in formats.items()
                     if "html" in f.lower() and u), None)
        authors = ", ".join(a.get("name", "?")
                            for a in (b.get("authors") or [])[:2]) or None
        out.append({
            "title": b.get("title"),
            "author": authors,
            "languages": (b.get("languages") or [None])[0],
            "downloads": b.get("download_count"),
            "read_url": read_url,
            "why_picked": (f"public-domain classic"
                           + (f" on “{topic}”" if topic else "")
                           + " — readable in full right now"),
        })
    return out
