from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd


# Defensive cap against broken logs producing giant gaps.
MAX_RUNNING_GAP_SECONDS = 3600


def format_hhmm_from_seconds(total_seconds: float) -> str:
    if total_seconds is None or not np.isfinite(total_seconds):
        return "00:00"
    clamped = max(0, int(total_seconds))
    hours = clamped // 3600
    minutes = (clamped % 3600) // 60
    return f"{hours:02d}:{minutes:02d}"


def build_running_elapsed_seconds_series(
    df: pd.DataFrame,
    *,
    timestamp_col: str = "timestamp",
    running_col: str = "machine_running",
    max_gap_seconds: int = MAX_RUNNING_GAP_SECONDS,
) -> pd.Series:
    """
    Cumulative running elapsed seconds using adjacent row deltas:
    - sort by timestamp
    - delta(i) = t[i] - t[i-1]
    - include delta(i) only when both row(i-1) and row(i) are running
    - ignore non-positive and over-cap deltas
    """
    if df.empty:
        return pd.Series(dtype=float)
    if timestamp_col not in df.columns or running_col not in df.columns:
        return pd.Series(np.zeros(len(df), dtype=float), index=df.index, dtype=float)

    d = df.copy()
    d[timestamp_col] = pd.to_datetime(d[timestamp_col], errors="coerce")
    d[running_col] = d[running_col].fillna(False).astype(bool)
    d = d.sort_values(timestamp_col)

    ts = d[timestamp_col]
    running = d[running_col]
    delta_sec = ts.diff().dt.total_seconds()
    valid_delta = delta_sec > 0
    if max_gap_seconds is not None and max_gap_seconds > 0:
        valid_delta = valid_delta & (delta_sec <= float(max_gap_seconds))
    # Use explicit boolean comparison to avoid future pandas downcasting warnings.
    running_pair = running & running.shift(1).eq(True)
    contrib = np.where(valid_delta & running_pair, delta_sec.to_numpy(dtype=float), 0.0)
    elapsed = pd.Series(np.cumsum(contrib), index=d.index, dtype=float)

    return elapsed.reindex(df.index).ffill().fillna(0.0)


def build_running_hhmm_labels(elapsed_seconds: Iterable[float]) -> list[str]:
    return [format_hhmm_from_seconds(v) for v in elapsed_seconds]
