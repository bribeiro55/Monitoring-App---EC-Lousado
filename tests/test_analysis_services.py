from __future__ import annotations

import pandas as pd

from features.analysis.services import (
    apply_single_test_analysis_filters,
    normalize_analysis_band_limits,
    normalize_analysis_filter_state,
    to_opt_datetime,
)


def test_normalize_analysis_filter_state_falls_back_to_defaults() -> None:
    out = normalize_analysis_filter_state({"time_mode": "after"})
    assert out["time_mode"] == "after"
    assert out["variable_filters"] == []
    assert out["time_time_a"] == "00:00"
    assert out["time_time_b"] == "23:59"


def test_normalize_analysis_band_limits_parses_numeric_values() -> None:
    out = normalize_analysis_band_limits({"upper": "45.5", "lower": "10"})
    assert out == {"upper": 45.5, "lower": 10.0}


def test_to_opt_datetime_combines_date_and_time() -> None:
    ts = to_opt_datetime("2026-01-02", "08:30", "00:00")
    assert ts == pd.Timestamp("2026-01-02 08:30:00")


def test_apply_single_test_analysis_filters_multi_variable_and_time() -> None:
    df = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                ["2026-01-01 09:00:00", "2026-01-01 10:00:00", "2026-01-01 11:00:00"]
            ),
            "cpc_temp_c": [10.0, 25.0, 40.0],
            "speed": [5.0, 30.0, 60.0],
        }
    )
    filters = {
        "variable_filters": [
            {"id": 0, "variable": "temperature", "mode": "between", "value_a": 20, "value_b": 40},
            {"id": 1, "variable": "speed", "mode": "above", "value_a": 25, "value_b": None},
        ],
        "time_mode": "between",
        "time_date_a": "2026-01-01",
        "time_time_a": "09:30",
        "time_date_b": "2026-01-01",
        "time_time_b": "10:30",
    }
    out = apply_single_test_analysis_filters(df, filters=filters)
    assert len(out) == 1
    assert float(out.iloc[0]["cpc_temp_c"]) == 25.0
    assert float(out.iloc[0]["speed"]) == 30.0
