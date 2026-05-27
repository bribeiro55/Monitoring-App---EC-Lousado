from __future__ import annotations

from typing import List, Optional

import pandas as pd
from dash import Input, Output, State, html

from config import (
    BAND_LOWER_LINE_COLOR as band_lower_line_color,
    BAND_UPPER_LINE_COLOR as band_upper_line_color,
    COMPARE_PALETTE as compare_palette,
    STEP_BORDER_COLORS as step_border_colors,
    STEP_COLORS as step_colors,
)
from features.analysis.figures import (
    build_comparison_figure,
    build_distribution_figure,
    build_step_average_figure,
)
from features.analysis.services import (
    build_analysis_test_frames,
    collect_band_crossing_violations,
    normalize_analysis_band_limits,
    summary_status_for_band,
)


def register_analysis_rendering_callbacks(app, *, VARIABLE_CONFIG) -> None:
    variable_config = VARIABLE_CONFIG

    @app.callback(
        Output("analysis-selected-tests", "children"),
        Input("analysis-tests-store", "data"),
        Input("analysis-variable-dropdown", "value"),
        State("analysis-data-store", "data"),
    )
    def render_analysis_sidebar_selected_tests(tests: Optional[List[dict]], selected_var: str, data: Optional[dict]):
        tests = list(tests or [])
        data = dict(data or {})
        selected_children: List = []
        if not tests:
            selected_children.append(
                html.Div(
                    style={"fontSize": "12px", "color": "var(--muted)", "padding": "8px 0 12px"},
                    children="No tests selected. Enter a test number and click Add.",
                )
            )
        else:
            for t in tests:
                tn = str(t.get("test_number", ""))
                ci = int(t.get("color_index", 0)) % len(compare_palette)
                color = compare_palette[ci]
                entry = data.get(tn, {})
                st = entry.get("status")
                sub = "" if st == "ok" else (entry.get("message") or st or "Error")
                selected_children.append(
                    html.Div(
                        className="test-selector-row",
                        children=[
                            html.Div(className="swatch", style={"background": color}),
                            html.Div(
                                className="ts-name",
                                children=(f"Test {tn}" if st == "ok" else html.Span([f"Test {tn} — ", html.Span(sub, className="error-text")])),
                            ),
                            html.Button("×", className="ts-remove", id={"type": "analysis-rm-test", "tn": tn}, n_clicks=0, title="Remove"),
                        ],
                    )
                )
        return selected_children

    @app.callback(
        Output("analysis-main-graph", "figure"),
        Output("analysis-dist-graph", "figure"),
        Output("analysis-step-graph", "figure"),
        Output("analysis-legend", "children"),
        Output("analysis-chart-title", "children"),
        Output("analysis-chart-sub", "children"),
        Output("analysis-violations-table", "children"),
        Output("analysis-violation-badge", "children"),
        Output("analysis-violation-badge", "className"),
        Output("analysis-summary-table", "children"),
        Output("analysis-violations-view-more-wrap", "style"),
        Output("analysis-violations-view-more-btn", "children"),
        Input("analysis-tests-store", "data"),
        Input("analysis-data-store", "data"),
        Input("analysis-limits-store", "data"),
        Input("analysis-data-filters-store", "data"),
        Input("analysis-active-steps-store", "data"),
        Input("analysis-ignore-stopped-store", "data"),
        Input("analysis-normalize-store", "data"),
        Input("analysis-variable-dropdown", "value"),
        Input("analysis-violations-expanded-store", "data"),
    )
    def render_analysis_outputs(tests, data, limits, data_filters, active_steps, ignore_stopped, normalize_x, selected_var, violations_expanded):
        tests = list(tests or [])
        band = normalize_analysis_band_limits(limits)
        upper, lower = band["upper"], band["lower"]
        expanded = bool(violations_expanded)
        test_frames, var_cfg, value_col, var_key = build_analysis_test_frames(
            tests=tests,
            data=data,
            active_steps=active_steps,
            ignore_stopped=ignore_stopped,
            selected_var=selected_var,
            data_filters=data_filters,
            variable_config=variable_config,
            compare_palette=compare_palette,
        )
        main_fig = build_comparison_figure(
            test_frames,
            value_col=value_col,
            var_label=var_cfg["label"],
            var_unit=var_cfg["unit"],
            band_limits=band,
            # Match Monitor behavior for single-test + ignore-stopped:
            # use sample-index (compressed runtime) x-axis so long stopped gaps
            # do not appear as long horizontal holds on date axis.
            normalize_x=bool(ignore_stopped) and len(test_frames) == 1,
            runtime_align_x=len(test_frames) >= 2,
            step_colors=step_colors,
            step_border_colors=step_border_colors,
        )
        dist_fig = build_distribution_figure(test_frames, value_col=value_col, var_unit=var_cfg["unit"], var_key=var_key)
        step_fig = build_step_average_figure(test_frames, value_col=value_col, var_unit=var_cfg["unit"])
        legend_children: List = [
            html.Div(className="legend-item", children=[html.Div(className="legend-line", style={"background": color}), html.Span(label)])
            for label, _dff, color in test_frames
        ]
        if band.get("upper") is not None:
            legend_children.append(
                html.Div(className="legend-item", children=[html.Div(className="legend-dash", style={"borderColor": band_upper_line_color}), html.Span(f"Upper limit · {float(band['upper']):g} {var_cfg['unit']}")])
            )
        if band.get("lower") is not None:
            legend_children.append(
                html.Div(className="legend-item", children=[html.Div(className="legend-dash", style={"borderColor": band_lower_line_color}), html.Span(f"Lower limit · {float(band['lower']):g} {var_cfg['unit']}")])
            )
        title = f"{var_cfg['label']} comparison"
        sub = " · ".join(l[0] for l in test_frames) if test_frames else ("Add tests to compare" if tests else "Select tests to compare")

        summary_body_rows: List = []
        for label, dff, color in test_frames:
            vals = pd.to_numeric(dff[value_col], errors="coerce").dropna()
            if vals.empty:
                continue
            mx = float(vals.max())
            av = float(vals.mean())
            mn = float(vals.min())
            status_lbl, status_cls = summary_status_for_band(mx, mn, upper, lower)
            summary_body_rows.append(html.Tr([html.Td(html.Span([html.Span(style={"display": "inline-block", "width": "8px", "height": "8px", "borderRadius": "50%", "background": color, "marginRight": "6px"}), html.Span(label.replace("Test ", ""), className="td-mono")])), html.Td(f"{mx:.1f} {var_cfg['unit']}", className="td-mono"), html.Td(f"{av:.1f} {var_cfg['unit']}", className="td-mono"), html.Td(html.Span(status_lbl, className=status_cls))]))
        summary_table = html.Table([html.Thead(html.Tr([html.Th("Test"), html.Th("Max"), html.Th("Avg"), html.Th("Status")])), html.Tbody(summary_body_rows)]) if summary_body_rows else html.Div("No tests selected.", style={"fontSize": "12px", "color": "var(--muted)"})

        viol = collect_band_crossing_violations(test_frames, value_col=value_col, upper=upper, lower=lower)
        viol_sorted = sorted(viol, key=lambda r: pd.Timestamp.min if pd.isna(r["ts"]) else r["ts"], reverse=True)
        n_viol = len(viol_sorted)
        preview_n = 5
        visible = viol_sorted if expanded or n_viol <= preview_n else viol_sorted[:preview_n]
        vm_style = {"display": "block", "marginTop": "10px", "textAlign": "center"} if n_viol > preview_n else {"display": "none", "marginTop": "10px", "textAlign": "center"}
        vm_label = "Show less" if (n_viol > preview_n and expanded) else "View more"
        if not viol_sorted:
            vrows = [html.Tr(html.Td("No limit crossings detected", colSpan=6, style={"textAlign": "center", "color": "var(--muted)", "fontSize": "12px", "padding": "20px"}))]
            badge, badge_cls = "OK", "badge-ok"
        else:
            badge, badge_cls = f"{n_viol} crossing{'s' if n_viol > 1 else ''}", "badge-red"
            vrows = []
            for r in visible:
                lim_col = band_upper_line_color if r.get("kind") == "upper" else band_lower_line_color
                vrows.append(html.Tr([html.Td([html.Span(style={"display": "inline-block", "width": "8px", "height": "8px", "borderRadius": "50%", "background": r["color"], "marginRight": "6px"}), html.Span(r["test"].replace("Test ", ""), className="td-mono")]), html.Td(html.Span(f"{r['lim_label']} ({float(r['limit_value']):g} {var_cfg['unit']})", style={"color": lim_col, "fontWeight": 500, "fontSize": "12px"})), html.Td(f"{r['value']:.1f} {var_cfg['unit']}", className="td-mono", style={"color": "var(--danger)", "fontWeight": 600}), html.Td(str(r["time_display"]), className="td-mono"), html.Td(f"Step {r['step']}" if r["step"] != "–" else "–", className="td-mono"), html.Td(html.Span("Crossing", className="td-badge badge-warn"))]))
        violations_table = html.Table([html.Thead(html.Tr([html.Th("Test"), html.Th("Crossing"), html.Th("Value"), html.Th("Time"), html.Th("Step"), html.Th("Status")])), html.Tbody(vrows)])
        return main_fig, dist_fig, step_fig, legend_children, title, sub, violations_table, badge, badge_cls, summary_table, vm_style, vm_label
