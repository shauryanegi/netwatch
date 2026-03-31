"""Rich terminal output: tables, stats panels, and ASCII charts.

This module handles all display logic. It converts raw data from database.py
into beautiful terminal output using Rich and Plotext.
Only call timezone conversion here — store and retrieve everything as UTC.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import plotext as plt
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from netwatch.database import SpeedReading, SpeedStats

console = Console()


def print_reading(reading: SpeedReading) -> None:
    """Print a single speed reading as a colorful summary panel."""
    dl = reading.download_mbps
    ul = reading.upload_mbps
    ping = reading.ping_ms

    dl_color = _speed_color(dl)
    ul_color = _speed_color(ul)
    ping_color = "green" if ping < 50 else "yellow" if ping < 100 else "red"

    content = (
        f"[bold]Download:[/bold]  [{dl_color}]{dl:.1f} Mbps[/{dl_color}]\n"
        f"[bold]Upload:[/bold]    [{ul_color}]{ul:.1f} Mbps[/{ul_color}]\n"
        f"[bold]Ping:[/bold]      [{ping_color}]{ping:.1f} ms[/{ping_color}]\n"
        f"[bold]Server:[/bold]    {reading.server_name}, {reading.server_country}\n"
        f"[bold]ISP:[/bold]       {reading.isp}\n"
        f"[bold]Time:[/bold]      {_local_ts(reading.timestamp)}"
    )
    console.print(Panel(content, title="[bold cyan]Speed Test Result[/bold cyan]", border_style="cyan"))


def print_stats(stats: SpeedStats, advertised_mbps: float) -> None:
    """Print aggregate statistics as a Rich panel."""
    pct_of_advertised = (stats.avg_download / advertised_mbps) * 100
    pct_color = "green" if pct_of_advertised >= 80 else "yellow" if pct_of_advertised >= 60 else "red"
    below_color = "green" if stats.below_threshold_pct < 20 else "yellow" if stats.below_threshold_pct < 40 else "red"

    content = (
        f"[bold]Readings collected:[/bold]  {stats.count}\n\n"
        f"[bold]Download[/bold]\n"
        f"  Average:  [{_speed_color(stats.avg_download)}]{stats.avg_download:.1f} Mbps[/{_speed_color(stats.avg_download)}]"
        f"  [{pct_color}]({pct_of_advertised:.0f}% of {advertised_mbps:.0f} Mbps advertised)[/{pct_color}]\n"
        f"  Range:    {stats.min_download:.1f} – {stats.max_download:.1f} Mbps\n\n"
        f"[bold]Upload[/bold]\n"
        f"  Average:  [{_speed_color(stats.avg_upload)}]{stats.avg_upload:.1f} Mbps[/{_speed_color(stats.avg_upload)}]\n"
        f"  Range:    {stats.min_upload:.1f} – {stats.max_upload:.1f} Mbps\n\n"
        f"[bold]Ping[/bold]\n"
        f"  Average:  {stats.avg_ping:.1f} ms\n\n"
        f"[bold]Below 80% threshold:[/bold]  [{below_color}]{stats.below_threshold_pct:.1f}%[/{below_color}] of readings"
    )
    console.print(Panel(content, title="[bold cyan]Network Statistics[/bold cyan]", border_style="cyan"))


def print_history(readings: list[SpeedReading], advertised_mbps: float) -> None:
    """Print speed readings as a Rich table."""
    if not readings:
        console.print("[yellow]No readings found. Run [bold]netwatch log[/bold] to take a speed test.[/yellow]")
        return

    table = Table(
        title="Speed Test History",
        box=box.ROUNDED,
        border_style="cyan",
        show_lines=False,
        header_style="bold cyan",
    )

    table.add_column("Time", style="dim", min_width=18)
    table.add_column("Download", justify="right", min_width=12)
    table.add_column("Upload", justify="right", min_width=10)
    table.add_column("Ping", justify="right", min_width=8)
    table.add_column("Server", style="dim")
    table.add_column("ISP", style="dim")

    for r in readings:
        dl_color = _speed_color(r.download_mbps)
        ul_color = _speed_color(r.upload_mbps)
        ping_color = "green" if r.ping_ms < 50 else "yellow" if r.ping_ms < 100 else "red"

        table.add_row(
            _local_ts(r.timestamp),
            f"[{dl_color}]{r.download_mbps:.1f} Mbps[/{dl_color}]",
            f"[{ul_color}]{r.upload_mbps:.1f} Mbps[/{ul_color}]",
            f"[{ping_color}]{r.ping_ms:.1f} ms[/{ping_color}]",
            r.server_name or "—",
            r.isp or "—",
        )

    console.print(table)
    console.print(f"[dim]Advertised speed: {advertised_mbps:.0f} Mbps[/dim]")


def print_chart(readings: list[SpeedReading]) -> None:
    """Print an ASCII line chart of download speed over time using Plotext."""
    if not readings:
        console.print("[yellow]No data to chart yet.[/yellow]")
        return

    # Reverse so oldest is left, newest is right
    ordered = list(reversed(readings))

    times = [_local_ts(r.timestamp, short=True) for r in ordered]
    downloads = [r.download_mbps for r in ordered]
    uploads = [r.upload_mbps for r in ordered]

    # Only label every Nth tick to avoid crowding
    n = max(1, len(times) // 8)
    xticks = list(range(0, len(times), n))
    xlabels = [times[i] for i in xticks]

    plt.clear_figure()
    plt.plot_size(width=80, height=20)
    plt.theme("dark")
    plt.title("Internet Speed Over Time")
    plt.xlabel("Time")
    plt.ylabel("Mbps")

    plt.plot(downloads, label="Download", color="cyan")
    plt.plot(uploads, label="Upload", color="green")

    plt.xticks(xticks, xlabels)
    plt.show()


def print_ai_result(title: str, content: str) -> None:
    """Print an AI-generated result in a styled panel."""
    console.print(Panel(content, title=f"[bold magenta]{title}[/bold magenta]", border_style="magenta"))


def print_error(message: str) -> None:
    """Print an error message."""
    console.print(f"[bold red]Error:[/bold red] {message}")


def print_success(message: str) -> None:
    """Print a success message."""
    console.print(f"[bold green]✓[/bold green] {message}")


def print_info(message: str) -> None:
    """Print an informational message."""
    console.print(f"[cyan]→[/cyan] {message}")


# ─────────────────────────────────────────────────────────────
#  Internal helpers
# ─────────────────────────────────────────────────────────────


def _speed_color(mbps: float) -> str:
    """Return a Rich color name based on speed quality."""
    if mbps >= 50:
        return "green"
    elif mbps >= 20:
        return "yellow"
    else:
        return "red"


def _local_ts(dt: datetime, short: bool = False) -> str:
    """Format a UTC datetime as a local-time string."""
    local = dt.astimezone()  # converts to system local timezone
    if short:
        return local.strftime("%m/%d %H:%M")
    return local.strftime("%Y-%m-%d %H:%M:%S")
