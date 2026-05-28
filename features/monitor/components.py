from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd
from dash import dcc, html

from services.chart_utils import _downsample
from config import MACHINE_ID_TO_LABEL, POSITION_LABELS, POS_COLORS, VARIABLE_CONFIG
from features.monitor.data import _df_after_ignore_stopped, _filter_by_steps, _placement_key, _rows_to_df
from features.monitor.figures import _runtime_hhmm_for_df, build_summary_stats, build_temperature_figure
from features.monitor.icons import _ICON_EMPTY_CHART, _ICON_EXPAND, ICON_REGISTRY, ICON_SYNC
from features.monitor.layout import make_empty_state, make_expand_button


def make_modal_stats(stats: dict, var_cfg: dict, run_time: str) -> List[html.Div]:
    unit = var_cfg["unit"]
    unit_span = html.Span(f" {unit}", style={"fontSize": "12px", "color": "var(--muted)"})

    def _stat(val, label: str, with_unit: bool = True) -> html.Div:
        return html.Div(
            className="stat",
            children=[
                html.Div(
                    className="stat-val",
                    children=[val, unit_span] if with_unit else [val],
                ),
                html.Div(className="stat-lbl", children=[label]),
            ],
        )

    return [
        _stat(stats["current"], "CURRENT"),
        _stat(stats["max"], "MAX"),
        _stat(stats["min"], "MIN"),
        _stat(stats["avg"], "AVG"),
        _stat(stats["std"], "STD DEV"),
        _stat(run_time, "RUN TIME", with_unit=False),
    ]


def make_step_legend(step_colors: Dict[int, str]) -> List[html.Div]:
    return [
        html.Div(
            className="legend-item",
            children=[
                html.Div(
                    className="legend-swatch",
                    style={"background": step_colors[s].replace("0.08", "0.6")},
                ),
                html.Span(f"Step {s}"),
            ],
        )
        for s in range(1, 10)
    ]


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


def _relative_time(dt: Optional[datetime]) -> str:
    if dt is None:
        return "Never"
    delta = int((datetime.now() - dt).total_seconds())
    if delta < 5:
        return "just now"
    if delta < 60:
        return f"{delta}s ago"
    if delta < 3600:
        return f"{delta // 60} min ago"
    return dt.strftime("%H:%M")


def _time_until(dt: Optional[datetime]) -> str:
    if dt is None:
        return "—"
    delta = int((dt - datetime.now()).total_seconds())
    if delta <= 0:
        return "now"
    if delta < 60:
        return f"in {delta}s"
    return f"in {delta // 60} min"


def make_sync_status_panel(state, source_root: str) -> html.Div:
    if state is None:
        last_txt = "Never synced"
        next_txt = "—"
        running = False
        enabled = True
        results = []
        error = None
    else:
        running = bool(state.get("running") if isinstance(state, dict) else state.running)
        enabled = bool(state.get("enabled", True) if isinstance(state, dict) else state.enabled)
        error = state.get("error") if isinstance(state, dict) else state.error
        results = state.get("results", []) if isinstance(state, dict) else state.results
        last_dt = state.get("last_sync_time") if isinstance(state, dict) else state.last_sync_time
        next_dt = state.get("next_sync_time") if isinstance(state, dict) else state.next_sync_time
        last_txt = "Syncing now..." if running else _relative_time(last_dt)
        next_txt = _time_until(next_dt) if enabled else "paused"

    source_ok = True
    try:
        import os
        source_ok = os.path.isdir(source_root)
    except Exception:
        source_ok = False

    def _status_icon(r) -> str:
        if isinstance(r, dict):
            found = r.get("found", False)
            err = r.get("error")
            res = r.get("result")
        else:
            found = r.found
            err = r.error
            res = r.result
        if err:
            return "✗"
        if not found:
            return "–"
        return "✓"

    def _status_detail(r) -> str:
        if isinstance(r, dict):
            err = r.get("error")
            found = r.get("found", False)
            res = r.get("result")
        else:
            err = r.error
            found = r.found
            res = r.result
        if err:
            return f"error: {err}"
        if not found:
            return "not found on share"
        if res is None:
            return ""
        copied = res.get("copied", 0) if isinstance(res, dict) else res.copied
        deleted = res.get("deleted", 0) if isinstance(res, dict) else res.deleted
        unchanged = res.get("unchanged", 0) if isinstance(res, dict) else res.unchanged
        return f"{copied} copied · {deleted} deleted · {unchanged} unchanged"

    test_rows = []
    for r in results:
        tn = r.get("test_number") if isinstance(r, dict) else r.test_number
        icon = _status_icon(r)
        detail = _status_detail(r)
        icon_color = "var(--muted)"
        if icon == "✓":
            icon_color = "#34C47C"
        elif icon == "✗":
            icon_color = "#E84040"
        test_rows.append(
            html.Div(
                className="sync-test-row",
                style={"display": "flex", "alignItems": "center", "gap": "8px",
                       "fontSize": "11px", "padding": "2px 0"},
                children=[
                    html.Span(icon, style={"color": icon_color, "width": "12px", "flexShrink": "0"}),
                    html.Span(tn, style={"fontFamily": "'DM Mono', monospace", "minWidth": "80px"}),
                    html.Span(detail, style={"color": "var(--muted)"}),
                ],
            )
        )

    warning = []
    if not source_ok:
        warning = [
            html.Div(
                id="sync-source-warning",
                className="sync-warning",
                style={"fontSize": "11px", "color": "#E84040", "marginBottom": "6px"},
                children=["⚠ Network share unreachable — sync paused"],
            )
        ]

    return html.Div(
        id="sync-status-panel",
        className="sync-status-panel",
        style={"padding": "10px 0", "borderTop": "1px solid var(--border)"},
        children=[
            html.Div(
                style={"display": "flex", "alignItems": "center", "gap": "12px", "marginBottom": "6px"},
                children=[
                    html.Img(src=ICON_SYNC, alt="", style={"width": "13px", "height": "13px", "opacity": "0.7"}),
                    html.Span(
                        id="sync-last-time",
                        style={"fontSize": "11px", "color": "var(--muted)"},
                        children=[f"Last sync: {last_txt} · Next: {next_txt}"],
                    ),
                    html.Div(style={"marginLeft": "auto", "display": "flex", "gap": "8px", "alignItems": "center"},
                             children=[
                                 html.Button(
                                     "Sync Now",
                                     id="sync-now-btn",
                                     className="refresh-btn",
                                     n_clicks=0,
                                     style={"fontSize": "11px", "padding": "3px 10px"},
                                 ),
                                 html.Div(
                                     className="toggle-wrap",
                                     style={"display": "flex", "alignItems": "center", "gap": "6px"},
                                     children=[
                                         html.Div(
                                             id="sync-enabled-toggle",
                                             className="toggle on" if enabled else "toggle",
                                             n_clicks=0,
                                         ),
                                         html.Span("Auto-sync", className="toggle-label",
                                                   style={"fontSize": "11px"}),
                                     ],
                                 ),
                             ]),
                ],
            ),
            *warning,
            html.Div(
                id="sync-test-rows",
                children=test_rows if test_rows else [
                    html.Span("No active tests in registry.",
                              style={"fontSize": "11px", "color": "var(--muted)"})
                ],
            ),
            html.Div(
                id="sync-next-time",
                style={"display": "none"},
            ),
        ],
    )


