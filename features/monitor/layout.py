from __future__ import annotations

from typing import Callable, List

from dash import dcc, html

from features.monitor.auto_refresh.layout import make_auto_refresh_banner, make_auto_refresh_toggle
from features.monitor.figures import _blank_figure
from features.monitor.icons import _ICON_CSV, _ICON_DOWNLOAD, ICON_SYNC


def make_empty_state(message: str = "No test assigned", icon_src: str | None = None) -> html.Div:
    return html.Div(
        className="empty-state",
        children=[
            html.Img(
                src=icon_src,
                alt="",
                style={"width": "24px", "height": "24px", "opacity": "0.3"},
            ),
            html.Span(message),
        ],
    )


def make_expand_button(slot_key: str, icon_src: str | None = None) -> html.Button:
    return html.Button(
        className="expand-btn",
        title="Expand",
        id={"type": "expand-btn", "slot": slot_key},
        children=[
            html.Img(
                src=icon_src,
                alt="",
                style={"width": "13px", "height": "13px", "display": "block"},
            )
        ],
    )


def _machine_input_slug(machine_label: str) -> str:
    return machine_label.replace(" ", "-").lower()


def _input_id(machine_label: str, position: int) -> str:
    return f"test-input-{_machine_input_slug(machine_label)}-pos{position}"


def build_monitor_layout(machines: List[str], input_id_fn: Callable[[str, int], str]) -> html.Div:
    return html.Div(
        id="monitor-page",
        className="tab-page",
        children=[
            html.Div(
                className="main",
                children=[
                    html.Div(
                        style={"display": "flex", "alignItems": "center", "gap": "12px"},
                        children=[
                            html.Div(className="section-label", children=["Current Tests Running"]),
                            html.Div(className="divider"),
                            html.Div(
                                className="toggle-wrap",
                                style={"display": "flex", "alignItems": "center", "gap": "6px", "marginBottom": "10px"},
                                children=[
                                    html.Div(id="sync-enabled-toggle", className="toggle on", n_clicks=0),
                                    html.Span("Auto-sync", className="toggle-label",
                                              style={"fontSize": "11px"}),
                                ],
                            ),
                            html.Div(
                                id="sync-status-text",
                                style={"fontSize": "11px", "color": "var(--muted)", "marginBottom": "10px"},
                            ),
                        ],
                    ),
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
                                                children=[html.Div(className="machine-indicator"), machines[i]],
                                            ),
                                            html.Div(
                                                className="positions-row",
                                                children=[
                                                    html.Div(
                                                        className="position-field",
                                                        children=[
                                                            html.Div(className="position-label", children=["Position 1"]),
                                                            dcc.Input(
                                                                id=input_id_fn(machines[i], 1),
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
                                                                id=input_id_fn(machines[i], 2),
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
                                    for i in range(len(machines))
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
                                style={"fontSize": "11px", "color": "var(--muted)", "marginLeft": "8px"},
                            ),
                            dcc.Store(id="active-steps-store", data=["all"]),
                            dcc.Store(id="ignore-stopped-store", data=False),
                            dcc.Store(id="loaded-logs-store", data={}),
                            dcc.Store(id="modal-open-store", data=False),
                            dcc.Store(id="modal-selection-store", data={}),
                            dcc.Store(id="png-export-state", data=0),
                            dcc.Store(id="sync-enabled-store", data=True),
                            dcc.Download(id="modal-csv-download"),
                            dcc.Interval(id="sync-poll-interval", interval=10_000, n_intervals=0),
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
                    html.Div(
                        id="registry-modal-overlay",
                        className="modal-overlay",
                        children=[
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
                                    html.Div(id="registry-modal-body"),
                                    html.Div(
                                        style={
                                            "display": "flex",
                                            "gap": "8px",
                                            "alignItems": "center",
                                            "paddingTop": "12px",
                                            "borderTop": "1px solid var(--border)",
                                        },
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
                            ),
                        ],
                    ),
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
                                                    make_modal_icon_button("modal-export-png-btn", _ICON_DOWNLOAD, "Export PNG"),
                                                    make_modal_icon_button("modal-export-csv-btn", _ICON_CSV, "Export CSV"),
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
    )


def make_modal_icon_button(btn_id: str, icon_src: str, title: str) -> html.Button:
    return html.Button(
        id=btn_id,
        className="modal-icon-btn",
        title=title,
        n_clicks=0,
        children=[html.Img(src=icon_src, alt="", style={"width": "14px", "height": "14px"})],
    )
