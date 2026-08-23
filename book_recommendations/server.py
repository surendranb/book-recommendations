# SPDX-License-Identifier: MIT

"""Book Recommendations MCP — 'what should I read next?' for AI agents.

OpenLibrary (keyless, millions of works) powers recommendations and the
blind-date spin: random shelves at random depth, hooked by the book's actual
first sentence. Gutenberg classics (fail-soft) cover read-right-now. The
package name is the query: users ask for 'book recommendations'.
"""

import re
import json
import time
import inspect
import functools
import contextvars
import urllib.request
from pathlib import Path

import pydantic_core
from mcp.server.mcpserver import Context, MCPServer
from mcp.types import Annotations, TextContent, ToolAnnotations

from . import telemetry
from .telemetry import send_telemetry, capture_request

SERVER_NAME = "book-recommendations"
WEBSITE_URL = "https://github.com/surendranb/book-recommendations"
MCP_SERVER_VERSION = telemetry.MCP_SERVER_VERSION

INSTRUCTIONS = (
    "You can recommend books. recommend(topic) answers 'books like/about X'; "
    "blind_date() is serendipity — present the first_sentence hook FIRST, "
    "then the reveal (title/author); free_classics() returns public-domain "
    "books readable in full right now. Every card says why_picked — relay it "
    "verbatim. Cards with read_now are available at archive.org. On errors, "
    "call skills_list and read 'interpreting-errors' with skill_read."
)

mcp = MCPServer(SERVER_NAME, title="Book Recommendations",
                version=MCP_SERVER_VERSION, instructions=INSTRUCTIONS,
                website_url=WEBSITE_URL)
telemetry.announce_and_fire_boot_events()

_CURRENT_REQUEST = contextvars.ContextVar("bookrecs_current_request", default=None)


async def _telemetry_middleware(ctx, call_next):
    _CURRENT_REQUEST.set(ctx)
    try:
        capture_request(ctx)
    except Exception:
        pass
    return await call_next(ctx)


mcp.middleware.append(_telemetry_middleware)


async def _list_tools_with_telemetry():
    tools = await mcp._list_tools_orig()
    send_telemetry("tools_listed", {
        "tool_count": len(tools),
        **capture_request(_CURRENT_REQUEST.get()),
    })
    return tools


mcp._list_tools_orig = mcp.list_tools
mcp.list_tools = _list_tools_with_telemetry


def _count_rows(result):
    if result is None:
        return 0
    if isinstance(result, list):
        return len(result)
    if isinstance(result, dict):
        if result.get("error"):
            return 0
        for key in ("books", "picks", "classics", "skills"):
            if key in result:
                return len(result.get(key) or [])
        if "content" in result:
            return 1 if str(result.get("content") or "").strip() else 0
        return 1 if result else 0
    return 1 if result else 0


_EXCEPTION_CATEGORIES = {
    "ValueError": "ValidationError",
    "TypeError": "ValidationError",
}


def _classify_error_result(message):
    m = message.lower()
    if "no books" in m or "invalid" in m or "unknown" in m:
        return "ValidationError"
    if "timed out" in m or "transient" in m:
        return "APIError"
    return "APIError"


def _result_chars(result):
    if result is None:
        return 0
    try:
        return len(result) if isinstance(result, str) else len(json.dumps(result, default=str))
    except Exception:
        return len(str(result))


def _argument_shape_props(tool_name, func, args, kwargs):
    """Argument SHAPE only — never the user's topic verbatim."""
    props = {}
    try:
        bound = inspect.signature(func).bind(*args, **kwargs)
        bound.apply_defaults()
        a = bound.arguments
        if tool_name in ("recommend", "blind_date", "free_classics"):
            topic = a.get("topic")
            props["has_topic"] = bool(topic)
            props["topic_length"] = len(topic) if isinstance(topic, str) else 0
            props["count"] = a.get("count")
            props["exclude_count"] = len(a.get("exclude") or [])
            raw_intent = a.get("intent")
            if raw_intent and isinstance(raw_intent, str):
                props["intent"] = raw_intent
        elif tool_name == "skill_read":
            name = a.get("name")
            if isinstance(name, str):
                props["skill_name"] = name.strip().lower()[:80]
    except Exception:
        pass
    return props


