from __future__ import annotations

from typing import List, Optional

import numpy as np
import pandas as pd

CAM_DEFS = [
    {"i": 1, "code": "CAM-01", "label": "Camera 1", "color": "#F0BA20"},
    {"i": 2, "code": "CAM-02", "label": "Camera 2", "color": "#E8721A"},
    {"i": 3, "code": "CAM-03", "label": "Camera 3", "color": "#4A90D9"},
    {"i": 4, "code": "CAM-04", "label": "Camera 4", "color": "#B36EE8"},
    {"i": 5, "code": "CAM-05", "label": "Camera 5", "color": "#34C47C"},
]

FAULT_NAN_FRAC = 0.50
FAULT_STD_EPS = 1e-6
FAULT_ZERO_MEAN_ABS = 0.5
FAULT_MIN_SAMPLES = 10


def _thermo_col(i: int) -> str:
    return f"thermo_cam_{i}"


def _camera_health(col_vals: pd.Series) -> bool:
    v = pd.to_numeric(col_vals, errors="coerce")
    if len(v) == 0:
        return True
    if float(v.isna().mean()) > FAULT_NAN_FRAC:
        return False
    vv = v.dropna()
    if len(vv) < FAULT_MIN_SAMPLES:
        return True
    std = float(vv.std(ddof=0))
    mean = float(vv.mean())
    return not (std < FAULT_STD_EPS and abs(mean) < FAULT_ZERO_MEAN_ABS)


def _filter_otkph_frame(df: pd.DataFrame, step_filter: str) -> pd.DataFrame:
    if df.empty:
        return df
    d = df.copy()
    if step_filter != "all":
        try:
            d = d[d["step"] == int(step_filter)]
        except (TypeError, ValueError):
            pass
    return d.sort_values("timestamp").reset_index(drop=True)


def _default_otkph_filter_state() -> dict:
    return {"time_mode": "all", "time_date_a": None, "time_date_b": None, "time_time_a": "00:00", "time_time_b": "23:59"}


def _normalize_otkph_filter_state(state: Optional[dict]) -> dict:
    fs = dict(_default_otkph_filter_state())
    if isinstance(state, dict):
        fs.update(state)
    tm = str(fs.get("time_mode") or "all").lower()
    fs["time_mode"] = tm if tm in {"all", "after", "before", "between"} else "all"
    fs["time_time_a"] = str(fs.get("time_time_a") or "00:00").strip() or "00:00"
    fs["time_time_b"] = str(fs.get("time_time_b") or "23:59").strip() or "23:59"
    return fs


def _to_opt_datetime(date_s: Optional[str], time_s: Optional[str], fallback_time: str) -> Optional[pd.Timestamp]:
    if not date_s:
        return None
    t = str(time_s or fallback_time).strip() or fallback_time
    try:
        return pd.to_datetime(f"{date_s} {t}", errors="coerce")
    except Exception:
        return None


def _apply_otkph_data_filters(df: pd.DataFrame, fs: Optional[dict]) -> pd.DataFrame:
    if df.empty:
        return df
    st = _normalize_otkph_filter_state(fs)
    d = df.sort_values("timestamp").reset_index(drop=True).copy()
    d["timestamp"] = pd.to_datetime(d["timestamp"], errors="coerce")
    d = d.dropna(subset=["timestamp"]).reset_index(drop=True)
    if d.empty:
        return d
    t_mode = st["time_mode"]
    ta = _to_opt_datetime(st.get("time_date_a"), st.get("time_time_a"), "00:00")
    tb = _to_opt_datetime(st.get("time_date_b"), st.get("time_time_b"), "23:59")
    if t_mode == "after" and ta is not None:
        d = d[d["timestamp"] >= ta]
    elif t_mode == "before" and ta is not None:
        d = d[d["timestamp"] <= ta]
    elif t_mode == "between" and ta is not None and tb is not None:
        lo, hi = (ta, tb) if ta <= tb else (tb, ta)
        d = d[(d["timestamp"] >= lo) & (d["timestamp"] <= hi)]
    return d.reset_index(drop=True)


def _apply_ignore_interrupted_rows(df: pd.DataFrame, ignore_interrupted: bool) -> pd.DataFrame:
    if df.empty or not ignore_interrupted:
        return df
    d = df.sort_values("timestamp").reset_index(drop=True).copy()
    if "speed" not in d.columns:
        return d
    spd = pd.to_numeric(d["speed"], errors="coerce").to_numpy(dtype=float, copy=False)
    # Interrupted rows: speed <= 0. NaN speed is kept (unknown state, not explicit stop).
    keep = ~(np.isfinite(spd) & (spd <= 0))
    return d.loc[keep].reset_index(drop=True)


