"""
Data Analysis tab: layout markup and Plotly figure builders.
Step-band helpers mirror app.py so we avoid importing app (circular import).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from dash import dcc, html
from services.runtime import build_running_elapsed_seconds_series, format_hhmm_from_seconds

# Distinct series colors (matches Dashboard_UI_new_tab.txt COMPARE_PALETTE).
COMPARE_PALETTE = [
    "#F0BA20",
    "#E8721A",
    "#4A90D9",
    "#34C47C",
    "#B36EE8",
    "#E84040",
    "#60C4C4",
    "#A0C030",
    "#E870A0",
]

LIMIT_PALETTE = ["#E84040", "#4A90D9", "#34C47C", "#E8721A", "#B36EE8"]

# Band limit lines on comparison chart (upper = hot / exceed, lower = cold / below)
BAND_UPPER_LINE_COLOR = LIMIT_PALETTE[0]
BAND_LOWER_LINE_COLOR = LIMIT_PALETTE[1]


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
    # Use plain numpy int dtype to avoid pd.NA boolean ambiguity.
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


def _blank_figure() -> go.Figure:
    fig = go.Figure()
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
    )
    return fig


def _tick_font() -> dict:
    return {"family": "DM Mono, monospace", "size": 10, "color": "#9A9EA8"}


def _insert_gap_breaks_for_plot(
    *,
    ts: pd.Series,
    x_vals: np.ndarray,
    y_vals: np.ndarray,
    custom_data: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Break plotted lines across long data gaps by inserting NaN rows.
    Gap threshold is adaptive to sampling cadence and resilient to sparse logs.
    """
    if len(x_vals) <= 1:
        return x_vals, y_vals, custom_data
    tser = pd.to_datetime(ts, errors="coerce")
    delta = tser.diff().dt.total_seconds()
    valid = delta[(delta > 0) & np.isfinite(delta)]
    if valid.empty:
        return x_vals, y_vals, custom_data
    cadence = float(valid.median())
    gap_threshold = max(30.0, cadence * 6.0)
    break_idx = np.flatnonzero((delta > gap_threshold).to_numpy(dtype=bool))
    if len(break_idx) == 0:
        return x_vals, y_vals, custom_data

    break_set = set(int(i) for i in break_idx.tolist())
    out_x: List[float] = []
    out_y: List[float] = []
    out_cd: List[List[object]] = []
    for i in range(len(x_vals)):
        if i in break_set:
            out_x.append(float(x_vals[i]))
            out_y.append(np.nan)
            out_cd.append(["—", "—"])
        out_x.append(float(x_vals[i]))
        out_y.append(float(y_vals[i]) if np.isfinite(y_vals[i]) else np.nan)
        out_cd.append(list(custom_data[i]))
    return np.asarray(out_x), np.asarray(out_y), np.asarray(out_cd, dtype=object)


