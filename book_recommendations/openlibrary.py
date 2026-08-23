# SPDX-License-Identifier: MIT

"""OpenLibrary client — the primary book-recommendation source. Keyless.

Search API: https://openlibrary.org/search.json (verified keyless).
Fields used: title, author_name, first_publish_year, cover_i, key, subject,
first_sentence (the blind-date hook), ebook_access (read-free-right-now
signal: 'public' = freely readable on archive.org, 'borrowable' = IA loan).
"""

import random

import requests

SEARCH_URL = "https://openlibrary.org/search.json"
COVER_URL = "https://covers.openlibrary.org/b/id/{cover_i}-M.jpg"
WORK_URL = "https://openlibrary.org{key}"
USER_AGENT = "book-recommendations/0.1.0 (MCP server; +https://github.com/surendranb/book-recommendations)"
TIMEOUT = 10.0
FIELDS = ("title,author_name,first_publish_year,cover_i,key,subject,"
          "first_sentence,ebook_access,edition_count,ratings_average")

# Curated blind-date subject pool: distinctive enough to fish the long tail,
# common enough that OpenLibrary always has works.
SUBJECT_POOL = [
    "lighthouses", "polar exploration", "clockwork", "tea", "islands",
    "circus", "beekeeping", "maps", "distillers", "gardens", "storms",
    "trains", "island life", "letters", "cooking", "sailing", "libraries",
    "mountains", "deserts", "birds", "ghosts", "heists", "monasteries",
    "circumnavigation", "puppetry", "cheese", "wine", "fonts", "bridges",
    "volcanoes", "codebreakers", "street food", "orchards", "fountain pens",
    "night markets", "archaeology", "translated literature", "small towns",
    "second chances", "quiet lives", "long walks", "ordinary miracles",
]


class OpenLibraryError(Exception):
    def __init__(self, message):
        super().__init__(message)


def _get(params):
    try:
        resp = requests.get(SEARCH_URL, params=params, timeout=TIMEOUT,
                            headers={"User-Agent": USER_AGENT})
        resp.raise_for_status()
        return resp.json()
    except requests.Timeout as e:
        raise OpenLibraryError("OpenLibrary request timed out "
                               "[TRANSIENT: retry once]") from e
    except requests.RequestException as e:
        raise OpenLibraryError(f"OpenLibrary request failed: {e} "
                               "[TRANSIENT: retry once]") from e
    except ValueError as e:
        raise OpenLibraryError("OpenLibrary returned a non-JSON body "
                               "[TRANSIENT]") from e


def _first_sentence(doc):
    raw = doc.get("first_sentence")
    if isinstance(raw, list):
        raw = raw[0] if raw else None
    if not raw:
        return None
    text = str(raw).strip()
    return text[:280] or None


def _card(doc, why):
    key = doc.get("key") or ""
    cover_i = doc.get("cover_i")
    access = doc.get("ebook_access") or "unknown"
    return {
        "title": doc.get("title"),
        "author": (doc.get("author_name") or [None])[0],
        "authors": (doc.get("author_name") or [])[:3],
        "first_published": doc.get("first_publish_year"),
        "subjects": [s for s in (doc.get("subject") or [])[:6]
                     if not any(c.isdigit() for c in s)][:6],
        "first_sentence": _first_sentence(doc),
        "cover_url": COVER_URL.format(cover_i=cover_i) if cover_i else None,
        "openlibrary_url": WORK_URL.format(key=key) if key else None,
        "read_now": ("free at archive.org" if access == "public"
                     else "borrowable at archive.org" if access == "borrowable"
                     else None),
        "rating": round(doc["ratings_average"], 1)
        if doc.get("ratings_average") else None,
        "why_picked": why,
    }


def search_works(query, limit=10, page=1, sort=None):
    """Search works by free-text query. Returns (cards, num_found)."""
    params = {"q": query, "limit": max(1, min(int(limit), 30)),
              "page": page, "fields": FIELDS}
    if sort:
        params["sort"] = sort
    data = _get(params)
    cards = [_card(d, f"matched your ask “{query}”") for d in data.get("docs", [])]
    return cards, data.get("numFound", 0)


def subject_works(subject, limit=10, page=1):
    """Works in a subject shelf (subject: search). Returns (cards, num_found)."""
    return search_works(f"subject:{subject}", limit=limit, page=page,
                        sort="rating" if page == 1 else None)


def blind_date(count=1, seed=None, exclude=None):
    """The differentiator: random subject from the pool, random page depth,
    random pick — a book chosen for serendipity, not bestseller lists.
    Cards carry first_sentence as the hook and why_picked honestly."""
    rng = random.Random(seed)
    picks, tried_subjects = [], []
    attempts = 0
    while len(picks) < count and attempts < 6:
        attempts += 1
        subject = rng.choice(SUBJECT_POOL)
        if subject in tried_subjects and len(tried_subjects) < len(SUBJECT_POOL):
            continue
        tried_subjects.append(subject)
        page = rng.randint(1, 8)  # deep shelf, not the top of the list
        try:
            cards, _found = subject_works(subject, limit=12, page=page)
        except OpenLibraryError:
            continue
        pool = [c for c in cards
                if c["title"] and c["author"]
                and not _excluded(c, exclude)]
        # The two-beat reveal needs a hook: prefer records that carry a
        # first sentence (don't require — some shelves lack them entirely).
        pool.sort(key=lambda c: c["first_sentence"] is None)
        if not pool:
            continue
        take = min(count - len(picks), max(1, len(pool) // 2))
        for card in rng.sample(pool, take):
            card["why_picked"] = (f"blind date: fished the “{subject}” shelf "
                                  f"at depth {page} — picked for serendipity, "
                                  f"not sales rank")
            card["hook"] = _hook(card)
            picks.append(card)
        if picks:
            break  # one subject per spin keeps picks thematically related
    return picks


def _excluded(card, exclude):
    if not exclude:
        return False
    hay = f"{card.get('title') or ''} {card.get('author') or ''}".lower()
    return any(str(e).lower() in hay for e in exclude)


def _hook(card):
    """The blind-date opening beat. The real first sentence when the record
    has one; otherwise an honest one-liner built from era + subjects +
    availability — never an invented sentence."""
    if card.get("first_sentence"):
        return card["first_sentence"]
    bits = []
    if card.get("first_published"):
        bits.append(f"from {card['first_published']}")
    if card.get("subjects"):
        about = ", ".join(card["subjects"][:2])
        bits.append(f"about {about}")
    if card.get("read_now"):
        bits.append(card["read_now"])
    return (f"A book {' '.join(bits)}" if bits
            else "A book chosen off the bestseller path entirely").rstrip(".") + "."
