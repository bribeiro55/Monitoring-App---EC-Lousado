from __future__ import annotations

from datetime import date

from dash import dcc, html

from features.monitor.occupation.excel_writer import _load_paths

_TODAY = date.today().isoformat()

_MACHINE_IDS = ["M7900", "M7950", "M7960"]


def make_occupation_button(machine_id: str, position: int, icon_src: str) -> html.Button:
    """Clock icon button that opens the occupation fill modal for this slot."""
    return html.Button(
        className="expand-btn",
        title="Fill Occupation",
        id={"type": "occ-btn", "machine": machine_id, "pos": position},
        n_clicks=0,
        children=[
            html.Img(
                src=icon_src,
                alt="",
                style={"width": "13px", "height": "13px", "display": "block"},
            )
        ],
    )


def make_occupation_modal() -> html.Div:
    """Occupation Fill modal overlay (starts hidden, opened by clock button callbacks)."""
    paths = _load_paths()
    return html.Div(
        id="occ-modal-overlay",
        className="modal-overlay",
        children=[
            dcc.Store(id="occ-slot-store", data={}),
            html.Div(
                className="modal",
                style={"maxWidth": "520px"},
                children=[
                    # Header
                    html.Div(
                        className="modal-header",
                        children=[
                            html.Div(
                                children=[
                                    html.Div(
                                        id="occ-modal-title",
                                        className="modal-title",
                                        children=["Occupation Fill"],
                                    ),
                                    html.Div(
                                        id="occ-modal-subtitle",
                                        className="modal-subtitle",
                                        children=["-"],
                                    ),
                                ]
                            ),
                            html.Button(
                                id="occ-modal-close-btn",
                                className="modal-close",
                                n_clicks=0,
                                children=["✕"],
                            ),
                        ],
                    ),
                    # Body
                    html.Div(
                        style={"padding": "16px 20px", "display": "flex", "flexDirection": "column", "gap": "14px"},
                        children=[
                            # Date picker
                            html.Div(
                                children=[
                                    html.Div(
                                        "Select date(s)",
                                        style={"fontSize": "11px", "color": "var(--muted)", "marginBottom": "6px", "textTransform": "uppercase", "letterSpacing": "0.05em"},
                                    ),
                                    dcc.DatePickerRange(
                                        id="occ-date-picker",
                                        start_date=_TODAY,
                                        end_date=_TODAY,
                                        display_format="DD/MM/YYYY",
                                        style={"fontSize": "13px"},
                                    ),
                                ]
                            ),
                            # Preview section
                            html.Div(
                                id="occ-preview",
                                style={
                                    "background": "var(--surface-2, #1e2130)",
                                    "borderRadius": "6px",
                                    "padding": "10px 12px",
                                    "fontSize": "12px",
                                    "fontFamily": "monospace",
                                    "minHeight": "40px",
                                    "color": "var(--muted)",
                                },
                                children=["Select dates to preview break intervals."],
                            ),
                            # Fill button + status
                            html.Div(
                                style={"display": "flex", "alignItems": "center", "gap": "10px"},
                                children=[
                                    html.Button(
                                        id="occ-fill-btn",
                                        n_clicks=0,
                                        style={
                                            "background": "var(--accent, #F0BA20)",
                                            "color": "#111",
                                            "border": "none",
                                            "borderRadius": "5px",
                                            "padding": "6px 16px",
                                            "fontWeight": "600",
                                            "cursor": "pointer",
                                            "fontSize": "12px",
                                        },
                                        children=["Fill Excel"],
                                    ),
                                    html.Div(
                                        id="occ-fill-status",
                                        style={"fontSize": "12px", "color": "var(--muted)"},
                                        children=[],
                                    ),
                                ],
                            ),
                            # Settings (collapsible)
                            html.Details(
                                style={"borderTop": "1px solid var(--border, #2a2f45)", "paddingTop": "10px"},
                                children=[
                                    html.Summary(
                                        "Excel path settings",
                                        style={"cursor": "pointer", "fontSize": "11px", "color": "var(--muted)", "textTransform": "uppercase", "letterSpacing": "0.05em", "userSelect": "none"},
                                    ),
                                    html.Div(
                                        style={"marginTop": "10px", "display": "flex", "flexDirection": "column", "gap": "8px"},
                                        children=[
                                            *[
                                                html.Div(
                                                    children=[
                                                        html.Div(
                                                            mid,
                                                            style={"fontSize": "11px", "color": "var(--muted)", "marginBottom": "3px"},
                                                        ),
                                                        dcc.Input(
                                                            id=f"occ-path-{mid}",
                                                            value=paths.get(mid, ""),
                                                            type="text",
                                                            style={"width": "100%", "fontSize": "11px", "fontFamily": "monospace"},
                                                            className="test-input",
                                                            debounce=False,
                                                        ),
                                                    ]
                                                )
                                                for mid in _MACHINE_IDS
                                            ],
                                            html.Div(
                                                style={"display": "flex", "alignItems": "center", "gap": "10px", "marginTop": "4px"},
                                                children=[
                                                    html.Button(
                                                        id="occ-save-paths-btn",
                                                        n_clicks=0,
                                                        style={
                                                            "background": "transparent",
                                                            "border": "1px solid var(--muted)",
                                                            "color": "var(--muted)",
                                                            "borderRadius": "4px",
                                                            "padding": "4px 12px",
                                                            "cursor": "pointer",
                                                            "fontSize": "11px",
                                                        },
                                                        children=["Save paths"],
                                                    ),
                                                    html.Div(
                                                        id="occ-paths-status",
                                                        style={"fontSize": "11px", "color": "var(--muted)"},
                                                        children=[],
                                                    ),
                                                ],
                                            ),
                                        ],
                                    ),
                                ],
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )
