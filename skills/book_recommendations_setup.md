# Setting Up Book Recommendations MCP Server

A zero-configuration book discovery, topic recommendation, blind-date serendipity, and public-domain classics engine for AI agents.

Official Repository: [github.com/surendranb/book-recommendations](https://github.com/surendranb/book-recommendations)

---

## 1. Quickstart (Zero API Keys Required)

`book-recommendations` connects to open bibliographic knowledge bases:
- **OpenLibrary**: Millions of cataloged works, ISBNs, first sentence hooks, and subjects
- **Project Gutenberg / Gutendex**: 70,000+ free, full-text public domain classics

**Zero API keys, zero accounts, and zero credit cards required.**

---

## 2. Client Configuration

### Claude Desktop (`claude_desktop_config.json`)
```json
{
  "mcpServers": {
    "book-recommendations": {
      "command": "uvx",
      "args": ["book-recommendations"]
    }
  }
}
```

### Cursor (`.cursor/mcp.json`)
```json
{
  "mcpServers": {
    "book-recommendations": {
      "command": "uvx",
      "args": ["book-recommendations"]
    }
  }
}
```

### Command Line / CLI Testing
```bash
uvx book-recommendations
```

---

## 3. Core Tools & Workflow

1. **`recommend_by_topic(topic="cyberpunk")`**:
   Search curated works on OpenLibrary by topic, era, or theme.

2. **`blind_date_with_a_book(genre="sci-fi")`**:
   Serendipitous discovery hooked on opening sentences before revealing author and title.

3. **`find_free_classics(query="Frankenstein")`**:
   Search full-text, public-domain classics with direct download and reading links.

4. **`skills_list()` / `skill_read(name="presenting-recommendations")`**:
   Load playbooks on presenting book cards and handling query ambiguity.

---

## 4. Troubleshooting & Operational Guidance

* **OpenLibrary Latency**: OpenLibrary API is free and community-hosted; queries use exponential backoff on transient 503s.
* **Update Verification**: Call `check_for_updates()` to check PyPI for newer versions and upgrade commands.
* **Dynamic Skills**: Call `skill_read(name='interpreting-errors')` for error handling and fallback patterns.
