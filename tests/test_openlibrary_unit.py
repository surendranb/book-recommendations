# SPDX-License-Identifier: MIT

"""Unit tests for card building, blind-date selection, exclusion — pure
logic with fixture docs. Live OpenLibrary behavior in test_live_e2e.py."""

from unittest import mock

from book_recommendations import openlibrary as ol


def _doc(title="The Light Keeper", author="A. Writer", year=1962,
         cover=123, key="/works/OL1W", subjects=("lighthouses", "islands"),
         first=None, access="public", rating=4.2):
    return {"title": title, "author_name": [author], "first_publish_year": year,
            "cover_i": cover, "key": key, "subject": list(subjects),
            "first_sentence": first, "ebook_access": access,
            "ratings_average": rating}


def test_card_projection():
    card = ol._card(_doc(first=["It began with a lamp."]), why="matched")
    assert card["title"] == "The Light Keeper"
    assert card["author"] == "A. Writer"
    assert card["first_sentence"] == "It began with a lamp."
    assert card["cover_url"].startswith("https://covers.openlibrary.org/")
    assert card["openlibrary_url"] == "https://openlibrary.org/works/OL1W"
    assert card["read_now"] == "free at archive.org"
    assert card["rating"] == 4.2


def test_card_access_variants():
    assert ol._card(_doc(access="borrowable"), "w")["read_now"] == \
        "borrowable at archive.org"
    assert ol._card(_doc(access="no_ebook"), "w")["read_now"] is None


def test_first_sentence_list_and_none():
    assert ol._first_sentence(_doc(first=["One."])) == "One."
    assert ol._first_sentence({"first_sentence": None}) is None
    long = "x" * 500
    assert len(ol._first_sentence({"first_sentence": [long]})) <= 280


def test_exclusion_substring_case_insensitive():
    card = {"title": "The Overstory", "author": "Richard Powers"}
    assert ol._excluded(card, ["overstory", "proust"])
    assert ol._excluded(card, ["dune"]) is False
    assert ol._excluded(card, None) is False


def test_blind_date_seeded_reproducible_and_fail_soft(monkeypatch):
    def fake_subject_works(subject, limit=10, page=1):
        return ([ol._card(_doc(title=f"{subject} book {i}",
                               author=f"Author {i}"), "w")
                 for i in range(6)], 6)

    monkeypatch.setattr(ol, "subject_works", fake_subject_works)
    a = ol.blind_date(count=1, seed=42)
    b = ol.blind_date(count=1, seed=42)
    assert a == b  # seeded spins are reproducible
    assert "blind date" in a[0]["why_picked"]
    assert a[0]["title"]


def test_blind_date_empty_when_upstream_fails(monkeypatch):
    def boom(subject, limit=10, page=1):
        raise ol.OpenLibraryError("down")
    monkeypatch.setattr(ol, "subject_works", boom)
    assert ol.blind_date(count=1) == []


def test_blind_date_respects_exclude(monkeypatch):
    def fake_subject_works(subject, limit=10, page=1):
        return ([ol._card(_doc(title="Kept Book", author="A"), "w"),
                 ol._card(_doc(title="Excluded Book", author="B"), "w")], 2)
    monkeypatch.setattr(ol, "subject_works", fake_subject_works)
    picks = ol.blind_date(count=1, seed=1, exclude=["Excluded Book"])
    assert all("Excluded" not in (p["title"] or "") for p in picks)


def test_subject_pool_sane():
    assert 20 <= len(ol.SUBJECT_POOL) <= 80
    assert all(isinstance(s, str) and s for s in ol.SUBJECT_POOL)


def test_hook_prefers_real_first_sentence():
    card = ol._card(_doc(first=["It began with a lamp."]), "w")
    assert ol._hook(card) == "It began with a lamp."


def test_hook_fallback_is_honest_not_invented():
    card = ol._card(_doc(first=None, subjects=("lighthouses", "islands"),
                          access="borrowable"), "w")
    hook = ol._hook(card)
    assert hook.startswith("A book from 1962 about lighthouses")
    assert "borrowable at archive.org" in hook
    # never quotes anything pretending to be the book's text
    assert '"' not in hook and '"' not in hook


def test_hook_minimal_card_still_gets_a_hook():
    assert ol._hook({}).startswith("A book")
