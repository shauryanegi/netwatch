"""SQLite storage layer for netwatch.

All database access goes through this module.
No other module should import sqlite3 directly.
"""

import csv
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


@dataclass
class SpeedReading:
    """A single speed test result."""

    id: Optional[int]
    timestamp: datetime
    download_mbps: float
    upload_mbps: float
    ping_ms: float
    server_name: str
    server_country: str
    isp: str


@dataclass
class SpeedStats:
    """Aggregate statistics over a set of readings."""

    count: int
    avg_download: float
    avg_upload: float
    avg_ping: float
    min_download: float
    max_download: float
    min_upload: float
    max_upload: float
    below_threshold_pct: float  # % of readings below advertised speed


_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS speed_logs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       TEXT NOT NULL,
    download_mbps   REAL NOT NULL,
    upload_mbps     REAL NOT NULL,
    ping_ms         REAL NOT NULL,
    server_name     TEXT NOT NULL DEFAULT '',
    server_country  TEXT NOT NULL DEFAULT '',
    isp             TEXT NOT NULL DEFAULT ''
);
"""

_CREATE_INDEX = """
CREATE INDEX IF NOT EXISTS idx_speed_logs_timestamp ON speed_logs(timestamp);
"""


from contextlib import contextmanager


@contextmanager
def _connect(db_path: Path):
    """Context manager that opens, yields, and always closes a SQLite connection."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    try:
        yield conn
    finally:
        conn.close()


def init_db(db_path: Path) -> None:
    """Create tables and indexes if they don't exist."""
    with _connect(db_path) as conn:
        conn.execute(_CREATE_TABLE)
        conn.execute(_CREATE_INDEX)
        conn.commit()


def insert_reading(db_path: Path, reading: SpeedReading) -> int:
    """Insert a new speed reading. Returns the new row id."""
    sql = """
        INSERT INTO speed_logs (timestamp, download_mbps, upload_mbps, ping_ms,
                                server_name, server_country, isp)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """
    ts = reading.timestamp.astimezone(timezone.utc).isoformat()
    with _connect(db_path) as conn:
        cursor = conn.execute(
            sql,
            (
                ts,
                reading.download_mbps,
                reading.upload_mbps,
                reading.ping_ms,
                reading.server_name,
                reading.server_country,
                reading.isp,
            ),
        )
        conn.commit()
        return cursor.lastrowid


def get_readings(
    db_path: Path,
    limit: int = 100,
    days: Optional[int] = None,
) -> list[SpeedReading]:
    """Fetch speed readings, newest first.

    Args:
        db_path: Path to the SQLite DB.
        limit: Max number of rows to return.
        days: If set, only return readings from the last N days.
    """
    sql = "SELECT * FROM speed_logs"
    params: list = []

    if days is not None:
        sql += " WHERE timestamp >= datetime('now', ?)"
        params.append(f"-{days} days")

    sql += " ORDER BY timestamp DESC LIMIT ?"
    params.append(limit)

    with _connect(db_path) as conn:
        rows = conn.execute(sql, params).fetchall()

    return [_row_to_reading(row) for row in rows]


def get_stats(db_path: Path, days: Optional[int] = None, advertised_mbps: float = 100.0) -> Optional[SpeedStats]:
    """Compute aggregate statistics across stored readings.

    Args:
        db_path: Path to the SQLite DB.
        days: If set, only consider readings from the last N days.
        advertised_mbps: Used to compute below-threshold percentage.
    """
    sql = """
        SELECT
            COUNT(*)           AS count,
            AVG(download_mbps) AS avg_download,
            AVG(upload_mbps)   AS avg_upload,
            AVG(ping_ms)       AS avg_ping,
            MIN(download_mbps) AS min_download,
            MAX(download_mbps) AS max_download,
            MIN(upload_mbps)   AS min_upload,
            MAX(upload_mbps)   AS max_upload,
            SUM(CASE WHEN download_mbps < ? THEN 1 ELSE 0 END) AS below_count
        FROM speed_logs
    """
    params: list = [advertised_mbps * 0.8]  # 80% of advertised = threshold

    if days is not None:
        sql += " WHERE timestamp >= datetime('now', ?)"
        params.append(f"-{days} days")

    with _connect(db_path) as conn:
        row = conn.execute(sql, params).fetchone()

    if row is None or row["count"] == 0:
        return None

    below_pct = (row["below_count"] / row["count"]) * 100 if row["count"] > 0 else 0.0

    return SpeedStats(
        count=row["count"],
        avg_download=round(row["avg_download"], 2),
        avg_upload=round(row["avg_upload"], 2),
        avg_ping=round(row["avg_ping"], 2),
        min_download=round(row["min_download"], 2),
        max_download=round(row["max_download"], 2),
        min_upload=round(row["min_upload"], 2),
        max_upload=round(row["max_upload"], 2),
        below_threshold_pct=round(below_pct, 1),
    )


def export_csv(db_path: Path, output_path: Path, days: Optional[int] = None) -> int:
    """Export speed readings to a CSV file.

    Args:
        db_path: Path to the SQLite DB.
        output_path: Destination CSV file path.
        days: If set, only export readings from the last N days.

    Returns:
        Number of rows written.
    """
    readings = get_readings(db_path, limit=100_000, days=days)

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "timestamp_utc", "timestamp_local",
            "download_mbps", "upload_mbps", "ping_ms",
            "server_name", "server_country", "isp",
        ])
        for r in reversed(readings):  # oldest first — natural order for spreadsheets
            local_ts = r.timestamp.astimezone().strftime("%Y-%m-%d %H:%M:%S")
            utc_ts   = r.timestamp.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            writer.writerow([
                utc_ts, local_ts,
                r.download_mbps, r.upload_mbps, r.ping_ms,
                r.server_name, r.server_country, r.isp,
            ])

    return len(readings)


def _row_to_reading(row: sqlite3.Row) -> SpeedReading:
    """Convert a sqlite3.Row to a SpeedReading dataclass."""
    ts = datetime.fromisoformat(row["timestamp"])
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return SpeedReading(
        id=row["id"],
        timestamp=ts,
        download_mbps=row["download_mbps"],
        upload_mbps=row["upload_mbps"],
        ping_ms=row["ping_ms"],
        server_name=row["server_name"],
        server_country=row["server_country"],
        isp=row["isp"],
    )
