from __future__ import annotations

from typing import List, Optional, Tuple

import numpy as np
import pandas as pd

from config import STORE_COLUMNS


def _rows_to_df(rows: List[dict]) -> pd.DataFrame:
    base_cols = [
        "timestamp",
        "machine_id",
        "position",
        "step",
        "speed",
        "load_kg",
        "deflection_mm",
        "inflation_pressure_kpa",
        "room_temp_c",
        "cpc_temp_c",
        "circumference_mm",
        "torque_nm",
        "machine_running",
        "thermo_cam_1",
        "thermo_cam_2",
        "thermo_cam_3",
        "thermo_cam_4",
        "thermo_cam_5",
    ]
    if not rows:
        return pd.DataFrame(columns=base_cols)
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


def _placement_key(machine_id: object, pos: object) -> Optional[Tuple[str, int]]:
    if machine_id is None or pos is None:
        return None
    try:
        if pd.isna(machine_id) or pd.isna(pos):
            return None
    except (ValueError, TypeError):
        return None
    try:
        return (str(machine_id), int(pos))
    except (ValueError, TypeError):
        return None


def _row_is_primary_placement(row: pd.Series, primary: Optional[Tuple[str, int]]) -> bool:
    if primary is None:
        return True
    k = _placement_key(row.get("machine_id"), row.get("position"))
    return k == primary


def _primary_placement_match_numpy(df: pd.DataFrame, primary: Tuple[str, int]) -> np.ndarray:
    """Row-wise boolean mask: True where (machine_id, position) matches primary."""
    mid = df["machine_id"].astype(str).to_numpy()
    pos = pd.to_numeric(df["position"], errors="coerce").fillna(-1).astype(int).to_numpy()
    return (mid == str(primary[0])) & (pos == int(primary[1]))


def _segment_run_bounds(is_prim: np.ndarray) -> List[Tuple[int, int, bool]]:
    """Contiguous True/False runs as (lo, hi, is_primary) index triples."""
    n = len(is_prim)
    if n == 0:
        return []
    starts = np.concatenate([[0], np.flatnonzero(is_prim[1:] != is_prim[:-1]) + 1])
    ends = np.concatenate([starts[1:] - 1, [n - 1]])
    return [(int(lo), int(hi), bool(is_prim[lo])) for lo, hi in zip(starts, ends)]
