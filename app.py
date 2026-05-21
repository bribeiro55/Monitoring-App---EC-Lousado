import os
import re
import urllib.parse
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from dash import Dash, Input, Output, State, callback_context, dcc, html, ALL
from dash.exceptions import PreventUpdate
from flask_caching import Cache

from config import (
    APP_ROOT,
    DISPLAY_TO_MACHINE_ID,
    MACHINE_BADGE,
    MACHINE_ID_TO_LABEL,
    MACHINES,
    OTHER_PLACEMENT_LINE_COLOR,
    PROJECT_ROOT,
    POSITION_LABELS,
    POS_COLORS,
    STEP_BORDER_COLORS,
    STEP_COLORS,
    STORE_COLUMNS,
    VARIABLE_CONFIG,
)
from log_parser import parse_log_file, parse_log_header_metadata

from analysis_tab import (
    BAND_LOWER_LINE_COLOR,
    BAND_UPPER_LINE_COLOR,
    COMPARE_PALETTE,
    _downsample,
    _index_bounds_for_timestamp_window,
    _x_at_step_transition,
    build_analysis_layout,
    build_comparison_figure,
    build_distribution_figure,
    build_step_ranges,
    build_step_transitions,
    build_step_average_figure,
    collect_band_crossing_violations,
    summary_status_for_band,
)
from features.otkph import build_otkph_layout, register_otkph_callbacks
from services.runtime import build_running_elapsed_seconds_series, format_hhmm_from_seconds
from services.log_service import build_cached_parse_log, find_log_path_for_test_number

from features.monitor.auto_refresh import register_monitor_auto_refresh_callbacks
from features.monitor.auto_refresh.layout import make_auto_refresh_banner, make_auto_refresh_toggle
from features.monitor.callbacks import register_monitor_callbacks
from features.navigation.callbacks import register_navigation_callbacks
from features.analysis.callbacks import register_analysis_callbacks
from features.monitor.layout import make_empty_state, make_expand_button, make_modal_icon_button

def _svg_data_uri(svg: str) -> str:
    """dash.html has no Svg/Path; use Img + data URI instead."""
    return "data:image/svg+xml;charset=utf-8," + urllib.parse.quote(svg)


# Icons (same paths as original mockups)
_ICON_EMPTY_CHART = _svg_data_uri(
    '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" fill="none" '
    'stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" '
    'viewBox="0 0 24 24"><path d="M9 17v-2m3 2v-4m3 4v-6M3 21h18M3 3h18"/></svg>'
)
_ICON_EXPAND = _svg_data_uri(
    '<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" fill="none" '
    'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" '
    'viewBox="0 0 24 24"><path d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4"/></svg>'
)
_ICON_DOWNLOAD = _svg_data_uri(
    '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="none" '
    'stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" '
    'viewBox="0 0 24 24"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="M7 10l5 5 5-5"/><path d="M12 15V3"/></svg>'
)
_ICON_CSV = _svg_data_uri(
    '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="none" '
    'stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" '
    'viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/><path d="M8 13h8M8 17h8M8 9h3"/></svg>'
)
_ICON_TAB_MONITOR = _svg_data_uri(
    '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="none" '
    'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" '
    'viewBox="0 0 24 24"><path d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/></svg>'
)
_ICON_TAB_ANALYSIS = _svg_data_uri(
    '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="none" '
    'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" '
    'viewBox="0 0 24 24"><path d="M9 17v-2m3 2v-4m3 4v-6M3 21h18M3 3h18"/></svg>'
)
_ICON_TAB_OTKPH = _svg_data_uri(
    '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="none" '
    'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" '
    'viewBox="0 0 24 24"><path d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/>'
    '<path d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"/></svg>'
)


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
    """ISO strings for dcc.Store rows; works for datetime, strings, empty frames (pandas 2/3)."""
    return pd.to_datetime(s, errors="coerce").dt.strftime("%Y-%m-%dT%H:%M:%S")