def build_comparison_figure(
    test_frames: List[Tuple[str, pd.DataFrame, str]],
    *,
    value_col: str,
    var_label: str,
    var_unit: str,
    band_limits: Optional[Dict[str, Optional[float]]],
    normalize_x: bool,
    runtime_align_x: bool = False,
    step_colors: Dict[int, str],
    step_border_colors: Dict[int, str],
) -> go.Figure:
    """
    Overlay one line per test. Step background bands use the longest-running filtered
    dataframe (ordinal index or time aligned to that series for band extents).
    """
    if not test_frames:
        return _blank_figure()

    # Reference frame for step bands/ticks/limit span: longest-running filtered test.
    ref_df: Optional[pd.DataFrame] = None
    ref_runtime_seconds: float = -1.0
    for _lbl, dff, _c in test_frames:
        if dff is not None and not dff.empty:
            cand = dff.sort_values("timestamp").reset_index(drop=True)
            elapsed = build_running_elapsed_seconds_series(cand)
            cand_runtime_seconds = float(elapsed.iloc[-1]) if len(elapsed) > 0 else 0.0
            if cand_runtime_seconds >= ref_runtime_seconds:
                ref_runtime_seconds = cand_runtime_seconds
                ref_df = cand
    if ref_df is None or ref_df.empty:
        return _blank_figure()

    align_by_sample_index = bool(normalize_x) and not runtime_align_x

    # With sample-index alignment, traces use _downsampled row indices 0…n−1. Step bands, limit span,
    # and tick labels must use the same ref_df length or lines sit on the left ~1% of the axis.
    if align_by_sample_index:
        ref_df = _downsample(ref_df)
    ref_runtime_hours = (
        build_running_elapsed_seconds_series(ref_df).to_numpy(dtype=float) / 3600.0
        if runtime_align_x
        else np.array([], dtype=float)
    )

    y_all: List[float] = []
    for _lbl, dff, _c in test_frames:
        if dff.empty:
            continue
        yv = pd.to_numeric(dff[value_col], errors="coerce").dropna()
        if not yv.empty:
            y_all.extend(yv.tolist())

    band = band_limits or {}
    u_lim = band.get("upper")
    l_lim = band.get("lower")
    for lv in (u_lim, l_lim):
        if lv is not None:
            try:
                y_all.append(float(lv))
            except (TypeError, ValueError):
                pass

    if not y_all:
        return _blank_figure()

    y_min = float(np.min(y_all))
    y_max = float(np.max(y_all))
    span = y_max - y_min
    pad = max(1.0, span * 0.08) if span > 0 else 5.0
    y_lo = y_min - pad
    y_hi = y_max + pad

    fig = go.Figure()
    tick_font = _tick_font()

    # Step bands from reference test (mockup: first test's phases).
    for step_val, t0, t1 in build_step_ranges(ref_df, pre_sorted=True):
        if step_val not in step_colors:
            continue
        if align_by_sample_index:
            x0, x1 = _index_bounds_for_timestamp_window(ref_df, t0, t1)
        elif runtime_align_x:
            i0, i1 = _index_bounds_for_timestamp_window(ref_df, t0, t1)
            lo = int(max(0, min(len(ref_runtime_hours) - 1, i0)))
            hi = int(max(0, min(len(ref_runtime_hours) - 1, i1)))
            x0, x1 = float(ref_runtime_hours[lo]), float(ref_runtime_hours[hi])
        else:
            x0, x1 = t0, t1
        fig.add_shape(
            type="rect",
            xref="x",
            yref="y",
            x0=x0,
            x1=x1,
            y0=y_lo,
            y1=y_hi,
            fillcolor=step_colors[step_val],
            layer="below",
            line=dict(width=0),
        )

    for from_step, to_step, boundary_ts in build_step_transitions(ref_df, pre_sorted=True):
        line_color = (
            step_border_colors.get(to_step)
            or step_border_colors.get(from_step)
            or "rgba(122,126,138,0.40)"
        )
        if align_by_sample_index:
            xv = _x_at_step_transition(ref_df, boundary_ts)
        elif runtime_align_x:
            idx = int(ref_df["timestamp"].searchsorted(boundary_ts, side="left"))
            if len(ref_runtime_hours) == 0:
                xv = 0.0
            else:
                idx = max(0, min(len(ref_runtime_hours) - 1, idx))
                xv = float(ref_runtime_hours[idx])
        else:
            xv = boundary_ts
        fig.add_shape(
            type="line",
            xref="x",
            yref="y",
            x0=xv,
            x1=xv,
            y0=y_lo,
            y1=y_hi,
            line=dict(color=line_color, width=1, dash="dash"),
            layer="above",
        )

    # X is still sample index; customdata holds the real timestamp for hover.
    hover_norm = (
        "%{fullData.name}<br>"
        "t=%{customdata[0]}<br>"
        "Run=%{customdata[1]}<br>"
        + f"{var_label}=%{{y:.2f}} {var_unit}<extra></extra>"
    )
    hover_time = (
        "%{fullData.name}<br>"
        "t=%{customdata[0]}<br>"
        "Run=%{customdata[1]}<br>"
        + f"{var_label}=%{{y:.2f}} {var_unit}<extra></extra>"
    )

    for label, dff, color in test_frames:
        if dff.empty:
            continue
        d_sorted = _downsample(dff.sort_values("timestamp").reset_index(drop=True))
        y = pd.to_numeric(d_sorted[value_col], errors="coerce")
        if y.dropna().empty:
            continue
        run_seconds = build_running_elapsed_seconds_series(d_sorted)
        run_hhmm = [format_hhmm_from_seconds(v) for v in run_seconds.to_numpy(dtype=float)]
        custom_ts = d_sorted["timestamp"].dt.strftime("%d %b %Y %H:%M:%S").fillna("—").tolist()
        custom_data = np.column_stack([custom_ts, run_hhmm])
        if align_by_sample_index:
            x_plot = np.arange(len(d_sorted), dtype=float)
            fig.add_trace(
                go.Scatter(
                    x=x_plot,
                    y=y,
                    mode="lines",
                    name=label,
                    line=dict(color=color, width=2, shape="hv"),
                    hovertemplate=hover_norm,
                    customdata=custom_data,
                )
            )
        elif runtime_align_x:
            x_plot = run_seconds.to_numpy(dtype=float) / 3600.0
            fig.add_trace(
                go.Scatter(
                    x=x_plot,
                    y=y,
                    mode="lines",
                    name=label,
                    line=dict(color=color, width=2, shape="hv"),
                    hovertemplate=hover_norm,
                    customdata=custom_data,
                )
            )
        else:
            fig.add_trace(
                go.Scatter(
                    x=d_sorted["timestamp"],
                    y=y,
                    mode="lines",
                    name=label,
                    line=dict(color=color, width=2, shape="hv"),
                    hovertemplate=hover_time,
                    customdata=custom_data,
                )
            )

    def _add_band_hline(lv: float, label: str, col: str) -> None:
        if align_by_sample_index and ref_df is not None and len(ref_df) > 0:
            x0 = 0.0
            x1 = float(len(ref_df) - 1)
            xs = [x0, x1]
        elif runtime_align_x and ref_runtime_hours.size > 0:
            xs = [float(ref_runtime_hours[0]), float(ref_runtime_hours[-1])]
        elif ref_df is not None and not ref_df.empty:
            xs = [ref_df["timestamp"].iloc[0], ref_df["timestamp"].iloc[-1]]
        else:
            xs = [0, 1]
        fig.add_trace(
            go.Scatter(
                x=xs,
                y=[lv, lv],
                mode="lines",
                name=f"{label} ({lv:g})",
                line=dict(color=col, width=2, dash="dash"),
                hovertemplate=f"{label}={lv:g} {var_unit}<extra></extra>",
            )
        )

    if u_lim is not None:
        try:
            _add_band_hline(float(u_lim), "Upper limit", BAND_UPPER_LINE_COLOR)
        except (TypeError, ValueError):
            pass
    if l_lim is not None:
        try:
            _add_band_hline(float(l_lim), "Lower limit", BAND_LOWER_LINE_COLOR)
        except (TypeError, ValueError):
            pass

    if align_by_sample_index:
        n = len(ref_df)
        nt = min(10, max(2, n))
        tick_vals = sorted({int(round(v)) for v in np.linspace(0, max(0, n - 1), nt)})
        tick_text: List[str] = []
        for i in tick_vals:
            tsi = ref_df.iloc[i]["timestamp"] if i < len(ref_df) else None
            tick_text.append("—" if tsi is None or pd.isna(tsi) else tsi.strftime("%d %b %Y\n%H:%M"))
        xaxis_cfg = dict(
            type="linear",
            title="Time (evenly spaced samples)",
            tickmode="array",
            tickvals=tick_vals,
            ticktext=tick_text,
            showgrid=False,
            tickfont=tick_font,
        )
    elif runtime_align_x:
        if ref_runtime_hours.size > 0:
            max_h = float(ref_runtime_hours[-1])
            tick_hours = np.linspace(0.0, max_h, min(10, max(2, len(ref_runtime_hours))))
            tick_vals = sorted({round(float(v), 6) for v in tick_hours})
            tick_text = [format_hhmm_from_seconds(v * 3600.0) for v in tick_vals]
        else:
            tick_vals = [0.0]
            tick_text = ["00:00"]
        xaxis_cfg = dict(
            type="linear",
            title="Running hours (HH:MM)",
            tickmode="array",
            tickvals=tick_vals,
            ticktext=tick_text,
            showgrid=False,
            tickfont=tick_font,
        )
    else:
        xaxis_cfg = dict(
            type="date",
            tickformat="%d %b %Y\n%H:%M",
            showgrid=False,
            tickfont=tick_font,
        )

    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=10, b=10),
        showlegend=False,
        xaxis=xaxis_cfg,
        yaxis=dict(
            title=f"{var_label} ({var_unit})",
            range=[y_lo, y_hi],
            showgrid=True,
            gridcolor="#E8EAF0",
            tickfont=tick_font,
            tickformat=".0f",
        ),
    )
    return fig


