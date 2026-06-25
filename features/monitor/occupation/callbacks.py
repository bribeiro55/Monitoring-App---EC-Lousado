from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Callable, List, Optional

from dash import ALL, Input, Output, State, callback_context, dcc, html, no_update
from dash.exceptions import PreventUpdate

from features.monitor.occupation.excel_writer import dates_in_range, detect_breaks

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

        # Guard: ignore synthetic fires from newly mounted components (n_clicks == 0)
        triggered_value = ctx.triggered[0].get("value") if ctx.triggered else None
        if not triggered_value:
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
    # 2. Render per-date break preview with copy-to-clipboard               #
    # ------------------------------------------------------------------ #
    @app.callback(
        Output("occ-preview", "children"),
        Output("occ-copy-all-clipboard", "content"),
        Input("occ-date-picker", "start_date"),
        Input("occ-date-picker", "end_date"),
        Input("occ-slot-store", "data"),
        prevent_initial_call=True,
    )
    def update_occ_preview(start_str, end_str, slot_data):
        if not slot_data or not slot_data.get("test_number"):
            return html.Span("No test loaded for this slot.", style={"color": "var(--muted)"}), ""
        if not start_str or not end_str:
            return html.Span("Select dates to preview.", style={"color": "var(--muted)"}), ""

        test_number: str = slot_data["test_number"]
        position: int = slot_data["position"]

        df = _get_df(test_number, position, find_log_path, cached_parse_log)

        start = _parse_date(start_str)
        end = _parse_date(end_str)
        if start is None or end is None:
            return html.Span("Invalid date selection.", style={"color": "var(--muted)"}), ""

        day_list = dates_in_range(start, end)
        if not day_list:
            return html.Span("No dates in range.", style={"color": "var(--muted)"}), ""

        rows = []
        copy_all_lines = []
        for d in day_list:
            date_iso = d.isoformat()
            label = d.strftime("%d/%m/%Y")
            break_text_id = {"type": "occ-break-text", "date": date_iso}

            break_str = detect_breaks(df, d) if df is not None else None

            if break_str is None:
                break_node = html.Span("Log unavailable", style={"color": "var(--muted)", "fontSize": "11px"})
                copy_btn = None
                line_text = "Log unavailable"
            elif not break_str:
                break_node = html.Span("No breaks", style={"color": "var(--muted)", "fontSize": "11px"})
                copy_btn = None
                line_text = "No breaks"
            else:
                break_node = html.Span(break_str, id=break_text_id, style={"color": "#F0BA20", "fontSize": "11px"})
                copy_btn = dcc.Clipboard(
                    target_id=break_text_id,
                    style={"fontSize": "13px", "color": "var(--muted)", "cursor": "pointer"},
                )
                line_text = break_str

            copy_all_lines.append(f"{label}  {line_text}")

            rows.append(
                html.Div(
                    style={
                        "display": "flex",
                        "alignItems": "center",
                        "gap": "10px",
                        "marginBottom": "6px",
                    },
                    children=[
                        c for c in [
                            html.Div(
                                label,
                                style={
                                    "fontWeight": "600",
                                    "fontSize": "12px",
                                    "width": "85px",
                                    "flexShrink": "0",
                                    "color": "var(--fg, #e0e4f0)",
                                },
                            ),
                            break_node,
                            copy_btn,
                        ] if c is not None
                    ],
                )
            )

        return rows, "\n".join(copy_all_lines)


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
