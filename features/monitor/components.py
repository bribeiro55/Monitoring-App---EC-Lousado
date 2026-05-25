from __future__ import annotations

from typing import List, Optional

import pandas as pd
from dash import dcc, html

from services.chart_utils import _downsample
from config import MACHINE_ID_TO_LABEL, POSITION_LABELS, POS_COLORS, VARIABLE_CONFIG
from features.monitor.data import _df_after_ignore_stopped, _filter_by_steps, _placement_key, _rows_to_df
from features.monitor.figures import _runtime_hhmm_for_df, build_summary_stats, build_temperature_figure
from features.monitor.icons import _ICON_EMPTY_CHART, _ICON_EXPAND
from features.monitor.layout import make_empty_state, make_expand_button


def _placement_history_note_children(
    df: pd.DataFrame, primary_mid: str, primary_pos: int
) -> List[html.Div]:
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
                    children=[html.Span("Click Refresh to load")],
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
                    children=[html.Div(className="error-text", children=[msg])],
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
                                    html.Span(tire_size, className="inline-stat-val"),
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
                                    html.Span(run_time_last, className="inline-stat-val"),
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
