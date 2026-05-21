from __future__ import annotations

from typing import Dict, List, Optional

from dash import ALL, Input, Output, State, callback_context, dcc, html
from dash.exceptions import PreventUpdate

from config import VARIABLE_CONFIG
from domain.models import make_analysis_band_limits
from features.analysis.services import (
    ANALYSIS_FILTER_VARIABLE_OPTIONS,
    analysis_parse_limit_field,
    count_active_variable_filters,
    default_analysis_filter_state,
    normalize_analysis_band_limits,
    normalize_analysis_filter_state,
    normalize_variable_filters,
    to_opt_datetime,
    to_opt_float,
)


def _next_var_filter_id(filters: List[dict]) -> int:
    ids = [int(x["id"]) for x in filters if x.get("id") is not None]
    return max(ids) + 1 if ids else 0


def _render_var_filter_rows(filters: List[dict]) -> List[html.Div]:
    vfs = normalize_variable_filters(filters)
    if not vfs:
        return [
            html.Div(
                "No variable filters. Add one to keep rows where any signal meets your criteria.",
                className="var-filter-empty",
            )
        ]
    rows: List[html.Div] = []
    for vf in vfs:
        fid = int(vf["id"])
        mode = vf["mode"]
        unit = VARIABLE_CONFIG.get(vf["variable"], {}).get("unit", "")
        label_a = ">" if mode == "above" else ("<" if mode == "below" else "≥")
        rows.append(
            html.Div(
                className="var-filter-row",
                children=[
                    html.Div(
                        className="var-filter-row-top",
                        children=[
                            dcc.Dropdown(
                                id={"type": "analysis-var-filter-var", "fid": fid},
                                options=ANALYSIS_FILTER_VARIABLE_OPTIONS,
                                value=vf["variable"],
                                clearable=False,
                                className="var-filter-var-dd",
                            ),
                            html.Button(
                                "×",
                                id={"type": "analysis-var-filter-rm", "fid": fid},
                                className="ts-remove",
                                n_clicks=0,
                                type="button",
                            ),
                        ],
                    ),
                    html.Div(
                        className="filter-mode-pills",
                        children=[
                            html.Button(
                                "Above",
                                id={"type": "analysis-var-filter-mode", "fid": fid, "mode": "above"},
                                className="filter-mode-pill active" if mode == "above" else "filter-mode-pill",
                                n_clicks=0,
                                type="button",
                            ),
                            html.Button(
                                "Below",
                                id={"type": "analysis-var-filter-mode", "fid": fid, "mode": "below"},
                                className="filter-mode-pill active" if mode == "below" else "filter-mode-pill",
                                n_clicks=0,
                                type="button",
                            ),
                            html.Button(
                                "Between",
                                id={"type": "analysis-var-filter-mode", "fid": fid, "mode": "between"},
                                className="filter-mode-pill active" if mode == "between" else "filter-mode-pill",
                                n_clicks=0,
                                type="button",
                            ),
                        ],
                    ),
                    html.Div(
                        children=[
                            html.Div(
                                className="filter-input-row",
                                children=[
                                    html.Label(label_a),
                                    dcc.Input(
                                        id={"type": "analysis-var-filter-a", "fid": fid},
                                        type="number",
                                        value=vf.get("value_a"),
                                        className="filter-num",
                                        debounce=True,
                                        placeholder="e.g. 80",
                                    ),
                                    html.Span(unit, style={"fontSize": "11px", "color": "var(--muted)"}),
                                ],
                            ),
                            html.Div(
                                className="filter-input-row",
                                style={"display": "flex"} if mode == "between" else {"display": "none"},
                                children=[
                                    html.Label("≤"),
                                    dcc.Input(
                                        id={"type": "analysis-var-filter-b", "fid": fid},
                                        type="number",
                                        value=vf.get("value_b"),
                                        className="filter-num",
                                        debounce=True,
                                        placeholder="e.g. 150",
                                    ),
                                    html.Span(unit, style={"fontSize": "11px", "color": "var(--muted)"}),
                                ],
                            ),
                        ],
                    ),
                ],
            )
        )
    return rows