def _serialize_df_rows(df: pd.DataFrame) -> List[dict]:
    cols = [c for c in STORE_COLUMNS if c in df.columns]
    df_store = df[cols].copy() if cols else df.copy()
    if "timestamp" in df_store.columns:
        df_store["timestamp"] = _timestamp_col_to_store_strings(df_store["timestamp"])
    df_store = df_store.where(pd.notnull(df_store), None)
    return df_store.to_dict("records")


def _filter_by_steps(df: pd.DataFrame, active_steps: List[object]) -> pd.DataFrame:
    """
    When 'All' steps is active, include rows with missing step so cpc_temp_c still plots.
    When specific steps are selected, only those step values (NaN steps excluded).
    """
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
    """Row-wise match to primary placement; same truth as _row_is_primary_placement (vectorized loop, no iloc)."""
    mid = df["machine_id"].to_numpy()
    pos = df["position"].to_numpy()
    n = len(df)
    out = np.zeros(n, dtype=bool)
    for i in range(n):
        out[i] = _placement_key(mid[i], pos[i]) == primary
    return out


def _segment_run_bounds(is_prim: np.ndarray) -> List[Tuple[int, int, bool]]:
    """Contiguous runs of True/False; same segments as the legacy while-loop over df_plot."""
    n = len(is_prim)
    if n == 0:
        return []
    starts = np.concatenate([[0], np.flatnonzero(is_prim[1:] != is_prim[:-1]) + 1])
    ends = np.concatenate([starts[1:] - 1, [n - 1]])
    return [(int(lo), int(hi), bool(is_prim[lo])) for lo, hi in zip(starts, ends)]


def _placement_history_note_children(
    df: pd.DataFrame, primary_mid: str, primary_pos: int
) -> List[html.Div]:
    """One line per earlier (machine, position) interval (chronological, visible df)."""
    primary = _placement_key(primary_mid, primary_pos)
    if primary is None or df.empty:
        return []

    d = df.sort_values("timestamp").reset_index(drop=True)
    mid_s = d["machine_id"].astype(str)
    pos_s = d["position"].astype(str)
    key_s = mid_s + "|" + pos_s
    d["_grp"] = (key_s != key_s.shift()).cumsum()
    lines: List[str] = []
    for _, grp in d.groupby("_grp", sort=False):
        row0 = grp.iloc[0]
        k = _placement_key(row0["machine_id"], row0["position"])
        if k is None or k == primary:
            continue
        t0 = grp["timestamp"].iloc[0]
        t1 = grp["timestamp"].iloc[-1]
        lbl = MACHINE_ID_TO_LABEL.get(k[0], k[0])
        t0s = t0.strftime("%d %b %Y %H:%M") if pd.notna(t0) else "?"
        t1s = t1.strftime("%d %b %Y %H:%M") if pd.notna(t1) else "?"
        lines.append(f"It was in {lbl} · Position {k[1]} from {t0s} to {t1s}.")
    return [html.Div(line, className="modal-placement-line") for line in lines]


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
    """
    Create the Plotly line chart with:
    - step-phase background bands
    - line + filled area under the line (fill only for the current placement segment)
    - Rows matching primary_machine_id/primary_position use the slot line color; other placements use OTHER_PLACEMENT_LINE_COLOR.
    - Line shape is 'hv' (sample-and-hold): no spline smoothing; long calendar gaps show as
      flat plateaus then a vertical jump, not a diagonal.
    - When ignore_stopped is True, x is sample index (stopped calendar gaps removed);
      hover and tick labels still show real timestamps.
    """
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

    # If all visible temps are NaN, treat as empty chart.
    if y.dropna().empty:
        return None

    primary = _placement_key(primary_machine_id, primary_position)
    if primary is None:
        multi_placement = False
    else:
        prim_match = _primary_placement_match_numpy(df_plot, primary)
        multi_placement = bool(np.any(~prim_match))

    primary_color = POS_COLORS[position]

    # Y span for step bands (use data axis; avoids Plotly add_vrect + yref="paper" bug → 'paper domain').
    y_vals = y.dropna()
    y_min = float(y_vals.min())
    y_max = float(y_vals.max())
    span = y_max - y_min
    pad = max(1.0, span * 0.08) if span > 0 else 5.0
    y_lo = y_min - pad
    y_hi = y_max + pad

    runtime_hhmm = _runtime_hhmm_for_df(df_plot)
    ts_hover = df_plot["timestamp"].dt.strftime("%d %b %Y %H:%M:%S").fillna("—").tolist()

    if ignore_stopped:
        # Sample index axis: step between consecutive running samples (no spline / no diagonals).
        line_shape = "hv"
        hover_tmpl = (
            "t=%{customdata[0]}<br>"
            "Run=%{customdata[1]}<br>"
            + f"{value_label}=%{{y:.2f}} {value_unit}<extra></extra>"
        )
    else:
        # Calendar time: hold value until next sample, then vertical jump — avoids spline overshoot
        # and diagonal segments across long gaps when the machine was stopped.
        line_shape = "hv"
        hover_tmpl = (
            "t=%{customdata[0]}<br>"
            "Run=%{customdata[1]}<br>"
            + f"{value_label}=%{{y:.2f}} {value_unit}<extra></extra>"
        )

    fig = go.Figure()

    # Invisible baseline for area fill. Using fill="tozeroy" makes Plotly's autorange (e.g. after
    # double-click zoom reset) include y=0; tonexty from this line keeps reset aligned with y_lo/y_hi.
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

    # Step-phase background bands (layout shapes, y-axis coords — compatible with Plotly 5/6).
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

    # Soft dashed separators at step transitions to make phase changes clearer.
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


