from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from config import VARIABLE_CONFIG
from features.monitor.data import _rows_to_df as rows_to_df, _apply_chart_filters as apply_chart_filters

ANALYSIS_FILTER_VARIABLE_OPTIONS = [
    {"label": cfg["label"], "value": key} for key, cfg in VARIABLE_CONFIG.items()
]


def analysis_parse_limit_field(v: object) -> Optional[float]:
    if v is None or v == "":
        return None
    try:
        x = float(v)
        if not np.isfinite(x):
            return None
        return x
    except (TypeError, ValueError):
        return None


def normalize_analysis_band_limits(raw: object) -> Dict[str, Optional[float]]:
    if isinstance(raw, dict):
        return {
            "upper": analysis_parse_limit_field(raw.get("upper")),
            "lower": analysis_parse_limit_field(raw.get("lower")),
        }
    return {"upper": None, "lower": None}


def default_analysis_filter_state() -> Dict[str, Any]:
    return {
        "variable_filters": [],
        "time_mode": "all",
        "time_date_a": None,
        "time_date_b": None,
        "time_time_a": "00:00",
        "time_time_b": "23:59",
    }


def to_opt_float(v: object) -> Optional[float]:
    if v in (None, ""):
        return None
    try:
        x = float(v)
        return x if np.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def normalize_variable_filter(raw: object, *, default_id: int = 0) -> Dict[str, Any]:
    item = dict(raw) if isinstance(raw, dict) else {}
    var = str(item.get("variable") or "temperature")
    if var not in VARIABLE_CONFIG:
        var = "temperature"
    mode = str(item.get("mode") or "above").lower()
    if mode not in {"above", "below", "between"}:
        mode = "above"
    try:
        fid = int(item.get("id", default_id))
    except (TypeError, ValueError):
        fid = default_id
    return {
        "id": fid,
        "variable": var,
        "mode": mode,
        "value_a": to_opt_float(item.get("value_a")),
        "value_b": to_opt_float(item.get("value_b")),
    }


