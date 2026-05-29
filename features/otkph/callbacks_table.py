from __future__ import annotations

import io
from typing import Callable, Dict, List

import numpy as np
import pandas as pd
from dash import Input, Output, State, dcc, html, callback_context
from dash.exceptions import PreventUpdate

from services.data_utils import _rows_to_df as rows_to_df, _serialize_df_rows as serialize_df_rows
from .services import CAM_DEFS, _build_effective_elapsed_seconds, _camera_health, _format_frozen_period, _thermo_col, collect_frozen_periods


def _running_hours_hhmm_labels(elapsed_seconds: pd.Series) -> List[str]:
    """Cumulative running time as H:MM (hours may exceed 24)."""
    out_lbl: List[str] = []
    for s in elapsed_seconds.to_numpy(dtype=float):
        if not np.isfinite(s) or s < 0:
            out_lbl.append("—")
            continue
        sec = int(round(float(s)))
        hh = sec // 3600
        mm = (sec % 3600) // 60
        out_lbl.append(f"{hh}:{mm:02d}")
    return out_lbl


def register_otkph_table_callbacks(
    app,
    *,
    step_colors: Dict[int, str],
    find_log_path: Callable,
    cached_parse: Callable,
) -> None:
    @app.callback(
        Output("otkph-frozen-visible-count-store", "data"),
        Input("otkph-frozen-view-more-btn", "n_clicks"),
        Input("otkph-filtered-rows-store", "data"),
        Input("otkph-active-cameras-store", "data"),
        Input("otkph-ignore-interrupted-store", "data"),
        State("otkph-frozen-visible-count-store", "data"),
    )
    def otkph_frozen_visible_count(view_more_clicks, rows, active, ignore_interrupted, cur_count):
        ctx = callback_context
        tid = ctx.triggered_id
        if tid == "otkph-frozen-view-more-btn":
            return int(cur_count or 10) + 10
        return 10

    @app.callback(
        Output("otkph-violations-body", "children"),
        Output("otkph-violation-badge", "children"),
        Output("otkph-violation-badge", "className"),
        Output("otkph-frozen-view-more-btn", "style"),
        Output("otkph-frozen-view-more-btn", "children"),
        Input("otkph-filtered-rows-store", "data"),
        Input("otkph-active-cameras-store", "data"),
        Input("otkph-thresholds-store", "data"),
        Input("otkph-ignore-interrupted-store", "data"),
        Input("otkph-frozen-visible-count-store", "data"),
    )
    def otkph_update_violations(rows, active_cams, thresholds, ignore_interrupted, visible_count):
        dff = rows_to_df(list(rows or []))
        active = list(active_cams or [1, 2, 3])
        frozen = collect_frozen_periods(dff, active, ignore_interrupted=bool(ignore_interrupted))
        visible_n = max(1, int(visible_count or 10))
        if frozen:
            badge_txt = f"{len(frozen)} frozen period{'s' if len(frozen) > 1 else ''}"
            badge_cls = "badge-red"
            vrows = []
            for r in frozen[:visible_n]:
                value_txt = f"{r['start_temp']:.2f}°C -> {r['end_temp']:.2f}°C"
                period_txt = _format_frozen_period(r["t_start"], r["t_end"])
                hh = int(r["duration_sec"] // 3600)
                mm = int((r["duration_sec"] % 3600) // 60)
                vrows.append(
                    html.Tr(
                        [
                            html.Td(className="td-mono", style={"fontSize": "11px"}, children=[r["camera"]]),
                            html.Td(className="td-mono", children=[value_txt]),
                            html.Td(className="td-mono", children=[period_txt]),
                            html.Td(className="td-mono", children=[f"{hh:02d}:{mm:02d}"]),
                        ]
                    )
                )
            remaining = max(0, len(frozen) - visible_n)
            btn_style = {"display": "inline-flex"} if remaining > 0 else {"display": "none"}
            btn_text = f"View more ({remaining})" if remaining > 0 else "View more"
        else:
            badge_txt = "OK"
            badge_cls = "badge-ok"
            vrows = [html.Tr(html.Td(colSpan=4, style={"textAlign": "center", "color": "var(--muted)", "fontSize": "12px", "padding": "20px"}, children=["No frozen camera periods detected"]))]
            btn_style = {"display": "none"}
            btn_text = "View more"

        return vrows, badge_txt, badge_cls, btn_style, btn_text

    @app.callback(
        *[Output(f"otkph-cam-temp-{cd['i']}", "children") for cd in CAM_DEFS],
        *[Output(f"otkph-cam-status-{cd['i']}", "children") for cd in CAM_DEFS],
        Input("otkph-filtered-rows-store", "data"),
        Input("otkph-active-cameras-store", "data"),
    )
    def otkph_update_camera_cards(rows, active_cams):
        dff = rows_to_df(list(rows or []))
        temps_out: List = []
        stat_out: List = []
        for cd in CAM_DEFS:
            i = cd["i"]
            col = _thermo_col(i)
            if dff.empty or col not in dff.columns:
                temps_out.append(["–", html.Span(" °C", className="cam-unit")])
                stat_out.append([html.Div(className="cam-dot", style={"background": "var(--green)"}), html.Span(style={"fontSize": "10px", "color": "var(--muted)"}, children=["Operational"])])
                continue
            ser = pd.to_numeric(dff[col], errors="coerce")
            last = ser.dropna()
            temps_out.append(["–", html.Span(" °C", className="cam-unit")] if last.empty else [f"{float(last.iloc[-1]):.1f}", html.Span(" °C", className="cam-unit")])
            ok = _camera_health(dff[col])
            stat_out.append([html.Div(className="cam-dot", style={"background": "var(--green)" if ok else "var(--red)"}), html.Span(style={"fontSize": "10px", "color": "var(--muted)"}, children=["Operational" if ok else "Fault"])])
        return (*temps_out, *stat_out)

    @app.callback(
        Output("otkph-csv-download", "data"),
        Input("otkph-export-btn", "n_clicks"),
        State("otkph-filtered-rows-store", "data"),
        State("otkph-active-cameras-store", "data"),
        prevent_initial_call=True,
    )
    def otkph_export_csv(_n, rows, active_cams):
        dff = rows_to_df(list(rows or []))
        active = list(active_cams or [1, 2, 3])
        if dff.empty:
            raise PreventUpdate
        ts = pd.to_datetime(dff["timestamp"], errors="coerce")
        helper = pd.DataFrame({"timestamp": ts, "speed": pd.to_numeric(dff["speed"], errors="coerce") if "speed" in dff.columns else np.nan})
        elapsed_sec = _build_effective_elapsed_seconds(helper, ignore_interrupted=True)
        running_labels = _running_hours_hhmm_labels(elapsed_sec)

        cpc_temp_vals = pd.to_numeric(dff["cpc_temp_c"], errors="coerce") if "cpc_temp_c" in dff.columns else pd.Series([pd.NA] * len(dff))
        out = pd.DataFrame(
            {
                "Date": ts.dt.strftime("%Y-%m-%d"),
                "Hour": ts.dt.strftime("%H:%M:%S"),
                "Running hours": running_labels,
                "Step": dff["step"],
                "Speed": pd.to_numeric(dff["speed"], errors="coerce") if "speed" in dff.columns else pd.Series([pd.NA] * len(dff)),
                "CPC Temp. (°C)": cpc_temp_vals,
            }
        )
        temp_col_idx = 1
        temp_col_names: List[str] = []
        for i in active[:3]:
            col = _thermo_col(i)
            if col in dff.columns:
                temp_name = f"Temp. {temp_col_idx}"
                out[temp_name] = pd.to_numeric(dff[col], errors="coerce")
                temp_col_names.append(temp_name)
                temp_col_idx += 1

        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
            out.to_excel(writer, sheet_name="Data", index=False)
            wb = writer.book

            running_col = int(out.columns.get_loc("Running hours"))
            n_data = len(out)
            last_excel_row = n_data  # header row 0; data rows 1..n_data
            # Line charts use a category X-axis; xlsxwriter expects interval_unit / interval_tick
            # (not interval_between_labels — those are ignored and every category gets a label).
            label_interval = 1 if n_data <= 1 else max(1, (n_data - 1) // 6)

            ws_chart = wb.add_worksheet("Test Analysis")
            chart = wb.add_chart({"type": "line"})
            speed_col = int(out.columns.get_loc("Speed"))
            cpc_col = int(out.columns.get_loc("CPC Temp. (°C)"))

            chart.add_series(
                {
                    "name": ["Data", 0, cpc_col],
                    "categories": ["Data", 1, running_col, last_excel_row, running_col],
                    "values": ["Data", 1, cpc_col, last_excel_row, cpc_col],
                }
            )

            for tname in temp_col_names:
                tcol = int(out.columns.get_loc(tname))
                chart.add_series(
                    {
                        "name": ["Data", 0, tcol],
                        "categories": ["Data", 1, running_col, last_excel_row, running_col],
                        "values": ["Data", 1, tcol, last_excel_row, tcol],
                    }
                )

            chart.add_series(
                {
                    "name": ["Data", 0, speed_col],
                    "categories": ["Data", 1, running_col, last_excel_row, running_col],
                    "values": ["Data", 1, speed_col, last_excel_row, speed_col],
                    "y2_axis": True,
                }
            )

            chart.set_title({"name": "Test Analysis"})
            chart.set_x_axis(
                {
                    "name": "Running hours (H:MM)",
                    "interval_unit": label_interval,
                    "interval_tick": label_interval,
                }
            )
            chart.set_y_axis({"name": "Temperature (ºC)", "min": 0, "max": 120})
            chart.set_y2_axis({"name": "Speed (km/h)", "min": 0, "max": 80})
            chart.set_legend({"position": "bottom"})
            ws_chart.insert_chart("B2", chart, {"x_scale": 1.7, "y_scale": 1.5})

        stamp = pd.Timestamp.utcnow().strftime("%Y%m%d_%H%M%S")
        return dcc.send_bytes(buffer.getvalue(), f"otkph_export_{stamp}.xlsx")

