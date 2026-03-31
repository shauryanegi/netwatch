"""Tests for ai.py — mocks Groq so no real API calls are made."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from netwatch.ai import AIError, _format_data_for_prompt, chat, complaint_letter, detect_anomalies, weekly_summary
from netwatch.config import Config
from netwatch.database import SpeedReading, SpeedStats


def _make_config(has_key=True) -> Config:
    return Config(
        db_path=None,
        interval_minutes=15,
        isp_name="TestISP",
        advertised_mbps=100.0,
        groq_api_key="test-key-123" if has_key else None,
        groq_model="llama3-8b-8192",
    )


def _make_readings(n=5) -> list[SpeedReading]:
    return [
        SpeedReading(
            id=i,
            timestamp=datetime(2024, 1, 1, i % 24, 0, tzinfo=timezone.utc),
            download_mbps=float(80 + i),
            upload_mbps=float(15 + i),
            ping_ms=float(10 + i),
            server_name="NYC Server",
            server_country="US",
            isp="TestISP",
        )
        for i in range(n)
    ]


def _make_stats() -> SpeedStats:
    return SpeedStats(
        count=5,
        avg_download=82.0,
        avg_upload=17.0,
        avg_ping=12.0,
        min_download=80.0,
        max_download=84.0,
        min_upload=15.0,
        max_upload=19.0,
        below_threshold_pct=0.0,
    )


class TestRequireApiKey:
    def test_raises_without_key(self):
        config = _make_config(has_key=False)
        with pytest.raises(AIError, match="GROQ_API_KEY"):
            chat("test question", [], None, config)

    def test_no_raise_with_key(self):
        config = _make_config(has_key=True)
        with patch("netwatch.ai._call_groq", return_value="mocked response"):
            result = chat("test", _make_readings(), _make_stats(), config)
        assert result == "mocked response"


class TestFormatDataForPrompt:
    def test_includes_stats(self):
        readings = _make_readings(3)
        stats = _make_stats()
        config = _make_config()

        result = _format_data_for_prompt(readings, stats, config)

        assert "AGGREGATE STATISTICS" in result
        assert "82.0 Mbps" in result
        assert "100.0 Mbps" in result

    def test_includes_readings(self):
        readings = _make_readings(3)
        config = _make_config()

        result = _format_data_for_prompt(readings, None, config)

        assert "RECENT READINGS" in result
        assert "Download" in result
        assert "Upload" in result

    def test_caps_at_50_readings(self):
        readings = _make_readings(60)
        config = _make_config()

        result = _format_data_for_prompt(readings, None, config)

        assert "10 older readings" in result

    def test_empty_readings(self):
        config = _make_config()
        result = _format_data_for_prompt([], None, config)
        assert "RECENT READINGS" in result


class TestAiFunctions:
    """Tests for the public AI functions — all mock _call_groq."""

    def setup_method(self):
        self.config = _make_config()
        self.readings = _make_readings()
        self.stats = _make_stats()

    @patch("netwatch.ai._call_groq", return_value="Weekly summary text")
    def test_weekly_summary(self, mock_groq):
        result = weekly_summary(self.readings, self.stats, self.config)
        assert result == "Weekly summary text"
        mock_groq.assert_called_once()

    def test_weekly_summary_no_data(self):
        result = weekly_summary([], None, self.config)
        assert "No speed data" in result

    @patch("netwatch.ai._call_groq", return_value="Anomaly report")
    def test_detect_anomalies(self, mock_groq):
        result = detect_anomalies(self.readings, self.config)
        assert result == "Anomaly report"

    def test_detect_anomalies_no_data(self):
        result = detect_anomalies([], self.config)
        assert "Not enough data" in result

    @patch("netwatch.ai._call_groq", return_value="Dear ISP...")
    def test_complaint_letter(self, mock_groq):
        result = complaint_letter(self.readings, self.stats, self.config)
        assert result == "Dear ISP..."

    def test_complaint_letter_no_data(self):
        result = complaint_letter([], None, self.config)
        assert "No speed data" in result

    @patch("netwatch.ai._call_groq", return_value="Your internet is slowest on Tuesdays.")
    def test_chat(self, mock_groq):
        result = chat("When is it slow?", self.readings, self.stats, self.config)
        assert "slowest on Tuesdays" in result
