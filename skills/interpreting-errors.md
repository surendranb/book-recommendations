---
description: Error shapes — no matches, transient upstream failures, and the Gutenberg fallback path.
---

# Interpreting errors

## `[INPUT_FIXABLE]`

- **"No books matched"** (recommend): the query was too narrow for
  OpenLibrary. Broaden it ("quiet Japanese novels" instead of "quiet
  postwar Japanese novels about glassblowing"), drop the exclude list, or
  switch to blind_date() for serendipity.

## `[TRANSIENT]`

- **"shelf came back empty"** (blind_date): OpenLibrary was busy or the
  random shelf was thin. Retry ONCE (different randomness), then fall back
  to recommend(topic).
- **"Gutenberg index unreachable"** (free_classics): gutendex.com is a
  community service and can be down. The error itself carries the
  alternative: recommend(topic) cards with read_now="free at archive.org"
  are also full free reads. Do not retry-loop.

## Honesty rules

- Relay why_picked verbatim — it says how the book was chosen.
- read_now reflects OpenLibrary's ebook_access: "free at archive.org" =
  readable now; "borrowable" = Internet Archive loan (free account).
- Never invent a first sentence or a plot summary; relay what's returned.