def register_analysis_filter_callbacks(app, deps: dict) -> None:
    @app.callback(
        Output("analysis-active-steps-store", "data"),
        Output({"type": "analysis-step-pill", "step": ALL}, "className"),
        Input({"type": "analysis-step-pill", "step": ALL}, "n_clicks"),
        State({"type": "analysis-step-pill", "step": ALL}, "id"),
        State("analysis-active-steps-store", "data"),
        prevent_initial_call=True,
    )
    def analysis_toggle_steps(_n_clicks, _ids, current_active):
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
        active_list: List[object] = ["all"] if "all" in active else sorted(active)
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
        Output("analysis-ignore-stopped-store", "data"),
        Output("analysis-ignore-toggle", "className"),
        Input("analysis-ignore-toggle", "n_clicks"),
        State("analysis-ignore-stopped-store", "data"),
    )
    def analysis_toggle_ignore(_n: int, current: bool):
        new_val = not bool(current)
        return new_val, "toggle on" if new_val else "toggle"

    @app.callback(
        Output("analysis-normalize-store", "data"),
        Output("analysis-norm-toggle", "className"),
        Input("analysis-norm-toggle", "n_clicks"),
        State("analysis-normalize-store", "data"),
    )
    def analysis_toggle_normalize(_n: int, current: bool):
        new_val = not bool(current)
        return new_val, "toggle on" if new_val else "toggle"

    @app.callback(
        Output("analysis-limits-store", "data", allow_duplicate=True),
        Output("analysis-limits-by-variable-store", "data"),
        Output("analysis-limits-prev-var", "data"),
        Input("analysis-variable-dropdown", "value"),
        State("analysis-limits-store", "data"),
        State("analysis-limits-by-variable-store", "data"),
        State("analysis-limits-prev-var", "data"),
        prevent_initial_call="initial_duplicate",
    )
    def sync_analysis_limits_for_variable(new_var: str, current_limits: object, by_variable: Optional[dict], prev_var: Optional[str]):
        if not new_var:
            raise PreventUpdate
        by_var: Dict[str, Dict[str, Optional[float]]] = {}
        for k, v in dict(by_variable or {}).items():
            by_var[str(k)] = normalize_analysis_band_limits(v)
        cur = normalize_analysis_band_limits(current_limits)
        if prev_var != new_var:
            if prev_var is not None:
                by_var[prev_var] = cur
            loaded = dict(by_var.get(new_var, {"upper": None, "lower": None}))
        else:
            loaded = cur
        return loaded, by_var, new_var

    @app.callback(
        Output("analysis-upper-limit", "value"),
        Output("analysis-lower-limit", "value"),
        Input("analysis-limits-store", "data"),
        prevent_initial_call=False,
    )
    def analysis_sync_band_inputs_from_store(store):
        b = normalize_analysis_band_limits(store)
        return b["upper"], b["lower"]

    @app.callback(
        Output("analysis-limits-store", "data", allow_duplicate=True),
        Input("analysis-upper-limit", "value"),
        Input("analysis-lower-limit", "value"),
        prevent_initial_call=True,
    )
    def analysis_band_store_from_inputs(upper, lower):
        return make_analysis_band_limits(
            analysis_parse_limit_field(upper),
            analysis_parse_limit_field(lower),
        )

    @app.callback(
        Output("analysis-variable-filters-ui", "children"),
        Input("analysis-data-filters-store", "data"),
    )
    def analysis_render_variable_filters_ui(filter_state):
        fs = normalize_analysis_filter_state(filter_state)
        return _render_var_filter_rows(fs.get("variable_filters") or [])

    @app.callback(
        Output("analysis-data-filters-store", "data", allow_duplicate=True),
        Input("analysis-add-var-filter-btn", "n_clicks"),
        State("analysis-data-filters-store", "data"),
        prevent_initial_call=True,
    )
    def analysis_add_var_filter(_n, current):
        if not _n:
            raise PreventUpdate
        fs = normalize_analysis_filter_state(current)
        vfs = list(fs.get("variable_filters") or [])
        vfs.append(
            {
                "id": _next_var_filter_id(vfs),
                "variable": "temperature",
                "mode": "above",
                "value_a": None,
                "value_b": None,
            }
        )
        fs["variable_filters"] = vfs
        return fs

    @app.callback(
        Output("analysis-data-filters-store", "data", allow_duplicate=True),
        Input({"type": "analysis-var-filter-rm", "fid": ALL}, "n_clicks"),
        State({"type": "analysis-var-filter-rm", "fid": ALL}, "id"),
        State("analysis-data-filters-store", "data"),
        prevent_initial_call=True,
    )
    def analysis_rm_var_filter(_n, ids, current):
        ctx = callback_context
        if not isinstance(ctx.triggered_id, dict) or ctx.triggered_id.get("type") != "analysis-var-filter-rm":
            raise PreventUpdate
        fid = ctx.triggered_id.get("fid")
        idx = next((i for i, bid in enumerate(ids or []) if bid == ctx.triggered_id), None)
        if idx is None or not _n or idx >= len(_n) or not _n[idx]:
            raise PreventUpdate
        fs = normalize_analysis_filter_state(current)
        fs["variable_filters"] = [x for x in (fs.get("variable_filters") or []) if int(x.get("id", -1)) != int(fid)]
        return fs

    @app.callback(
        Output("analysis-data-filters-store", "data", allow_duplicate=True),
        Input({"type": "analysis-var-filter-mode", "fid": ALL, "mode": ALL}, "n_clicks"),
        State({"type": "analysis-var-filter-mode", "fid": ALL, "mode": ALL}, "id"),
        State("analysis-data-filters-store", "data"),
        prevent_initial_call=True,
    )
    def analysis_var_filter_mode(_n, ids, current):
        ctx = callback_context
        tid = ctx.triggered_id
        if not isinstance(tid, dict) or tid.get("type") != "analysis-var-filter-mode":
            raise PreventUpdate
        fid = int(tid["fid"])
        mode = str(tid.get("mode") or "above")
        idx = next((i for i, bid in enumerate(ids or []) if bid == tid), None)
        if idx is None or not _n or idx >= len(_n) or not _n[idx]:
            raise PreventUpdate
        fs = normalize_analysis_filter_state(current)
        vfs = [dict(x) for x in (fs.get("variable_filters") or [])]
        for x in vfs:
            if int(x.get("id", -1)) == fid:
                x["mode"] = mode
                break
        fs["variable_filters"] = vfs
        return fs

    @app.callback(
        Output("analysis-data-filters-store", "data", allow_duplicate=True),
        Input({"type": "analysis-var-filter-var", "fid": ALL}, "value"),
        State({"type": "analysis-var-filter-var", "fid": ALL}, "id"),
        State("analysis-data-filters-store", "data"),
        prevent_initial_call=True,
    )
    def analysis_var_filter_variable(vals, ids, current):
        ctx = callback_context
        tid = ctx.triggered_id
        if not isinstance(tid, dict) or tid.get("type") != "analysis-var-filter-var":
            raise PreventUpdate
        fid = int(tid["fid"])
        new_v = None
        for i, bid in enumerate(ids or []):
            if bid == tid and vals is not None and i < len(vals):
                new_v = vals[i]
                break
        if not new_v:
            raise PreventUpdate
        fs = normalize_analysis_filter_state(current)
        vfs = [dict(x) for x in (fs.get("variable_filters") or [])]
        for x in vfs:
            if int(x.get("id", -1)) == fid:
                x["variable"] = str(new_v)
                break
        fs["variable_filters"] = vfs
        return fs

    @app.callback(
        Output("analysis-data-filters-store", "data", allow_duplicate=True),
        Input({"type": "analysis-var-filter-a", "fid": ALL}, "value"),
        State({"type": "analysis-var-filter-a", "fid": ALL}, "id"),
        State("analysis-data-filters-store", "data"),
        prevent_initial_call=True,
    )
    def analysis_var_filter_value_a(vals, ids, current):
        ctx = callback_context
        tid = ctx.triggered_id
        if not isinstance(tid, dict) or tid.get("type") != "analysis-var-filter-a":
            raise PreventUpdate
        fid = int(tid["fid"])
        new_v = None
        for i, bid in enumerate(ids or []):
            if bid == tid and vals is not None and i < len(vals):
                new_v = vals[i]
                break
        fs = normalize_analysis_filter_state(current)
        vfs = [dict(x) for x in (fs.get("variable_filters") or [])]
        for x in vfs:
            if int(x.get("id", -1)) == fid:
                x["value_a"] = to_opt_float(new_v)
                break
        fs["variable_filters"] = vfs
        return fs

    @app.callback(
        Output("analysis-data-filters-store", "data", allow_duplicate=True),
        Input({"type": "analysis-var-filter-b", "fid": ALL}, "value"),
        State({"type": "analysis-var-filter-b", "fid": ALL}, "id"),
        State("analysis-data-filters-store", "data"),
        prevent_initial_call=True,
    )
    def analysis_var_filter_value_b(vals, ids, current):
        ctx = callback_context
        tid = ctx.triggered_id
        if not isinstance(tid, dict) or tid.get("type") != "analysis-var-filter-b":
            raise PreventUpdate
        fid = int(tid["fid"])
        new_v = None
        for i, bid in enumerate(ids or []):
            if bid == tid and vals is not None and i < len(vals):
                new_v = vals[i]
                break
        fs = normalize_analysis_filter_state(current)
        vfs = [dict(x) for x in (fs.get("variable_filters") or [])]
        for x in vfs:
            if int(x.get("id", -1)) == fid:
                x["value_b"] = to_opt_float(new_v)
                break
        fs["variable_filters"] = vfs
        return fs

    @app.callback(
        Output("analysis-data-filters-store", "data"),
        Input("analysis-filter-time-all", "n_clicks"),
        Input("analysis-filter-time-after", "n_clicks"),
        Input("analysis-filter-time-before", "n_clicks"),
        Input("analysis-filter-time-between", "n_clicks"),
        Input("analysis-filter-reset-btn", "n_clicks"),
        Input("analysis-filter-time-date-a", "date"),
        Input("analysis-filter-time-date-b", "date"),
        Input("analysis-filter-time-time-a", "value"),
        Input("analysis-filter-time-time-b", "value"),
        State("analysis-data-filters-store", "data"),
        prevent_initial_call=True,
    )
    def update_analysis_filter_state(
        _t_all,
        _t_after,
        _t_before,
        _t_between,
        _reset,
        time_date_a,
        time_date_b,
        time_time_a,
        time_time_b,
        current,
    ):
        fs = normalize_analysis_filter_state(current)
        trig = callback_context.triggered_id
        if trig == "analysis-filter-reset-btn":
            return default_analysis_filter_state()
        if trig == "analysis-filter-time-all":
            fs["time_mode"] = "all"
        elif trig == "analysis-filter-time-after":
            fs["time_mode"] = "after"
        elif trig == "analysis-filter-time-before":
            fs["time_mode"] = "before"
        elif trig == "analysis-filter-time-between":
            fs["time_mode"] = "between"
        fs["time_date_a"] = str(time_date_a) if time_date_a else None
        fs["time_date_b"] = str(time_date_b) if time_date_b else None
        fs["time_time_a"] = str(time_time_a or "").strip() or "00:00"
        fs["time_time_b"] = str(time_time_b or "").strip() or "23:59"
        return fs

    @app.callback(
        Output("analysis-filter-multi-notice", "style"),
        Output("analysis-filter-body", "style"),
        Output("analysis-filter-badge", "style"),
        Output("analysis-filter-badge", "children"),
        Output("analysis-filter-time-all", "className"),
        Output("analysis-filter-time-after", "className"),
        Output("analysis-filter-time-before", "className"),
        Output("analysis-filter-time-between", "className"),
        Output("analysis-filter-time-inputs", "style"),
        Output("analysis-filter-time-row-b", "style"),
        Output("analysis-filter-time-label-a", "children"),
        Input("analysis-tests-store", "data"),
        Input("analysis-data-filters-store", "data"),
    )
    def render_analysis_filter_ui(tests: Optional[List[dict]], filter_state: Optional[dict]):
        tests = list(tests or [])
        fs = normalize_analysis_filter_state(filter_state)
        single = len(tests) == 1

        def _cls(mode_val: str, active: str) -> str:
            return "filter-mode-pill active" if mode_val == active else "filter-mode-pill"

        t_mode = fs.get("time_mode", "all")
        active_count = count_active_variable_filters(fs.get("variable_filters") or [])
        t1 = to_opt_datetime(fs.get("time_date_a"), fs.get("time_time_a"), "00:00")
        t2 = to_opt_datetime(fs.get("time_date_b"), fs.get("time_time_b"), "23:59")
        if t_mode in {"after", "before"} and t1 is not None:
            active_count += 1
        elif t_mode == "between" and t1 is not None and t2 is not None:
            active_count += 1
        notice_style = {"display": "none"} if single else {"display": "flex"}
        body_style = {"opacity": "1", "pointerEvents": "auto"} if single else {"opacity": "0.35", "pointerEvents": "none"}
        badge_style = {
            "display": "inline-flex" if active_count else "none",
            "marginLeft": "auto",
            "background": "var(--gold)",
            "color": "#fff",
            "borderRadius": "20px",
            "padding": "1px 7px",
            "fontSize": "10px",
            "fontWeight": 600,
            "fontFamily": "DM Mono, monospace",
        }
        badge_txt = str(active_count)
        t_inputs_style = {"display": "none"} if t_mode == "all" else {"display": "block"}
        t_row_b_style = {"display": "flex"} if t_mode == "between" else {"display": "none"}
        t_label = "After" if t_mode == "after" else ("Before" if t_mode == "before" else "From")
        return (
            notice_style,
            body_style,
            badge_style,
            badge_txt,
            _cls(t_mode, "all"),
            _cls(t_mode, "after"),
            _cls(t_mode, "before"),
            _cls(t_mode, "between"),
            t_inputs_style,
            t_row_b_style,
            t_label,
        )
