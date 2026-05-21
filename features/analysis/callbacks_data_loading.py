from __future__ import annotations

from typing import Dict, List, Optional

from dash import ALL, Input, Output, State, callback_context
from dash.exceptions import PreventUpdate

from domain.models import make_analysis_data_entry, make_analysis_test_ref


def register_analysis_data_loading_callbacks(app, deps: dict) -> None:
    compare_palette = deps["COMPARE_PALETTE"]
    find_log_path_for_test_number = deps["find_log_path_for_test_number"]
    cached_parse_log = deps["cached_parse_log"]
    serialize_df_rows = deps["_serialize_df_rows"]

    @app.callback(
        Output("analysis-tests-store", "data"),
        Output("analysis-data-store", "data"),
        Output("analysis-test-input", "value"),
        Input("analysis-add-test-btn", "n_clicks"),
        State("analysis-test-input", "value"),
        State("analysis-tests-store", "data"),
        State("analysis-data-store", "data"),
        prevent_initial_call=True,
    )
    def analysis_add_test(_n, raw_input, tests: Optional[List[dict]], data: Optional[dict]):
        tests = list(tests or [])
        data = dict(data or {})
        tn = str(raw_input or "").strip()
        if not tn:
            raise PreventUpdate
        if any(str(t.get("test_number", "")).strip() == tn for t in tests):
            return tests, data, ""
        log_path = find_log_path_for_test_number(tn)
        if not log_path:
            data[tn] = make_analysis_data_entry(
                test_number=tn,
                status="not_found",
                message=f"Log for test {tn} not found",
                rows=[],
            )
        else:
            try:
                df = cached_parse_log(log_path)
                data[tn] = make_analysis_data_entry(
                    test_number=tn,
                    status="ok",
                    rows=serialize_df_rows(df),
                    load_debug={"log_path": log_path},
                )
            except Exception as e:
                data[tn] = make_analysis_data_entry(
                    test_number=tn,
                    status="error",
                    message=str(e),
                    rows=[],
                    load_debug={"log_path": log_path},
                )
        color_index = len(tests) % len(compare_palette)
        tests.append(make_analysis_test_ref(test_number=tn, color_index=color_index))
        return tests, data, ""

    @app.callback(
        Output("analysis-tests-store", "data", allow_duplicate=True),
        Output("analysis-data-store", "data", allow_duplicate=True),
        Input({"type": "analysis-rm-test", "tn": ALL}, "n_clicks"),
        State({"type": "analysis-rm-test", "tn": ALL}, "id"),
        State("analysis-tests-store", "data"),
        State("analysis-data-store", "data"),
        prevent_initial_call=True,
    )
    def analysis_remove_test(_n_clicks, _ids, tests: Optional[List[dict]], data: Optional[dict]):
        ctx = callback_context
        if not ctx.triggered_id:
            raise PreventUpdate
        tests = list(tests or [])
        data = dict(data or {})
        triggered = ctx.triggered_id
        if not isinstance(triggered, dict) or triggered.get("type") != "analysis-rm-test":
            raise PreventUpdate
        tn = str(triggered.get("tn", ""))
        idx = next((i for i, bid in enumerate(_ids or []) if bid == triggered), None)
        if idx is None:
            raise PreventUpdate
        clicks = _n_clicks[idx] if _n_clicks and idx < len(_n_clicks) else 0
        if not clicks:
            raise PreventUpdate
        tests = [t for t in tests if str(t.get("test_number")) != tn]
        data.pop(tn, None)
        return tests, data

    @app.callback(
        Output("analysis-violations-expanded-store", "data", allow_duplicate=True),
        Input("analysis-violations-view-more-btn", "n_clicks"),
        State("analysis-violations-expanded-store", "data"),
        prevent_initial_call=True,
    )
    def analysis_toggle_violations_expanded(_n_clicks, expanded):
        ctx = callback_context
        if not ctx.triggered_id:
            raise PreventUpdate
        return not bool(expanded)

    @app.callback(
        Output("analysis-violations-expanded-store", "data", allow_duplicate=True),
        Input("analysis-tests-store", "data"),
        Input("analysis-data-store", "data"),
        Input("analysis-limits-store", "data"),
        Input("analysis-data-filters-store", "data"),
        Input("analysis-variable-dropdown", "value"),
        Input("analysis-active-steps-store", "data"),
        Input("analysis-ignore-stopped-store", "data"),
        prevent_initial_call=True,
    )
    def analysis_reset_violations_expanded(_tests, _data, _limits, _filters, _var, _steps, _ignore):
        return False
