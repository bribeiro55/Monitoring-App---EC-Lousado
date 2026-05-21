from __future__ import annotations

from dash import html


def make_auto_refresh_toggle() -> html.Div:
    return html.Div(
        className="toggle-wrap",
        children=[
            html.Div(id="auto-refresh-toggle", className="toggle on", n_clicks=0),
            html.Span(className="toggle-label", children=["Auto-refresh"]),
        ],
    )


def make_auto_refresh_banner() -> html.Div:
    return html.Div(
        id="auto-refresh-banner",
        className="auto-refresh-banner hidden",
        children=[
            html.Span(id="auto-refresh-banner-text", children=[""]),
            html.Button(
                id="auto-refresh-dismiss-btn",
                className="auto-refresh-dismiss-btn",
                n_clicks=0,
                children=["Dismiss"],
            ),
        ],
    )