def _rgba_from_hex(hex_color: str, alpha: float) -> str:
    # Expect: #RRGGBB
    h = hex_color.lstrip("#")
    r = int(h[0:2], 16)
    g = int(h[2:4], 16)
    b = int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def _runtime_hhmm_for_df(df: pd.DataFrame) -> List[str]:
    if df.empty:
        return []
    elapsed = build_running_elapsed_seconds_series(df)
    return [format_hhmm_from_seconds(v) for v in elapsed.to_numpy(dtype=float)]


def build_summary_stats(df: pd.DataFrame, *, value_col: str) -> Dict[str, str]:
    """
    Stats are computed from visible points (NaNs ignored): current, max, min, avg, std.
    """
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


def make_chart_panel(
    *,
    machine_label: str,
    position: int,
    test_number: str,
    slot_key: str,
    loaded_entry: Optional[dict],
    active_steps: List[object],
    ignore_stopped: bool,
    selected_var: str,
) -> html.Div:
    if not test_number:
        return html.Div(
            className="chart-panel",
            children=[make_empty_state("No test assigned", _ICON_EMPTY_CHART)],
        )

    if not loaded_entry:
        return html.Div(
            className="chart-panel",
            children=[
                html.Div(
                    className="empty-chart",
                    children=[
                        html.Span("Click Refresh to load"),
                    ],
                )
            ],
        )

    status = loaded_entry.get("status")
    if status != "ok":
        msg = loaded_entry.get("message") or status or "error"
        return html.Div(
            className="chart-panel",
            children=[
                html.Div(
                    className="empty-chart",
                    children=[
                        html.Div(className="error-text", children=[msg]),
                    ],
                )
            ],
        )

    if "slot_eligible" in loaded_entry and not loaded_entry.get("slot_eligible"):
        lm = loaded_entry.get("latest_machine_id")
        lp = loaded_entry.get("latest_position")
        if lm is not None and lp is not None:
            try:
                lp_i = int(lp)
                lbl = MACHINE_ID_TO_LABEL.get(str(lm), str(lm))
                hint = (
                    f"Latest data is on {lbl} · Position {lp_i} — "
                    "enter this test in that machine/position slot, then Refresh."
                )
            except (ValueError, TypeError):
                hint = "Latest data is not from this machine/position — move the test to the matching slot."
        else:
            hint = "Could not verify this test for this slot — check the log."
        return html.Div(className="chart-panel", children=[make_empty_state(hint, _ICON_EMPTY_CHART)])

    df = _rows_to_df(loaded_entry.get("rows", []))
    if df.empty:
        return html.Div(
            className="chart-panel",
            children=[make_empty_state("No data rows in this test log", _ICON_EMPTY_CHART)],
        )

    df_ig = _df_after_ignore_stopped(df, ignore_stopped)
    if not df.empty and df_ig.empty:
        return html.Div(
            className="chart-panel",
            children=[make_empty_state("No data after Ignore when machine stopped", _ICON_EMPTY_CHART)],
        )

    df_step = _filter_by_steps(df_ig, active_steps)
    if not df_ig.empty and df_step.empty:
        return html.Div(
            className="chart-panel",
            children=[
                make_empty_state(
                    "No rows for selected step(s) in this test log — try STEP = All or another step.",
                    _ICON_EMPTY_CHART,
                )
            ],
        )

    df_visible = df_step.sort_values("timestamp").reset_index(drop=True)
    var_cfg = VARIABLE_CONFIG[selected_var]
    pm = loaded_entry.get("latest_machine_id")
    pp = loaded_entry.get("latest_position")
    if pm is None or pp is None:
        if not df.empty:
            last = df.sort_values("timestamp").iloc[-1]
            pm = last.get("machine_id")
            pp = last.get("position")
    try:
        pp_i = int(pp) if pp is not None and not pd.isna(pp) else None
    except (ValueError, TypeError):
        pp_i = None

    df_plot_ds = _downsample(df_visible)
    fig = build_temperature_figure(
        df,
        position=position,
        active_steps=active_steps,
        ignore_stopped=ignore_stopped,
        value_col=var_cfg["col"],
        value_unit=var_cfg["unit"],
        value_label=var_cfg["label"],
        primary_machine_id=str(pm) if pm is not None and not pd.isna(pm) else None,
        primary_position=pp_i,
        prefiltered_df=df_plot_ds,
        prefiltered_already_downsampled=True,
    )

    if fig is None:
        return html.Div(
            className="chart-panel",
            children=[make_empty_state(f"No valid data points for {var_cfg['label']}", _ICON_EMPTY_CHART)],
        )

    inline_stats = build_summary_stats(df_visible, value_col=var_cfg["col"])
    run_labels = _runtime_hhmm_for_df(df_plot_ds)
    run_time_last = run_labels[-1] if run_labels else "00:00"
    tire_size = str(loaded_entry.get("tire_size") or "-").strip() or "-"

    pos_dot_style = {"background": POS_COLORS[position]}

    return html.Div(
        className="chart-panel",
        children=[
            html.Div(
                className="chart-panel-header",
                children=[
                    html.Div(
                        className="chart-panel-title",
                        children=[
                            html.Div(className="pos-dot", style=pos_dot_style),
                            html.Span(POSITION_LABELS[position]),
                        ],
                    ),
                    html.Div(
                        style={"display": "flex", "alignItems": "center", "marginLeft": "20px"},
                        children=[
                            html.Span(
                                className="inline-stat",
                                children=[
                                    html.Span("TIRE SIZE ", className="inline-stat-label"),
                                    html.Span(
                                        tire_size,
                                        className="inline-stat-val",
                                    ),
                                ],
                            ),
                        ],
                    ),
                    html.Div(
                        className="chart-inline-stats",
                        children=[
                            html.Span(
                                className="inline-stat",
                                children=[
                                    html.Span("LATEST ", className="inline-stat-label"),
                                    html.Span(
                                        f"{inline_stats['current']} {var_cfg['unit']}",
                                        className="inline-stat-val",
                                    ),
                                ],
                            ),
                            html.Span(
                                className="inline-stat",
                                children=[
                                    html.Span("RUN TIME ", className="inline-stat-label"),
                                    html.Span(
                                        run_time_last,
                                        className="inline-stat-val",
                                    ),
                                ],
                            ),
                        ],
                    ),
                    html.Div(
                        style={"display": "flex", "alignItems": "center", "gap": "8px"},
                        children=[
                            html.Span(className="test-tag", children=[test_number]),
                            make_expand_button(slot_key, _ICON_EXPAND),
                        ],
                    ),
                ],
            ),
            html.Div(
                className="chart-wrap",
                children=[
                    dcc.Graph(
                        figure=fig,
                        config={"displayModeBar": False},
                        style={"height": "200px"},
                    )
                ],
            ),
        ],
    )