def _bin_edges_for_variable(values: np.ndarray, var_key: str) -> np.ndarray:
    v = values[np.isfinite(values)]
    if v.size == 0:
        return np.array([0.0, 1.0])
    lo, hi = float(np.min(v)), float(np.max(v))
    if lo == hi:
        lo -= 0.5
        hi += 0.5
    if var_key in ("temperature", "room_temperature"):
        width = 10.0
        start = np.floor(lo / width) * width
        end = np.ceil(hi / width) * width
        return np.arange(start, end + width, width)
    n_bins = min(16, max(8, int(np.sqrt(len(v))) or 8))
    return np.linspace(lo, hi, n_bins + 1)


def build_distribution_figure(
    test_frames: List[Tuple[str, pd.DataFrame, str]],
    *,
    value_col: str,
    var_unit: str,
    var_key: str,
) -> go.Figure:
    if not test_frames:
        return _blank_figure()

    all_vals: List[float] = []
    for _l, dff, _c in test_frames:
        if dff.empty:
            continue
        yv = pd.to_numeric(dff[value_col], errors="coerce").dropna()
        all_vals.extend(yv.tolist())
    if not all_vals:
        return _blank_figure()

    edges = _bin_edges_for_variable(np.array(all_vals), var_key)
    centers = (edges[:-1] + edges[1:]) / 2.0
    labels = [f"{c:.0f}" for c in centers]

    fig = go.Figure()
    for label, dff, color in test_frames:
        if dff.empty:
            continue
        yv = pd.to_numeric(dff[value_col], errors="coerce").dropna()
        if yv.empty:
            continue
        counts, _ = np.histogram(yv.to_numpy(), bins=edges)
        fig.add_trace(
            go.Bar(
                name=label,
                x=labels,
                y=counts,
                marker=dict(color=color, line=dict(color=color, width=1), opacity=0.85),
            )
        )

    tick_font = _tick_font()
    fig.update_layout(
        barmode="group",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=10, b=10),
        showlegend=False,
        xaxis=dict(title=f"Bin ({var_unit})", tickfont=tick_font, showgrid=False),
        yaxis=dict(title="Count", tickfont=tick_font, gridcolor="#E8EAF0"),
    )
    return fig


