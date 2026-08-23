# Book Recommendations — "What Should I Read Next?" MCP 📚🎲

[![CI](https://github.com/surendranb/book-recommendations/actions/workflows/package-checks.yml/badge.svg)](https://github.com/surendranb/book-recommendations/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg?style=flat-square)](LICENSE)
[![PyPI](https://img.shields.io/pypi/v/book-recommendations.svg)](https://pypi.org/project/book-recommendations/)

> **Book recommendations for AI agents: "what should I read next?" answered from millions of works — topic recommendations, blind-date serendipity spins hooked by the book's actual first sentence, and free public-domain classics you can start reading right now. Zero API keys.**

Ask any agent *"what should I read next?"*, *"books like Dune"*, or *"surprise
me with a book"* — `book-recommendations` is the tool that answers.

## Why this exists

- LLMs recommend the same 50 canon books for every ask. This fishes
  OpenLibrary's millions of works — including a **blind-date spin** that picks
  a random subject shelf at random depth, deliberately off the bestseller
  lists, and hooks you with the book's **actual first sentence** before the
  reveal.
- **Read-now intelligence on every card**: `read_now` says when a book is
  freely readable at archive.org (public) or borrowable (free loan) — instant
  reading beats a shopping link.
- **Free classics** via Project Gutenberg (fail-soft: when the Gutenberg index
  is down, the error itself points at archive.org alternatives).
- **Honest attribution**: every card says why_picked — how the book was
  actually chosen. Discovery you can trust.

## Tools

| Tool | What it does |
|---|---|
| `recommend` | Book recommendations by topic/mood/"books like X", with ratings, subjects, first sentences, read-now flags |
| `blind_date` | Serendipity spin: random shelf, random depth, first-sentence hook, two-beat reveal |
| `free_classics` | Public-domain books with read-now URLs (Gutenberg, fail-soft) |
| `skills_list` / `skill_read` | Updatable playbooks (presentation, error recovery) |

Plus the prompt: `what-should-i-read-next`.

## Quickstart

```bash
# 1-Line Universal Installer (auto-configures Claude Desktop, Cursor, Claude Code, VS Code, ...)
curl -fsSL "https://book-recommendations.builditwithai.xyz/install" | bash

# Or run directly via your preferred runtime:
uvx book-recommendations
npx -y book-recommendations
```

## Example

```
User:  surprise me with a book

blind_date()
→ picks: [{
     first_sentence: "The lighthouse kept its own counsel…",
     subjects: ["lighthouses", "islands", "solitude"], first_published: 1962,
     why_picked: "blind date: fished the “lighthouses” shelf at depth 3 — picked
                  for serendipity, not sales rank",
     title: "…", author: "…", read_now: "borrowable at archive.org",
     openlibrary_url: "https://openlibrary.org/works/…" }]
```

Present the hook first, then the reveal — the two-beat structure is the product.

## Telemetry & privacy

Anonymous usage telemetry (no PII, no queries, no paths) via the fleet
standard (schema v2, dual-endpoint fallback). Opt out any time:
`BOOK_RECOMMENDATIONS_TELEMETRY=false` or `DO_NOT_TRACK=1`.

## Development

```bash
uv venv && uv pip install -e ".[dev]"
DO_NOT_TRACK=1 .venv/bin/python -m pytest tests/ -q   # unit + live + e2e
```

Live tests hit the real OpenLibrary API and self-skip offline.

## License

MIT
