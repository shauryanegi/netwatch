"""CLI entry point for netwatch.

All user-facing commands live here. This module wires together
config, database, logger, ai, and reports into a clean CLI.

Usage:
    netwatch log                        # Run a single speed test
    netwatch start                      # Start background daemon
    netwatch serve                      # Launch local web dashboard
    netwatch stats [--days N]           # Show aggregate stats
    netwatch history [--limit N]        # Show recent readings table
    netwatch chart [--days N]           # Show ASCII speed chart
    netwatch ai summary                 # AI weekly summary
    netwatch ai anomalies               # AI anomaly detection
    netwatch ai letter                  # AI complaint letter
    netwatch ai chat "your question"    # Chat with your data
"""

import sys

import click
from rich.console import Console

from netwatch import __version__
from netwatch.ai import AIError, chat, complaint_letter, detect_anomalies, weekly_summary
from netwatch.config import get_config
from netwatch.database import get_readings, get_stats, init_db
from netwatch.logger import SpeedTestError, log_speed, start_daemon
from netwatch.reports import (
    print_ai_result,
    print_chart,
    print_error,
    print_history,
    print_info,
    print_reading,
    print_stats,
    print_success,
)

console = Console()


# ─────────────────────────────────────────────────────────────
#  Root group
# ─────────────────────────────────────────────────────────────


@click.group()
@click.version_option(version=__version__, prog_name="netwatch")
def main():
    """netwatch — Track your ISP speed and get AI-powered insights.

    \b
    Quick start:
      netwatch log          Run a speed test right now
      netwatch start        Start logging every 15 minutes
      netwatch stats        View your performance summary
      netwatch ai summary   Get an AI-written weekly report
    """


# ─────────────────────────────────────────────────────────────
#  Core commands
# ─────────────────────────────────────────────────────────────


@main.command()
def log():
    """Run a single speed test and save the result."""
    config = get_config()
    print_info("Running speed test... (this may take 30–60 seconds)")

    try:
        reading = log_speed(config)
        print_reading(reading)
        print_success("Result saved to local database.")
    except SpeedTestError as exc:
        print_error(str(exc))
        sys.exit(1)


@main.command()
@click.option("--port", "-p", default=8080, show_default=True, help="Port to run the web dashboard on.")
@click.option("--no-browser", is_flag=True, default=False, help="Don't open the browser automatically.")
def serve(port: int, no_browser: bool):
    """Launch the local web dashboard at http://localhost:[PORT].

    All data stays on your machine — the server only binds to 127.0.0.1.
    Press Ctrl+C to stop.
    """
    import threading
    import time
    import webbrowser

    import uvicorn

    from netwatch.server import create_app

    config = get_config()
    app = create_app(config)
    url = f"http://127.0.0.1:{port}"

    print_info(f"Starting web dashboard at [bold cyan]{url}[/bold cyan]")
    if config.groq_api_key:
        print_info("AI features are [bold green]enabled[/bold green]")
    else:
        print_info("AI features are [bold yellow]disabled[/bold yellow] (no GROQ_API_KEY)")
    console.print("[dim]Press Ctrl+C to stop.[/dim]\n")

    if not no_browser:
        # Give the server a moment to start before opening the browser
        def _open():
            time.sleep(1.2)
            webbrowser.open(url)
        threading.Thread(target=_open, daemon=True).start()

    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


@main.command()
def start():
    """Start the background daemon — logs speed every N minutes.

    The interval is controlled by NETWATCH_INTERVAL (default: 15 minutes).
    Press Ctrl+C to stop.
    """
    config = get_config()
    print_info(f"Starting daemon — running speed test every {config.interval_minutes} minute(s).")
    print_info("Press Ctrl+C to stop.\n")

    def on_result(reading):
        print_reading(reading)

    def on_error(exc):
        print_error(f"Speed test failed: {exc}")

    try:
        start_daemon(config, on_result=on_result, on_error=on_error)
    except KeyboardInterrupt:
        console.print("\n[cyan]Daemon stopped.[/cyan]")


@main.command()
@click.option("--days", "-d", default=30, show_default=True, help="Number of days to include in stats.")
def stats(days: int):
    """Show aggregate statistics for your connection."""
    config = get_config()
    init_db(config.db_path)

    result = get_stats(config.db_path, days=days, advertised_mbps=config.advertised_mbps)

    if result is None:
        print_info("No data yet. Run [bold]netwatch log[/bold] to take your first speed test.")
        return

    print_stats(result, config.advertised_mbps)
    console.print(f"[dim]Showing stats for the past {days} days.[/dim]")


@main.command()
@click.option("--limit", "-n", default=20, show_default=True, help="Number of recent readings to show.")
@click.option("--days", "-d", default=None, type=int, help="Only show readings from the last N days.")
def history(limit: int, days):
    """Show a table of recent speed test readings."""
    config = get_config()
    init_db(config.db_path)

    readings = get_readings(config.db_path, limit=limit, days=days)
    print_history(readings, config.advertised_mbps)


