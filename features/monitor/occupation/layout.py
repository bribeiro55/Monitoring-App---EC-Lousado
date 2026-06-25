from __future__ import annotations

from datetime import date

from dash import dcc, html

_TODAY = date.today().isoformat()


def make_occupation_button(machine_id: str, position: int, icon_src: str) -> html.Button:
    """Clock icon button that opens the occupation breaks modal for this slot."""
    return html.Button(
        className="expand-btn",
        title="Occupation Breaks",
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
    """Occupation Breaks modal overlay (starts hidden, opened by clock button callbacks)."""
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
                                        children=["Occupation Breaks"],
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
                            # Copy-all row
                            html.Div(
                                style={"display": "flex", "alignItems": "center", "gap": "8px"},
                                children=[
                                    html.Div(
                                        "Copy all days",
                                        style={"fontSize": "11px", "color": "var(--muted)"},
                                    ),
                                    dcc.Clipboard(
                                        id="occ-copy-all-clipboard",
                                        content="",
                                        style={"fontSize": "13px", "color": "var(--muted)", "cursor": "pointer"},
                                    ),
                                ],
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
                        ],
                    ),
                ],
            ),
        ],
    )