app = Dash(__name__, assets_folder="assets", suppress_callback_exceptions=True)
server = app.server
cache = Cache(
    server,
    config={
        "CACHE_TYPE": "FileSystemCache",
        "CACHE_DIR": os.path.join(APP_ROOT, ".cache"),
        "CACHE_DEFAULT_TIMEOUT": 600,
    },
)
os.makedirs(os.path.join(APP_ROOT, ".cache"), exist_ok=True)

cached_parse_log = build_cached_parse_log(cache, parse_log_file)


def _machine_input_slug(machine_label: str) -> str:
    return machine_label.replace(" ", "-").lower()


def _input_id(machine_label: str, position: int) -> str:
    return f"test-input-{_machine_input_slug(machine_label)}-pos{position}"


_img_tab_style = {"width": "14px", "height": "14px", "display": "block", "opacity": "0.85"}

app.layout = html.Div(
    children=[
        html.Div(
            className="topbar",
            children=[
                html.Div(
                    className="topbar-left",
                    children=[
                        html.Div(
                            className="brand",
                            children=[html.Div(className="brand-dot"), "TireTherm"],
                        ),
                        html.Div(
                            className="nav-tabs",
                            children=[
                                html.Button(
                                    id="tab-monitor-btn",
                                    className="nav-tab active",
                                    n_clicks=0,
                                    type="button",
                                    children=[
                                        html.Img(src=_ICON_TAB_MONITOR, alt="", style=_img_tab_style),
                                        "Live Monitor",
                                    ],
                                ),
                                html.Button(
                                    id="tab-analysis-btn",
                                    className="nav-tab",
                                    n_clicks=0,
                                    type="button",
                                    children=[
                                        html.Img(src=_ICON_TAB_ANALYSIS, alt="", style=_img_tab_style),
                                        "Data Analysis",
                                    ],
                                ),
                                html.Button(
                                    id="tab-otkph-btn",
                                    className="nav-tab",
                                    n_clicks=0,
                                    type="button",
                                    children=[
                                        html.Img(src=_ICON_TAB_OTKPH, alt="", style=_img_tab_style),
                                        "O-TKPH Analysis",
                                    ],
                                ),
                            ],
                        ),
                    ],
                ),
                html.Div(
                    className="topbar-right",
                    children=[
                        html.Div(className="live-pill", children=[html.Div(className="live-dot"), html.Span("LIVE")]),
                        html.Div(
                            id="clock",
                            style={"fontFamily": "'DM Mono', monospace", "fontSize": "11px", "color": "var(--muted)"},
                        ),
                    ],
                ),
            ],
        ),
        dcc.Store(id="main-tab-store", data="monitor"),
        dcc.Store(id="auto-refresh-enabled-store", data=True),
        dcc.Store(id="auto-refresh-cycle-store", data={}),
        dcc.Store(id="auto-refresh-trigger-store", data=0),
        dcc.Interval(id="clock-interval", interval=1000, n_intervals=0),
        html.Div(
            id="monitor-page",
            className="tab-page",
            children=[
                html.Div(
                    className="main",
                    children=[
                html.Div(className="section-label", children=["Current Tests Running"]),
                html.Div(
                    className="tests-panel",
                    children=[
                        html.Div(
                            className="tests-grid",
                            children=[
                                html.Div(
                                    className="machine-block",
                                    children=[
                                        html.Div(
                                            className="machine-label",
                                            children=[html.Div(className="machine-indicator"), MACHINES[i]],
                                        ),
                                        html.Div(
                                            className="positions-row",
                                            children=[
                                                html.Div(
                                                    className="position-field",
                                                    children=[
                                                        html.Div(className="position-label", children=["Position 1"]),
                                                        dcc.Input(
                                                            id=_input_id(MACHINES[i], 1),
                                                            className="test-input",
                                                            placeholder="Test #",
                                                            type="text",
                                                            value="",
                                                            debounce=True,
                                                        ),
                                                    ],
                                                ),
                                                html.Div(
                                                    className="position-field",
                                                    children=[
                                                        html.Div(className="position-label", children=["Position 2"]),
                                                        dcc.Input(
                                                            id=_input_id(MACHINES[i], 2),
                                                            className="test-input",
                                                            placeholder="Test #",
                                                            type="text",
                                                            value="",
                                                            debounce=True,
                                                        ),
                                                    ],
                                                ),
                                            ],
                                        ),
                                    ],
                                )
                                for i in range(3)
                            ],
                        ),
                    ],
                ),

                html.Div(
                    className="controls-bar",
                    children=[
                        html.Div(
                            className="controls-group",
                            children=[
                                html.Span(className="ctrl-label", children=["STEP"]),
                                html.Div(
                                    className="step-pills",
                                    id="step-pills",
                                    children=[
                                        html.Button(
                                            className="step-pill all-pill active",
                                            id={"type": "step-pill", "step": "all"},
                                            n_clicks=0,
                                            children=["All"],
                                        ),
                                        *[
                                            html.Button(
                                                className="step-pill",
                                                id={"type": "step-pill", "step": s},
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
                            className="toggle-wrap",
                            children=[
                                html.Div(id="ignore-toggle", className="toggle", n_clicks=0),
                                html.Span(className="toggle-label", children=["Ignore when machine stopped"]),
                            ],
                        ),
                        html.Button(id="refresh-btn", className="refresh-btn", n_clicks=0, children=["Refresh"]),
                        make_auto_refresh_toggle(),
                        html.Div(
                            className="variable-filter",
                            style={"marginLeft": "auto"},
                            children=[
                                html.Span(className="ctrl-label", children=["VARIABLE"]),
                                dcc.Dropdown(
                                    id="variable-dropdown",
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
                        html.Span(
                            "Enter test numbers, then click Refresh to load charts.",
                            style={
                                "fontSize": "11px",
                                "color": "var(--muted)",
                                "marginLeft": "8px",
                            },
                        ),
                        dcc.Store(id="active-steps-store", data=["all"]),
                        dcc.Store(id="ignore-stopped-store", data=False),
                        dcc.Store(id="loaded-logs-store", data={}),
                        dcc.Store(id="modal-open-store", data=False),
                        dcc.Store(id="modal-selection-store", data={}),
                        dcc.Store(id="png-export-state", data=0),
                        dcc.Download(id="modal-csv-download"),
                    ],
                ),

                html.Details(
                    className="load-debug-details",
                    open=False,
                    children=[
                        html.Summary("Diagnostics", className="load-debug-summary"),
                        html.Div(id="load-debug-panel", className="load-debug"),
                    ],
                ),

                make_auto_refresh_banner(),
                html.Div(id="graphs-section-label", className="section-label", children=["Temperature Over Time"]),
                html.Div(id="charts-grid", className="charts-grid"),

                # Expanded modal (custom overlay to match your reference)
                html.Div(
                    id="modal-overlay",
                    className="modal-overlay",
                    children=[
                        html.Div(
                            className="modal",
                            children=[
                                html.Div(
                                    className="modal-header",
                                    children=[
                                        html.Div(
                                            children=[
                                                html.Div(id="modal-title", className="modal-title", children=["-"]),
                                                html.Div(id="modal-subtitle", className="modal-subtitle", children=["-"]),
                                            ]
                                        ),
                                        html.Div(
                                            className="modal-actions",
                                            children=[
                                                make_modal_icon_button(
                                                    "modal-export-png-btn",
                                                    _ICON_DOWNLOAD,
                                                    "Export PNG",
                                                ),
                                                make_modal_icon_button(
                                                    "modal-export-csv-btn",
                                                    _ICON_CSV,
                                                    "Export CSV",
                                                ),
                                                html.Button(
                                                    id="modal-close-btn",
                                                    className="modal-close",
                                                    n_clicks=0,
                                                    children=["✕"],
                                                ),
                                            ],
                                        ),
                                    ],
                                ),
                                html.Div(id="modal-placement-note", className="modal-placement-note"),
                                html.Div(id="modal-stats", className="stat-row"),
                                html.Div(
                                    className="modal-chart",
                                    children=[
                                        dcc.Loading(
                                            type="circle",
                                            color="#F0BA20",
                                            delay_show=120,
                                            children=[
                                                dcc.Graph(
                                                    id="modal-graph",
                                                    figure=_blank_figure(),
                                                    config={"displayModeBar": False},
                                                    style={"height": "380px"},
                                                )
                                            ],
                                        ),
                                    ],
                                ),
                                html.Div(id="modal-legend", className="step-legend"),
                            ],
                        )
                    ],
                ),
                ],
                ),
            ],
        ),
        html.Div(
            id="analysis-page",
            className="tab-page",
            style={"display": "none"},
            children=[
                html.Div(
                    className="main",
                    children=[build_analysis_layout()],
                ),
            ],
        ),
        html.Div(
            id="otkph-page",
            className="tab-page",
            style={"display": "none"},
            children=[
                html.Div(
                    className="main",
                    children=[build_otkph_layout()],
                ),
            ],
        ),
    ],
)

register_monitor_callbacks(
    app,
    {
        "VARIABLE_CONFIG": VARIABLE_CONFIG,
        "MACHINES": MACHINES,
        "MACHINE_BADGE": MACHINE_BADGE,
        "STEP_COLORS": STEP_COLORS,
        "_input_id": _input_id,
        "find_log_path_for_test_number": lambda test_number: find_log_path_for_test_number(test_number, PROJECT_ROOT),
        "parse_log_header_metadata": parse_log_header_metadata,
        "cached_parse_log": cached_parse_log,
        "DISPLAY_TO_MACHINE_ID": DISPLAY_TO_MACHINE_ID,
        "_serialize_df_rows": _serialize_df_rows,
        "make_chart_panel": make_chart_panel,
        "_rows_to_df": _rows_to_df,
        "_apply_chart_filters": _apply_chart_filters,
        "build_temperature_figure": build_temperature_figure,
        "_blank_figure": _blank_figure,
        "build_summary_stats": build_summary_stats,
        "_downsample": _downsample,
        "_runtime_hhmm_for_df": _runtime_hhmm_for_df,
        "_placement_history_note_children": _placement_history_note_children,
    },
)

register_monitor_auto_refresh_callbacks(
    app,
    {
        "MACHINES": MACHINES,
        "_input_id": _input_id,
    },
)

register_navigation_callbacks(app)

register_analysis_callbacks(
    app,
    {
        "VARIABLE_CONFIG": VARIABLE_CONFIG,
        "COMPARE_PALETTE": COMPARE_PALETTE,
        "STEP_COLORS": STEP_COLORS,
        "STEP_BORDER_COLORS": STEP_BORDER_COLORS,
        "BAND_UPPER_LINE_COLOR": BAND_UPPER_LINE_COLOR,
        "BAND_LOWER_LINE_COLOR": BAND_LOWER_LINE_COLOR,
        "summary_status_for_band": summary_status_for_band,
        "build_comparison_figure": build_comparison_figure,
        "build_distribution_figure": build_distribution_figure,
        "build_step_average_figure": build_step_average_figure,
        "collect_band_crossing_violations": collect_band_crossing_violations,
        "_rows_to_df": _rows_to_df,
        "_apply_chart_filters": _apply_chart_filters,
        "find_log_path_for_test_number": lambda tn: find_log_path_for_test_number(tn, PROJECT_ROOT),
        "cached_parse_log": cached_parse_log,
        "_serialize_df_rows": _serialize_df_rows,
    },
)

register_otkph_callbacks(
    app,
    step_colors=STEP_COLORS,
    rows_to_df=_rows_to_df,
    find_log_path=lambda test_number: find_log_path_for_test_number(test_number, PROJECT_ROOT),
    cached_parse=cached_parse_log,
    serialize_df_rows=_serialize_df_rows,
)

if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=8050)
