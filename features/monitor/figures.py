from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from services.chart_utils import (
    _downsample,
    _index_bounds_for_timestamp_window,
    _x_at_step_transition,
    build_step_ranges,
    build_step_transitions,
)
from config import OTHER_PLACEMENT_LINE_COLOR, POS_COLORS, STEP_BORDER_COLORS, STEP_COLORS
from services.runtime import build_running_elapsed_seconds_series, format_hhmm_from_seconds
from features.monitor.data import (
    _apply_chart_filters,
    _placement_key,
    _primary_placement_match_numpy,
    _segment_run_bounds,
)


def _rgba_from_hex(hex_color: str, alpha: float) -> str:
    h = hex_color.lstrip("#")
    r = int(h[0:2], 16)
    g = int(h[2:4], 16)
    b = int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def _blank_figure() -> go.Figure:
    fig = go.Figure()
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=0, b=0),
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
    )
    return fig


def _runtime_hhmm_for_df(df: pd.DataFrame) -> List[str]:
    if df.empty:
        return []
    elapsed = build_running_elapsed_seconds_series(df)
    return [format_hhmm_from_seconds(v) for v in elapsed.to_numpy(dtype=float)]


def build_summary_stats(df: pd.DataFrame, *, value_col: str) -> Dict[str, str]:
    keys = ["current", "max", "min", "avg", "std"]
    if df.empty:
        return {k: "–" for k in keys}
    df = df.sort_values("timestamp").copy()
    vals = pd.to_numeric(df[value_col], errors="coerce")
    vals_non_null = vals.dropna()
    if vals_non_null.empty:
        return {k: "–" for k in keys}
    current = vals_non_null.iloc[-1]
    std_val = vals_non_null.std()
    std_s = "–" if pd.isna(std_val) else f"{float(std_val):.2f}"
    return {
        "current": f"{current:.1f}",
        "max": f"{vals_non_null.max():.1f}",
        "min": f"{vals_non_null.min():.1f}",
        "avg": f"{vals_non_null.mean():.1f}",
        "std": std_s,
    }


