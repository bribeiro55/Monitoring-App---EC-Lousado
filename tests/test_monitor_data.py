from __future__ import annotations

import numpy as np
import pandas as pd

from features.monitor.data import _primary_placement_match_numpy


def _make_df(rows):
    return pd.DataFrame(rows, columns=["machine_id", "position"])


def test_matching_rows_return_true():
    df = _make_df([
        {"machine_id": "M7900", "position": 1},
        {"machine_id": "M7950", "position": 2},
        {"machine_id": "M7900", "position": 1},
    ])
    result = _primary_placement_match_numpy(df, ("M7900", 1))
    assert list(result) == [True, False, True]


def test_nan_machine_id_does_not_match():
    df = _make_df([
        {"machine_id": np.nan, "position": 1},
        {"machine_id": "M7900", "position": 1},
    ])
    result = _primary_placement_match_numpy(df, ("M7900", 1))
    assert list(result) == [False, True]


def test_nan_position_does_not_match():
    df = _make_df([
        {"machine_id": "M7900", "position": np.nan},
        {"machine_id": "M7900", "position": 1},
    ])
    result = _primary_placement_match_numpy(df, ("M7900", 1))
    assert list(result) == [False, True]


def test_empty_dataframe_returns_empty_array():
    df = pd.DataFrame(columns=["machine_id", "position"])
    result = _primary_placement_match_numpy(df, ("M7900", 1))
    assert len(result) == 0
    assert result.dtype == bool
