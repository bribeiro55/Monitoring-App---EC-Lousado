from __future__ import annotations

from typing import List

import numpy as np
import pandas as pd

from config import OUTPUT_COLUMNS, STORE_COLUMNS


def _rows_to_df(rows: List[dict]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)
    df = pd.DataFrame(rows)
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df["machine_running"] = df["machine_running"].astype(bool)
    for k in range(1, 6):
        c = f"thermo_cam_{k}"
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    if "speed" in df.columns:
        df["speed"] = pd.to_numeric(df["speed"], errors="coerce")
    return df


def _timestamp_col_to_store_strings(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s, errors="coerce").dt.strftime("%Y-%m-%dT%H:%M:%S")


def _serialize_df_rows(df: pd.DataFrame) -> List[dict]:
    cols = [c for c in STORE_COLUMNS if c in df.columns]
    df_store = df[cols].copy() if cols else df.copy()
    if "timestamp" in df_store.columns:
        df_store["timestamp"] = _timestamp_col_to_store_strings(df_store["timestamp"])
    df_store = df_store.where(pd.notnull(df_store), None)
    return df_store.to_dict("records")


def _filter_by_steps(df: pd.DataFrame, active_steps: List[object]) -> pd.DataFrame:
    # When 'All' is active, include NaN-step rows so cpc_temp_c still plots.
    if df.empty:
        return df
    steps_set = set(active_steps or ["all"])
    if "all" in steps_set or not steps_set:
        visible = set(range(1, 10))
        return df[df["step"].isna() | df["step"].isin(visible)]
    visible_steps = set(int(s) for s in steps_set)
    return df[df["step"].isin(visible_steps)]


def _df_after_ignore_stopped(df: pd.DataFrame, ignore_stopped: bool) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.sort_values("timestamp").copy()
    if ignore_stopped:
        out = out[out["machine_running"] == True]
    return out


def _apply_chart_filters(df: pd.DataFrame, active_steps: List[object], ignore_stopped: bool) -> pd.DataFrame:
    out = _df_after_ignore_stopped(df, ignore_stopped)
    return _filter_by_steps(out, active_steps)