def build_step_average_figure(
    test_frames: List[Tuple[str, pd.DataFrame, str]],
    *,
    value_col: str,
    var_unit: str,
) -> go.Figure:
    if not test_frames:
        return _blank_figure()

    steps_present: List[int] = []
    for _l, dff, _c in test_frames:
        if dff.empty or dff["step"].dropna().empty:
            continue
        steps_present.extend(int(x) for x in dff["step"].dropna().unique())
    if not steps_present:
        return _blank_figure()

    smin, smax = min(steps_present), max(steps_present)
    step_labels = [f"S{s}" for s in range(smin, smax + 1)]
    x_idx = list(range(smin, smax + 1))

    fig = go.Figure()
    for label, dff, color in test_frames:
        if dff.empty:
            continue
        vals_num = pd.to_numeric(dff[value_col], errors="coerce")
        step_means = vals_num.groupby(dff["step"]).mean()
        means: List[Optional[float]] = [
            float(step_means[s]) if s in step_means.index and pd.notna(step_means[s]) else None
            for s in x_idx
        ]
        fig.add_trace(
            go.Bar(
                name=label,
                x=step_labels,
                y=means,
                marker=dict(color=color, line=dict(color=color, width=1), opacity=0.85),
            )
        )

    tick_font = _tick_font()
    fig.update_layout(
        barmode="group",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=10, b=10),
        showlegend=False,
        xaxis=dict(tickfont=tick_font, showgrid=False),
        yaxis=dict(title=f"Avg ({var_unit})", tickfont=tick_font, gridcolor="#E8EAF0"),
    )
    return fig