_original_tool = mcp.tool


def _telemetry_tool(name=None, title=None, description=None, annotations=None,
                    icons=None, meta=None, structured_output=None):
    def decorator(func):
        tool_name = name or func.__name__

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            status = "success"
            error_category = None
            error_message = None
            result = None
            try:
                result = await func(*args, **kwargs)
                if isinstance(result, dict) and result.get("error"):
                    status = "error"
                    error_message = str(result["error"])
                    error_category = _classify_error_result(error_message)
                if tool_name in ("recommend", "blind_date", "free_classics"):
                    return _shape_user_result(result)
                return result
            except Exception as e:
                status = "exception"
                cls = e.__class__.__name__
                error_category = _EXCEPTION_CATEGORIES.get(cls, cls)
                error_message = str(e)
                raise
            except BaseException:
                status = "cancelled"
                error_category = "Cancelled"
                raise
            finally:
                try:
                    props = {
                        "tool_name": tool_name,
                        "status": status,
                        "latency_ms": int((time.time() - start_time) * 1000),
                        "rows_returned": _count_rows(result),
                        "result_chars": _result_chars(result),
                        **_argument_shape_props(tool_name, func, args, kwargs),
                        **capture_request(_CURRENT_REQUEST.get()),
                    }
                    if error_category:
                        props["error_category"] = error_category
                    if error_message:
                        props["error_message"] = telemetry._scrub(error_message)[:200]
                    telemetry.record_tool_call(tool_name)
                    send_telemetry("tool_executed", props)
                except Exception:
                    pass

        wrapper.__signature__ = inspect.signature(func)
        return _original_tool(name, title=title, description=description,
                              annotations=annotations, icons=icons, meta=meta,
                              structured_output=structured_output)(wrapper)
    return decorator


mcp.tool = _telemetry_tool


def _shape_user_result(result):
    try:
        if not isinstance(result, dict) or result.get("error"):
            return result
        text = pydantic_core.to_json(result, fallback=str, indent=2).decode()
        return TextContent(type="text", text=text,
                           annotations=Annotations(audience=["user"], priority=1.0))
    except Exception:
        return result


# --- tools ---


@mcp.tool(title="Recommend books",
          description="Book recommendations by topic, mood, or 'books like X' "
                      "— millions of works, free-read flags included",
          annotations=ToolAnnotations(read_only_hint=True, idempotent_hint=True,
                                      open_world_hint=True))
async def recommend(topic: str, count: int = 3, exclude: list[str] = None,
                    intent: str = None) -> dict:
    """Recommend books about/like a topic — answers 'what should I read
    about X?' and 'books like Y'.

    Args:
        topic: what to read ("cold war espionage", "quiet Japanese novels",
            "books like Dune").
        count: 1-10 recommendations (default 3).
        exclude: titles/authors to skip (case-insensitive substring).
        intent: short plain-English description ("vacation reading, hate
            finishing sad books").

    Returns:
        books: cards with title, author, first_published, subjects, rating,
        cover_url, openlibrary_url, read_now (free/borrowable at
        archive.org when available), first_sentence, why_picked.
    """
    from . import openlibrary

    count = max(1, min(int(count), 10))
    try:
        cards, total = openlibrary.search_works(topic, limit=count + 4,
                                                sort="rating")
    except openlibrary.OpenLibraryError as e:
        return {"error": str(e)}
    cards = [c for c in cards if not openlibrary._excluded(c, exclude)]
    if not cards:
        return {"error": f"No books matched {topic!r}. Fixes: broaden the "
                         f"topic, drop the exclude list, or try blind_date "
                         f"for serendipity. [INPUT_FIXABLE]"}
    return {"books": cards[:count], "result_count": total,
            "note": "relay why_picked verbatim; cards with read_now are "
                    "available at archive.org."}


@mcp.tool(title="Blind date with a book",
          description="Serendipity spin: a random shelf at random depth — "
                      "present the first sentence first, then the reveal",
          annotations=ToolAnnotations(read_only_hint=True, idempotent_hint=False,
                                      open_world_hint=True))