def _build_effective_elapsed_seconds(df: pd.DataFrame, ignore_interrupted: bool) -> pd.Series:
    if df.empty:
        return pd.Series(dtype=float)
    d = df.sort_values("timestamp").reset_index(drop=True)
    ts = pd.to_datetime(d["timestamp"], errors="coerce")
    delta = ts.diff().dt.total_seconds()
    valid = delta[(delta > 0) & np.isfinite(delta)]
    if valid.empty:
        return pd.Series(np.zeros(len(d), dtype=float), index=d.index, dtype=float)
    if ignore_interrupted:
        cadence = float(valid.median())
        interruption_gap = max(30.0, cadence * 6.0)
        running_mask = np.ones(len(d), dtype=bool)
        if "speed" in d.columns:
            spd = pd.to_numeric(d["speed"], errors="coerce").to_numpy(dtype=float, copy=False)
            # Treat zero/negative speed as interrupted; ignore elapsed across those periods.
            stopped = np.isfinite(spd) & (spd <= 0)
            if len(stopped) > 1:
                running_mask[1:] &= ~stopped[1:] & ~stopped[:-1]
            else:
                running_mask &= ~stopped
        contrib = np.where(
            (delta > 0) & (delta <= interruption_gap) & running_mask,
            delta.to_numpy(dtype=float),
            0.0,
        )
    else:
        contrib = np.where(delta > 0, delta.to_numpy(dtype=float), 0.0)
    return pd.Series(np.cumsum(contrib), index=d.index, dtype=float)


def _with_plot_axis(df: pd.DataFrame, ignore_interrupted: bool) -> pd.DataFrame:
    if df.empty:
        return df
    d = df.sort_values("timestamp").reset_index(drop=True).copy()
    d["timestamp"] = pd.to_datetime(d["timestamp"], errors="coerce")
    d = d.dropna(subset=["timestamp"]).reset_index(drop=True)
    if d.empty:
        return d
    d["plot_x"] = _build_effective_elapsed_seconds(d, ignore_interrupted) if ignore_interrupted else d["timestamp"]
    return d


def _format_frozen_period(start_ts: pd.Timestamp, end_ts: pd.Timestamp) -> str:
    if pd.isna(start_ts) or pd.isna(end_ts):
        return "–"
    if start_ts.date() == end_ts.date():
        return f"{start_ts.strftime('%d %b %Y')} {start_ts.strftime('%H:%M')} - {end_ts.strftime('%H:%M')}"
    return f"{start_ts.strftime('%d %b %Y %H:%M')} -> {end_ts.strftime('%d %b %Y %H:%M')}"


def collect_frozen_periods(
    df: pd.DataFrame,
    active: List[int],
    *,
    ignore_interrupted: bool,
    tolerance_c: float = 0.01,
    min_duration_sec: float = 3 * 3600,
) -> List[dict]:
    out: List[dict] = []
    if df.empty:
        return out
    d = df.sort_values("timestamp").reset_index(drop=True).copy()
    d["timestamp"] = pd.to_datetime(d["timestamp"], errors="coerce")
    d = d.dropna(subset=["timestamp"]).reset_index(drop=True)
    if d.empty:
        return out
    elapsed = _build_effective_elapsed_seconds(d, ignore_interrupted)
    ts = d["timestamp"]
    for i in active:
        col = _thermo_col(i)
        if col not in d.columns:
            continue
        vals = pd.to_numeric(d[col], errors="coerce").to_numpy(dtype=np.float64, copy=False)
        n = len(vals)
        s = 0
        while s < n:
            if np.isnan(vals[s]):
                s += 1
                continue
            anchor = float(vals[s])
            e = s
            while e + 1 < n and not np.isnan(vals[e + 1]) and abs(float(vals[e + 1]) - anchor) <= tolerance_c:
                e += 1
            dur = float(elapsed.iloc[e] - elapsed.iloc[s]) if e >= s else 0.0
            if dur >= float(min_duration_sec):
                cd = CAM_DEFS[i - 1]
                out.append({"camera": cd["code"], "start_temp": float(vals[s]), "end_temp": float(vals[e]), "t_start": ts.iloc[s], "t_end": ts.iloc[e], "duration_sec": dur})
            s = e + 1
    out.sort(key=lambda r: (r["t_start"], r["camera"]), reverse=True)
    return out

