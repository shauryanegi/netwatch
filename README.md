# netwatch

**Local ISP speed logger with AI-powered insights.**

Track your internet speed over time, detect anomalies, and generate evidence-backed ISP complaint letters — all from your terminal. Your data stays on your machine. AI features use the [Groq API](https://console.groq.com) (free tier).

---

## Features

- **Automatic speed logging** — runs every N minutes in the background
- **Beautiful terminal UI** — rich tables, color-coded speeds, ASCII charts
- **AI weekly summary** — plain English performance report
- **AI anomaly detection** — finds throttling, congestion, and outage patterns
- **AI complaint letter generator** — formal letter with your speed data as evidence
- **Natural language Q&A** — ask questions like "When is my internet slowest?"
- **100% local** — all data stored in SQLite on your machine

---

## Quick Start

### 1. Install

```bash
git clone https://github.com/yourusername/netwatch.git
cd netwatch
pip install -e .
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env and add your GROQ_API_KEY (free at https://console.groq.com)
# Also set NETWATCH_ISP_NAME and NETWATCH_ADVERTISED_MBPS
```

### 3. Run

```bash
# Take your first speed test
netwatch log

# Start logging automatically every 15 minutes
netwatch start

# View your stats
netwatch stats

# Show history table
netwatch history

# Show ASCII chart
netwatch chart
```

---

## AI Features

All AI features require a free Groq API key. Get one at [console.groq.com](https://console.groq.com).

```bash
# Weekly performance summary
netwatch ai summary

# Detect anomalies and patterns
netwatch ai anomalies

# Generate an ISP complaint letter
netwatch ai letter

# Ask any question about your data
netwatch ai chat "When is my internet slowest?"
netwatch ai chat "How many times did my speed drop below 50 Mbps?"
netwatch ai chat "Is my upload speed getting worse over time?"
```

---

## Configuration

All configuration is via environment variables in your `.env` file:

| Variable | Default | Description |
|---|---|---|
| `GROQ_API_KEY` | — | Free at console.groq.com. Required for AI features. |
| `NETWATCH_DB_PATH` | `~/.netwatch/data.db` | Where to store the SQLite database |
| `NETWATCH_INTERVAL` | `15` | Minutes between auto tests in daemon mode |
| `NETWATCH_ISP_NAME` | `My ISP` | Your ISP name (used in complaint letters) |
| `NETWATCH_ADVERTISED_MBPS` | `100` | Your plan's advertised download speed |
| `GROQ_MODEL` | `llama3-8b-8192` | Groq model to use |

---

## All Commands

```
netwatch log                        Run a single speed test now
netwatch start                      Start background daemon (Ctrl+C to stop)
netwatch stats [--days 30]          Aggregate statistics
netwatch history [--limit 20]       Recent readings table
netwatch chart [--days 7]           ASCII speed chart
netwatch ai summary [--days 7]      AI weekly report
netwatch ai anomalies [--days 14]   AI anomaly detection
netwatch ai letter [--days 30]      AI complaint letter
netwatch ai chat "question"         Ask anything about your data
netwatch --version                  Show version
netwatch --help                     Show help
```

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

See [CLAUDE.md](CLAUDE.md) for architecture details and contribution guidelines.

---

## Why netwatch?

Most ISPs are not held accountable for poor service because customers lack documentation.
netwatch gives you a continuous, timestamped record of your actual speeds — so when your ISP
claims they're meeting their SLA, you have months of receipts.

The AI layer turns raw data into actionable insights without you having to dig through spreadsheets.

---

## License

MIT — see [LICENSE](LICENSE) for details.