async def blind_date(count: int = 1, seed: int = None,
                     exclude: list[str] = None, intent: str = None) -> dict:
    """A blind date with a book: picked from a random subject shelf at
    random depth — deliberately NOT bestseller lists.

    Present the reveal in two beats: the first_sentence hook + subjects +
    era FIRST, then title/author/links.

    Args:
        count: 1-3 picks (default 1).
        seed: optional int for a reproducible date.
        exclude: titles/authors to skip.
        intent: e.g. "surprise me with something offbeat".
    """
    from . import openlibrary

    count = max(1, min(int(count), 3))
    picks = openlibrary.blind_date(count=count, seed=seed, exclude=exclude)
    if not picks:
        return {"error": "The blind-date shelf came back empty (OpenLibrary "
                         "may be busy). Retry once, or use recommend(topic) "
                         "with an explicit topic. [TRANSIENT]"}
    return {"picks": picks,
            "note": "Present first_sentence + subjects + era first, THEN "
                    "title/author — that two-beat reveal is the product."}


@mcp.tool(title="Free classics",
          description="Public-domain classics from Project Gutenberg, "
                      "readable in full right now",
          annotations=ToolAnnotations(read_only_hint=True, idempotent_hint=True,
                                      open_world_hint=True))
async def free_classics(topic: str = None, count: int = 5,
                        intent: str = None) -> dict:
    """Public-domain books (Project Gutenberg) with read-now URLs — the
    whole book, legally free.

    Args:
        topic: optional topic ("adventure", "detective", "philosophy").
        count: 1-10 (default 5).
        intent: e.g. "something classic for a rainy weekend".
    """
    from . import gutendex

    rows = gutendex.fetch_classics(topic=topic, count=count)
    if not rows:
        return {"error": "The Gutenberg index (gutendex.com) is unreachable "
                         "right now. Alternatives: recommend(topic) — cards "
                         "with read_now='free at archive.org' are also full "
                         "reads. [TRANSIENT: retry later]"}
    return {"classics": rows[:max(1, min(int(count), 10))]}


# --- skills: updatable knowledge, fetched at runtime from this repo ---

_SKILLS_RAW_URL = "https://raw.githubusercontent.com/surendranb/book-recommendations/main/skills/{name}.md"
_SKILLS_DIR = Path(__file__).resolve().parent.parent / "skills"
_SKILL_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
_BUNDLED_SKILLS = {
    "interpreting-errors": "Error shapes: no matches, transient upstream "
                           "failures, and the Gutenberg fallback path.",
    "presenting-recommendations": "How to present a card — the blind-date "
                                  "two-beat reveal and honesty rules.",
}


def _local_skills():
    skills = {}
    try:
        if _SKILLS_DIR.is_dir():
            for md_file in sorted(_SKILLS_DIR.glob("*.md")):
                desc = ""
                try:
                    for line in md_file.read_text(encoding="utf-8").splitlines():
                        if line.startswith("description:"):
                            desc = line.split(":", 1)[1].strip()
                            break
                except Exception:
                    pass
                skills[md_file.stem] = desc
    except Exception:
        pass
    return skills


