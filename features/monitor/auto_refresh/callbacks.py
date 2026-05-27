from __future__ import annotations

from datetime import datetime

from dash import Input, Output, State
from dash.exceptions import PreventUpdate

from features.monitor.auto_refresh.schedule import (
    dismiss_cycle,
    has_any_test_input,
    next_cycle_state,
)


def register_monitor_auto_refresh_callbacks(
    app,
    *,
    MACHINES,
    input_id_fn,
) -> None:
    _input_id = input_id_fn

    def _test_input_states():
        return [
            State(_input_id(MACHINES[0], 1), "value"),
            State(_input_id(MACHINES[0], 2), "value"),
            State(_input_id(MACHINES[1], 1), "value"),
            State(_input_id(MACHINES[1], 2), "value"),
            State(_input_id(MACHINES[2], 1), "value"),
            State(_input_id(MACHINES[2], 2), "value"),
        ]

    @app.callback(
        Output("auto-refresh-cycle-store", "data"),
        Output("auto-refresh-trigger-store", "data"),
        Input("clock-interval", "n_intervals"),
        State("auto-refresh-cycle-store", "data"),
        State("auto-refresh-enabled-store", "data"),
        State("auto-refresh-trigger-store", "data"),
        State("main-tab-store", "data"),
        *_test_input_states(),
    )
    def tick_auto_refresh_cycle(
        _n_intervals,
        cycle,
        enabled,
        trigger_count,
        tab,
        tA1,
        tA2,
        tB1,
        tB2,
        tC1,
        tC2,
    ):
        result = next_cycle_state(
            datetime.now(),
            cycle,
            bool(enabled),
            tab or "monitor",
            [tA1, tA2, tB1, tB2, tC1, tC2],
        )
        if result.cycle == (cycle or {}) and not result.fire_refresh:
            raise PreventUpdate

        new_trigger = int(trigger_count or 0)
        if result.fire_refresh:
            new_trigger += 1

        if result.cycle == (cycle or {}) and new_trigger == int(trigger_count or 0):
            raise PreventUpdate

        return result.cycle, new_trigger

    @app.callback(
        Output("auto-refresh-cycle-store", "data", allow_duplicate=True),
        Input("auto-refresh-dismiss-btn", "n_clicks"),
        State("auto-refresh-cycle-store", "data"),
        prevent_initial_call=True,
    )
    def dismiss_auto_refresh_cycle(_n_clicks, cycle):
        if not _n_clicks:
            raise PreventUpdate
        return dismiss_cycle(cycle)

    @app.callback(
        Output("auto-refresh-enabled-store", "data"),
        Output("auto-refresh-toggle", "className"),
        Input("auto-refresh-toggle", "n_clicks"),
        State("auto-refresh-enabled-store", "data"),
    )
    def toggle_auto_refresh(_n_clicks, current):
        new_val = not bool(current) if _n_clicks else bool(current)
        return new_val, "toggle on" if new_val else "toggle"

    @app.callback(
        Output("auto-refresh-banner", "className"),
        Output("auto-refresh-banner-text", "children"),
        Input("auto-refresh-cycle-store", "data"),
        Input("main-tab-store", "data"),
    )
    def render_auto_refresh_banner(cycle, tab):
        cycle = cycle or {}
        phase = cycle.get("phase")
        dismissed = bool(cycle.get("dismissed"))
        on_monitor = (tab or "monitor") == "monitor"
        visible = on_monitor and phase == "countdown" and not dismissed

        if not visible:
            return "auto-refresh-banner hidden", [""]

        seconds = int(cycle.get("seconds_remaining") or 0)
        label = f"View will update in {seconds} second{'s' if seconds != 1 else ''}"
        return "auto-refresh-banner", [label]
