"""Speed test runner and daemon scheduler.

Runs speedtest-cli, parses results, and stores them via database.py.
Also manages the background daemon that runs tests on an interval.
"""

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import schedule
import speedtest

from netwatch.config import Config
from netwatch.database import SpeedReading, init_db, insert_reading


class SpeedTestError(Exception):
    """Raised when a speed test fails after all retries."""


def run_speed_test(config: Config, retries: int = 2) -> SpeedReading:
    """Run a speed test and return a SpeedReading.

    Args:
        config: Application config (db_path used for storage).
        retries: Number of times to retry on failure before raising.

    Raises:
        SpeedTestError: If all attempts fail.
    """
    last_error: Optional[Exception] = None

    for attempt in range(1, retries + 2):  # +2 so retries=2 means 3 total attempts
        try:
            st = speedtest.Speedtest(secure=True)
            st.get_best_server()
            st.download()
            st.upload()
            results = st.results.dict()

            reading = SpeedReading(
                id=None,
                timestamp=datetime.now(tz=timezone.utc),
                download_mbps=round(results["download"] / 1_000_000, 2),
                upload_mbps=round(results["upload"] / 1_000_000, 2),
                ping_ms=round(results["ping"], 2),
                server_name=results.get("server", {}).get("name", ""),
                server_country=results.get("server", {}).get("country", ""),
                isp=results.get("client", {}).get("isp", ""),
            )
            return reading

        except Exception as exc:
            last_error = exc
            if attempt <= retries:
                time.sleep(3 * attempt)  # back-off: 3s, 6s

    raise SpeedTestError(f"Speed test failed after {retries + 1} attempts: {last_error}") from last_error


def log_speed(config: Config) -> SpeedReading:
    """Run a speed test, store to DB, and return the reading.

    This is the main function called by the CLI and daemon.
    """
    init_db(config.db_path)
    reading = run_speed_test(config)
    insert_reading(config.db_path, reading)
    return reading


def start_daemon(config: Config, on_result=None, on_error=None) -> None:
    """Start the background daemon that runs speed tests on an interval.

    This function BLOCKS the calling thread — run it in the main thread
    or a dedicated process.

    Args:
        config: Application config (interval_minutes, db_path).
        on_result: Optional callback(SpeedReading) called after each success.
        on_error: Optional callback(Exception) called after each failure.
    """

    def _job():
        try:
            reading = log_speed(config)
            if on_result:
                on_result(reading)
        except SpeedTestError as exc:
            if on_error:
                on_error(exc)

    # Run once immediately, then on schedule
    _job()
    schedule.every(config.interval_minutes).minutes.do(_job)

    while True:
        schedule.run_pending()
        time.sleep(30)