@main.command()
@click.option("--days", "-d", default=7, show_default=True, help="Number of days of data to chart.")
def chart(days: int):
    """Show an ASCII line chart of download and upload speed over time."""
    config = get_config()
    init_db(config.db_path)

    readings = get_readings(config.db_path, limit=500, days=days)

    if not readings:
        print_info("No data yet. Run [bold]netwatch log[/bold] first.")
        return

    print_chart(readings)


# ─────────────────────────────────────────────────────────────
#  AI command group
# ─────────────────────────────────────────────────────────────


@main.group()
def ai():
    """AI-powered insights using Groq (free tier).

    \b
    Requires GROQ_API_KEY in your .env file.
    Get a free key at: https://console.groq.com
    """


@ai.command("summary")
@click.option("--days", "-d", default=7, show_default=True, help="Days of data to summarize.")
def ai_summary(days: int):
    """Generate a plain English weekly performance summary."""
    config = get_config()
    init_db(config.db_path)

    if not config.groq_api_key:
        _print_ai_disabled()
        return

    print_info("Analyzing your speed data with AI...")

    readings = get_readings(config.db_path, limit=500, days=days)
    result_stats = get_stats(config.db_path, days=days, advertised_mbps=config.advertised_mbps)

    try:
        result = weekly_summary(readings, result_stats, config)
        print_ai_result("Weekly Performance Summary", result)
    except AIError as exc:
        print_error(str(exc))
        sys.exit(1)


@ai.command("anomalies")
@click.option("--days", "-d", default=14, show_default=True, help="Days of data to analyze.")
def ai_anomalies(days: int):
    """Detect and explain unusual patterns in your speed data."""
    config = get_config()
    init_db(config.db_path)

    if not config.groq_api_key:
        _print_ai_disabled()
        return

    print_info("Running anomaly detection with AI...")

    readings = get_readings(config.db_path, limit=500, days=days)

    try:
        result = detect_anomalies(readings, config)
        print_ai_result("Anomaly Detection Report", result)
    except AIError as exc:
        print_error(str(exc))
        sys.exit(1)


@ai.command("letter")
@click.option("--days", "-d", default=30, show_default=True, help="Days of evidence to include.")
def ai_letter(days: int):
    """Generate a formal ISP complaint letter with your speed data as evidence."""
    config = get_config()
    init_db(config.db_path)

    if not config.groq_api_key:
        _print_ai_disabled()
        return

    print_info(f"Generating complaint letter for {config.isp_name}...")

    readings = get_readings(config.db_path, limit=500, days=days)
    result_stats = get_stats(config.db_path, days=days, advertised_mbps=config.advertised_mbps)

    try:
        result = complaint_letter(readings, result_stats, config)
        print_ai_result("ISP Complaint Letter", result)
        console.print("\n[dim]Tip: Copy the letter above, fill in [Your Name] / [Your Address], and send![/dim]")
    except AIError as exc:
        print_error(str(exc))
        sys.exit(1)


@ai.command("chat")
@click.argument("question")
@click.option("--days", "-d", default=30, show_default=True, help="Days of data to include as context.")
def ai_chat(question: str, days: int):
    """Ask a natural language question about your speed data.

    \b
    Examples:
      netwatch ai chat "When is my internet slowest?"
      netwatch ai chat "How many outages did I have this week?"
      netwatch ai chat "Is my upload speed getting worse over time?"
    """
    config = get_config()
    init_db(config.db_path)

    if not config.groq_api_key:
        _print_ai_disabled()
        return

    print_info(f'Thinking about: "{question}"')

    readings = get_readings(config.db_path, limit=500, days=days)
    result_stats = get_stats(config.db_path, days=days, advertised_mbps=config.advertised_mbps)

    try:
        result = chat(question, readings, result_stats, config)
        print_ai_result("Answer", result)
    except AIError as exc:
        print_error(str(exc))
        sys.exit(1)


def _print_ai_disabled() -> None:
    """Print a friendly message when no Groq API key is configured."""
    console.print(
        "\n[bold yellow]AI features are disabled.[/bold yellow]\n\n"
        "netwatch works fully without AI — use these commands anytime:\n"
        "  [cyan]netwatch log[/cyan]      Run a speed test\n"
        "  [cyan]netwatch stats[/cyan]    View statistics\n"
        "  [cyan]netwatch history[/cyan]  Browse readings\n"
        "  [cyan]netwatch chart[/cyan]    ASCII speed chart\n\n"
        "To enable AI features, get a [bold]free[/bold] Groq API key:\n"
        "  1. Visit [link]https://console.groq.com[/link]\n"
        "  2. Add to your [bold].env[/bold] file:  [green]GROQ_API_KEY=your_key_here[/green]\n"
    )
