"""Tests for CSV export functionality."""

import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from netwatch.database import SpeedReading, export_csv, init_db, insert_reading


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "test.db"
    init_db(path)
    return path


def _insert(db_path, download=100.0, upload=20.0, ping=10.0, hours_ago=0):
    ts = datetime.now(tz=timezone.utc) - timedelta(hours=hours_ago)
    reading = SpeedReading(
        id=None,
        timestamp=ts,
        download_mbps=download,
        upload_mbps=upload,
        ping_ms=ping,
        server_name="Test Server",
        server_country="US",
        isp="Test ISP",
    )
    insert_reading(db_path, reading)


class TestExportCsv:
    def test_creates_csv_file(self, db_path, tmp_path):
        _insert(db_path)
        out = tmp_path / "out.csv"
        export_csv(db_path, out)
        assert out.exists()

    def test_correct_headers(self, db_path, tmp_path):
        _insert(db_path)
        out = tmp_path / "out.csv"
        export_csv(db_path, out)

        with open(out) as f:
            reader = csv.DictReader(f)
            assert set(reader.fieldnames) == {
                "timestamp_utc", "timestamp_local",
                "download_mbps", "upload_mbps", "ping_ms",
                "server_name", "server_country", "isp",
            }

    def test_correct_row_count(self, db_path, tmp_path):
        for i in range(5):
            _insert(db_path, download=float(i * 10))
        out = tmp_path / "out.csv"
        count = export_csv(db_path, out)
        assert count == 5

        with open(out) as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 5

    def test_oldest_first_ordering(self, db_path, tmp_path):
        _insert(db_path, download=10.0, hours_ago=2)
        _insert(db_path, download=20.0, hours_ago=1)
        _insert(db_path, download=30.0, hours_ago=0)
        out = tmp_path / "out.csv"
        export_csv(db_path, out)

        with open(out) as f:
            rows = list(csv.DictReader(f))

        # Oldest (10 Mbps) should be first row
        assert float(rows[0]["download_mbps"]) == 10.0
        assert float(rows[-1]["download_mbps"]) == 30.0

    def test_correct_values(self, db_path, tmp_path):
        _insert(db_path, download=87.5, upload=22.3, ping=14.7)
        out = tmp_path / "out.csv"
        export_csv(db_path, out)

        with open(out) as f:
            rows = list(csv.DictReader(f))

        assert float(rows[0]["download_mbps"]) == 87.5
        assert float(rows[0]["upload_mbps"]) == 22.3
        assert float(rows[0]["ping_ms"]) == 14.7
        assert rows[0]["server_name"] == "Test Server"
        assert rows[0]["isp"] == "Test ISP"

    def test_days_filter(self, db_path, tmp_path):
        _insert(db_path, download=100.0, hours_ago=1)     # recent
        _insert(db_path, download=50.0, hours_ago=200)    # old (8+ days)
        out = tmp_path / "out.csv"
        count = export_csv(db_path, out, days=7)
        assert count == 1

        with open(out) as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 1
        assert float(rows[0]["download_mbps"]) == 100.0

    def test_empty_db_returns_zero(self, db_path, tmp_path):
        out = tmp_path / "out.csv"
        count = export_csv(db_path, out)
        assert count == 0
        # File is still created but with only a header row
        with open(out) as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 0
