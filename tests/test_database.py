"""Tests for database.py — uses in-memory SQLite, never touches real DB."""

import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from netwatch.database import (
    SpeedReading,
    get_readings,
    get_stats,
    init_db,
    insert_reading,
)


@pytest.fixture
def db_path(tmp_path):
    """Temporary SQLite DB path, cleaned up after each test."""
    path = tmp_path / "test.db"
    init_db(path)
    return path


def _make_reading(download=100.0, upload=20.0, ping=10.0, hours_ago=0) -> SpeedReading:
    """Helper to create a SpeedReading for testing."""
    from datetime import timedelta
    ts = datetime.now(tz=timezone.utc) - timedelta(hours=hours_ago)
    return SpeedReading(
        id=None,
        timestamp=ts,
        download_mbps=download,
        upload_mbps=upload,
        ping_ms=ping,
        server_name="Test Server",
        server_country="US",
        isp="Test ISP",
    )


class TestInitDb:
    def test_creates_table(self, db_path):
        """init_db should create the speed_logs table."""
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        table_names = [t[0] for t in tables]
        assert "speed_logs" in table_names
        conn.close()

    def test_idempotent(self, db_path):
        """Calling init_db twice should not raise."""
        init_db(db_path)  # second call — should be fine
        init_db(db_path)  # third call


class TestInsertAndRead:
    def test_insert_returns_id(self, db_path):
        reading = _make_reading()
        row_id = insert_reading(db_path, reading)
        assert isinstance(row_id, int)
        assert row_id >= 1

    def test_insert_and_retrieve(self, db_path):
        reading = _make_reading(download=95.5, upload=18.3, ping=12.4)
        insert_reading(db_path, reading)

        results = get_readings(db_path, limit=10)
        assert len(results) == 1
        assert results[0].download_mbps == 95.5
        assert results[0].upload_mbps == 18.3
        assert results[0].ping_ms == 12.4

    def test_multiple_readings_ordered_newest_first(self, db_path):
        insert_reading(db_path, _make_reading(download=50.0, hours_ago=2))
        insert_reading(db_path, _make_reading(download=80.0, hours_ago=1))
        insert_reading(db_path, _make_reading(download=100.0, hours_ago=0))

        results = get_readings(db_path, limit=10)
        assert len(results) == 3
        # Newest first
        assert results[0].download_mbps == 100.0
        assert results[1].download_mbps == 80.0
        assert results[2].download_mbps == 50.0

    def test_limit_respected(self, db_path):
        for i in range(10):
            insert_reading(db_path, _make_reading(download=float(i * 10)))

        results = get_readings(db_path, limit=3)
        assert len(results) == 3

    def test_empty_db_returns_empty_list(self, db_path):
        results = get_readings(db_path)
        assert results == []


class TestGetStats:
    def test_returns_none_for_empty_db(self, db_path):
        assert get_stats(db_path) is None

    def test_basic_stats(self, db_path):
        insert_reading(db_path, _make_reading(download=100.0, upload=20.0, ping=10.0))
        insert_reading(db_path, _make_reading(download=80.0, upload=15.0, ping=20.0))

        stats = get_stats(db_path, advertised_mbps=100.0)
        assert stats is not None
        assert stats.count == 2
        assert stats.avg_download == 90.0
        assert stats.avg_upload == 17.5
        assert stats.avg_ping == 15.0
        assert stats.min_download == 80.0
        assert stats.max_download == 100.0

    def test_below_threshold_calculation(self, db_path):
        # 80% of 100 Mbps = 80 Mbps threshold
        # 50 Mbps reading is below threshold
        insert_reading(db_path, _make_reading(download=50.0))   # below threshold
        insert_reading(db_path, _make_reading(download=90.0))   # above threshold
        insert_reading(db_path, _make_reading(download=95.0))   # above threshold
        insert_reading(db_path, _make_reading(download=85.0))   # above threshold

        stats = get_stats(db_path, advertised_mbps=100.0)
        assert stats.below_threshold_pct == 25.0  # 1 out of 4

    def test_days_filter(self, db_path):
        insert_reading(db_path, _make_reading(download=100.0, hours_ago=1))    # recent
        insert_reading(db_path, _make_reading(download=50.0, hours_ago=200))   # old (8+ days ago)

        stats = get_stats(db_path, days=7, advertised_mbps=100.0)
        assert stats is not None
        assert stats.count == 1
        assert stats.avg_download == 100.0