def make_registry_modal(entries: List[dict]) -> List:
    active = [e for e in entries if e.get("status") == "active"]
    planned = [e for e in entries if e.get("status") == "planned"]

    def _make_row(entry: dict) -> html.Div:
        tn = entry["test_number"]
        status = entry.get("status", "active")
        promote_label = "→ Planned" if status == "active" else "→ Active"
        new_status = "planned" if status == "active" else "active"
        return html.Div(
            className="registry-row",
            style={"display": "flex", "alignItems": "center", "gap": "8px",
                   "padding": "4px 0", "borderBottom": "1px solid var(--border)"},
            children=[
                html.Span(
                    tn,
                    style={"fontFamily": "'DM Mono', monospace", "fontSize": "13px", "flex": "1"},
                ),
                html.Button(
                    promote_label,
                    id={"type": "registry-set-status", "index": tn},
                    n_clicks=0,
                    className="modal-icon-btn",
                    title=f"Move to {new_status}",
                    style={"fontSize": "11px"},
                    **{"data-status": new_status},
                ),
                html.Button(
                    "✕",
                    id={"type": "registry-remove", "index": tn},
                    n_clicks=0,
                    className="modal-close",
                    title="Remove",
                    style={"fontSize": "11px"},
                ),
            ],
        )

    def _make_section(title: str, rows: List[dict]) -> html.Div:
        return html.Div(
            style={"flex": "1", "minWidth": "200px"},
            children=[
                html.Div(title, style={"fontSize": "11px", "color": "var(--muted)",
                                        "fontWeight": "600", "marginBottom": "8px",
                                        "textTransform": "uppercase", "letterSpacing": "0.04em"}),
                html.Div(
                    [_make_row(e) for e in rows] if rows
                    else [html.Span("—", style={"fontSize": "12px", "color": "var(--muted)"})],
                ),
            ],
        )

    return [
        html.Div(
            className="modal",
            style={"maxWidth": "640px", "width": "90%"},
            children=[
                html.Div(
                    className="modal-header",
                    children=[
                        html.Div(
                            html.Div("Test Registry", className="modal-title"),
                        ),
                        html.Div(
                            className="modal-actions",
                            children=[
                                html.Button(
                                    "✕",
                                    id="registry-modal-close-btn",
                                    className="modal-close",
                                    n_clicks=0,
                                ),
                            ],
                        ),
                    ],
                ),
                html.Div(
                    style={"display": "flex", "gap": "24px", "padding": "16px 0", "flexWrap": "wrap"},
                    children=[
                        _make_section("Active Tests", active),
                        _make_section("Planned Tests", planned),
                    ],
                ),
                html.Div(
                    style={"display": "flex", "gap": "8px", "alignItems": "center", "paddingTop": "12px",
                           "borderTop": "1px solid var(--border)"},
                    children=[
                        dcc.Input(
                            id="registry-add-input",
                            className="test-input",
                            placeholder="Test number",
                            type="text",
                            value="",
                            debounce=False,
                            style={"width": "140px"},
                        ),
                        html.Button(
                            "Add Active",
                            id="registry-add-btn",
                            className="refresh-btn",
                            n_clicks=0,
                            style={"fontSize": "12px"},
                        ),
                    ],
                ),
            ],
        )
    ]


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
