# CLAUDE.md — netwatch

This file provides guidance for AI agents (Claude and others) working on this codebase.
Read this before making any changes.

---

## Project Overview

**netwatch** is a local-first ISP speed logger with AI-powered insights.
It runs periodic internet speed tests, stores results in a local SQLite database,
and uses the Groq API (free tier) to provide natural language analysis,
anomaly detection, and ISP complaint letter generation.

**Key design principles:**
- Local-first: all data stays on the user's machine
- AI on demand: Groq API is only called when the user explicitly asks
- Zero accounts required: no sign-up, no cloud sync
- Simple CLI: one command to start, intuitive subcommands for everything else

---

## Architecture

```
netwatch/
├── netwatch/
│   ├── config.py       # All config: paths, env vars, defaults
│   ├── database.py     # SQLite CRUD — single source of truth for data
│   ├── logger.py       # Runs speedtest-cli, writes to DB
│   ├── ai.py           # Groq API calls: chat, anomalies, letter, summary
│   ├── reports.py      # Formats DB data into rich tables + ASCII charts
│   └── cli.py          # Click CLI — the only entry point for users
├── tests/
│   ├── test_database.py
│   ├── test_logger.py
│   └── test_ai.py
├── pyproject.toml
├── .env.example
└── CLAUDE.md
```

**Data flow:**
```
speedtest-cli → logger.py → database.py (SQLite)
                                  ↓
                            reports.py → rich terminal output
                                  ↓
                              ai.py → Groq API → plain English insights
```

---

## Development Guidelines

### Do NOT do these things:
- Do not add cloud sync or any feature that sends speed data to external servers
  without explicit user consent
- Do not hardcode API keys — always read from environment variables via `config.py`
- Do not add dependencies without updating `pyproject.toml`
- Do not break the CLI interface — existing commands must remain backward compatible
- Do not use `print()` directly in non-CLI modules — use the logger or return values

### Always do these things:
- Run `pip install -e ".[dev]"` after changing `pyproject.toml`
- Keep AI calls in `ai.py` only — no Groq imports elsewhere
- Keep DB access in `database.py` only — no raw sqlite3 calls elsewhere
- Format data for AI in `ai.py` using the helper `_format_data_for_prompt()`
- Add tests for any new database functions or AI prompt changes

### Code style:
- Python 3.9+ compatible
- Type hints on all function signatures
- Docstrings on public functions
- Max line length: 100 characters
- No unused imports

---

## Key Files Quick Reference

| File | Responsibility | Key functions |
|------|---------------|---------------|
| `config.py` | Env vars, paths, defaults | `get_config()` |
| `database.py` | All SQLite operations | `insert_reading()`, `get_readings()`, `get_stats()` |
| `logger.py` | Run speedtest + save | `run_speed_test()`, `start_daemon()` |
| `ai.py` | All Groq API calls | `chat()`, `complaint_letter()`, `weekly_summary()`, `detect_anomalies()` |
| `reports.py` | Rich terminal output | `show_stats()`, `show_history()`, `show_chart()` |
| `cli.py` | CLI entry point | all `@cli.command()` decorated functions |

---

## Environment Variables

See `.env.example` for all variables. Critical ones:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GROQ_API_KEY` | Yes (for AI) | None | Free at console.groq.com |
| `NETWATCH_DB_PATH` | No | `~/.netwatch/data.db` | SQLite DB location |
| `NETWATCH_INTERVAL` | No | `15` | Minutes between auto tests |
| `NETWATCH_ISP_NAME` | No | `My ISP` | Used in complaint letters |
| `NETWATCH_ADVERTISED_MBPS` | No | `100` | Your advertised plan speed |

---

## Running the Project

```bash
# Install
pip install -e ".[dev]"

# Copy and fill in env vars
cp .env.example .env

# Run a single speed test
netwatch log

# Start daemon (tests every 15 min)
netwatch start

# View stats
netwatch stats
netwatch history
netwatch chart

# AI features (requires GROQ_API_KEY)
netwatch ai summary
netwatch ai anomalies
netwatch ai letter
netwatch ai chat "When is my internet slowest?"
```

---

## Testing

```bash
pytest tests/ -v
pytest tests/ -v --cov=netwatch
```

Tests use a temporary in-memory SQLite DB — never touch the real `~/.netwatch/data.db`.

---

## Adding New AI Features

1. Add a new function in `ai.py` following the existing pattern:
   - Fetch data via `database.get_readings()`
   - Format it using `_format_data_for_prompt()`
   - Call `_call_groq()` with a system + user prompt
   - Return a plain string
2. Add a new subcommand in `cli.py` under the `ai` group
3. Add a test in `tests/test_ai.py` that mocks the Groq client

---

## Common Pitfalls

- `speedtest-cli` can occasionally timeout — `logger.py` has retry logic, don't remove it
- Groq free tier has rate limits — don't call it in loops or daemons automatically
- SQLite timestamps are stored as UTC — convert to local time only in `reports.py`
- The `start` daemon uses `schedule` library — it blocks the main thread intentionally
