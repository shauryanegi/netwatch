# netwatch

> Local ISP speed logger with AI-powered insights — no account, no cloud, no bullshit.

![Python](https://img.shields.io/badge/python-3.9%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Tests](https://img.shields.io/badge/tests-27%20passing-brightgreen)
![AI](https://img.shields.io/badge/AI-Groq%20%28optional%2C%20free%29-purple)

---

## The problem

Your ISP advertises 200 Mbps. You're getting 40. You complain. They say everything looks fine on their end.

**You have no proof.**

netwatch runs silently in the background, logs every speed test to a local SQLite database, and gives you months of timestamped evidence. When you're ready to fight back, one command writes the complaint letter for you.

No sign-up. No subscription. No data leaves your machine unless you ask it to.

---

## What it looks like

```
$ netwatch log
→ Running speed test...
╭─────────────────────── Speed Test Result ────────────────────────╮
│ Download:  87.4 Mbps                                             │
│ Upload:    22.1 Mbps                                             │
│ Ping:      14.3 ms                                               │
│ Server:    New York, US                                          │
│ ISP:       Comcast                                               │
│ Time:      2026-03-31 22:03:23                                   │
╰──────────────────────────────────────────────────────────────────╯
✓ Result saved to local database.
```

```
$ netwatch stats
╭──────────────────────── Network Statistics ──────────────────────╮
│ Readings collected:  847                                         │
│                                                                  │
│ Download                                                         │
│   Average:  61.2 Mbps  (31% of 200 Mbps advertised)             │
│   Range:    4.1 – 198.3 Mbps                                     │
│                                                                  │
│ Upload                                                           │
│   Average:  18.4 Mbps                                           │
│   Range:    0.8 – 24.9 Mbps                                      │
│                                                                  │
│ Ping                                                             │
│   Average:  22.7 ms                                              │
│                                                                  │
│ Below 80% threshold:  68.3% of readings                          │
╰──────────────────────────────────────────────────────────────────╯
```

```
$ netwatch ai anomalies
╭──────────────────── Anomaly Detection Report ────────────────────╮
│ Your download speed drops consistently between 7–10pm on         │
│ weekdays — averaging 23 Mbps vs your usual 87 Mbps. This is     │
│ classic peak-hour congestion: your ISP is overselling bandwidth  │
│ in your area and can't handle the evening load.                  │
│                                                                  │
│ There were also 3 complete outages this month (speeds below      │
│ 1 Mbps for 10+ minutes), on March 4, 11, and 22.               │
╰──────────────────────────────────────────────────────────────────╯
```

---

## Features

### Core (no setup required)
| Command | What it does |
|---|---|
| `netwatch log` | Run a speed test right now and save it |
| `netwatch start` | Run tests every 15 minutes in the background |
| `netwatch stats` | Aggregate stats with color-coded performance |
| `netwatch history` | Scrollable table of all your readings |
| `netwatch chart` | ASCII line chart of speed over time |

### AI layer (optional — free Groq API key)
| Command | What it does |
|---|---|
| `netwatch ai summary` | Plain English weekly performance report |
| `netwatch ai anomalies` | Detects throttling, congestion, outages |
| `netwatch ai letter` | Writes a formal ISP complaint letter with your data as evidence |
| `netwatch ai chat "..."` | Ask anything: *"when is my internet slowest?"* |

AI features work with the **free tier** of [Groq](https://console.groq.com) — no credit card needed. If you don't set a key, everything else still works perfectly.

---

## Installation

```bash
git clone https://github.com/shauryanegi/netwatch.git
cd netwatch
python3 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e .
```

### Optional: enable AI features

```bash
cp .env.example .env
# Open .env and set:
#   GROQ_API_KEY=your_key_here         ← free at console.groq.com
#   NETWATCH_ISP_NAME=Comcast
#   NETWATCH_ADVERTISED_MBPS=200
```

---

## Usage

### Start logging

```bash
# One-off test
netwatch log

# Daemon mode — logs every 15 minutes until you hit Ctrl+C
netwatch start
```

### View your data

```bash
# Stats summary (default: last 30 days)
netwatch stats
netwatch stats --days 7

# History table (default: last 20 readings)
netwatch history
netwatch history --limit 50 --days 7

# ASCII chart (default: last 7 days)
netwatch chart
netwatch chart --days 30
```

### AI insights

```bash
# Weekly summary
netwatch ai summary

# Anomaly & pattern detection
netwatch ai anomalies

# Generate a complaint letter ready to email/post
netwatch ai letter

# Ask anything about your data
netwatch ai chat "When is my internet slowest?"
netwatch ai chat "How many outages did I have this month?"
netwatch ai chat "Is my upload speed getting worse over time?"
```

---

## Configuration

All settings go in your `.env` file (copy from `.env.example`):

| Variable | Default | Description |
|---|---|---|
| `GROQ_API_KEY` | — | Free at [console.groq.com](https://console.groq.com). Required only for AI features. |
| `NETWATCH_DB_PATH` | `~/.netwatch/data.db` | Where your speed data is stored |
| `NETWATCH_INTERVAL` | `15` | Minutes between tests in daemon mode |
| `NETWATCH_ISP_NAME` | `My ISP` | Your ISP's name (used in complaint letters) |
| `NETWATCH_ADVERTISED_MBPS` | `100` | Your plan's advertised download speed |
| `GROQ_MODEL` | `llama3-8b-8192` | Groq model (free tier) |

Your data is stored at `~/.netwatch/data.db` — a plain SQLite file you can open, query, export, or delete at any time.

---

## How to use the complaint letter

1. Run `netwatch start` and let it collect data for a few weeks
2. Run `netwatch ai letter` — it generates a formal letter with your speed data as evidence
3. Fill in `[Your Name]` and `[Your Address]`
4. Email it to your ISP's customer service or post it on social media

The more data you have, the stronger the case.

---

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run tests with coverage
pytest --cov=netwatch
```

See [CLAUDE.md](CLAUDE.md) for architecture overview, module responsibilities, and contribution guidelines. The project is designed for agentic contributions — the CLAUDE.md tells AI agents exactly what to do and what not to do.

---

## Architecture

```
netwatch/
├── config.py     — env vars, typed Config dataclass
├── database.py   — all SQLite operations (single source of truth)
├── logger.py     — runs speedtest-cli, retry logic, daemon scheduler
├── ai.py         — all Groq API calls (chat, summary, anomalies, letter)
├── reports.py    — Rich tables, color output, ASCII charts
└── cli.py        — Click CLI that wires everything together
```

Data flow:
```
speedtest-cli → logger.py → SQLite DB → reports.py → terminal
                                      ↘ ai.py → Groq → plain English
```

---

## Why open source?

ISPs get away with bad service because individual customers are disorganized and have no data.
A widely-used open source tool changes that:

- Transparent — you can read every line of code
- Private — your speeds never go to anyone's server
- Trustworthy — no company can change the terms on you
- Improvable — if you have a feature idea, open a PR

---

## Contributing

PRs welcome. See [CLAUDE.md](CLAUDE.md) for architecture details before making changes.

For bugs or feature requests, [open an issue](https://github.com/shauryanegi/netwatch/issues).

---

## License

MIT — do whatever you want with it.