def build_temperature_figure(
    df: pd.DataFrame,
    *,
    position: int,
    active_steps: List[object],
    ignore_stopped: bool,
    value_col: str,
    value_unit: str,
    value_label: str,
    primary_machine_id: Optional[str] = None,
    primary_position: Optional[int] = None,
    prefiltered_df: Optional[pd.DataFrame] = None,
    prefiltered_already_downsampled: bool = False,
) -> Optional[go.Figure]:
    if prefiltered_df is not None:
        df_plot = prefiltered_df
    else:
        if df.empty:
            return None
        df_plot = _apply_chart_filters(df, active_steps, ignore_stopped)

    if df_plot.empty:
        return None

    if not prefiltered_already_downsampled:
        df_plot = _downsample(df_plot.sort_values("timestamp").reset_index(drop=True))
    y = pd.to_numeric(df_plot[value_col], errors="coerce")

    if y.dropna().empty:
        return None

    primary = _placement_key(primary_machine_id, primary_position)
    if primary is None:
        multi_placement = False
    else:
        prim_match = _primary_placement_match_numpy(df_plot, primary)
        multi_placement = bool(np.any(~prim_match))

    primary_color = POS_COLORS[position]

    y_vals = y.dropna()
    y_min = float(y_vals.min())
    y_max = float(y_vals.max())
    span = y_max - y_min
    pad = max(1.0, span * 0.08) if span > 0 else 5.0
    y_lo = y_min - pad
    y_hi = y_max + pad

    runtime_hhmm = _runtime_hhmm_for_df(df_plot)
    ts_hover = df_plot["timestamp"].dt.strftime("%d %b %Y %H:%M:%S").fillna("—").tolist()

    line_shape = "hv"
    hover_tmpl = (
        "t=%{customdata[0]}<br>"
        "Run=%{customdata[1]}<br>"
        + f"{value_label}=%{{y:.2f}} {value_unit}<extra></extra>"
    )

    fig = go.Figure()

    # Invisible baseline so fill="tonexty" stays aligned with y_lo/y_hi on zoom reset.
    _baseline_line = dict(width=0, color="rgba(0,0,0,0)")

    def _add_segment_trace(lo: int, hi: int, is_primary_seg: bool) -> None:
        seg = df_plot.iloc[lo : hi + 1]
        y_seg = pd.to_numeric(seg[value_col], errors="coerce")
        col = primary_color if is_primary_seg else OTHER_PLACEMENT_LINE_COLOR
        if ignore_stopped:
            x_seg = np.arange(lo, hi + 1, dtype=float)
            custom_ts = ts_hover[lo : hi + 1]
            custom_run = runtime_hhmm[lo : hi + 1]
            extras: Dict = {"customdata": np.column_stack([custom_ts, custom_run])}
        else:
            x_seg = seg["timestamp"]
            custom_ts = ts_hover[lo : hi + 1]
            custom_run = runtime_hhmm[lo : hi + 1]
            extras = {"customdata": np.column_stack([custom_ts, custom_run])}
        fill_kw: Dict = {}
        if is_primary_seg:
            fig.add_trace(
                go.Scatter(
                    x=x_seg,
                    y=np.full(len(x_seg), y_lo, dtype=float),
                    mode="lines",
                    line={**_baseline_line, "shape": line_shape},
                    hoverinfo="skip",
                    showlegend=False,
                )
            )
            fill_kw = {"fill": "tonexty", "fillcolor": _rgba_from_hex(primary_color, alpha=0.10)}
        fig.add_trace(
            go.Scatter(
                x=x_seg,
                y=y_seg,
                mode="lines",
                line={"color": col, "width": 2, "shape": line_shape},
                hovertemplate=hover_tmpl,
                name="temp",
                showlegend=False,
                **fill_kw,
                **extras,
            )
        )

    if not multi_placement:
        if ignore_stopped:
            n = len(df_plot)
            x_plot = np.arange(n, dtype=float)
            extras: Dict = {"customdata": np.column_stack([ts_hover, runtime_hhmm])}
        else:
            x_plot = df_plot["timestamp"]
            extras = {"customdata": np.column_stack([ts_hover, runtime_hhmm])}
        fig.add_trace(
            go.Scatter(
                x=x_plot,
                y=np.full(len(df_plot), y_lo, dtype=float),
                mode="lines",
                line={**_baseline_line, "shape": line_shape},
                hoverinfo="skip",
                showlegend=False,
            )
        )
        fig.add_trace(
            go.Scatter(
                x=x_plot,
                y=y,
                mode="lines",
                line={"color": primary_color, "width": 2, "shape": line_shape},
                fill="tonexty",
                fillcolor=_rgba_from_hex(primary_color, alpha=0.10),
                hovertemplate=hover_tmpl,
                name="temp",
                showlegend=False,
                **extras,
            )
        )
    else:
        assert primary is not None
        is_prim = _primary_placement_match_numpy(df_plot, primary)
        segments = _segment_run_bounds(is_prim)
        for lo, hi, is_p in sorted(segments, key=lambda s: (not s[2], s[0])):
            _add_segment_trace(lo, hi, is_p)

    for step_val, t0, t1 in build_step_ranges(df_plot, pre_sorted=True):
        if step_val not in STEP_COLORS:
            continue
        if ignore_stopped:
            x0, x1 = _index_bounds_for_timestamp_window(df_plot, t0, t1)
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
            fillcolor=STEP_COLORS[step_val],
            layer="below",
            line=dict(width=0),
        )

    for from_step, to_step, boundary_ts in build_step_transitions(df_plot, pre_sorted=True):
        line_color = STEP_BORDER_COLORS.get(to_step) or STEP_BORDER_COLORS.get(from_step) or "rgba(122,126,138,0.40)"
        xv = _x_at_step_transition(df_plot, boundary_ts) if ignore_stopped else boundary_ts
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

    tick_font = {"family": "DM Mono, monospace", "size": 10, "color": "#9A9EA8"}
    if ignore_stopped:
        n = len(df_plot)
        nt = min(8, max(2, n))
        tick_vals = sorted({int(round(v)) for v in np.linspace(0, max(0, n - 1), nt)})
        tick_text: List[str] = []
        for i in tick_vals:
            tsi = df_plot.iloc[i]["timestamp"]
            tick_text.append("—" if pd.isna(tsi) else tsi.strftime("%d %b %Y\n%H:%M"))
        xaxis_cfg = dict(
            type="linear",
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
        xaxis=xaxis_cfg,
        yaxis=dict(
            range=[y_lo, y_hi],
            showgrid=True,
            gridcolor="#E8EAF0",
            tickfont=tick_font,
            tickformat=".0f",
        ),
    )

    return fig
