from __future__ import annotations

from datetime import datetime
from typing import Optional

from dash import ALL, Input, Output, State, callback_context, no_update
from dash.exceptions import PreventUpdate

from dash import html


# --- helpers -----------------------------------------------------------------

def _relative_time(dt: Optional[datetime]) -> str:
    if dt is None:
        return "Never"
    delta = int((datetime.now() - dt).total_seconds())
    if delta < 5:
        return "just now"
    if delta < 60:
        return f"{delta}s ago"
    if delta < 3600:
        return f"{delta // 60} min ago"
    return dt.strftime("%H:%M")


def _time_until(dt: Optional[datetime]) -> str:
    if dt is None:
        return "—"
    delta = int((dt - datetime.now()).total_seconds())
    if delta <= 0:
        return "now"
    if delta < 60:
        return f"in {delta}s"
    return f"in {delta // 60} min"


def _build_status_text(state, source_root: str) -> str:
    if state is None:
        return "Last sync: Never · Next: —"
    running = state.running
    enabled = state.enabled
    last_txt = "Syncing now..." if running else _relative_time(state.last_sync_time)
    next_txt = _time_until(state.next_sync_time) if enabled else "paused"
    return f"Last sync: {last_txt} · Next: {next_txt}"



def _build_registry_body(entries):
    active = [e for e in entries if e.get("status") == "active"]
    planned = [e for e in entries if e.get("status") == "planned"]

    def _row(entry):
        tn = entry["test_number"]
        status = entry.get("status", "active")
        promote_label = "→ Planned" if status == "active" else "→ Active"
        return html.Div(
            style={"display": "flex", "alignItems": "center", "gap": "8px",
                   "padding": "4px 0", "borderBottom": "1px solid var(--border)"},
            children=[
                html.Span(tn, style={"fontFamily": "'DM Mono', monospace",
                                     "fontSize": "13px", "flex": "1"}),
                html.Button(
                    promote_label,
                    id={"type": "registry-set-status", "index": tn},
                    n_clicks=0,
                    className="modal-icon-btn",
                    style={"fontSize": "11px"},
                ),
                html.Button(
                    "✕",
                    id={"type": "registry-remove", "index": tn},
                    n_clicks=0,
                    className="modal-close",
                    style={"fontSize": "11px"},
                ),
            ],
        )

    def _section(title, rows):
        return html.Div(
            style={"flex": "1", "minWidth": "200px"},
            children=[
                html.Div(title, style={"fontSize": "11px", "color": "var(--muted)",
                                       "fontWeight": "600", "marginBottom": "8px",
                                       "textTransform": "uppercase", "letterSpacing": "0.04em"}),
                html.Div(
                    [_row(e) for e in rows] if rows
                    else [html.Span("—", style={"fontSize": "12px", "color": "var(--muted)"})],
                ),
            ],
        )

    return [html.Div(
        style={"display": "flex", "gap": "24px", "padding": "16px 0", "flexWrap": "wrap"},
        children=[_section("Active Tests", active), _section("Planned Tests", planned)],
    )]


# --- registration ------------------------------------------------------------

def register_sync_callbacks(app, *, registry, scheduler, SYNC_SOURCE_ROOT) -> None:

    @app.callback(
        Output("sync-status-text", "children"),
        Input("sync-poll-interval", "n_intervals"),
    )
    def poll_sync_state(_n):
        return _build_status_text(scheduler.get_state(), SYNC_SOURCE_ROOT)

    @app.callback(
        Output("registry-modal-body", "children"),
        Output("registry-open-btn", "className"),
        Input("sync-poll-interval", "n_intervals"),
    )
    def poll_registry(_n):
        entries = registry.get_all()
        btn_class = "icon-btn active" if entries else "icon-btn"
        return _build_registry_body(entries), btn_class

    @app.callback(
        Output("sync-enabled-toggle", "className"),
        Output("sync-enabled-store", "data"),
        Input("sync-enabled-toggle", "n_clicks"),
        State("sync-enabled-store", "data"),
        prevent_initial_call=True,
    )
    def toggle_sync_enabled(_n_clicks, current):
        new_val = not bool(current)
        scheduler.set_enabled(new_val)
        return "toggle on" if new_val else "toggle", new_val

    @app.callback(
        Output("registry-modal-overlay", "className"),
        Input("registry-open-btn", "n_clicks"),
        Input("registry-modal-close-btn", "n_clicks"),
        prevent_initial_call=True,
    )
    def toggle_registry_modal(_open, _close):
        ctx = callback_context
        if not ctx.triggered_id:
            raise PreventUpdate
        if ctx.triggered_id == "registry-open-btn":
            return "modal-overlay open"
        return "modal-overlay"

    @app.callback(
        Output("registry-add-input", "value"),
        Output("registry-modal-body", "children", allow_duplicate=True),
        Output("registry-open-btn", "className", allow_duplicate=True),
        Input("registry-add-btn", "n_clicks"),
        Input("registry-add-input", "n_submit"),
        State("registry-add-input", "value"),
        prevent_initial_call=True,
    )
    def add_test(n_clicks, n_submit, test_number):
        if not test_number or not test_number.strip():
            raise PreventUpdate
        registry.add(test_number.strip(), status="active")
        entries = registry.get_all()
        btn_class = "icon-btn active" if entries else "icon-btn"
        return "", _build_registry_body(entries), btn_class

    @app.callback(
        Output("registry-modal-body", "children", allow_duplicate=True),
        Output("registry-open-btn", "className", allow_duplicate=True),
        Input({"type": "registry-remove", "index": ALL}, "n_clicks"),
        State({"type": "registry-remove", "index": ALL}, "id"),
        prevent_initial_call=True,
    )
    def remove_test(n_clicks_list, id_list):
        ctx = callback_context
        if not ctx.triggered_id or not isinstance(ctx.triggered_id, dict):
            raise PreventUpdate
        triggered_index = ctx.triggered_id.get("index")
        idx = next((i for i, bid in enumerate(id_list or []) if bid.get("index") == triggered_index), None)
        if idx is None or not (n_clicks_list and n_clicks_list[idx]):
            raise PreventUpdate
        registry.remove(triggered_index)
        entries = registry.get_all()
        btn_class = "icon-btn active" if entries else "icon-btn"
        return _build_registry_body(entries), btn_class

    @app.callback(
        Output("registry-modal-body", "children", allow_duplicate=True),
        Input({"type": "registry-set-status", "index": ALL}, "n_clicks"),
        State({"type": "registry-set-status", "index": ALL}, "id"),
        prevent_initial_call=True,
    )
    def set_test_status(n_clicks_list, id_list):
        ctx = callback_context
        if not ctx.triggered_id or not isinstance(ctx.triggered_id, dict):
            raise PreventUpdate
        triggered_index = ctx.triggered_id.get("index")
        idx = next((i for i, bid in enumerate(id_list or []) if bid.get("index") == triggered_index), None)
        if idx is None or not (n_clicks_list and n_clicks_list[idx]):
            raise PreventUpdate
        entries = registry.get_all()
        current_status = next((e["status"] for e in entries if e["test_number"] == triggered_index), "active")
        new_status = "planned" if current_status == "active" else "active"
        registry.set_status(triggered_index, new_status)
        return _build_registry_body(registry.get_all())
