from __future__ import annotations

from typing import List, Tuple

import numpy as np
import pandas as pd


def _downsample(df: pd.DataFrame, max_points: int = 2000) -> pd.DataFrame:
    if len(df) <= max_points:
        return df
    step = max(1, len(df) // max_points)
    return df.iloc[::step].copy()


def build_step_ranges(df: pd.DataFrame, pre_sorted: bool = False) -> List[Tuple[int, pd.Timestamp, pd.Timestamp]]:
    if df.empty:
        return []
    if not pre_sorted:
        df = df.sort_values("timestamp").copy()
    else:
        df = df.copy()
    step_num = pd.to_numeric(df["step"], errors="coerce")
    mask = step_num.notna()
    if not mask.any():
        return []
    d = df.loc[mask, ["timestamp"]].copy()
    d["step_i"] = step_num.loc[mask].astype(int).to_numpy()
    run_id = d["step_i"].ne(d["step_i"].shift()).fillna(True).cumsum()
    d["run_id"] = run_id.to_numpy()
    grp = d.groupby("run_id", sort=False)
    out: List[Tuple[int, pd.Timestamp, pd.Timestamp]] = []
    for _rid, g in grp:
        out.append((int(g["step_i"].iloc[0]), g["timestamp"].iloc[0], g["timestamp"].iloc[-1]))
    return out


def build_step_transitions(df: pd.DataFrame, pre_sorted: bool = False) -> List[Tuple[int, int, pd.Timestamp]]:
    if df.empty:
        return []
    if not pre_sorted:
        d = df.sort_values("timestamp").copy()
    else:
        d = df.copy()
    step_num = pd.to_numeric(d["step"], errors="coerce")
    mask = step_num.notna()
    if not mask.any():
        return []
    d = d.loc[mask, ["timestamp"]].copy()
    d["step_i"] = step_num.loc[mask].astype(int).to_numpy()
    if len(d) < 2:
        return []
    changed = d["step_i"].ne(d["step_i"].shift()).fillna(True)
    idx = np.flatnonzero(changed.to_numpy(dtype=bool))
    if len(idx) <= 1:
        return []
    out: List[Tuple[int, int, pd.Timestamp]] = []
    ts = d["timestamp"].to_numpy()
    for j in range(1, len(idx)):
        cur_i = int(idx[j])
        prev_i = int(idx[j - 1])
        out.append((int(d["step_i"].iloc[prev_i]), int(d["step_i"].iloc[cur_i]), ts[cur_i]))
    return out


def _index_bounds_for_timestamp_window(
    df: pd.DataFrame, t0: pd.Timestamp, t1: pd.Timestamp
) -> Tuple[float, float]:
    if df.empty:
        return 0.0, 0.0
    ts = df["timestamp"]
    mask = (ts >= t0) & (ts <= t1)
    if not mask.any():
        return 0.0, 0.0
    idx = np.flatnonzero(mask.to_numpy())
    return float(idx[0]), float(idx[-1])


def _x_at_step_transition(df: pd.DataFrame, boundary_ts: pd.Timestamp) -> float:
    if df.empty:
        return -0.5
    ts = df["timestamp"]
    idx = int(ts.searchsorted(boundary_ts, side="left"))
    if idx >= len(df):
        return float(max(0, len(df) - 1))
    return float(max(0, idx)) - 0.5
