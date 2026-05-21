from __future__ import annotations

from dash import dcc, html

from .figures import _blank_fig
from .services import CAM_DEFS, _default_otkph_filter_state


def build_otkph_layout() -> html.Div:
    return html.Div(
        className="otkph-page-inner",
        children=[
            dcc.Store(id="otkph-active-cameras-store", data=[1, 2, 3]),
            dcc.Store(id="otkph-thresholds-store", data=[]),
            dcc.Store(id="otkph-smooth-store", data=False),
            dcc.Store(id="otkph-ignore-interrupted-store", data=True),
            dcc.Store(id="otkph-frozen-visible-count-store", data=10),
            dcc.Store(id="otkph-data-filters-store", data=_default_otkph_filter_state()),
            dcc.Store(id="otkph-resolved-rows-store", data=[]),
            dcc.Store(id="otkph-filtered-rows-store", data=[]),
            dcc.Download(id="otkph-csv-download"),
            html.Div(
                className="card otkph-config-card",
                children=[
                    html.Div(
                        className="otkph-config-bar",
                        children=[
                            html.Div(className="section-label otkph-config-heading", children=["Test configuration"]),
                            html.Div(
                                className="otkph-test-field-row",
                                children=[
                                    html.Div(
                                        className="otkph-test-field-inline",
                                        children=[
                                            html.Label("Test number"),
                                            dcc.Input(id="otkph-test-input", className="test-input", type="text", placeholder="Test #", value="", debounce=True),
                                        ],
                                    ),
                                    html.Div(id="otkph-test-warning", className="otkph-test-warning"),
                                ],
                            ),
                            html.Div(className="otkph-config-spacer"),
                            html.Div(
                                className="otkph-field otkph-step-field",
                                children=[
                                    html.Label("Step filter"),
                                    dcc.Dropdown(id="otkph-step-select", options=[{"label": "All Steps", "value": "all"}] + [{"label": f"Step {s}", "value": str(s)} for s in range(1, 10)], value="all", clearable=False),
                                ],
                            ),
                            html.Div(className="otkph-export-wrap", children=[html.Button(id="otkph-export-btn", className="btn btn-ghost btn-sm", type="button", children="Export")]),
                        ],
                    ),
                ],
            ),
            html.Div(
                className="card otkph-ribbon-card",
                children=[
                    html.Div(className="section-label", children=["Temperature Cameras — select up to 3 active"]),
                    html.Div(id="otkph-cam-warning", style={"fontSize": "12px", "color": "var(--red)", "marginBottom": "8px"}),
                    html.Div(
                        className="camera-grid",
                        children=[
                            html.Div(
                                id={"type": "otkph-cam", "i": cd["i"]},
                                className="cam-card card",
                                n_clicks=0,
                                children=[
                                    html.Div(className="cam-card-top", children=[html.Div(className="cam-name", children=[cd["code"]]), html.Div(className="cam-icon", style={"background": cd["color"] + "22"}, children=[])]),
                                    html.Div(style={"fontSize": "10px", "color": "var(--muted)", "marginBottom": "4px", "fontFamily": "'DM Mono',monospace"}, children=[cd["label"]]),
                                    html.Div(className="cam-temp", id=f"otkph-cam-temp-{cd['i']}", children=["–", html.Span(" °C", className="cam-unit")]),
                                    html.Div(className="cam-status", id=f"otkph-cam-status-{cd['i']}", children=[html.Div(className="cam-dot", style={"background": "var(--green)"}), html.Span(style={"fontSize": "10px", "color": "var(--muted)"}, children=["Operational"])]),
                                    html.Div(className="cam-check", children=[]),
                                ],
                            )
                            for cd in CAM_DEFS
                        ],
                    ),
                    html.Div(id="otkph-stats-strip", className="otkph-stats-strip"),
                ],
            ),
            html.Div(
                className="otkph-layout",
                children=[
                    html.Div(
                        className="otkph-sidebar",
                        children=[
                            html.Div(className="card sidebar-card", children=[html.Div(className="sidebar-title", children=["Camera Stats"]), html.Div(id="otkph-cam-compare")]),
                            html.Div(
                                className="card sidebar-card filter-card",
                                children=[
                                    html.Div(className="sidebar-title", style={"marginBottom": "10px"}, children=["Data Filters"]),
                                    html.Div(
                                        className="filter-section",
                                        children=[
                                            html.Div("Date filter", className="filter-section-label"),
                                            html.Div(className="filter-mode-pills", children=[html.Button("All", id="otkph-filter-time-all", className="filter-mode-pill active", n_clicks=0), html.Button("After", id="otkph-filter-time-after", className="filter-mode-pill", n_clicks=0), html.Button("Before", id="otkph-filter-time-before", className="filter-mode-pill", n_clicks=0), html.Button("Between", id="otkph-filter-time-between", className="filter-mode-pill", n_clicks=0)]),
                                            html.Div(
                                                id="otkph-filter-time-inputs",
                                                style={"display": "none"},
                                                children=[
                                                    html.Div(className="filter-input-row", children=[html.Label(id="otkph-filter-time-label-a", children=["After"]), dcc.DatePickerSingle(id="otkph-filter-time-date-a", className="filter-datetime", display_format="YYYY-MM-DD", placeholder="YYYY-MM-DD"), dcc.Input(id="otkph-filter-time-time-a", type="text", value="00:00", className="filter-time", debounce=False, placeholder="00:00", maxLength=5)]),
                                                    html.Div(id="otkph-filter-time-row-b", className="filter-input-row", style={"display": "none"}, children=[html.Label("To"), dcc.DatePickerSingle(id="otkph-filter-time-date-b", className="filter-datetime", display_format="YYYY-MM-DD", placeholder="YYYY-MM-DD"), dcc.Input(id="otkph-filter-time-time-b", type="text", value="23:59", className="filter-time", debounce=False, placeholder="23:59", maxLength=5)]),
                                                ],
                                            ),
                                        ],
                                    ),
                                    html.Button("Reset all filters", id="otkph-filter-reset-btn", className="filter-reset", n_clicks=0, type="button"),
                                ],
                            ),
                            html.Div(className="card sidebar-card", children=[html.Div(className="sidebar-title", children=["Thresholds"]), html.Div(id="otkph-thresholds-ui"), html.Button(id="otkph-add-threshold-btn", className="btn btn-ghost", style={"width": "100%", "marginTop": "6px", "justifyContent": "center"}, type="button", children=["+ Add threshold"])]),
                        ],
                    ),
                    html.Div(
                        className="otkph-main",
                        children=[
                            html.Div(
                                className="card otkph-chart-card",
                                children=[
                                    html.Div(className="otkph-chart-header", children=[html.Div(children=[html.Div(className="otkph-chart-title", children=["Camera Temperature Over Time"]), html.Div(id="otkph-cam-chart-sub", className="otkph-chart-sub", children=["Selected cameras overlaid"])]), html.Div(className="toggle-wrap", id="otkph-smooth-wrap", children=[html.Div(id="otkph-smooth-toggle", className="toggle", n_clicks=0), html.Span(className="toggle-label", style={"fontSize": "11px"}, children=["Smooth"])]), html.Div(className="toggle-wrap", id="otkph-ignore-interrupted-wrap", children=[html.Div(id="otkph-ignore-interrupted-toggle", className="toggle on", n_clicks=0), html.Span(className="toggle-label", style={"fontSize": "11px"}, children=["Ignore when interrupted"])])]),
                                    html.Div(className="otkph-graph-wrap", children=[dcc.Graph(id="otkph-cam-graph", figure=_blank_fig(), config={"displayModeBar": False}, style={"height": "280px"})]),
                                    html.Div(id="otkph-cam-legend", className="analysis-legend"),
                                    html.Div(id="otkph-step-legend", className="step-legend-row"),
                                ],
                            ),
                            html.Div(className="card otkph-chart-card", children=[html.Div(className="otkph-chart-header", children=[html.Div(children=[html.Div(className="otkph-chart-title", children=["Inter-Camera Temperature Spread (ΔT)"]), html.Div(className="otkph-chart-sub", children=["Max − Min across selected cameras at each time point"])]), html.Div(id="otkph-max-delta-badge", className="badge-warn", children=["–"])]), html.Div(className="otkph-graph-wrap", children=[dcc.Graph(id="otkph-delta-graph", figure=_blank_fig(), config={"displayModeBar": False}, style={"height": "180px"})])]),
                            html.Div(
                                className="otkph-bottom-grid",
                                children=[
                                    html.Div(className="card obottom-card obottom-card-speed", children=[html.Div(className="otkph-chart-header", style={"marginBottom": "10px"}, children=[html.Div(className="otkph-chart-title", style={"fontSize": "13px"}, children=["Speed During Test"]), html.Div(className="otkph-chart-sub", children=["Machine speed over the test timeline"])]), html.Div(className="otkph-graph-wrap", children=[dcc.Graph(id="otkph-step-graph", figure=_blank_fig(), config={"displayModeBar": False}, style={"height": "220px"})])]),
                                    html.Div(className="card obottom-card obottom-card-correlation", children=[html.Div(className="otkph-chart-header", style={"marginBottom": "10px"}, children=[html.Div(className="otkph-chart-title", style={"fontSize": "13px"}, children=["Camera Correlation"]), html.Div(className="otkph-chart-sub", id="otkph-scatter-sub", children=["Scatter: pick two active cameras"])]), html.Div(style={"display": "flex", "gap": "8px", "marginBottom": "10px"}, children=[dcc.Dropdown(id="otkph-corr-a", options=[], value=None, clearable=False), html.Span(style={"fontSize": "12px", "color": "var(--muted)", "alignSelf": "center"}, children=["vs"]), dcc.Dropdown(id="otkph-corr-b", options=[], value=None, clearable=False)]), html.Div(className="otkph-graph-wrap", children=[dcc.Graph(id="otkph-scatter-graph", figure=_blank_fig(), config={"displayModeBar": False}, style={"height": "190px"})])]),
                                ],
                            ),
                            html.Div(className="card violations-card", style={"marginTop": "0"}, children=[html.Div(className="violations-header", children=[html.Div(className="violations-title", children=["Cameras - Frozen Periods Analysis"]), html.Span(id="otkph-violation-badge", className="badge-ok", children=["OK"])]), html.Table(children=[html.Thead(html.Tr([html.Th("Camera"), html.Th("Value"), html.Th("Time Period"), html.Th("Duration")])), html.Tbody(id="otkph-violations-body")]), html.Div(style={"display": "flex", "justifyContent": "center", "marginTop": "10px"}, children=[html.Button(id="otkph-frozen-view-more-btn", className="btn btn-ghost btn-sm", type="button", n_clicks=0, children=["View more"], style={"display": "none"})]), html.Div(style={"fontSize": "10px", "color": "var(--muted)", "marginTop": "6px"}, children=["Frozen period: same camera temperature within ±0.01°C for more than 3h. Duration follows the active timeline (interruption gaps ignored when toggle is on)."])]),
                        ],
                    ),
                ],
            ),
        ],
    )


__all__ = ["build_otkph_layout"]

