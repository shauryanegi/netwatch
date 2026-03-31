"""AI-powered insights via the Groq API (free tier).

All Groq API calls live here. Other modules must not import groq directly.

Available features:
  - chat()             — Ask any question about your speed data
  - weekly_summary()   — Plain English summary of the past 7 days
  - detect_anomalies() — Find and explain unusual patterns
  - complaint_letter() — Generate a formal ISP complaint with evidence
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

from groq import Groq

from netwatch.config import Config
from netwatch.database import SpeedReading, SpeedStats


class AIError(Exception):
    """Raised when the Groq API call fails or no API key is set."""


# ─────────────────────────────────────────────────────────────
#  Public API
# ─────────────────────────────────────────────────────────────


def chat(
    question: str,
    readings: list[SpeedReading],
    stats: Optional[SpeedStats],
    config: Config,
) -> str:
    """Answer a natural language question about the user's speed data.

    Args:
        question: The user's question, e.g. "When is my internet slowest?"
        readings: Recent speed readings from the DB.
        stats: Aggregate stats (can be None if no data yet).
        config: App config (API key, ISP info).

    Returns:
        Plain text answer from the LLM.
    """
    _require_api_key(config)
    context = _format_data_for_prompt(readings, stats, config)

    system = (
        "You are a helpful network analyst assistant. "
        "The user has shared their internet speed test history. "
        "Answer their question clearly and concisely. "
        "Reference specific data points from the history where relevant. "
        "Use plain English — no jargon. Keep the answer under 200 words."
    )
    user = f"Here is my internet speed history:\n\n{context}\n\nMy question: {question}"

    return _call_groq(system, user, config)


def weekly_summary(
    readings: list[SpeedReading],
    stats: Optional[SpeedStats],
    config: Config,
) -> str:
    """Generate a plain English summary of the past 7 days of speed data.

    Args:
        readings: Speed readings from the last 7 days.
        stats: Aggregate stats over those readings.
        config: App config.

    Returns:
        A short, readable summary paragraph with key insights.
    """
    _require_api_key(config)

    if not readings:
        return "No speed data available for the past 7 days. Run `netwatch log` to start logging."

    context = _format_data_for_prompt(readings, stats, config)

    system = (
        "You are a network analyst writing a weekly internet performance report for a regular user. "
        "Be concise, use plain language, and highlight the most important findings. "
        "Structure your response as: 1) Overall performance summary, "
        "2) Best and worst times, 3) One actionable recommendation. "
        "Keep it under 250 words."
    )
    user = (
        f"Here is my internet speed data for the past 7 days:\n\n{context}\n\n"
        f"My ISP advertises {config.advertised_mbps} Mbps download. "
        "Please write a weekly performance summary."
    )

    return _call_groq(system, user, config)


def detect_anomalies(
    readings: list[SpeedReading],
    config: Config,
) -> str:
    """Detect unusual patterns in speed data and explain them in plain English.

    Args:
        readings: Speed readings to analyze (recommend at least 7 days).
        config: App config.

    Returns:
        Plain text description of detected anomalies and possible causes.
    """
    _require_api_key(config)

    if not readings:
        return "Not enough data to detect anomalies. Log at least a few days of speed tests first."

    context = _format_data_for_prompt(readings, None, config)

    system = (
        "You are a network analyst specializing in ISP performance issues. "
        "Analyze the speed test data and identify anomalies, patterns, or problems. "
        "Look for: consistent slowdowns at specific times (peak hour congestion), "
        "sudden drops (possible outages), gradual degradation (throttling), "
        "or intermittent spikes (unstable connection). "
        "For each anomaly found, explain what it likely means in plain English. "
        "If the data looks normal, say so clearly. Keep it under 300 words."
    )
    user = (
        f"Here is my internet speed history:\n\n{context}\n\n"
        f"My ISP ({config.isp_name}) advertises {config.advertised_mbps} Mbps download. "
        "Please identify any anomalies or concerning patterns."
    )

    return _call_groq(system, user, config)


def complaint_letter(
    readings: list[SpeedReading],
    stats: Optional[SpeedStats],
    config: Config,
) -> str:
    """Generate a formal, evidence-backed complaint letter to the ISP.

    Args:
        readings: Speed readings (ideally 30 days).
        stats: Aggregate stats to include as evidence.
        config: App config (ISP name, advertised speed).

    Returns:
        A formatted complaint letter ready to send or email.
    """
    _require_api_key(config)

    if not readings:
        return "No speed data available. Log at least a few days of speed tests first."

    context = _format_data_for_prompt(readings, stats, config)
    today = datetime.now().strftime("%B %d, %Y")

    system = (
        "You are a consumer rights advocate helping a customer write a formal complaint letter "
        "to their internet service provider. "
        "Write a professional, polite but firm letter that: "
        "1) States the problem clearly with specific data evidence, "
        "2) References consumer protection rights where appropriate, "
        "3) Requests a specific resolution (credit, fix, or explanation), "
        "4) Sets a reasonable deadline for response (14 days). "
        "Use formal letter format with placeholders like [Your Name] and [Your Address] "
        "where personal details are needed."
    )
    user = (
        f"Today's date: {today}\n"
        f"ISP: {config.isp_name}\n"
        f"Advertised speed: {config.advertised_mbps} Mbps\n\n"
        f"My speed test data (evidence):\n\n{context}\n\n"
        "Please write a formal complaint letter I can send to my ISP."
    )

    return _call_groq(system, user, config, max_tokens=1200)


# ─────────────────────────────────────────────────────────────
#  Internal helpers
# ─────────────────────────────────────────────────────────────


def _require_api_key(config: Config) -> None:
    """Raise AIError if no Groq API key is configured."""
    if not config.groq_api_key:
        raise AIError(
            "No GROQ_API_KEY found.\n"
            "Get a free key at https://console.groq.com and add it to your .env file:\n"
            "  GROQ_API_KEY=your_key_here"
        )


def _format_data_for_prompt(
    readings: list[SpeedReading],
    stats: Optional[SpeedStats],
    config: Config,
) -> str:
    """Format speed readings and stats into a compact string for LLM context.

    Keeps tokens low by summarising older data and showing recent readings in full.
    """
    lines: list[str] = []

    if stats:
        lines.append("=== AGGREGATE STATISTICS ===")
        lines.append(f"Total readings: {stats.count}")
        lines.append(f"Average download: {stats.avg_download} Mbps (advertised: {config.advertised_mbps} Mbps)")
        lines.append(f"Average upload: {stats.avg_upload} Mbps")
        lines.append(f"Average ping: {stats.avg_ping} ms")
        lines.append(f"Download range: {stats.min_download} – {stats.max_download} Mbps")
        lines.append(f"% readings below 80% of advertised: {stats.below_threshold_pct}%")
        lines.append("")

    lines.append("=== RECENT READINGS (newest first) ===")
    lines.append("Timestamp (UTC)          | Download | Upload | Ping")
    lines.append("-" * 60)

    for r in readings[:50]:  # cap at 50 rows to stay within token limits
        ts = r.timestamp.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M")
        lines.append(f"{ts}  |  {r.download_mbps:6.1f} Mbps  |  {r.upload_mbps:6.1f} Mbps  |  {r.ping_ms:5.1f} ms")

    if len(readings) > 50:
        lines.append(f"... and {len(readings) - 50} older readings (summarized in stats above)")

    return "\n".join(lines)


def _call_groq(
    system_prompt: str,
    user_prompt: str,
    config: Config,
    max_tokens: int = 800,
) -> str:
    """Make a chat completion call to Groq and return the response text.

    Args:
        system_prompt: The system role instructions.
        user_prompt: The user message with data context.
        config: App config (API key, model).
        max_tokens: Max tokens in the response.

    Returns:
        The assistant's text response.

    Raises:
        AIError: On API failure.
    """
    try:
        client = Groq(api_key=config.groq_api_key)
        response = client.chat.completions.create(
            model=config.groq_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=max_tokens,
            temperature=0.3,  # lower = more factual, less creative
        )
        return response.choices[0].message.content.strip()
    except Exception as exc:
        raise AIError(f"Groq API call failed: {exc}") from exc
