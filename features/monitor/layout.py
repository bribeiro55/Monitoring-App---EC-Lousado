from __future__ import annotations

from dash import html


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


def make_modal_icon_button(btn_id: str, icon_src: str, title: str) -> html.Button:
    return html.Button(
        id=btn_id,
        className="modal-icon-btn",
        title=title,
        n_clicks=0,
        children=[html.Img(src=icon_src, alt="", style={"width": "14px", "height": "14px"})],
    )
