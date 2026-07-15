from __future__ import annotations

from dash import dcc, html


def make_end_confirm_modal() -> html.Div:
    """'Test Finished?' confirm modal (starts hidden, opened by End button callbacks)."""
    return html.Div(
        id="end-confirm-overlay",
        className="modal-overlay",
        children=[
            dcc.Store(id="end-confirm-slot-store", data={}),
            html.Div(
                className="modal",
                style={"maxWidth": "380px"},
                children=[
                    html.Div(
                        className="modal-header",
                        children=[
                            html.Div(
                                children=[
                                    html.Div(
                                        id="end-confirm-title",
                                        className="modal-title",
                                        children=["Test Finished?"],
                                    ),
                                    html.Div(
                                        id="end-confirm-subtitle",
                                        className="modal-subtitle",
                                        children=["-"],
                                    ),
                                ]
                            ),
                            html.Button(
                                id="end-confirm-close-btn",
                                className="modal-close",
                                n_clicks=0,
                                children=["✕"],
                            ),
                        ],
                    ),
                    html.Div(
                        style={"padding": "16px 20px", "display": "flex", "flexDirection": "column", "gap": "14px"},
                        children=[
                            html.Div(
                                id="end-confirm-status",
                                style={"fontSize": "12px", "color": "var(--muted)", "minHeight": "18px"},
                                children=[],
                            ),
                            html.Div(
                                className="confirm-actions",
                                children=[
                                    html.Button(
                                        "No",
                                        id="end-confirm-no-btn",
                                        n_clicks=0,
                                        className="confirm-btn confirm-btn-no",
                                    ),
                                    html.Button(
                                        "Yes",
                                        id="end-confirm-yes-btn",
                                        n_clicks=0,
                                        className="confirm-btn confirm-btn-yes",
                                    ),
                                ],
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )
