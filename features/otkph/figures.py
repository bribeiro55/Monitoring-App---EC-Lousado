from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from services.chart_utils import TICK_FONT, blank_figure, build_step_ranges
from .services import CAM_DEFS, _thermo_col, _with_plot_axis


_blank_fig = blank_figure


def _compressed_axis_date_ticks(df: pd.DataFrame, max_ticks: int = 8) -> Tuple[List[float], List[str]]:
    if df.empty or "plot_x" not in df.columns:
        return [], []
    # Compressed ticks only apply when plot_x is numeric (interruption-compressed axis).
    if pd.api.types.is_datetime64_any_dtype(df["plot_x"]):
        return [], []
    n = len(df)
    nt = min(max_ticks, max(2, n))
    idxs = sorted({int(round(v)) for v in np.linspace(0, max(0, n - 1), nt)})
    tick_vals, tick_text = [], []
    for i in idxs:
        pv = df.iloc[i]["plot_x"]
        try:
            tick_vals.append(float(pv))
        except (TypeError, ValueError):
            continue
        ts = df.iloc[i]["timestamp"]
        tick_text.append("–" if pd.isna(ts) else ts.strftime("%d %b %Y\n%H:%M"))
    return tick_vals, tick_text


def _step_shapes_datetime(df: pd.DataFrame, step_colors: Dict[int, str]) -> List[dict]:
    if df.empty or "plot_x" not in df.columns:
        return []
    d = df.sort_values("timestamp")
    ts_ns = pd.to_datetime(d["timestamp"], errors="coerce").astype("int64").to_numpy()
    px = d["plot_x"].to_numpy()
    n = len(d)
    shapes: List[dict] = []
    for step_val, t0, t1 in build_step_ranges(d, pre_sorted=True):
        try:
            si = int(step_val)
        except (TypeError, ValueError):
            continue
        fill = step_colors.get(si, "rgba(128,128,128,0.07)")
        t0_ns = pd.Timestamp(t0).value
        t1_ns = pd.Timestamp(t1).value
        i0 = int(np.searchsorted(ts_ns, t0_ns, side="left"))
        i1 = int(np.searchsorted(ts_ns, t1_ns, side="right")) - 1
        if i0 >= n or i1 < i0 or i1 < 0:
            continue
        shapes.append(
            dict(
                type="rect",
                xref="x",
                yref="paper",
                x0=px[i0],
                x1=px[i1],
                y0=0,
                y1=1,
                fillcolor=fill,
                line=dict(width=0),
                layer="below",
            )
        )
    return shapes


def build_camera_time_figure(
    df: pd.DataFrame,
    active: List[int],
    limits: List[dict],
    smooth: bool,
    step_colors: Dict[int, str],
    ignore_interrupted: bool,
    dplot: Optional[pd.DataFrame] = None,
) -> go.Figure:
    if df.empty or not active:
        return _blank_fig()
    if dplot is None:
        dplot = _with_plot_axis(df, ignore_interrupted)
    tick_font = TICK_FONT
    fig = go.Figure()
    shapes = _step_shapes_datetime(dplot, step_colors)
    x = dplot["plot_x"]
    custom_ts = dplot["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S").fillna("–")
    for i in active:
        col = _thermo_col(i)
        if col not in dplot.columns:
            continue
        y = pd.to_numeric(dplot[col], errors="coerce")
        if smooth and len(y) > 0:
            y = y.rolling(window=5, min_periods=1).mean()
        cd = CAM_DEFS[i - 1]
        fig.add_trace(go.Scatter(x=x, y=y, mode="lines", name=cd["code"], line=dict(color=cd["color"], width=2), connectgaps=False, customdata=custom_ts, hovertemplate=f"{cd['code']}: %{{y:.2f}} °C<br>%{{customdata}}<extra></extra>"))
    for lim in limits:
        if not lim.get("active"):
            continue
        try:
            lv = float(lim["value"])
        except (TypeError, ValueError):
            continue
        fig.add_hline(y=lv, line=dict(color=lim.get("color") or "#E84040", width=1, dash="dash"), annotation_text=f"{lim.get('name', '')} {lv}°C", annotation_position="right")
    yvals: List[float] = []
    for i in active:
        col = _thermo_col(i)
        if col in dplot.columns:
            yvals.extend(pd.to_numeric(dplot[col], errors="coerce").dropna().tolist())
    for lim in limits:
        if lim.get("active"):
            try:
                yvals.append(float(lim["value"]))
            except (TypeError, ValueError):
                pass
    if not yvals:
        return _blank_fig()
    xaxis_cfg = dict(gridcolor="#E8EAF0", tickfont=tick_font, title=dict(text=""), type="date")
    if ignore_interrupted:
        tick_vals, tick_text = _compressed_axis_date_ticks(dplot)
        xaxis_cfg = dict(gridcolor="#E8EAF0", tickfont=tick_font, title=dict(text=""), type="linear", tickmode="array", tickvals=tick_vals, ticktext=tick_text)
    fig.update_layout(
        shapes=shapes,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=10, b=10),
        showlegend=False,
        xaxis=xaxis_cfg,
        yaxis=dict(gridcolor="#E8EAF0", tickfont=tick_font, title=dict(text="°C", font=tick_font), range=[max(0, min(yvals) - 10), max(yvals) + 10]),
        hovermode="x unified",
    )
    return fig


