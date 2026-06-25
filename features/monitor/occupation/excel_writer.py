from __future__ import annotations

from datetime import date, timedelta
from typing import List

import pandas as pd


def detect_breaks(df: pd.DataFrame, target_date: date) -> str:
    """Return a break string for target_date from a parsed log DataFrame.

    Each continuous zero-speed interval becomes one 'Break:HH:MM-HH:MM' entry.
    Multiple breaks are joined with a single space. Returns '' when speed is never 0.
    """
    df = df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    day_df = df[df["timestamp"].dt.date == target_date].sort_values("timestamp")
    if day_df.empty:
        return ""

    speed = pd.to_numeric(day_df["speed"], errors="coerce").fillna(0)
    breaks: list[str] = []
    in_break = False
    start_ts = None

    for ts, is_zero in zip(day_df["timestamp"], speed == 0):
        if is_zero and not in_break:
            in_break = True
            start_ts = ts
        elif not is_zero and in_break:
            in_break = False
            breaks.append(f"Break:{start_ts.strftime('%H:%M')}-{ts.strftime('%H:%M')}")

    if in_break and start_ts is not None:
        end_ts = day_df["timestamp"].iloc[-1]
        breaks.append(f"Break:{start_ts.strftime('%H:%M')}-{end_ts.strftime('%H:%M')}")

    return " ".join(breaks)


def dates_in_range(start: date, end: date) -> List[date]:
    """Return all dates from start to end inclusive."""
    result = []
    current = start
    while current <= end:
        result.append(current)
        current += timedelta(days=1)
    return result