def normalize_variable_filters(raw: object) -> List[Dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    out: List[Dict[str, Any]] = []
    for i, item in enumerate(raw):
        out.append(normalize_variable_filter(item, default_id=i))
    return out


def count_active_variable_filters(filters: List[Dict[str, Any]]) -> int:
    n = 0
    for vf in filters:
        mode = vf.get("mode", "above")
        va = vf.get("value_a")
        vb = vf.get("value_b")
        if mode in {"above", "below"} and va is not None:
            n += 1
        elif mode == "between" and va is not None and vb is not None:
            n += 1
    return n


def normalize_analysis_filter_state(raw: object) -> Dict[str, Any]:
    base = default_analysis_filter_state()
    if not isinstance(raw, dict):
        return base
    out = dict(base)
    out.update(raw)
    if "variable_filters" not in raw and raw.get("value_mode") not in (None, "all"):
        out["variable_filters"] = normalize_variable_filters(
            [
                {
                    "id": 0,
                    "variable": "temperature",
                    "mode": raw.get("value_mode"),
                    "value_a": raw.get("value_a"),
                    "value_b": raw.get("value_b"),
                }
            ]
        )
    else:
        out["variable_filters"] = normalize_variable_filters(out.get("variable_filters"))
    if out.get("time_mode") not in {"all", "after", "before", "between"}:
        out["time_mode"] = "all"
    return out


def to_opt_date(v: object) -> Optional[pd.Timestamp]:
    if v in (None, ""):
        return None
    ts = pd.to_datetime(v, errors="coerce")
    if pd.isna(ts):
        return None
    return pd.Timestamp(ts).normalize()


def parse_hhmm(v: object, default: Optional[str] = None) -> Optional[Tuple[int, int]]:
    txt = str(v if v not in (None, "") else (default or "")).strip()
    m = re.fullmatch(r"([01]?\d|2[0-3]):([0-5]\d)", txt)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def to_opt_datetime(date_value: object, hhmm_value: object, default_hhmm: str) -> Optional[pd.Timestamp]:
    d = to_opt_date(date_value)
    hm = parse_hhmm(hhmm_value, default_hhmm)
    if d is None or hm is None:
        return None
    return d + pd.Timedelta(hours=hm[0], minutes=hm[1])


def apply_single_test_analysis_filters(
    dff: pd.DataFrame,
    *,
    filters: Optional[dict],
    variable_config: Optional[dict] = None,
) -> pd.DataFrame:
    d = dff.copy()
    fs = normalize_analysis_filter_state(filters)
    var_cfg = variable_config or VARIABLE_CONFIG

    for vf in fs.get("variable_filters") or []:
        var_key = vf.get("variable", "temperature")
        col = var_cfg.get(var_key, var_cfg.get("temperature", {})).get("col")
        if not col or col not in d.columns:
            continue
        mode = vf.get("mode", "above")
        va = vf.get("value_a")
        vb = vf.get("value_b")
        y = pd.to_numeric(d[col], errors="coerce")
        if mode == "above" and va is not None:
            d = d[y > va]
        elif mode == "below" and va is not None:
            d = d[y < va]
        elif mode == "between" and va is not None and vb is not None:
            lo, hi = sorted((va, vb))
            d = d[(y >= lo) & (y <= hi)]

    time_mode = fs.get("time_mode", "all")
    t1 = to_opt_datetime(fs.get("time_date_a"), fs.get("time_time_a"), "00:00")
    t2 = to_opt_datetime(fs.get("time_date_b"), fs.get("time_time_b"), "23:59")
    if time_mode != "all" and "timestamp" in d.columns and not d.empty:
        ts = pd.to_datetime(d["timestamp"], errors="coerce")
        if time_mode == "after" and t1 is not None:
            d = d[ts >= t1]
        elif time_mode == "before" and t1 is not None:
            d = d[ts <= t1]
        elif time_mode == "between" and t1 is not None and t2 is not None:
            lo, hi = sorted((t1, t2))
            d = d[(ts >= lo) & (ts <= hi)]

    return d


def build_analysis_test_frames(
    *,
    tests: Optional[List[dict]],
    data: Optional[dict],
    active_steps: List[object],
    ignore_stopped: bool,
    selected_var: str,
    data_filters: Optional[dict],
    variable_config: dict,
    compare_palette: list[str],
) -> Tuple[List[Tuple[str, pd.DataFrame, str]], dict, str, str]:
    tests = list(tests or [])
    data = dict(data or {})
    var_cfg = variable_config.get(selected_var, variable_config["temperature"])
    value_col = var_cfg["col"]
    var_key = selected_var or "temperature"
    single_test_mode = len(tests) == 1
    test_frames: List[Tuple[str, pd.DataFrame, str]] = []
    for t in tests:
        tn = str(t.get("test_number", ""))
        ci = int(t.get("color_index", 0)) % len(compare_palette)
        color = compare_palette[ci]
        entry = data.get(tn, {})
        if entry.get("status") != "ok":
            continue
        df = rows_to_df(entry.get("rows") or [])
        if df.empty:
            continue
        dff = apply_chart_filters(df, active_steps, ignore_stopped)
        if single_test_mode:
            dff = apply_single_test_analysis_filters(
                dff, filters=data_filters, variable_config=variable_config
            )
        if dff.empty:
            continue
        test_frames.append((f"Test {tn}", dff, color))
    return test_frames, var_cfg, value_col, var_key


def summary_status_for_band(
    max_val: float,
    min_val: float,
    upper: Optional[float],
    lower: Optional[float],
) -> Tuple[str, str]:
    if upper is None and lower is None:
        return "OK", "badge-ok"
    bad = False
    if upper is not None and max_val > upper:
        bad = True
    if lower is not None and min_val < lower:
        bad = True
    if bad:
        return "WARN", "badge-warn"
    return "OK", "badge-ok"


def collect_band_crossing_violations(
    test_frames: List[Tuple[str, pd.DataFrame, str]],
    *,
    value_col: str,
    upper: Optional[float],
    lower: Optional[float],
) -> List[dict]:
    if upper is None and lower is None:
        return []
    rows: List[dict] = []
    for label, dff, color in test_frames:
        if dff.empty or value_col not in dff.columns:
            continue
        d_sorted = dff.sort_values("timestamp").reset_index(drop=True)
        vals = pd.to_numeric(d_sorted[value_col], errors="coerce")
        valid = vals.notna()
        outside_upper = (vals > upper) if upper is not None else pd.Series(False, index=vals.index)
        outside_lower = (vals < lower) if lower is not None else pd.Series(False, index=vals.index)
        outside = outside_upper | outside_lower
        cur_in = (~outside).where(valid, np.nan)
        prev_in = cur_in.ffill().shift(1).fillna(True).astype(bool)
        crossings = valid & outside & prev_in
        for i in np.flatnonzero(crossings.to_numpy()):
            val = float(vals.iloc[i])
            if not np.isfinite(val):
                continue
            if upper is not None and val > upper:
                kind = "upper"
                lim_disp = float(upper)
                lim_label = "Above upper limit"
            elif lower is not None and val < lower:
                kind = "lower"
                lim_disp = float(lower)
                lim_label = "Below lower limit"
            else:
                continue
            row = d_sorted.iloc[i]
            step_v = row.get("step")
            step_s = int(step_v) if pd.notna(step_v) else "–"
            ts = row.get("timestamp")
            ts_raw = ts if pd.notna(ts) else pd.NaT
            ts_str = ts.strftime("%d %b %Y %H:%M:%S") if pd.notna(ts) else "–"
            rows.append(
                {
                    "test": label,
                    "kind": kind,
                    "lim_label": lim_label,
                    "limit_value": lim_disp,
                    "value": val,
                    "time_display": ts_str,
                    "ts": ts_raw,
                    "step": step_s,
                    "color": color,
                }
            )
    return rows