def build_delta_figure(df: pd.DataFrame, active: List[int], step_colors: Dict[int, str]) -> go.Figure:
    if df.empty or len(active) < 2:
        return _blank_fig()
    mats = []
    for i in active:
        col = _thermo_col(i)
        if col not in df.columns:
            return _blank_fig()
        mats.append(pd.to_numeric(df[col], errors="coerce").to_numpy())
    arr = np.vstack(mats).T
    if not (~np.isnan(arr).any(axis=1)).any():
        return _blank_fig()
    delta = np.nanmax(arr, axis=1) - np.nanmin(arr, axis=1)
    x = df["plot_x"]
    tick_font = TICK_FONT
    fig = go.Figure(data=[go.Scatter(x=x, y=delta, mode="lines", line=dict(color="#B36EE8", width=2), connectgaps=False, customdata=df["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S").fillna("–"), hovertemplate="ΔT: %{y:.2f} °C<br>%{customdata}<extra></extra>")])
    x_is_numeric = "plot_x" in df.columns and pd.api.types.is_numeric_dtype(df["plot_x"])
    xaxis_cfg = dict(gridcolor="#E8EAF0", tickfont=tick_font, type="linear" if x_is_numeric else "date")
    if x_is_numeric:
        tv, tt = _compressed_axis_date_ticks(df)
        xaxis_cfg = dict(gridcolor="#E8EAF0", tickfont=tick_font, type="linear", tickmode="array", tickvals=tv, ticktext=tt)
    fig.update_layout(shapes=_step_shapes_datetime(df, step_colors), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin=dict(l=10, r=10, t=10, b=10), showlegend=False, xaxis=xaxis_cfg, yaxis=dict(gridcolor="#E8EAF0", tickfont=tick_font, title=dict(text="ΔT (°C)", font=tick_font), range=[0, (float(np.nanmax(delta)) if np.isfinite(np.nanmax(delta)) else 1.0) * 1.1 + 1e-6]))
    return fig


def _compute_max_delta(dff: pd.DataFrame, active: List[int]) -> float:
    if len(active) < 2 or dff.empty:
        return 0.0
    mats = []
    for i in active:
        col = _thermo_col(i)
        if col in dff.columns:
            mats.append(pd.to_numeric(dff[col], errors="coerce").to_numpy())
    if len(mats) < 2:
        return 0.0
    a = np.vstack(mats).T
    valid = ~np.isnan(a).any(axis=1)
    if not valid.any():
        return 0.0
    return float(np.max(np.nanmax(a[valid], axis=1) - np.nanmin(a[valid], axis=1)))


def build_speed_figure(df: pd.DataFrame, step_colors: Dict[int, str]) -> go.Figure:
    if df.empty or "speed" not in df.columns:
        return _blank_fig()
    tick_font = TICK_FONT
    x = df["plot_x"] if "plot_x" in df.columns else df["timestamp"]
    spd = pd.to_numeric(df["speed"], errors="coerce")
    if spd.dropna().empty:
        return _blank_fig()
    fig = go.Figure(data=[go.Scatter(x=x, y=spd, mode="lines", line=dict(color="#4A90D9", width=2), connectgaps=False, customdata=df["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S").fillna("–"), hovertemplate="Speed: %{y:.0f}<br>%{customdata}<extra></extra>")])
    xaxis_cfg = dict(gridcolor="#E8EAF0", tickfont=tick_font, type="linear" if ("plot_x" in df.columns and pd.api.types.is_numeric_dtype(df["plot_x"])) else "date")
    if "plot_x" in df.columns and pd.api.types.is_numeric_dtype(df["plot_x"]):
        tv, tt = _compressed_axis_date_ticks(df)
        xaxis_cfg = dict(gridcolor="#E8EAF0", tickfont=tick_font, type="linear", tickmode="array", tickvals=tv, ticktext=tt)
    fig.update_layout(shapes=_step_shapes_datetime(df, step_colors), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin=dict(l=10, r=10, t=10, b=10), showlegend=False, xaxis=xaxis_cfg, yaxis=dict(gridcolor="#E8EAF0", tickfont=tick_font, title=dict(text="Speed", font=tick_font), range=[0, max(10.0, float(spd.max()) * 1.1)]))
    return fig


def build_scatter_figure(df: pd.DataFrame, cam_a: int, cam_b: int) -> go.Figure:
    if df.empty or cam_a == cam_b:
        return _blank_fig()
    ca, cb = _thermo_col(cam_a), _thermo_col(cam_b)
    if ca not in df.columns or cb not in df.columns:
        return _blank_fig()
    xa = pd.to_numeric(df[ca], errors="coerce")
    xb = pd.to_numeric(df[cb], errors="coerce")
    m = xa.notna() & xb.notna()
    if not m.any():
        return _blank_fig()
    xs, ys = xa[m].to_numpy(), xb[m].to_numpy()
    tick_font = TICK_FONT
    fig = go.Figure(data=[go.Scatter(x=xs, y=ys, mode="markers", marker=dict(size=6, color=CAM_DEFS[cam_a - 1]["color"], opacity=0.65), name="samples")])
    if len(xs) > 1:
        coef = np.polyfit(xs, ys, 1)
        xline = np.array([np.min(xs), np.max(xs)])
        fig.add_trace(go.Scatter(x=xline, y=coef[0] * xline + coef[1], mode="lines", line=dict(color="#9A9EA8", width=2, dash="dash"), name="trend"))
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin=dict(l=10, r=10, t=10, b=10), showlegend=False, xaxis=dict(gridcolor="#E8EAF0", tickfont=tick_font, title=dict(text=f"{CAM_DEFS[cam_a - 1]['code']} (°C)", font=tick_font)), yaxis=dict(gridcolor="#E8EAF0", tickfont=tick_font, title=dict(text=f"{CAM_DEFS[cam_b - 1]['code']} (°C)", font=tick_font)))
    return fig

