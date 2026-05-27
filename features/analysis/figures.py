from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from config import BAND_LOWER_LINE_COLOR, BAND_UPPER_LINE_COLOR, STEP_COLORS, STEP_BORDER_COLORS
from services.chart_utils import (
    TICK_FONT,
    _downsample,
    _index_bounds_for_timestamp_window,
    _x_at_step_transition,
    blank_figure,
    build_step_ranges,
    build_step_transitions,
)
from services.runtime import build_running_elapsed_seconds_series, format_hhmm_from_seconds


_blank_figure = blank_figure


def _insert_gap_breaks_for_plot(
    *,
    ts: pd.Series,
    x_vals: np.ndarray,
    y_vals: np.ndarray,
    custom_data: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
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


def _value_in_band(v: float, upper: Optional[float], lower: Optional[float]) -> bool:
    if upper is not None and v > upper:
        return False
    if lower is not None and v < lower:
        return False
    return True


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
    if not test_frames:
        return _blank_figure()

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
    tick_font = TICK_FONT

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

    hover_norm = (
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
                    hovertemplate=hover_norm,
                    customdata=custom_data,
                )
            )

    def _add_band_hline(lv: float, label: str, col: str) -> None:
        if align_by_sample_index and ref_df is not None and len(ref_df) > 0:
            xs = [0.0, float(len(ref_df) - 1)]
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
    tick_font = TICK_FONT
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
    tick_font = TICK_FONT
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
