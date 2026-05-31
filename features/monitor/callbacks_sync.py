from __future__ import annotations

import platform
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


def _build_sync_diagnostics(state, source_root: str) -> list:
    import os
    on_windows = platform.system() == "Windows"
    conn_label = "Windows · local share" if on_windows else "Linux · SMB + credentials"
    source_ok = os.path.isdir(source_root) if on_windows else None  # SMB reachability checked via sync results

    source_color = "var(--muted)"
    if on_windows:
        source_color = "#34C47C" if source_ok else "#E84040"

    rows = [
        html.Div(
            style={"display": "flex", "alignItems": "center", "gap": "8px", "marginBottom": "6px"},
            children=[
                html.Span("Source:", style={"color": "var(--muted)", "minWidth": "52px"}),
                html.Span(source_root, style={"fontFamily": "'DM Mono', monospace", "color": source_color}),
                html.Span(f"[{conn_label}]", style={"color": "var(--muted)", "marginLeft": "4px"}),
            ],
        )
    ]

    if state is None or not state.results:
        rows.append(html.Span("No sync results yet.", style={"color": "var(--muted)"}))
        return rows

    if state.error:
        rows.append(
            html.Div(
                style={"color": "#E84040", "marginBottom": "4px"},
                children=[f"⚠  Sync error: {state.error}"],
            )
        )

    for r in state.results:
        tn = r.test_number
        if r.error:
            icon, detail, color = "✗", f"error: {r.error}", "#E84040"
        elif not r.found:
            icon, detail, color = "–", "not found on share", "var(--muted)"
        else:
            res = r.result
            detail = f"{res.copied} copied · {res.unchanged} unchanged · {res.deleted} deleted"
            if res.errors:
                detail += f" · {res.errors} file error(s)"
            icon, color = "✓", "#34C47C"

        rows.append(
            html.Div(
                style={"display": "flex", "alignItems": "center", "gap": "8px", "padding": "1px 0"},
                children=[
                    html.Span(icon, style={"color": color, "width": "12px", "flexShrink": "0"}),
                    html.Span(tn, style={"fontFamily": "'DM Mono', monospace", "minWidth": "80px"}),
                    html.Span(detail, style={"color": "var(--muted)"}),
                ],
            )
        )

    return rows


# --- registration ------------------------------------------------------------

def register_sync_callbacks(app, *, registry, scheduler, SYNC_SOURCE_ROOT) -> None:

    @app.callback(
        Output("sync-status-text", "children"),
        Output("sync-last-seen-time-store", "data"),
        Output("auto-refresh-trigger-store", "data"),
        Output("sync-diagnostics", "children"),
        Input("sync-poll-interval", "n_intervals"),
        State("sync-last-seen-time-store", "data"),
        State("auto-refresh-trigger-store", "data"),
        State("auto-refresh-enabled-store", "data"),
        prevent_initial_call=True,
    )
    def poll_sync_state(_n, last_seen, trigger_count, ar_enabled):
        state = scheduler.get_state()
        status_text = _build_status_text(state, SYNC_SOURCE_ROOT)
        diagnostics = _build_sync_diagnostics(state, SYNC_SOURCE_ROOT)

        current_time_str = state.last_sync_time.isoformat() if state.last_sync_time else None

        new_trigger = int(trigger_count or 0)
        if current_time_str is not None and current_time_str != last_seen and bool(ar_enabled):
            new_trigger += 1

        return status_text, current_time_str, new_trigger, diagnostics

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
        Output("sync-status-text", "children", allow_duplicate=True),
        Input("sync-now-btn", "n_clicks"),
        prevent_initial_call=True,
    )
    def trigger_sync_now(_n_clicks):
        scheduler.trigger_now()
        return "Syncing now..."

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
