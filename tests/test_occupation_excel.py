"""Unit tests for occupation break detection logic. No SMB, no file I/O, no Dash."""

from datetime import date, datetime

import pandas as pd

from features.monitor.occupation.excel_writer import detect_breaks, dates_in_range


def _make_df(rows: list[tuple]) -> pd.DataFrame:
    """Build a minimal log DataFrame with timestamp, speed, position columns."""
    return pd.DataFrame(rows, columns=["timestamp", "speed", "position"])


TARGET = date(2026, 6, 6)
OTHER = date(2026, 6, 7)


def _ts(h: int, m: int, d: date = TARGET) -> str:
    return datetime(d.year, d.month, d.day, h, m).isoformat()


# ──────────────────────────────────────────────────────────────────────────────
# detect_breaks
# ──────────────────────────────────────────────────────────────────────────────

class TestDetectBreaks:
    def test_basic_single_break(self):
        """One zero-speed block → one Break: entry."""
        df = _make_df([
            (_ts(8, 0),  10.0, 1),
            (_ts(9, 0),   0.0, 1),
            (_ts(9, 30),  0.0, 1),
            (_ts(10, 0), 10.0, 1),
            (_ts(11, 0), 10.0, 1),
        ])
        result = detect_breaks(df, TARGET)
        assert result == "Break:09:00-10:00"

    def test_multiple_breaks(self):
        """Two separate zero-speed intervals → two Break: entries joined by a space."""
        df = _make_df([
            (_ts(8, 0),  10.0, 1),
            (_ts(9, 0),   0.0, 1),
            (_ts(9, 30), 10.0, 1),
            (_ts(10, 0),  0.0, 1),
            (_ts(10, 45), 10.0, 1),
        ])
        result = detect_breaks(df, TARGET)
        assert result == "Break:09:00-09:30 Break:10:00-10:45"

    def test_no_zeros(self):
        """speed never 0 → empty string."""
        df = _make_df([
            (_ts(8, 0), 5.0, 1),
            (_ts(9, 0), 8.0, 1),
        ])
        result = detect_breaks(df, TARGET)
        assert result == ""

    def test_wrong_date_filtered_out(self):
        """Data on a different date → empty string."""
        df = _make_df([
            (_ts(9, 0,  OTHER), 0.0, 1),
            (_ts(10, 0, OTHER), 5.0, 1),
        ])
        result = detect_breaks(df, TARGET)
        assert result == ""

    def test_empty_dataframe(self):
        """Empty DataFrame → empty string."""
        df = _make_df([])
        result = detect_breaks(df, TARGET)
        assert result == ""

    def test_break_open_ended_at_day_boundary(self):
        """Zero-speed that never ends in the day → closes at last timestamp."""
        df = _make_df([
            (_ts(22, 0), 10.0, 1),
            (_ts(23, 0),  0.0, 1),
            (_ts(23, 59),  0.0, 1),
        ])
        result = detect_breaks(df, TARGET)
        assert result == "Break:23:00-23:59"

    def test_mixed_numeric_and_string_speed(self):
        """Speed column can have mixed types; pd.to_numeric coerces safely."""
        df = _make_df([
            (_ts(8, 0),  "10", 1),
            (_ts(9, 0),  "0",  1),
            (_ts(10, 0), "5",  1),
        ])
        result = detect_breaks(df, TARGET)
        assert result == "Break:09:00-10:00"


# ──────────────────────────────────────────────────────────────────────────────
# dates_in_range
# ──────────────────────────────────────────────────────────────────────────────

class TestDatesInRange:
    def test_single_day(self):
        assert dates_in_range(date(2026, 6, 6), date(2026, 6, 6)) == [date(2026, 6, 6)]

    def test_three_days(self):
        result = dates_in_range(date(2026, 6, 1), date(2026, 6, 3))
        assert result == [date(2026, 6, 1), date(2026, 6, 2), date(2026, 6, 3)]

    def test_end_before_start(self):
        assert dates_in_range(date(2026, 6, 5), date(2026, 6, 4)) == []
