from __future__ import annotations

from dash import dcc, html

from features.analysis.figures import _blank_figure


def build_analysis_layout() -> html.Div:
    return html.Div(
        className="analysis-page-inner",
        children=[
            html.Div(
                className="card controls-bar analysis-controls",
                style={"marginBottom": "20px"},
                children=[
                    html.Div(
                        className="controls-group",
                        children=[
                            html.Span(className="ctrl-label", children=["STEP FILTER"]),
                            html.Div(
                                className="step-pills",
                                id="analysis-step-pills",
                                children=[
                                    html.Button(
                                        className="step-pill all-pill active",
                                        id={"type": "analysis-step-pill", "step": "all"},
                                        n_clicks=0,
                                        children=["All"],
                                    ),
                                    *[
                                        html.Button(
                                            className="step-pill",
                                            id={"type": "analysis-step-pill", "step": s},
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
                        className="controls-group",
                        children=[
                            html.Span(className="ctrl-label", children=["NORMALISE X"]),
                            html.Div(
                                className="toggle-wrap",
                                id="analysis-norm-wrap",
                                children=[
                                    html.Div(id="analysis-norm-toggle", className="toggle", n_clicks=0),
                                    html.Span(className="toggle-label", style={"fontSize": "12px"}, children=["Align step start"]),
                                ],
                            ),
                        ],
                    ),
                    html.Div(className="divider"),
                    html.Div(
                        className="toggle-wrap",
                        id="analysis-ignore-wrap",
                        children=[
                            html.Div(id="analysis-ignore-toggle", className="toggle", n_clicks=0),
                            html.Span(className="toggle-label", children=["Ignore when machine stopped"]),
                        ],
                    ),
                    html.Div(
                        className="variable-filter",
                        style={"marginLeft": "auto"},
                        children=[
                            html.Span(className="ctrl-label", children=["VARIABLE"]),
                            dcc.Dropdown(
                                id="analysis-variable-dropdown",
                                options=[
                                    {"label": "Temperature", "value": "temperature"},
                                    {"label": "Load", "value": "load"},
                                    {"label": "Inflation Pressure", "value": "inflation_pressure"},
                                    {"label": "Room Temperature", "value": "room_temperature"},
                                    {"label": "Speed", "value": "speed"},
                                    {"label": "Torque", "value": "torque"},
                                    {"label": "Deflection", "value": "deflection"},
                                ],
                                value="temperature",
                                clearable=False,
                                style={"width": "220px"},
                            ),
                        ],
                    ),
                ],
            ),
            html.Div(
                className="analysis-layout",
                children=[
                    html.Div(
                        className="sidebar",
                        children=[
                            html.Div(
                                className="card sidebar-card",
                                children=[
                                    html.Div(
                                        className="sidebar-title",
                                        children=["Compare Tests"],
                                    ),
                                    html.Div(id="analysis-selected-tests"),
                                    html.Div(
                                        className="add-test-row",
                                        children=[
                                            dcc.Input(
                                                id="analysis-test-input",
                                                type="text",
                                                placeholder="Test #",
                                                className="test-input",
                                                debounce=False,
                                            ),
                                            html.Button("Add", id="analysis-add-test-btn", className="btn btn-primary", n_clicks=0),
                                        ],
                                    ),
                                ],
                            ),
                            html.Div(
                                className="card sidebar-card filter-card",
                                children=[
                                    html.Div(
                                        className="sidebar-title",
                                        style={"marginBottom": "10px"},
                                        children=[
                                            "Data Filters",
                                            html.Span(
                                                id="analysis-filter-badge",
                                                style={
                                                    "display": "none",
                                                    "marginLeft": "auto",
                                                    "background": "var(--gold)",
                                                    "color": "#fff",
                                                    "borderRadius": "20px",
                                                    "padding": "1px 7px",
                                                    "fontSize": "10px",
                                                    "fontWeight": 600,
                                                    "fontFamily": "DM Mono, monospace",
                                                },
                                            ),
                                        ],
                                    ),
                                    html.Div(
                                        id="analysis-filter-multi-notice",
                                        className="filter-notice",
                                        style={"display": "none"},
                                        children=["Available when analysing a single test."],
                                    ),
                                    html.Div(
                                        id="analysis-filter-body",
                                        children=[
                                            html.Div(
                                                className="filter-section",
                                                children=[
                                                    html.Div("Variable filters", className="filter-section-label"),
                                                    html.Div(id="analysis-variable-filters-ui"),
                                                    html.Button(
                                                        "+ Add variable filter",
                                                        id="analysis-add-var-filter-btn",
                                                        className="btn btn-ghost btn-sm",
                                                        style={"width": "100%", "marginTop": "6px", "justifyContent": "center"},
                                                        n_clicks=0,
                                                        type="button",
                                                    ),
                                                ],
                                            ),
                                            html.Div(
                                                className="filter-section",
                                                children=[
                                                    html.Div("Time filter", className="filter-section-label"),
                                                    html.Div(
                                                        className="filter-mode-pills",
                                                        children=[
                                                            html.Button("All", id="analysis-filter-time-all", className="filter-mode-pill active", n_clicks=0),
                                                            html.Button("After", id="analysis-filter-time-after", className="filter-mode-pill", n_clicks=0),
                                                            html.Button("Before", id="analysis-filter-time-before", className="filter-mode-pill", n_clicks=0),
                                                            html.Button("Between", id="analysis-filter-time-between", className="filter-mode-pill", n_clicks=0),
                                                        ],
                                                    ),
                                                    html.Div(
                                                        id="analysis-filter-time-inputs",
                                                        style={"display": "none"},
                                                        children=[
                                                            html.Div(
                                                                className="filter-input-row",
                                                                children=[
                                                                    html.Label(id="analysis-filter-time-label-a", children=["After"]),
                                                                    dcc.DatePickerSingle(
                                                                        id="analysis-filter-time-date-a",
                                                                        className="filter-datetime",
                                                                        display_format="YYYY-MM-DD",
                                                                        placeholder="YYYY-MM-DD",
                                                                    ),
                                                                    dcc.Input(
                                                                        id="analysis-filter-time-time-a",
                                                                        type="text",
                                                                        value="00:00",
                                                                        className="filter-time",
                                                                        debounce=False,
                                                                        placeholder="00:00",
                                                                        maxLength=5,
                                                                    ),
                                                                ],
                                                            ),
                                                            html.Div(
                                                                id="analysis-filter-time-row-b",
                                                                className="filter-input-row",
                                                                style={"display": "none"},
                                                                children=[
                                                                    html.Label("To"),
                                                                    dcc.DatePickerSingle(
                                                                        id="analysis-filter-time-date-b",
                                                                        className="filter-datetime",
                                                                        display_format="YYYY-MM-DD",
                                                                        placeholder="YYYY-MM-DD",
                                                                    ),
                                                                    dcc.Input(
                                                                        id="analysis-filter-time-time-b",
                                                                        type="text",
                                                                        value="23:59",
                                                                        className="filter-time",
                                                                        debounce=False,
                                                                        placeholder="23:59",
                                                                        maxLength=5,
                                                                    ),
                                                                ],
                                                            ),
                                                        ],
                                                    ),
                                                ],
                                            ),
                                            html.Button(
                                                "Reset all filters",
                                                id="analysis-filter-reset-btn",
                                                className="filter-reset",
                                                n_clicks=0,
                                                type="button",
                                            ),
                                        ],
                                    ),
                                ],
                            ),
                            html.Div(
                                className="card sidebar-card",
                                children=[
                                    html.Div(className="sidebar-title", children=["Limits"]),
                                    html.Div(
                                        className="analysis-band-limits",
                                        children=[
                                            html.Div(
                                                className="band-limit-field",
                                                children=[
                                                    html.Label("Upper limit", className="band-limit-label"),
                                                    dcc.Input(
                                                        id="analysis-upper-limit",
                                                        type="number",
                                                        className="test-input band-limit-input",
                                                        debounce=True,
                                                        placeholder="Vacant",
                                                    ),
                                                ],
                                            ),
                                            html.Div(
                                                className="band-limit-field",
                                                children=[
                                                    html.Label("Lower limit", className="band-limit-label"),
                                                    dcc.Input(
                                                        id="analysis-lower-limit",
                                                        type="number",
                                                        className="test-input band-limit-input",
                                                        debounce=True,
                                                        placeholder="Vacant",
                                                    ),
                                                ],
                                            ),
                                            html.P(
                                                className="band-limit-hint",
                                                children=[
                                                    "Violations show only the first point where the signal "
                                                    "leaves the band (above upper or below lower)."
                                                ],
                                            ),
                                        ],
                                    ),
                                ],
                            ),
                            html.Div(
                                className="card sidebar-card",
                                children=[
                                    html.Div(className="sidebar-title", children=["Test Summary"]),
                                    html.Div(id="analysis-summary-table", style={"overflowX": "auto"}),
                                ],
                            ),
                        ],
                    ),
                    html.Div(
                        className="analysis-main-column",
                        children=[
                            html.Div(
                                className="card analysis-main-card",
                                style={"marginBottom": "16px"},
                                children=[
                                    html.Div(
                                        className="analysis-chart-header",
                                        children=[
                                            html.Div(
                                                children=[
                                                    html.Div(id="analysis-chart-title", className="analysis-chart-title"),
                                                    html.Div(id="analysis-chart-sub", className="analysis-chart-sub"),
                                                ]
                                            ),
                                            html.Div(
                                                style={"display": "flex", "gap": "8px"},
                                                children=[
                                                    html.Button(
                                                        id="analysis-export-csv-btn",
                                                        className="btn btn-ghost",
                                                        n_clicks=0,
                                                        children=["Export CSV"],
                                                    ),
                                                ],
                                            ),
                                        ],
                                    ),
                                    html.Div(
                                        className="analysis-chart-wrap",
                                        children=[
                                            dcc.Graph(
                                                id="analysis-main-graph",
                                                figure=_blank_figure(),
                                                config={"displayModeBar": False},
                                                style={"height": "340px"},
                                            )
                                        ],
                                    ),
                                    html.Div(id="analysis-legend", className="analysis-legend"),
                                ],
                            ),
                            html.Div(
                                className="dist-grid",
                                children=[
                                    html.Div(
                                        className="card dist-card",
                                        children=[
                                            html.Div(className="section-label", style={"marginBottom": "0"}, children=["Distribution"]),
                                            html.Div(
                                                className="dist-chart-wrap",
                                                children=[
                                                    dcc.Graph(
                                                        id="analysis-dist-graph",
                                                        figure=_blank_figure(),
                                                        config={"displayModeBar": False},
                                                        style={"height": "200px"},
                                                    )
                                                ],
                                            ),
                                        ],
                                    ),
                                    html.Div(
                                        className="card dist-card",
                                        children=[
                                            html.Div(
                                                className="section-label",
                                                style={"marginBottom": "0"},
                                                children=["Step-avg heatmap"],
                                            ),
                                            html.Div(
                                                className="dist-chart-wrap",
                                                children=[
                                                    dcc.Graph(
                                                        id="analysis-step-graph",
                                                        figure=_blank_figure(),
                                                        config={"displayModeBar": False},
                                                        style={"height": "200px"},
                                                    )
                                                ],
                                            ),
                                        ],
                                    ),
                                ],
                            ),
                            html.Div(
                                className="card violations-card",
                                children=[
                                    html.Div(
                                        className="violations-header",
                                        children=[
                                            html.Div(className="violations-title", children=["Limit Violations"]),
                                            html.Span(id="analysis-violation-badge", className="badge-ok", children=["OK"]),
                                        ],
                                    ),
                                    html.Div(id="analysis-violations-table"),
                                    html.Div(
                                        id="analysis-violations-view-more-wrap",
                                        style={"display": "none", "marginTop": "10px", "textAlign": "center"},
                                        children=[
                                            html.Button(
                                                id="analysis-violations-view-more-btn",
                                                className="btn btn-ghost btn-sm",
                                                n_clicks=0,
                                                type="button",
                                                children=["View more"],
                                            ),
                                        ],
                                    ),
                                ],
                            ),
                        ],
                    ),
                ],
            ),
            dcc.Store(id="analysis-active-steps-store", data=["all"]),
            dcc.Store(id="analysis-ignore-stopped-store", data=False),
            dcc.Store(id="analysis-normalize-store", data=False),
            dcc.Store(id="analysis-tests-store", data=[]),
            dcc.Store(id="analysis-data-store", data={}),
            dcc.Store(id="analysis-limits-store", data={"upper": None, "lower": None}),
            dcc.Store(id="analysis-limits-by-variable-store", data={}),
            dcc.Store(id="analysis-limits-prev-var", data="temperature"),
            dcc.Store(id="analysis-violations-expanded-store", data=False),
            dcc.Store(
                id="analysis-data-filters-store",
                data={
                    "variable_filters": [],
                    "time_mode": "all",
                    "time_date_a": None,
                    "time_date_b": None,
                    "time_time_a": "00:00",
                    "time_time_b": "23:59",
                },
            ),
            dcc.Download(id="analysis-csv-download"),
        ],
    )
