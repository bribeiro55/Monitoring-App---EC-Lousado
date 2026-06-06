from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Callable, List, Optional

from dash import ALL, Input, Output, State, callback_context, html, no_update
from dash.exceptions import PreventUpdate

from features.monitor.occupation.excel_writer import (
    dates_in_range,
    detect_breaks,
    fill_occupation,
    save_paths,
    _load_paths,
)

_log = logging.getLogger(__name__)

_POSITIONS = [1, 2]


def register_occupation_callbacks(
    app,
    *,
    MACHINES: List[str],
    DISPLAY_TO_MACHINE_ID: dict,
    input_id_fn: Callable[[str, int], str],
    find_log_path: Callable[[str], Optional[str]],
    cached_parse_log: Callable,
) -> None:

    # Build (machine_label, position) → test input id mapping once
    _slot_input_ids = [
        (m, p, input_id_fn(m, p))
        for m in MACHINES
        for p in _POSITIONS
    ]

    # ------------------------------------------------------------------ #
    # 1. Open / close the occupation modal                                 #
    # ------------------------------------------------------------------ #
    @app.callback(
        Output("occ-modal-overlay", "className"),
        Output("occ-slot-store", "data"),
        Output("occ-modal-subtitle", "children"),
        Input({"type": "occ-btn", "machine": ALL, "pos": ALL}, "n_clicks"),
        Input("occ-modal-close-btn", "n_clicks"),
        [State(tid, "value") for _, _, tid in _slot_input_ids],
        prevent_initial_call=True,
    )
    def toggle_occ_modal(btn_clicks, _close, *test_values):
        ctx = callback_context
        if not ctx.triggered_id:
            raise PreventUpdate

        # Close path
        if ctx.triggered_id == "occ-modal-close-btn":
            return "modal-overlay", no_update, no_update

        # Open path — triggered by one of the occ-btn pattern-matched buttons
        tid = ctx.triggered_id
        if not isinstance(tid, dict) or tid.get("type") != "occ-btn":
            raise PreventUpdate

        machine_id: str = tid["machine"]
        position: int = tid["pos"]

        # Find the corresponding test input value
        test_number = ""
        for i, (m, p, _) in enumerate(_slot_input_ids):
            if DISPLAY_TO_MACHINE_ID.get(m) == machine_id and p == position:
                test_number = (test_values[i] or "").strip()
                break

        slot_data = {
            "machine_id": machine_id,
            "position": position,
            "test_number": test_number,
        }
        subtitle = f"{machine_id}  ·  Position {position}"
        if test_number:
            subtitle += f"  ·  Test {test_number}"
        return "modal-overlay open", slot_data, subtitle

    # ------------------------------------------------------------------ #
    # 2. Update break preview when dates or slot changes                   #
    # ------------------------------------------------------------------ #
    @app.callback(
        Output("occ-preview", "children"),
        Input("occ-date-picker", "start_date"),
        Input("occ-date-picker", "end_date"),
        Input("occ-slot-store", "data"),
        prevent_initial_call=True,
    )
    def update_occ_preview(start_str, end_str, slot_data):
        if not slot_data or not slot_data.get("test_number"):
            return html.Span("No test loaded for this slot.", style={"color": "var(--muted)"})
        if not start_str or not end_str:
            return html.Span("Select dates to preview.", style={"color": "var(--muted)"})

        test_number: str = slot_data["test_number"]
        position: int = slot_data["position"]
        machine_id: str = slot_data["machine_id"]

        df = _get_df(test_number, position, find_log_path, cached_parse_log)
        if df is None:
            return html.Span(f"Log not found for test {test_number}.", style={"color": "var(--muted)"})

        start = _parse_date(start_str)
        end = _parse_date(end_str)
        if start is None or end is None:
            return html.Span("Invalid date selection.", style={"color": "var(--muted)"})

        rows = []
        for d in dates_in_range(start, end):
            break_str = detect_breaks(df, d)
            label = d.strftime("%d/%m/%Y")
            if break_str:
                rows.append(html.Div([
                    html.Span(label, style={"color": "var(--fg, #e0e4f0)", "marginRight": "8px"}),
                    html.Span(break_str.replace("\n", "  |  "), style={"color": "#F0BA20"}),
                ], style={"marginBottom": "4px"}))
            else:
                rows.append(html.Div([
                    html.Span(label, style={"color": "var(--fg, #e0e4f0)", "marginRight": "8px"}),
                    html.Span("No breaks detected", style={"color": "var(--muted)"}),
                ], style={"marginBottom": "4px"}))

        return rows if rows else html.Span("No dates in range.", style={"color": "var(--muted)"})

    # ------------------------------------------------------------------ #
    # 3. Fill Excel                                                        #
    # ------------------------------------------------------------------ #
    @app.callback(
        Output("occ-fill-status", "children"),
        Input("occ-fill-btn", "n_clicks"),
        State("occ-date-picker", "start_date"),
        State("occ-date-picker", "end_date"),
        State("occ-slot-store", "data"),
        prevent_initial_call=True,
    )
    def fill_excel_cb(_n, start_str, end_str, slot_data):
        if not _n:
            raise PreventUpdate
        if not slot_data or not slot_data.get("test_number"):
            return _status("No test loaded for this slot.", error=True)
        if not start_str or not end_str:
            return _status("Select dates first.", error=True)

        test_number: str = slot_data["test_number"]
        machine_id: str = slot_data["machine_id"]
        position: int = slot_data["position"]

        start = _parse_date(start_str)
        end = _parse_date(end_str)
        if start is None or end is None:
            return _status("Invalid date selection.", error=True)

        df = _get_df(test_number, position, find_log_path, cached_parse_log)
        if df is None:
            return _status(f"Log not found for test {test_number}.", error=True)

        _log.info("Occupation fill: %s pos%d test=%s dates=%s..%s", machine_id, position, test_number, start, end)
        msg = fill_occupation(machine_id, position, dates_in_range(start, end), df)
        is_error = msg.lower().startswith("error") or "not found" in msg.lower()
        return _status(msg, error=is_error)

    # ------------------------------------------------------------------ #
    # 4. Save Excel path settings                                          #
    # ------------------------------------------------------------------ #
    @app.callback(
        Output("occ-paths-status", "children"),
        Input("occ-save-paths-btn", "n_clicks"),
        State("occ-path-M7900", "value"),
        State("occ-path-M7950", "value"),
        State("occ-path-M7960", "value"),
        prevent_initial_call=True,
    )
    def save_occ_paths_cb(_n, p7900, p7950, p7960):
        if not _n:
            raise PreventUpdate
        paths = {"M7900": p7900 or "", "M7950": p7950 or "", "M7960": p7960 or ""}
        try:
            save_paths(paths)
        except ValueError as exc:
            return _status(str(exc), error=True)
        return _status("Paths saved.", error=False)


# --------------------------------------------------------------------------- #
# Helpers                                                                       #
# --------------------------------------------------------------------------- #

def _parse_date(s: str) -> Optional[date]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s).date()
    except Exception:
        return None


def _get_df(test_number, position, find_log_path, cached_parse_log):
    """Return the parsed DataFrame for the given test, filtered to the given position."""
    import pandas as pd
    path = find_log_path(test_number)
    if not path:
        return None
    try:
        df = cached_parse_log(path)
    except Exception as exc:
        _log.error("Failed to parse log for test %s: %s", test_number, exc)
        return None
    if df is None or df.empty:
        return None
    if "position" in df.columns:
        df = df[df["position"] == position]
    return df


def _status(msg: str, error: bool = False) -> html.Span:
    color = "#E84040" if error else "#34C47C"
    return html.Span(msg, style={"color": color, "fontSize": "12px"})
