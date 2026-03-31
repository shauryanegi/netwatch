"""Tests for logger.py — mocks speedtest-cli so no real network calls."""

from unittest.mock import MagicMock, patch

import pytest

from netwatch.config import Config
from netwatch.logger import SpeedTestError, run_speed_test


def _make_config(tmp_path) -> Config:
    return Config(
        db_path=tmp_path / "test.db",
        interval_minutes=15,
        isp_name="TestISP",
        advertised_mbps=100.0,
        groq_api_key=None,
        groq_model="llama3-8b-8192",
    )


def _mock_speedtest_results():
    """Return a mock that mimics speedtest.Speedtest().results.dict()."""
    mock_results = {
        "download": 95_000_000,   # 95 Mbps in bps
        "upload": 20_000_000,     # 20 Mbps
        "ping": 12.5,
        "server": {"name": "NYC", "country": "US"},
        "client": {"isp": "TestISP"},
    }
    mock_st = MagicMock()
    mock_st.results.dict.return_value = mock_results
    return mock_st


class TestRunSpeedTest:
    def test_success_returns_reading(self, tmp_path):
        config = _make_config(tmp_path)

        with patch("netwatch.logger.speedtest.Speedtest", return_value=_mock_speedtest_results()):
            reading = run_speed_test(config, retries=0)

        assert reading.download_mbps == 95.0
        assert reading.upload_mbps == 20.0
        assert reading.ping_ms == 12.5
        assert reading.server_name == "NYC"
        assert reading.isp == "TestISP"
        assert reading.id is None  # not yet saved to DB

    def test_raises_after_all_retries(self, tmp_path):
        config = _make_config(tmp_path)

        with patch("netwatch.logger.speedtest.Speedtest", side_effect=Exception("network error")):
            with patch("netwatch.logger.time.sleep"):  # skip the back-off sleep in tests
                with pytest.raises(SpeedTestError, match="Speed test failed"):
                    run_speed_test(config, retries=1)

    def test_retries_then_succeeds(self, tmp_path):
        config = _make_config(tmp_path)
        call_count = 0

        def flaky_speedtest(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("transient error")
            return _mock_speedtest_results()

        with patch("netwatch.logger.speedtest.Speedtest", side_effect=flaky_speedtest):
            with patch("netwatch.logger.time.sleep"):
                reading = run_speed_test(config, retries=2)

        assert reading.download_mbps == 95.0
        assert call_count == 2
