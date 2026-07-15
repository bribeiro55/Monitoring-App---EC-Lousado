from __future__ import annotations

import logging
from typing import Callable

from dash import ALL, Input, Output, State, callback_context, no_update
from dash.exceptions import PreventUpdate

_log = logging.getLogger(__name__)


def register_end_test_callbacks(
    app,
    *,
    copy_test_folder: Callable[[str, str], object],
    dest_root: str,
) -> None:

    # ------------------------------------------------------------------ #
    # 1. Open / close the "Test Finished?" confirm modal                   #
    # ------------------------------------------------------------------ #
    @app.callback(
        Output("end-confirm-overlay", "className"),
        Output("end-confirm-slot-store", "data"),
        Output("end-confirm-subtitle", "children"),
        Output("end-confirm-status", "children"),
        Input({"type": "end-btn", "slot": ALL}, "n_clicks"),
        Input("end-confirm-no-btn", "n_clicks"),
        Input("end-confirm-close-btn", "n_clicks"),
        State({"type": "end-btn", "slot": ALL}, "id"),
        State("loaded-logs-store", "data"),
        prevent_initial_call=True,
    )
    def toggle_end_confirm_modal(_end_clicks, _no, _close, _ids, loaded_logs):
        ctx = callback_context
        if not ctx.triggered_id:
            raise PreventUpdate

        triggered = ctx.triggered_id
        if triggered in ("end-confirm-no-btn", "end-confirm-close-btn"):
            return "modal-overlay", {}, no_update, []

        if not isinstance(triggered, dict) or triggered.get("type") != "end-btn":
            raise PreventUpdate

        # Guard: ignore synthetic fires from newly mounted components (n_clicks == 0),
        # e.g. after Refresh recreates the charts grid.
        idx = next((i for i, bid in enumerate(_ids or []) if bid == triggered), None)
        if idx is None:
            raise PreventUpdate
        clicks = _end_clicks[idx] if _end_clicks is not None and idx < len(_end_clicks) else 0
        if not clicks:
            raise PreventUpdate

        slot = triggered.get("slot")
        if not slot:
            raise PreventUpdate

        entry = (loaded_logs or {}).get(slot) or {}
        test_number = entry.get("test_number") or ""
        machine_label, _, pos = slot.partition("|")
        subtitle = f"{machine_label}  ·  Position {pos}" if pos else slot
        if test_number:
            subtitle += f"  ·  Test {test_number}"

        return "modal-overlay open", {"slot": slot}, subtitle, []

    # ------------------------------------------------------------------ #
    # 2. Yes — copy the test folder from prstruh to the archive share      #
    # ------------------------------------------------------------------ #
    @app.callback(
        Output("end-confirm-status", "children", allow_duplicate=True),
        Output("end-confirm-overlay", "className", allow_duplicate=True),
        Input("end-confirm-yes-btn", "n_clicks"),
        State("end-confirm-slot-store", "data"),
        State("loaded-logs-store", "data"),
        background=True,
        running=[
            (Output("end-confirm-yes-btn", "disabled"), True, False),
            (Output("end-confirm-status", "children"), "Copying…", no_update),
        ],
        prevent_initial_call=True,
    )
    def confirm_end_test(n_clicks, slot_data, loaded_logs):
        if not n_clicks:
            raise PreventUpdate

        slot = (slot_data or {}).get("slot")
        if not slot:
            raise PreventUpdate

        entry = (loaded_logs or {}).get(slot) or {}
        log_path = (entry.get("load_debug") or {}).get("log_path")
        if not log_path:
            return "✗ No log file loaded for this position.", no_update

        try:
            result = copy_test_folder(log_path, dest_root)
        except Exception as e:
            _log.exception("Failed to copy test folder for slot %s", slot)
            return f"✗ Copy failed: {e}", no_update

        if result.error:
            return f"✗ Copy failed: {result.error}", no_update

        # Success — close the dialog automatically. On failure, leave it open
        # with the error message so the user can see what went wrong.
        return "✓ Copied to archive.", "modal-overlay"
