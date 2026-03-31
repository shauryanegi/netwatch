"""Configuration management for netwatch.

All environment variables and application defaults live here.
Import `get_config()` wherever you need settings — never read os.environ directly.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the current working directory (or any parent)
load_dotenv()


@dataclass
class Config:
    """Application-wide configuration."""

    # Database
    db_path: Path

    # Daemon
    interval_minutes: int

    # ISP info (used in AI complaint letters)
    isp_name: str
    advertised_mbps: float

    # Groq AI
    groq_api_key: str | None
    groq_model: str


def _load_api_key(value: str | None) -> str | None:
    """Return None if the key is missing or still the placeholder value."""
    if not value or value.startswith("your_"):
        return None
    return value


def get_config() -> Config:
    """Read config from environment variables, falling back to sensible defaults."""
    db_path_str = os.getenv("NETWATCH_DB_PATH", str(Path.home() / ".netwatch" / "data.db"))
    db_path = Path(db_path_str)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    return Config(
        db_path=db_path,
        interval_minutes=int(os.getenv("NETWATCH_INTERVAL", "15")),
        isp_name=os.getenv("NETWATCH_ISP_NAME", "My ISP"),
        advertised_mbps=float(os.getenv("NETWATCH_ADVERTISED_MBPS", "100")),
        groq_api_key=_load_api_key(os.getenv("GROQ_API_KEY")),
        groq_model=os.getenv("GROQ_MODEL", "llama3-8b-8192"),
    )
