from __future__ import annotations

from typing import Callable, Dict, List

import numpy as np
import pandas as pd
from dash import ALL, Input, Output, State, callback_context, dcc, html
from dash.exceptions import PreventUpdate

from analysis_tab import LIMIT_PALETTE
from .figures import (
    _blank_fig,
    _compute_max_delta,
    build_camera_time_figure,
    build_delta_figure,
    build_scatter_figure,
    build_speed_figure,
)
from .services import CAM_DEFS, _thermo_col, _with_plot_axis


def _next_th_id(th: List[dict]) -> int:
    ids = [int(x["id"]) for x in th if x.get("id") is not None]
    return max(ids) + 1 if ids else 0


def register_otkph_visual_callbacks(
    app,
    *,
    step_colors: Dict[int, str],
    rows_to_df: Callable,
    find_log_path: Callable,
    cached_parse: Callable,
    serialize_df_rows: Callable,
) -> None:
    @app.callback(
        Output("otkph-thresholds-store", "data"),
        Input("otkph-add-threshold-btn", "n_clicks"),
        State("otkph-thresholds-store", "data"),
        prevent_initial_call=True,
    )
    def otkph_add_threshold(_n, th):
        th = list(th or [])
        nid = _next_th_id(th)
        th.append(
            {
                "id": nid,
                "name": f"Threshold {len(th)}",
                "value": 100.0,
                "active": True,
                "color": LIMIT_PALETTE[nid % len(LIMIT_PALETTE)],
            }
        )
        return th

    @app.callback(
        Output("otkph-thresholds-store", "data", allow_duplicate=True),
        Input({"type": "otkph-thr-remove", "tid": ALL}, "n_clicks"),
        State({"type": "otkph-thr-remove", "tid": ALL}, "id"),
        State("otkph-thresholds-store", "data"),
        prevent_initial_call=True,
    )
    def otkph_rm_threshold(_n, ids, th):
        ctx = callback_context
        if not isinstance(ctx.triggered_id, dict):
            raise PreventUpdate
        tid = ctx.triggered_id.get("tid")
        idx = next((i for i, b in enumerate(ids or []) if b == ctx.triggered_id), None)
        if idx is None or not _n or idx >= len(_n) or not _n[idx]:
            raise PreventUpdate
        return [x for x in (th or []) if x.get("id") != tid]

    @app.callback(
        Output("otkph-thresholds-store", "data", allow_duplicate=True),
        Input({"type": "otkph-thr-active", "tid": ALL}, "n_clicks"),
        State({"type": "otkph-thr-active", "tid": ALL}, "id"),
        State("otkph-thresholds-store", "data"),
        prevent_initial_call=True,
    )
    def otkph_thr_toggle(_n, ids, th):
        ctx = callback_context
        if not isinstance(ctx.triggered_id, dict):
            raise PreventUpdate
        tid = ctx.triggered_id.get("tid")
        idx = next((i for i, b in enumerate(ids or []) if b == ctx.triggered_id), None)
        if idx is None or not _n or idx >= len(_n) or not _n[idx]:
            raise PreventUpdate
        th = [dict(x) for x in (th or [])]
        for x in th:
            if x.get("id") == tid:
                x["active"] = not bool(x.get("active", True))
                break
        return th

    @app.callback(
        Output("otkph-thresholds-store", "data", allow_duplicate=True),
        Input({"type": "otkph-thr-val", "tid": ALL}, "value"),
        State({"type": "otkph-thr-val", "tid": ALL}, "id"),
        State("otkph-thresholds-store", "data"),
        prevent_initial_call=True,
    )
    def otkph_thr_val(vals, ids, th):
        ctx = callback_context
        if not isinstance(ctx.triggered_id, dict) or ctx.triggered_id.get("type") != "otkph-thr-val":
            raise PreventUpdate
        tid = ctx.triggered_id.get("tid")
        new_v = None
        for i, bid in enumerate(ids or []):
            if bid == ctx.triggered_id and vals is not None and i < len(vals):
                new_v = vals[i]
                break
        if new_v is None or new_v == "":
            raise PreventUpdate
        try:
            fv = float(new_v)
        except (TypeError, ValueError):
            raise PreventUpdate
        th = [dict(x) for x in (th or [])]
        for x in th:
            if x.get("id") == tid:
                x["value"] = fv
                break
        return th

    @app.callback(
        Output("otkph-thresholds-store", "data", allow_duplicate=True),
        Input({"type": "otkph-thr-name", "tid": ALL}, "value"),
        State({"type": "otkph-thr-name", "tid": ALL}, "id"),
        State("otkph-thresholds-store", "data"),
        prevent_initial_call=True,
    )
    def otkph_thr_name(vals, ids, th):
        ctx = callback_context
        if not isinstance(ctx.triggered_id, dict) or ctx.triggered_id.get("type") != "otkph-thr-name":
            raise PreventUpdate
        tid = ctx.triggered_id.get("tid")
        new_v = None
        for i, bid in enumerate(ids or []):
            if bid == ctx.triggered_id and vals is not None and i < len(vals):
                new_v = vals[i]
                break
        if new_v is None:
            raise PreventUpdate
        th = [dict(x) for x in (th or [])]
        for x in th:
            if x.get("id") == tid:
                x["name"] = str(new_v)
                break
        return th

    @app.callback(Output("otkph-thresholds-ui", "children"), Input("otkph-thresholds-store", "data"))
    def otkph_render_thresholds(th):
        th = list(th or [])
        rows = []
        for lim in th:
            tid = lim.get("id")
            rows.append(
                html.Div(
                    className="limit-row",
                    children=[
                        html.Div(className="limit-color", style={"background": lim.get("color") or "#E8721A"}),
                        dcc.Input(
                            className="limit-name-input",
                            id={"type": "otkph-thr-name", "tid": tid},
                            value=str(lim.get("name", "")),
                            debounce=True,
                        ),
                        html.Div(
                            className="limit-input-wrap",
                            children=[
                                dcc.Input(
                                    id={"type": "otkph-thr-val", "tid": tid},
                                    type="number",
                                    value=float(lim.get("value", 0)),
                                    debounce=True,
                                    className="limit-val-input",
                                ),
                                html.Span(className="limit-unit", children=["°C"]),
                            ],
                        ),
                        html.Button(
                            "●" if lim.get("active", True) else "○",
                            className="limit-active-toggle on" if lim.get("active", True) else "limit-active-toggle",
                            id={"type": "otkph-thr-active", "tid": tid},
                            n_clicks=0,
                        ),
                        html.Button(
                            "×",
                            className="ts-remove",
                            id={"type": "otkph-thr-remove", "tid": tid},
                            n_clicks=0,
                        ),
                    ],
                )
            )
        return rows

    @app.callback(
        Output("otkph-cam-graph", "figure"),
        Output("otkph-delta-graph", "figure"),
        Output("otkph-step-graph", "figure"),
        Output("otkph-scatter-graph", "figure"),
        Output("otkph-cam-chart-sub", "children"),
        Output("otkph-cam-legend", "children"),
        Output("otkph-step-legend", "children"),
        Output("otkph-scatter-sub", "children"),
        Output("otkph-max-delta-badge", "children"),
        Output("otkph-max-delta-badge", "className"),
        Output("otkph-stats-strip", "children"),
        Output("otkph-cam-compare", "children"),
        Input("otkph-filtered-rows-store", "data"),
        Input("otkph-active-cameras-store", "data"),
        Input("otkph-thresholds-store", "data"),
        Input("otkph-smooth-store", "data"),
        Input("otkph-ignore-interrupted-store", "data"),
        Input("otkph-corr-a", "value"),
        Input("otkph-corr-b", "value"),
    )
    def otkph_update_figures_and_stats(rows, active_cams, thresholds, smooth, ignore_interrupted, corr_a, corr_b):
        dff = rows_to_df(list(rows or []))
        dff_plot = _with_plot_axis(dff, bool(ignore_interrupted))
        active = list(active_cams or [1, 2, 3])
        th = list(thresholds or [])
        smooth_b = bool(smooth)
        max_dt = _compute_max_delta(dff_plot, active)

        fig_cam = build_camera_time_figure(
            dff, active, th, smooth_b, step_colors, bool(ignore_interrupted), dplot=dff_plot
        )
        fig_d = build_delta_figure(dff_plot, active, step_colors)
        fig_s = build_speed_figure(dff_plot, step_colors)
        ca, cb = corr_a, corr_b
        if ca is None or cb is None or ca == cb:
            fig_sc = _blank_fig()
        else:
            fig_sc = build_scatter_figure(dff_plot, int(ca), int(cb))
        sub_scatter = (
            f"Scatter: {CAM_DEFS[int(ca) - 1]['code']} vs {CAM_DEFS[int(cb) - 1]['code']}"
            if ca and cb and ca != cb
            else "Select two distinct active cameras"
        )
        max_badge_txt = f"Max ΔT: {max_dt:.1f}°C" if max_dt else "–"
        max_badge_cls = "badge-red" if max_dt > 20 else "badge-warn" if max_dt > 10 else "badge-ok"
        cam_names = ", ".join(CAM_DEFS[i - 1]["code"] for i in active)
        sub_cam = f"{cam_names} · {len(active)} camera(s) selected"

        leg_items = []
        for i in active:
            cd = CAM_DEFS[i - 1]
            leg_items.append(
                html.Div(
                    className="legend-item",
                    children=[html.Div(className="legend-line", style={"background": cd["color"]}), f"{cd['code']} · {cd['label']}"],
                )
            )
        for lim in th:
            if lim.get("active"):
                leg_items.append(
                    html.Div(
                        className="legend-item",
                        children=[html.Div(className="legend-dash", style={"borderColor": lim.get("color")}), f"{lim.get('name')} {float(lim.get('value', 0)):.0f}°C"],
                    )
                )
        step_leg = [
            html.Div(
                className="step-swatch",
                children=[html.Div(className="step-swatch-box", style={"background": step_colors.get(s + 1, '#ccc').replace('0.08', '0.5')}), f"S{s + 1}"],
            )
            for s in range(9)
        ]
        all_vals: List[float] = []
        for i in active:
            col = _thermo_col(i)
            if col in dff.columns:
                all_vals.extend(pd.to_numeric(dff[col], errors="coerce").dropna().tolist())
        if all_vals:
            arr = np.array(all_vals)
            mx, mn, av, std = float(np.max(arr)), float(np.min(arr)), float(np.mean(arr)), float(np.std(arr))
        else:
            mx = mn = av = std = 0.0

        def _ostat(lbl, val, unit, sub):
            return html.Div(
                className="card ostat",
                children=[
                    html.Div(className="ostat-lbl", children=[lbl]),
                    html.Div(className="ostat-val", children=[str(val), html.Span(f" {unit}", className="ostat-unit")]),
                    html.Div(className="ostat-delta", style={"color": "var(--muted)"}, children=[sub]),
                ],
            )

        strip = html.Div(
            style={"display": "grid", "gridTemplateColumns": "repeat(6, 1fr)", "gap": "10px"},
            children=[
                _ostat("Overall Max", f"{mx:.1f}" if all_vals else "–", "°C", "All cameras"),
                _ostat("Overall Min", f"{mn:.1f}" if all_vals else "–", "°C", "All cameras"),
                _ostat("Average", f"{av:.1f}" if all_vals else "–", "°C", "All cameras"),
                _ostat("Std Dev", f"{std:.2f}" if all_vals else "–", "°C", "Variability"),
                _ostat("Max ΔT", f"{max_dt:.1f}" if max_dt else "–", "°C", "Inter-camera spread"),
                _ostat("Active Cameras", str(len(active)), "/ 5", f"{5 - len(active)} not selected"),
            ],
        )

        compare_rows = []
        for i in active:
            col = _thermo_col(i)
            cd = CAM_DEFS[i - 1]
            if col not in dff.columns:
                continue
            v = pd.to_numeric(dff[col], errors="coerce").dropna()
            if len(v) == 0:
                continue
            compare_rows.append(
                html.Tr(
                    [
                        html.Td(html.Span(className="td-mono", style={"fontSize": "11px"}, children=[cd["code"]])),
                        html.Td(className="td-mono", children=[f"{float(v.max()):.1f}°"]),
                        html.Td(className="td-mono", children=[f"{float(v.mean()):.1f}°"]),
                        html.Td(className="td-mono", children=[f"{float(v.std(ddof=0)):.2f}"]),
                    ]
                )
            )
        compare_tbl = (
            html.Table(
                className="cam-compare-table",
                children=[html.Thead(html.Tr([html.Th("Camera"), html.Th("Max"), html.Th("Avg"), html.Th("σ")])), html.Tbody(compare_rows)],
            )
            if compare_rows
            else html.Div("No data.", style={"fontSize": "12px", "color": "var(--muted)"})
        )
        return (fig_cam, fig_d, fig_s, fig_sc, sub_cam, leg_items, step_leg, sub_scatter, max_badge_txt, max_badge_cls, strip, compare_tbl)