def _value_in_band(v: float, upper: Optional[float], lower: Optional[float]) -> bool:
    if upper is not None and v > upper:
        return False
    if lower is not None and v < lower:
        return False
    return True


def summary_status_for_band(
    max_val: float,
    min_val: float,
    upper: Optional[float],
    lower: Optional[float],
) -> Tuple[str, str]:
    """Test Summary STATUS: warn if any sample could leave band (min/max vs limits)."""
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
    """
    One row per transition from inside the band to outside (first offending sample only).
    If both limits unset, returns []. NaN samples do not advance state.
    """
    if upper is None and lower is None:
        return []
    rows: List[dict] = []
    for label, dff, color in test_frames:
        if dff.empty or value_col not in dff.columns:
            continue
        d_sorted = dff.sort_values("timestamp").reset_index(drop=True)
        vals = pd.to_numeric(d_sorted[value_col], errors="coerce")

        # Behavior parity with prior implementation:
        # - NaN samples do not advance state.
        # - Non-finite values (e.g., inf) advance state but are never emitted.
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


def build_analysis_layout() -> html.Div:
    """Full Data Analysis page (inside tab container)."""
    return html.Div(
        className="analysis-page-inner",
        children=[
            html.Div(
                className="card controls-bar analysis-controls",
                style={"marginBottom": "20px"},
                children=[
                    html.Div(
                        className="controls-group",
                        children=[
                            html.Span(className="ctrl-label", children=["STEP FILTER"]),
                            html.Div(
                                className="step-pills",
                                id="analysis-step-pills",
                                children=[
                                    html.Button(
                                        className="step-pill all-pill active",
                                        id={"type": "analysis-step-pill", "step": "all"},
                                        n_clicks=0,
                                        children=["All"],
                                    ),
                                    *[
                                        html.Button(
                                            className="step-pill",
                                            id={"type": "analysis-step-pill", "step": s},
                                            n_clicks=0,
                                            children=[str(s)],
                                        )
                                        for s in range(1, 10)
                                    ],
                                ],
                            ),
                        ],
                    ),
                    html.Div(className="divider"),
                    html.Div(
                        className="controls-group",
                        children=[
                            html.Span(className="ctrl-label", children=["NORMALISE X"]),
                            html.Div(
                                className="toggle-wrap",
                                id="analysis-norm-wrap",
                                children=[
                                    html.Div(id="analysis-norm-toggle", className="toggle", n_clicks=0),
                                    html.Span(className="toggle-label", style={"fontSize": "12px"}, children=["Align step start"]),
                                ],
                            ),
                        ],
                    ),
                    html.Div(className="divider"),
                    html.Div(
                        className="toggle-wrap",
                        id="analysis-ignore-wrap",
                        children=[
                            html.Div(id="analysis-ignore-toggle", className="toggle", n_clicks=0),
                            html.Span(className="toggle-label", children=["Ignore when machine stopped"]),
                        ],
                    ),
                    html.Div(
                        className="variable-filter",
                        style={"marginLeft": "auto"},
                        children=[
                            html.Span(className="ctrl-label", children=["VARIABLE"]),
                            dcc.Dropdown(
                                id="analysis-variable-dropdown",
                                options=[
                                    {"label": "Temperature", "value": "temperature"},
                                    {"label": "Load", "value": "load"},
                                    {"label": "Inflation Pressure", "value": "inflation_pressure"},
                                    {"label": "Room Temperature", "value": "room_temperature"},
                                    {"label": "Speed", "value": "speed"},
                                    {"label": "Torque", "value": "torque"},
                                ],
                                value="temperature",
                                clearable=False,
                                style={"width": "220px"},
                            ),
                        ],
                    ),
                ],
            ),
            html.Div(
                className="analysis-layout",
                children=[
                    html.Div(
                        className="sidebar",
                        children=[
                            html.Div(
                                className="card sidebar-card",
                                children=[
                                    html.Div(
                                        className="sidebar-title",
                                        children=["Compare Tests"],
                                    ),
                                    html.Div(id="analysis-selected-tests"),
                                    html.Div(
                                        className="add-test-row",
                                        children=[
                                            dcc.Input(
                                                id="analysis-test-input",
                                                type="text",
                                                placeholder="Test #",
                                                className="test-input",
                                                debounce=False,
                                            ),
                                            html.Button("Add", id="analysis-add-test-btn", className="btn btn-primary", n_clicks=0),
                                        ],
                                    ),
                                ],
                            ),
                            html.Div(
                                className="card sidebar-card filter-card",
                                children=[
                                    html.Div(
                                        className="sidebar-title",
                                        style={"marginBottom": "10px"},
                                        children=[
                                            "Data Filters",
                                            html.Span(
                                                id="analysis-filter-badge",
                                                style={
                                                    "display": "none",
                                                    "marginLeft": "auto",
                                                    "background": "var(--gold)",
                                                    "color": "#fff",
                                                    "borderRadius": "20px",
                                                    "padding": "1px 7px",
                                                    "fontSize": "10px",
                                                    "fontWeight": 600,
                                                    "fontFamily": "DM Mono, monospace",
                                                },
                                            ),
                                        ],
                                    ),
                                    html.Div(
                                        id="analysis-filter-multi-notice",
                                        className="filter-notice",
                                        style={"display": "none"},
                                        children=["Available when analysing a single test."],
                                    ),
                                    html.Div(
                                        id="analysis-filter-body",
                                        children=[
                                            html.Div(
                                                className="filter-section",
                                                children=[
                                                    html.Div("Variable filters", className="filter-section-label"),
                                                    html.Div(id="analysis-variable-filters-ui"),
                                                    html.Button(
                                                        "+ Add variable filter",
                                                        id="analysis-add-var-filter-btn",
                                                        className="btn btn-ghost btn-sm",
                                                        style={"width": "100%", "marginTop": "6px", "justifyContent": "center"},
                                                        n_clicks=0,
                                                        type="button",
                                                    ),
                                                ],
                                            ),
                                            html.Div(
                                                className="filter-section",
                                                children=[
                                                    html.Div("Time filter", className="filter-section-label"),
                                                    html.Div(
                                                        className="filter-mode-pills",
                                                        children=[
                                                            html.Button("All", id="analysis-filter-time-all", className="filter-mode-pill active", n_clicks=0),
                                                            html.Button("After", id="analysis-filter-time-after", className="filter-mode-pill", n_clicks=0),
                                                            html.Button("Before", id="analysis-filter-time-before", className="filter-mode-pill", n_clicks=0),
                                                            html.Button("Between", id="analysis-filter-time-between", className="filter-mode-pill", n_clicks=0),
                                                        ],
                                                    ),
                                                    html.Div(
                                                        id="analysis-filter-time-inputs",
                                                        style={"display": "none"},
                                                        children=[
                                                            html.Div(
                                                                className="filter-input-row",
                                                                children=[
                                                                    html.Label(id="analysis-filter-time-label-a", children=["After"]),
                                                                    dcc.DatePickerSingle(
                                                                        id="analysis-filter-time-date-a",
                                                                        className="filter-datetime",
                                                                        display_format="YYYY-MM-DD",
                                                                        placeholder="YYYY-MM-DD",
                                                                    ),
                                                                    dcc.Input(
                                                                        id="analysis-filter-time-time-a",
                                                                        type="text",
                                                                        value="00:00",
                                                                        className="filter-time",
                                                                        debounce=False,
                                                                        placeholder="00:00",
                                                                        maxLength=5,
                                                                    ),
                                                                ],
                                                            ),
                                                            html.Div(
                                                                id="analysis-filter-time-row-b",
                                                                className="filter-input-row",
                                                                style={"display": "none"},
                                                                children=[
                                                                    html.Label("To"),
                                                                    dcc.DatePickerSingle(
                                                                        id="analysis-filter-time-date-b",
                                                                        className="filter-datetime",
                                                                        display_format="YYYY-MM-DD",
                                                                        placeholder="YYYY-MM-DD",
                                                                    ),
                                                                    dcc.Input(
                                                                        id="analysis-filter-time-time-b",
                                                                        type="text",
                                                                        value="23:59",
                                                                        className="filter-time",
                                                                        debounce=False,
                                                                        placeholder="23:59",
                                                                        maxLength=5,
                                                                    ),
                                                                ],
                                                            ),
                                                        ],
                                                    ),
                                                ],
                                            ),
                                            html.Button(
                                                "Reset all filters",
                                                id="analysis-filter-reset-btn",
                                                className="filter-reset",
                                                n_clicks=0,
                                                type="button",
                                            ),
                                        ],
                                    ),
                                ],
                            ),
                            html.Div(
                                className="card sidebar-card",
                                children=[
                                    html.Div(className="sidebar-title", children=["Limits"]),
                                    html.Div(
                                        className="analysis-band-limits",
                                        children=[
                                            html.Div(
                                                className="band-limit-field",
                                                children=[
                                                    html.Label("Upper limit", className="band-limit-label"),
                                                    dcc.Input(
                                                        id="analysis-upper-limit",
                                                        type="number",
                                                        className="test-input band-limit-input",
                                                        debounce=True,
                                                        placeholder="Vacant",
                                                    ),
                                                ],
                                            ),
                                            html.Div(
                                                className="band-limit-field",
                                                children=[
                                                    html.Label("Lower limit", className="band-limit-label"),
                                                    dcc.Input(
                                                        id="analysis-lower-limit",
                                                        type="number",
                                                        className="test-input band-limit-input",
                                                        debounce=True,
                                                        placeholder="Vacant",
                                                    ),
                                                ],
                                            ),
                                            html.P(
                                                className="band-limit-hint",
                                                children=[
                                                    "Violations show only the first point where the signal "
                                                    "leaves the band (above upper or below lower)."
                                                ],
                                            ),
                                        ],
                                    ),
                                ],
                            ),
                            html.Div(
                                className="card sidebar-card",
                                children=[
                                    html.Div(className="sidebar-title", children=["Test Summary"]),
                                    html.Div(id="analysis-summary-table", style={"overflowX": "auto"}),
                                ],
                            ),
                        ],
                    ),
                    html.Div(
                        className="analysis-main-column",
                        children=[
                            html.Div(
                                className="card analysis-main-card",
                                style={"marginBottom": "16px"},
                                children=[
                                    html.Div(
                                        className="analysis-chart-header",
                                        children=[
                                            html.Div(
                                                children=[
                                                    html.Div(id="analysis-chart-title", className="analysis-chart-title"),
                                                    html.Div(id="analysis-chart-sub", className="analysis-chart-sub"),
                                                ]
                                            ),
                                            html.Div(
                                                style={"display": "flex", "gap": "8px"},
                                                children=[
                                                    html.Button(
                                                        id="analysis-export-csv-btn",
                                                        className="btn btn-ghost",
                                                        n_clicks=0,
                                                        children=["Export CSV"],
                                                    ),
                                                ],
                                            ),
                                        ],
                                    ),
                                    html.Div(
                                        className="analysis-chart-wrap",
                                        children=[
                                            dcc.Graph(
                                                id="analysis-main-graph",
                                                figure=_blank_figure(),
                                                config={"displayModeBar": False},
                                                style={"height": "340px"},
                                            )
                                        ],
                                    ),
                                    html.Div(id="analysis-legend", className="analysis-legend"),
                                ],
                            ),
                            html.Div(
                                className="dist-grid",
                                children=[
                                    html.Div(
                                        className="card dist-card",
                                        children=[
                                            html.Div(className="section-label", style={"marginBottom": "0"}, children=["Distribution"]),
                                            html.Div(
                                                className="dist-chart-wrap",
                                                children=[
                                                    dcc.Graph(
                                                        id="analysis-dist-graph",
                                                        figure=_blank_figure(),
                                                        config={"displayModeBar": False},
                                                        style={"height": "200px"},
                                                    )
                                                ],
                                            ),
                                        ],
                                    ),
                                    html.Div(
                                        className="card dist-card",
                                        children=[
                                            html.Div(
                                                className="section-label",
                                                style={"marginBottom": "0"},
                                                children=["Step-avg heatmap"],
                                            ),
                                            html.Div(
                                                className="dist-chart-wrap",
                                                children=[
                                                    dcc.Graph(
                                                        id="analysis-step-graph",
                                                        figure=_blank_figure(),
                                                        config={"displayModeBar": False},
                                                        style={"height": "200px"},
                                                    )
                                                ],
                                            ),
                                        ],
                                    ),
                                ],
                            ),
                            html.Div(
                                className="card violations-card",
                                children=[
                                    html.Div(
                                        className="violations-header",
                                        children=[
                                            html.Div(className="violations-title", children=["Limit Violations"]),
                                            html.Span(id="analysis-violation-badge", className="badge-ok", children=["OK"]),
                                        ],
                                    ),
                                    html.Div(id="analysis-violations-table"),
                                    html.Div(
                                        id="analysis-violations-view-more-wrap",
                                        style={"display": "none", "marginTop": "10px", "textAlign": "center"},
                                        children=[
                                            html.Button(
                                                id="analysis-violations-view-more-btn",
                                                className="btn btn-ghost btn-sm",
                                                n_clicks=0,
                                                type="button",
                                                children=["View more"],
                                            ),
                                        ],
                                    ),
                                ],
                            ),
                        ],
                    ),
                ],
            ),
            dcc.Store(id="analysis-active-steps-store", data=["all"]),
            dcc.Store(id="analysis-ignore-stopped-store", data=False),
            dcc.Store(id="analysis-normalize-store", data=False),
            dcc.Store(id="analysis-tests-store", data=[]),
            dcc.Store(id="analysis-data-store", data={}),
            dcc.Store(id="analysis-limits-store", data={"upper": None, "lower": None}),
            dcc.Store(id="analysis-limits-by-variable-store", data={}),
            dcc.Store(id="analysis-limits-prev-var", data="temperature"),
            dcc.Store(id="analysis-violations-expanded-store", data=False),
            dcc.Store(
                id="analysis-data-filters-store",
                data={
                    "variable_filters": [],
                    "time_mode": "all",
                    "time_date_a": None,
                    "time_date_b": None,
                    "time_time_a": "00:00",
                    "time_time_b": "23:59",
                },
            ),
            dcc.Download(id="analysis-csv-download"),
        ],
    )
