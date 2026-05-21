from __future__ import annotations

import pandas as pd

from features.otkph.services import (
    _apply_otkph_data_filters,
    _build_effective_elapsed_seconds,
    _default_otkph_filter_state,
    _normalize_otkph_filter_state,
    collect_frozen_periods,
)


def test_normalize_otkph_filter_state_defaults() -> None:
    state = _normalize_otkph_filter_state({"time_mode": "bad", "time_time_a": ""})
    assert state["time_mode"] == "all"
    assert state["time_time_a"] == "00:00"
    assert state["time_time_b"] == "23:59"


def test_apply_otkph_data_filters_time_between() -> None:
    df = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                ["2026-01-01 09:00:00", "2026-01-01 10:00:00", "2026-01-01 11:00:00"]
            ),
            "thermo_cam_1": [40.0, 41.0, 42.0],
        }
    )
    fs = _default_otkph_filter_state()
    fs.update(
        {
            "time_mode": "between",
            "time_date_a": "2026-01-01",
            "time_time_a": "09:30",
            "time_date_b": "2026-01-01",
            "time_time_b": "10:30",
        }
    )
    out = _apply_otkph_data_filters(df, fs)
    assert len(out) == 1
    assert out.iloc[0]["timestamp"] == pd.Timestamp("2026-01-01 10:00:00")


def test_collect_frozen_periods_detects_long_constant_segment() -> None:
    df = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                [
                    "2026-01-01 00:00:00",
                    "2026-01-01 01:00:00",
                    "2026-01-01 02:00:00",
                    "2026-01-01 03:30:00",
                    "2026-01-01 04:00:00",
                ]
            ),
            "thermo_cam_1": [50.0, 50.0, 50.0, 50.0, 52.0],
        }
    )
    out = collect_frozen_periods(df, [1], ignore_interrupted=False)
    assert len(out) == 1
    assert out[0]["camera"] == "CAM-01"
    assert out[0]["duration_sec"] >= 3 * 3600


def test_effective_elapsed_ignores_zero_speed_intervals_when_enabled() -> None:
    df = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                [
                    "2026-01-01 00:00:00",
                    "2026-01-01 00:01:00",
                    "2026-01-01 00:02:00",
                ]
            ),
            "speed": [10.0, 0.0, 10.0],
        }
    )
    elapsed = _build_effective_elapsed_seconds(df, ignore_interrupted=True)
    assert elapsed.tolist() == [0.0, 0.0, 0.0]


def test_effective_elapsed_counts_zero_speed_intervals_when_disabled() -> None:
    df = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                [
                    "2026-01-01 00:00:00",
                    "2026-01-01 00:01:00",
                    "2026-01-01 00:02:00",
                ]
            ),
            "speed": [10.0, 0.0, 10.0],
        }
    )
    elapsed = _build_effective_elapsed_seconds(df, ignore_interrupted=False)
    assert elapsed.tolist() == [0.0, 60.0, 120.0]

