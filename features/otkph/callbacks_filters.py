from __future__ import annotations

from typing import Callable, Dict, List, Optional

import pandas as pd
from dash import Input, Output, State, callback_context

from .services import (
    _apply_ignore_interrupted_rows,
    _apply_otkph_data_filters,
    _default_otkph_filter_state,
    _filter_otkph_frame,
    _normalize_otkph_filter_state,
)


def register_otkph_filter_callbacks(
    app,
    *,
    step_colors: Dict[int, str],
    rows_to_df: Callable[[List[dict]], pd.DataFrame],
    find_log_path: Callable[[str], Optional[str]],
    cached_parse: Callable[[str], pd.DataFrame],
    serialize_df_rows: Callable[[pd.DataFrame], List[dict]],
) -> None:
    @app.callback(
        Output("otkph-test-warning", "children"),
        Input("otkph-test-input", "value"),
        Input("loaded-logs-store", "data"),
    )
    def otkph_test_warning(raw_test: Optional[str], loaded: Optional[dict]):
        tn = str(raw_test or "").strip()
        if not tn:
            return ""
        loaded = loaded or {}
        for _sk, entry in loaded.items():
            if entry.get("status") != "ok":
                continue
            if str(entry.get("test_number") or "").strip() == tn:
                return ""
        if find_log_path(tn):
            return ""
        return f"Test {tn} not found"

    @app.callback(
        Output("otkph-resolved-rows-store", "data"),
        Input("otkph-test-input", "value"),
        Input("loaded-logs-store", "data"),
    )
    def otkph_resolve_rows(raw_test: Optional[str], loaded: Optional[dict]):
        tn = str(raw_test or "").strip()
        if not tn:
            return []
        loaded = loaded or {}
        for _sk, entry in loaded.items():
            if entry.get("status") != "ok":
                continue
            if str(entry.get("test_number") or "").strip() != tn:
                continue
            return entry.get("rows") or []
        path = find_log_path(tn)
        if not path:
            return []
        try:
            df = cached_parse(path)
            return serialize_df_rows(df)
        except Exception:
            return []

    @app.callback(
        Output("otkph-filtered-rows-store", "data"),
        Input("otkph-resolved-rows-store", "data"),
        Input("otkph-step-select", "value"),
        Input("otkph-data-filters-store", "data"),
        Input("otkph-ignore-interrupted-store", "data"),
    )
    def otkph_filtered_rows_store(rows, step_filt, filter_state, ignore_interrupted):
        df = rows_to_df(list(rows or []))
        dff = _filter_otkph_frame(df, str(step_filt or "all"))
        dff = _apply_otkph_data_filters(dff, filter_state)
        dff = _apply_ignore_interrupted_rows(dff, bool(ignore_interrupted))
        return serialize_df_rows(dff)

    @app.callback(
        Output("otkph-data-filters-store", "data"),
        Input("otkph-filter-time-all", "n_clicks"),
        Input("otkph-filter-time-after", "n_clicks"),
        Input("otkph-filter-time-before", "n_clicks"),
        Input("otkph-filter-time-between", "n_clicks"),
        Input("otkph-filter-reset-btn", "n_clicks"),
        Input("otkph-filter-time-date-a", "date"),
        Input("otkph-filter-time-date-b", "date"),
        Input("otkph-filter-time-time-a", "value"),
        Input("otkph-filter-time-time-b", "value"),
        State("otkph-data-filters-store", "data"),
        prevent_initial_call=True,
    )
    def otkph_update_filter_state(
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
        fs = _normalize_otkph_filter_state(current)
        trig = callback_context.triggered_id
        if trig == "otkph-filter-reset-btn":
            return _default_otkph_filter_state()
        if trig == "otkph-filter-time-all":
            fs["time_mode"] = "all"
        elif trig == "otkph-filter-time-after":
            fs["time_mode"] = "after"
        elif trig == "otkph-filter-time-before":
            fs["time_mode"] = "before"
        elif trig == "otkph-filter-time-between":
            fs["time_mode"] = "between"
        fs["time_date_a"] = str(time_date_a) if time_date_a else None
        fs["time_date_b"] = str(time_date_b) if time_date_b else None
        fs["time_time_a"] = str(time_time_a or "").strip() or "00:00"
        fs["time_time_b"] = str(time_time_b or "").strip() or "23:59"
        return fs

    @app.callback(
        Output("otkph-filter-time-all", "className"),
        Output("otkph-filter-time-after", "className"),
        Output("otkph-filter-time-before", "className"),
        Output("otkph-filter-time-between", "className"),
        Output("otkph-filter-time-inputs", "style"),
        Output("otkph-filter-time-row-b", "style"),
        Output("otkph-filter-time-label-a", "children"),
        Input("otkph-data-filters-store", "data"),
    )
    def otkph_render_filter_ui(filter_state):
        fs = _normalize_otkph_filter_state(filter_state)
        t_mode = fs.get("time_mode", "all")

        def _cls(mode_val: str, active_val: str) -> str:
            return "filter-mode-pill active" if mode_val == active_val else "filter-mode-pill"

        t_inputs_style = {"display": "none"} if t_mode == "all" else {"display": "block"}
        t_row_b_style = {"display": "flex"} if t_mode == "between" else {"display": "none"}
        t_label = "After" if t_mode == "after" else ("Before" if t_mode == "before" else "From")

        return (
            _cls(t_mode, "all"),
            _cls(t_mode, "after"),
            _cls(t_mode, "before"),
            _cls(t_mode, "between"),
            t_inputs_style,
            t_row_b_style,
            t_label,
        )

