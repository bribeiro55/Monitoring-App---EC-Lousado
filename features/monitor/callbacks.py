from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd
from dash import ALL, Input, Output, State, callback_context, dcc, html, no_update
from dash.exceptions import PreventUpdate

from services.chart_utils import _downsample
from domain.models import make_modal_selection
from features.monitor.auto_refresh.schedule import has_any_test_input
from features.monitor.data import _rows_to_df, _apply_chart_filters, _serialize_df_rows
from features.monitor.figures import _blank_figure, build_summary_stats, build_temperature_figure, _runtime_hhmm_for_df
from features.monitor.components import (
    _placement_history_note_children,
    make_chart_panel,
    make_modal_stats,
    make_step_legend,
)
from features.monitor.log_loading import load_logs_for_test_inputs
from features.monitor.callbacks_registry import register_registry_callbacks


def register_monitor_callbacks(
    app,
    *,
    VARIABLE_CONFIG,
    MACHINES,
    MACHINE_BADGE,
    STEP_COLORS,
    input_id_fn,
    find_log_path_for_test_number,
    parse_log_header_metadata,
    cached_parse_log,
    DISPLAY_TO_MACHINE_ID,
    registry=None,
    slot_store=None,
) -> None:
    _input_id = input_id_fn

    @app.callback(
        Output("clock", "children"),
        Input("clock-interval", "n_intervals"),
    )
    def update_clock(_):
        now = datetime.now()
        return now.strftime("%H:%M:%S")


    @app.callback(Output("load-debug-panel", "children"), Input("loaded-logs-store", "data"))
    def render_load_debug(store: Optional[dict]):
        if not store:
            return html.Div(
                "Diagnostics appear here after you click Refresh.",
                style={"margin": 0, "color": "var(--muted)"},
            )
        lines: List[str] = []
        for slot in sorted(store.keys()):
            entry = store[slot]
            status = entry.get("status")
            dbg = entry.get("load_debug") or {}
            if status == "ok":
                n = len(entry.get("rows") or [])
                lines.append(
                    f"{slot}: OK  rows={n}  parsed={dbg.get('parsed_rows')} "
                    f"filtered={dbg.get('filtered_rows')}  fallback={dbg.get('used_full_log_fallback')}  "
                    f"{dbg.get('expected', '')}"
                )
                if dbg.get("log_path"):
                    lines.append(f"  path: {dbg['log_path']}")
            elif status == "error":
                lines.append(f"{slot}: PARSE ERROR — {entry.get('message')}")
                if dbg.get("log_path"):
                    lines.append(f"  path: {dbg['log_path']}")
            else:
                lines.append(f"{slot}: {status} — {entry.get('message', '')}")
                if dbg.get("reason"):
                    lines.append(f"  {dbg['reason']}")
        return html.Pre("\n".join(lines), style={"margin": 0})


    @app.callback(
        Output("graphs-section-label", "children"),
        Input("variable-dropdown", "value"),
    )
    def update_graphs_section_label(selected_var: str):
        cfg = VARIABLE_CONFIG.get(selected_var, VARIABLE_CONFIG["temperature"])
        return f"{cfg['label']} Over Time"


    @app.callback(
        Output("active-steps-store", "data"),
        Output({"type": "step-pill", "step": ALL}, "className"),
        Input({"type": "step-pill", "step": ALL}, "n_clicks"),
        State({"type": "step-pill", "step": ALL}, "id"),
        State("active-steps-store", "data"),
        prevent_initial_call=True,
    )
    def toggle_step_buttons(_n_clicks, _ids, current_active):
        # NOTE: Dash will pass ALL button IDs; we only use the triggered one.
        ctx = callback_context
        if not ctx.triggered:
            raise PreventUpdate

        triggered = ctx.triggered_id
        step_clicked = triggered.get("step") if isinstance(triggered, dict) else None

        active = set(current_active or ["all"])
        if step_clicked == "all":
            active = {"all"}
        else:
            active.discard("all")
            step_int = int(step_clicked)
            if step_int in active:
                active.remove(step_int)
            else:
                active.add(step_int)
            if not active:
                active = {"all"}

        active_list: List[object]
        if "all" in active:
            active_list = ["all"]
        else:
            active_list = sorted(active)

        # Build classes in the same order as Dash matched the ALL pattern.
        step_classes = []
        for id_obj in _ids:
            step_val = id_obj.get("step")
            try:
                if step_val == "all":
                    step_classes.append("step-pill all-pill active" if "all" in active else "step-pill all-pill")
                else:
                    step_int = int(step_val)
                    step_classes.append("step-pill active" if step_int in active else "step-pill")
            except Exception:
                step_classes.append("step-pill")

        return active_list, step_classes


    @app.callback(
        Output("ignore-stopped-store", "data"),
        Output("ignore-toggle", "className"),
        Input("ignore-toggle", "n_clicks"),
        State("ignore-stopped-store", "data"),
    )
    def toggle_ignore(_n_clicks: int, current: bool):
        # Any click toggles the boolean.
        new_val = not bool(current)
        return new_val, "toggle on" if new_val else "toggle"


    @app.callback(
        Output("loaded-logs-store", "data"),
        Output("modal-open-store", "data", allow_duplicate=True),
        Output("modal-selection-store", "data", allow_duplicate=True),
        Input("refresh-btn", "n_clicks"),
        Input("auto-refresh-trigger-store", "data"),
        State(_input_id(MACHINES[0], 1), "value"),
        State(_input_id(MACHINES[0], 2), "value"),
        State(_input_id(MACHINES[1], 1), "value"),
        State(_input_id(MACHINES[1], 2), "value"),
        State(_input_id(MACHINES[2], 1), "value"),
        State(_input_id(MACHINES[2], 2), "value"),
        State("modal-open-store", "data"),
        prevent_initial_call=True,
    )
    def load_logs_on_refresh(
        _n_clicks: int,
        _auto_trigger: int,
        tA1: str,
        tA2: str,
        tB1: str,
        tB2: str,
        tC1: str,
        tC2: str,
        modal_open: bool,
    ):
        ctx = callback_context
        triggered = ctx.triggered_id
        is_auto = triggered == "auto-refresh-trigger-store"

        if is_auto and not has_any_test_input([tA1, tA2, tB1, tB2, tC1, tC2]):
            raise PreventUpdate

        loaded = load_logs_for_test_inputs(
            MACHINES,
            tA1,
            tA2,
            tB1,
            tB2,
            tC1,
            tC2,
            find_log_path_for_test_number=find_log_path_for_test_number,
            parse_log_header_metadata=parse_log_header_metadata,
            cached_parse_log=cached_parse_log,
            display_to_machine_id=DISPLAY_TO_MACHINE_ID,
            serialize_df_rows=_serialize_df_rows,
        )

        if is_auto and modal_open:
            return loaded, no_update, no_update

        # Close enlarged view on manual refresh; user must click Expand again to open it.
        return loaded, False, {}


    @app.callback(
        Output("slot-persist-sink", "data"),
        Input(_input_id(MACHINES[0], 1), "value"),
        Input(_input_id(MACHINES[0], 2), "value"),
        Input(_input_id(MACHINES[1], 1), "value"),
        Input(_input_id(MACHINES[1], 2), "value"),
        Input(_input_id(MACHINES[2], 1), "value"),
        Input(_input_id(MACHINES[2], 2), "value"),
        prevent_initial_call=True,
    )
    def persist_slot_inputs(tA1, tA2, tB1, tB2, tC1, tC2):
        if slot_store is None:
            raise PreventUpdate
        slot_store.set_many(
            {
                f"{MACHINES[0]}|1": tA1,
                f"{MACHINES[0]}|2": tA2,
                f"{MACHINES[1]}|1": tB1,
                f"{MACHINES[1]}|2": tB2,
                f"{MACHINES[2]}|1": tC1,
                f"{MACHINES[2]}|2": tC2,
            }
        )
        return no_update


    @app.callback(
        Output("charts-grid", "children"),
        Input("active-steps-store", "data"),
        Input("ignore-stopped-store", "data"),
        Input("loaded-logs-store", "data"),
        Input("variable-dropdown", "value"),
        State(_input_id(MACHINES[0], 1), "value"),
        State(_input_id(MACHINES[0], 2), "value"),
        State(_input_id(MACHINES[1], 1), "value"),
        State(_input_id(MACHINES[1], 2), "value"),
        State(_input_id(MACHINES[2], 1), "value"),
        State(_input_id(MACHINES[2], 2), "value"),
    )
    def render_charts_grid(
        active_steps: List[object],
        ignore_stopped: bool,
        loaded_store: dict,
        selected_var: str,
        tA1: str,
        tA2: str,
        tB1: str,
        tB2: str,
        tC1: str,
        tC2: str,
    ):
        loaded_store = loaded_store or {}
        test_numbers = {
            MACHINES[0]: {1: str(tA1).strip() if tA1 else "", 2: str(tA2).strip() if tA2 else ""},
            MACHINES[1]: {1: str(tB1).strip() if tB1 else "", 2: str(tB2).strip() if tB2 else ""},
            MACHINES[2]: {1: str(tC1).strip() if tC1 else "", 2: str(tC2).strip() if tC2 else ""},
        }

        charts_children: List[html.Div] = []

        for machine_label in MACHINES:
            p1_test = test_numbers[machine_label][1]
            p2_test = test_numbers[machine_label][2]
            if not p1_test and not p2_test:
                continue

            row_children = [
                html.Div(
                    className="machine-row-header",
                    children=[
                        html.Div(
                            className="machine-row-title",
                            children=[
                                html.Span(className="machine-badge", children=[MACHINE_BADGE.get(machine_label, "?")]),
                                html.Span(machine_label),
                            ],
                        ),
                        html.Div(
                            style={"display": "flex", "gap": "8px", "alignItems": "center"},
                            children=[
                                html.Span(
                                    style={"fontSize": "11px", "color": "var(--muted)"},
                                    children=[
                                        "Pos 1: ",
                                        html.B(f"{p1_test}") if p1_test else "",
                                    ],
                                )
                                if p1_test
                                else html.Span(),
                                html.Span(
                                    style={"fontSize": "11px", "color": "var(--muted)"},
                                    children=[
                                        "Pos 2: ",
                                        html.B(f"{p2_test}") if p2_test else "",
                                    ],
                                )
                                if p2_test
                                else html.Span(),
                            ],
                        ),
                    ],
                ),
                html.Div(
                    className="machine-charts",
                    children=[
                        make_chart_panel(
                            machine_label=machine_label,
                            position=1,
                            test_number=p1_test,
                            slot_key=f"{machine_label}|1",
                            loaded_entry=(
                                loaded_store.get(f"{machine_label}|1")
                                if loaded_store.get(f"{machine_label}|1", {}).get("test_number") == p1_test
                                else None
                            ),
                            active_steps=active_steps,
                            ignore_stopped=ignore_stopped,
                            selected_var=selected_var,
                        ),
                        make_chart_panel(
                            machine_label=machine_label,
                            position=2,
                            test_number=p2_test,
                            slot_key=f"{machine_label}|2",
                            loaded_entry=(
                                loaded_store.get(f"{machine_label}|2")
                                if loaded_store.get(f"{machine_label}|2", {}).get("test_number") == p2_test
                                else None
                            ),
                            active_steps=active_steps,
                            ignore_stopped=ignore_stopped,
                            selected_var=selected_var,
                        ),
                    ],
                ),
            ]

            charts_children.append(html.Div(className="machine-row", children=row_children))

        return charts_children


    # --- Modal open/close and content ---
    # Single callback: Dash forbids two callbacks writing the same Output (modal-open-store).
    @app.callback(
        Output("modal-open-store", "data"),
        Output("modal-selection-store", "data"),
        Input({"type": "expand-btn", "slot": ALL}, "n_clicks"),
        Input("modal-close-btn", "n_clicks"),
        State({"type": "expand-btn", "slot": ALL}, "id"),
        State(_input_id(MACHINES[0], 1), "value"),
        State(_input_id(MACHINES[0], 2), "value"),
        State(_input_id(MACHINES[1], 1), "value"),
        State(_input_id(MACHINES[1], 2), "value"),
        State(_input_id(MACHINES[2], 1), "value"),
        State(_input_id(MACHINES[2], 2), "value"),
        prevent_initial_call=True,
    )
    def modal_open_or_close(_expand_clicks, _close_clicks, _ids, tA1, tA2, tB1, tB2, tC1, tC2):
        ctx = callback_context
        if not ctx.triggered_id:
            raise PreventUpdate
        triggered = ctx.triggered_id
        if triggered == "modal-close-btn":
            return False, {}

        # Only open on a real expand click (n_clicks >= 1). After Refresh, buttons are recreated
        # with n_clicks=0; ignore spurious callbacks so the modal does not open by itself.
        if isinstance(triggered, dict) and triggered.get("type") == "expand-btn":
            idx = next((i for i, bid in enumerate(_ids or []) if bid == triggered), None)
            if idx is None:
                raise PreventUpdate
            clicks = _expand_clicks[idx] if _expand_clicks is not None and idx < len(_expand_clicks) else 0
            if not clicks:
                raise PreventUpdate

        slot = triggered.get("slot") if isinstance(triggered, dict) else None
        if not slot:
            raise PreventUpdate

        test_map = {
            MACHINES[0]: {1: str(tA1).strip() if tA1 else "", 2: str(tA2).strip() if tA2 else ""},
            MACHINES[1]: {1: str(tB1).strip() if tB1 else "", 2: str(tB2).strip() if tB2 else ""},
            MACHINES[2]: {1: str(tC1).strip() if tC1 else "", 2: str(tC2).strip() if tC2 else ""},
        }

        if "|" not in slot:
            return False, {}
        machine_label, pos_str = slot.split("|", 1)
        try:
            pos_num = int(pos_str)
        except ValueError:
            pos_num = 0

        current_test = test_map.get(machine_label, {}).get(pos_num, "")
        return True, make_modal_selection(slot, current_test)


    @app.callback(
        Output("modal-overlay", "className"),
        Input("modal-open-store", "data"),
    )
    def sync_modal_overlay_class(open_store: bool):
        return "modal-overlay open" if open_store else "modal-overlay"


    @app.callback(
        Output("modal-title", "children"),
        Output("modal-subtitle", "children"),
        Output("modal-placement-note", "children"),
        Output("modal-stats", "children"),
        Output("modal-graph", "figure"),
        Output("modal-legend", "children"),
        Input("modal-open-store", "data"),
        Input("modal-selection-store", "data"),
        Input("active-steps-store", "data"),
        Input("ignore-stopped-store", "data"),
        Input("loaded-logs-store", "data"),
        Input("variable-dropdown", "value"),
    )
    def update_modal_content(open_store, selection, active_steps, ignore_stopped, loaded_store, selected_var):
        if not open_store or not selection or not selection.get("slot"):
            return "-", "-", [], [], _blank_figure(), []

        slot_key = selection["slot"]
        selected_test = str(selection.get("test_number") or "").strip()
        loaded_entry = loaded_store.get(slot_key)
        if (
            not loaded_entry
            or loaded_entry.get("status") != "ok"
            or (selected_test and loaded_entry.get("test_number") != selected_test)
        ):
            return (
                "-",
                "Click Refresh to load",
                [],
                [],
                _blank_figure(),
                [],
            )

        if "slot_eligible" in loaded_entry and not loaded_entry.get("slot_eligible"):
            return (
                "-",
                "This slot does not match the latest data for this test — Refresh after moving the test number.",
                [],
                [],
                _blank_figure(),
                [],
            )

        # Parse slot key back into machine+position.
        if "|" not in slot_key:
            return "-", "-", [], [], _blank_figure(), []
        machine_label, pos_str = slot_key.split("|", 1)
        position = int(pos_str)
        test_number = loaded_entry.get("test_number", selected_test)

        df = _rows_to_df(loaded_entry.get("rows", []))

        # Apply same filters for summary stats and modal chart.
        steps_set = set(active_steps or ["all"])
        if "all" in steps_set or not steps_set:
            visible_steps = set(range(1, 10))
        else:
            visible_steps = set(int(s) for s in steps_set)

        var_cfg = VARIABLE_CONFIG[selected_var]

        df_visible = _apply_chart_filters(df, active_steps, ignore_stopped).sort_values("timestamp")

        pm = loaded_entry.get("latest_machine_id")
        pp = loaded_entry.get("latest_position")
        if pm is None or pp is None:
            if not df.empty:
                last = df.sort_values("timestamp").iloc[-1]
                pm = last.get("machine_id")
                pp = last.get("position")
        try:
            pp_i = int(pp) if pp is not None and not pd.isna(pp) else None
        except (ValueError, TypeError):
            pp_i = None

        fig = build_temperature_figure(
            df,
            position=position,
            active_steps=active_steps,
            ignore_stopped=ignore_stopped,
            value_col=var_cfg["col"],
            value_unit=var_cfg["unit"],
            value_label=var_cfg["label"],
            primary_machine_id=str(pm) if pm is not None and not pd.isna(pm) else None,
            primary_position=pp_i,
            prefiltered_df=df_visible,
        )
        if fig is None:
            fig = _blank_figure()

        stats = build_summary_stats(df_visible, value_col=var_cfg["col"])
        df_plot_basis = _downsample(df_visible.sort_values("timestamp").reset_index(drop=True))
        run_labels = _runtime_hhmm_for_df(df_plot_basis)
        run_time_last = run_labels[-1] if run_labels else "00:00"

        placement_note_children: List = []
        if pm is not None and pp_i is not None and not pd.isna(pm):
            placement_note_children = _placement_history_note_children(df_visible, str(pm), pp_i)

        step_label = "1–9" if ("all" in steps_set or not steps_set) else ",".join(str(s) for s in sorted(visible_steps))
        subtitle = f"Test {test_number} · Steps {step_label}"
        if ignore_stopped:
            subtitle += " · Ignore stopped"

        title = f"{machine_label} · Position {position}"
        return (
            title,
            subtitle,
            placement_note_children,
            make_modal_stats(stats, var_cfg, run_time_last),
            fig,
            make_step_legend(STEP_COLORS),
        )


    app.clientside_callback(
        """
        function(n_clicks, fig_json) {
            if (!n_clicks || !fig_json) {
                return window.dash_clientside.no_update;
            }
            const wrap = document.getElementById("modal-graph");
            if (!wrap || !window.Plotly) {
                return window.dash_clientside.no_update;
            }
            const plotDiv = wrap.querySelector(".js-plotly-plot");
            if (!plotDiv) {
                return window.dash_clientside.no_update;
            }
            const stamp = new Date().toISOString().replace(/[:.]/g, "-");
            const oldPaper = (plotDiv.layout && plotDiv.layout.paper_bgcolor) || null;
            const oldPlot = (plotDiv.layout && plotDiv.layout.plot_bgcolor) || null;

            return window.Plotly.relayout(plotDiv, {
                paper_bgcolor: "#FFFFFF",
                plot_bgcolor: "#FFFFFF"
            }).then(function() {
                return window.Plotly.downloadImage(plotDiv, {
                    format: "png",
                    filename: "tire-temp-" + stamp,
                    scale: 2
                });
            }).then(function() {
                return window.Plotly.relayout(plotDiv, {
                    paper_bgcolor: oldPaper || "rgba(0,0,0,0)",
                    plot_bgcolor: oldPlot || "rgba(0,0,0,0)"
                });
            }).then(function() {
                return n_clicks;
            }).catch(function() {
                return window.dash_clientside.no_update;
            });
        }
        """,
        Output("png-export-state", "data"),
        Input("modal-export-png-btn", "n_clicks"),
        State("modal-graph", "figure"),
        prevent_initial_call=True,
    )


    @app.callback(
        Output("modal-csv-download", "data"),
        Input("modal-export-csv-btn", "n_clicks"),
        State("modal-open-store", "data"),
        State("modal-selection-store", "data"),
        State("active-steps-store", "data"),
        State("ignore-stopped-store", "data"),
        State("loaded-logs-store", "data"),
        State("variable-dropdown", "value"),
        prevent_initial_call=True,
    )
    def export_modal_csv(_n_clicks, modal_open, selection, active_steps, ignore_stopped, loaded_store, selected_var):
        if not modal_open or not selection or not selection.get("slot"):
            raise PreventUpdate

        slot_key = selection["slot"]
        loaded_entry = loaded_store.get(slot_key)
        if not loaded_entry or loaded_entry.get("status") != "ok":
            raise PreventUpdate

        df = _rows_to_df(loaded_entry.get("rows", []))
        if df.empty:
            raise PreventUpdate

        df_visible = _apply_chart_filters(df, active_steps, ignore_stopped).sort_values("timestamp")
        if df_visible.empty:
            raise PreventUpdate

        var_cfg = VARIABLE_CONFIG.get(selected_var, VARIABLE_CONFIG["temperature"])
        value_col = var_cfg["col"]
        value_label = var_cfg["label"]
        value_unit = var_cfg["unit"]

        out = pd.DataFrame(
            {
                "Position": df_visible["position"],
                "Date": df_visible["timestamp"].dt.strftime("%Y-%m-%d"),
                "Time": df_visible["timestamp"].dt.strftime("%H:%M:%S"),
                value_label: pd.to_numeric(df_visible[value_col], errors="coerce"),
            }
        )
        out = out.dropna(subset=["Date", "Time", value_label]).copy()
        if out.empty:
            raise PreventUpdate

        test_no = str(loaded_entry.get("test_number") or "test").strip()
        safe_test = "".join(ch for ch in test_no if ch.isalnum() or ch in ("-", "_"))
        safe_slot = "".join(ch for ch in slot_key.replace("|", "_") if ch.isalnum() or ch in ("-", "_"))
        safe_var = "".join(ch for ch in selected_var if ch.isalnum() or ch in ("-", "_"))
        filename = f"{safe_test or 'test'}_{safe_slot}_{safe_var}.xlsx"
        return dcc.send_data_frame(out.to_excel, filename, index=False, engine="openpyxl")

    if registry is not None:
        register_registry_callbacks(app, registry=registry)