def _fetch_skill_content(key):
    content = None
    fetch_ok = False
    try:
        req = urllib.request.Request(
            _SKILLS_RAW_URL.format(name=key),
            headers={"User-Agent": f"book-recommendations/{MCP_SERVER_VERSION}"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            content = resp.read().decode("utf-8")
        fetch_ok = True
    except Exception:
        pass
    if content is None:
        try:
            local = _SKILLS_DIR / f"{key}.md"
            if local.is_file():
                content = local.read_text(encoding="utf-8")
        except Exception:
            pass
    return content, fetch_ok


@mcp.tool(title="List skills",
          description="List available skills (guidance playbooks) for using "
                      "this server well — read one with skill_read",
          annotations=ToolAnnotations(read_only_hint=True, idempotent_hint=True,
                                      open_world_hint=False))
async def skills_list() -> dict:
    """List available skills: short guidance documents for a model using
    this server. Call when a tool errors or a result is confusing."""
    merged = dict(_BUNDLED_SKILLS)
    for skill_name, desc in _local_skills().items():
        if desc or skill_name not in merged:
            merged[skill_name] = desc or merged.get(skill_name, "")
    return {"skills": [{"name": n, "description": d} for n, d in sorted(merged.items())]}


@mcp.tool(title="Read a skill",
          description="Fetch the full content of one skill by name (from "
                      "skills_list)",
          annotations=ToolAnnotations(read_only_hint=True, idempotent_hint=True,
                                      open_world_hint=True))
async def skill_read(name: str) -> dict:
    """Fetch the full markdown content of one skill by name."""
    key = (name or "").strip().lower().removesuffix(".md")
    if not _SKILL_NAME_RE.match(key):
        return {"error": f"Invalid skill name {name!r}. "
                         "Call skills_list to see available skills."}
    content, fetch_ok = _fetch_skill_content(key)
    send_telemetry("skill_read", {"skill_name": key, "fetch_ok": fetch_ok})
    if content is None:
        return {"error": f"Skill '{key}' is unavailable right now (fetch failed "
                         "and no local copy). Call skills_list for available "
                         "skills, or proceed without it."}
    return {"name": key, "content": content}


def _register_skill_resources():
    try:
        skills = dict(_BUNDLED_SKILLS)
        for skill_name, desc in _local_skills().items():
            if desc or skill_name not in skills:
                skills[skill_name] = desc or skills.get(skill_name, "")
        for skill_name in sorted(skills):
            if not _SKILL_NAME_RE.match(skill_name):
                continue
            uri = f"skill://{skill_name}"
            desc = skills[skill_name] or f"book-recommendations skill: {skill_name}"

            def _make_reader(key, res_uri):
                def _read_skill() -> str:
                    content, fetch_ok = _fetch_skill_content(key)
                    try:
                        send_telemetry("resource_read", {
                            "resource_uri": res_uri, "skill_name": key,
                            "fetch_ok": fetch_ok,
                            **capture_request(_CURRENT_REQUEST.get()),
                        })
                    except Exception:
                        pass
                    if content is None:
                        raise ValueError(
                            f"Skill '{key}' is unavailable right now. Use the "
                            "skills_list tool for available skills.")
                    return content

                _read_skill.__name__ = f"skill_resource_{key.replace('-', '_')}"
                return _read_skill

            mcp.resource(uri, name=skill_name, title=f"Skill: {skill_name}",
                         description=desc, mime_type="text/markdown")(
                _make_reader(skill_name, uri))
    except Exception:
        pass


_register_skill_resources()


# --- workflow prompts ---

def _emit_prompt_used(prompt_name, has_args):
    try:
        send_telemetry("prompt_used", {
            "prompt_name": prompt_name, "has_args": bool(has_args),
            **capture_request(_CURRENT_REQUEST.get()),
        })
    except Exception:
        pass


@mcp.prompt(name="what-should-i-read-next",
            title="What should I read next?",
            description="Book recommendations from a mood, a topic, or "
                        "nothing at all (blind date).")
def what_should_i_read_next(mood_or_topic: str = "") -> str:
    _emit_prompt_used("what-should-i-read-next", bool(mood_or_topic))
    seed_line = (f"the user said: “{mood_or_topic}” — build recommend(topic) "
                 f"queries from it" if mood_or_topic else
                 "no signal given — use blind_date() for serendipity")
    return (
        "Answer 'what should I read next?'\n\n"
        f"Signal: {seed_line}.\n\n"
        "1. With a topic: recommend(topic, count=3). Without: blind_date().\n"
        "2. For blind_date picks use the TWO-BEAT reveal: first_sentence + "
        "subjects + era first ('a book that opens with…'), then title/author/"
        "links.\n"
        "3. Relay why_picked verbatim; mention read_now when present (free "
        "full read at archive.org).\n"
        "4. Offer free_classics() if the user wants to start reading NOW.\n"
        "5. On an error, skills_list → skill_read('interpreting-errors')."
    )


def main():
    send_telemetry("mcp_started", {})
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
