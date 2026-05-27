from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from dash import Input, Output, State, dcc
from dash.exceptions import PreventUpdate

from features.analysis.services import apply_single_test_analysis_filters
from services.data_utils import _apply_chart_filters, _rows_to_df


def register_analysis_export_callbacks(app, *, VARIABLE_CONFIG) -> None:
    variable_config = VARIABLE_CONFIG
    rows_to_df = _rows_to_df
    apply_chart_filters = _apply_chart_filters

    @app.callback(
        Output("analysis-csv-download", "data"),
        Input("analysis-export-csv-btn", "n_clicks"),
        State("analysis-tests-store", "data"),
        State("analysis-data-store", "data"),
        State("analysis-active-steps-store", "data"),
        State("analysis-ignore-stopped-store", "data"),
        State("analysis-normalize-store", "data"),
        State("analysis-data-filters-store", "data"),
        State("analysis-variable-dropdown", "value"),
        prevent_initial_call=True,
    )
    def export_analysis_csv(_n, tests: Optional[List[dict]], data: Optional[dict], active_steps: List[object], ignore_stopped: bool, normalize_x: bool, data_filters: Optional[dict], selected_var: str):
        tests = list(tests or [])
        data = dict(data or {})
        var_cfg = variable_config.get(selected_var, variable_config["temperature"])
        value_col = var_cfg["col"]
        series: Dict[str, Tuple[pd.DataFrame, str]] = {}
        for t in tests:
            tn = str(t.get("test_number", ""))
            entry = data.get(tn, {})
            if entry.get("status") != "ok":
                continue
            df = rows_to_df(entry.get("rows") or [])
            dff = apply_chart_filters(df, active_steps, ignore_stopped)
            if len(tests) == 1:
                dff = apply_single_test_analysis_filters(dff, value_col=value_col, filters=data_filters)
            dff = dff.sort_values("timestamp").reset_index(drop=True)
            if dff.empty:
                continue
            col_name = f"{var_cfg['label'].replace(' ', '_')}_test_{tn}"
            series[col_name] = (dff, tn)
        if not series:
            raise PreventUpdate
        max_len = max(len(dff) for dff, _tn in series.values())
        dfs_to_merge = []
        for col_name, (dff, tn) in series.items():
            tmp = dff[[value_col, "step", "timestamp"]].reset_index(drop=True).copy()
            tmp = tmp.rename(columns={value_col: col_name, "step": f"step_{tn}"})
            dfs_to_merge.append(tmp.reindex(range(max_len)))
        out = pd.concat(dfs_to_merge, axis=1)
        ts_drop = [c for c in out.columns if c == "timestamp" or (isinstance(c, str) and c.startswith("timestamp."))]
        out = out.drop(columns=ts_drop, errors="ignore")
        out.insert(0, "index", range(len(out)))
        if not normalize_x:
            first_dff = next(iter(series.values()))[0]
            ts_series = first_dff["timestamp"].reindex(range(max_len))
            out.insert(1, "timestamp", ts_series.dt.strftime("%Y-%m-%d %H:%M:%S").fillna(""))
        for col_name, (_dff, tn) in series.items():
            val_arr = pd.to_numeric(out[col_name], errors="coerce").to_numpy(dtype=float, copy=False)
            val_obj = np.empty(len(val_arr), dtype=object)
            nan_v = np.isnan(val_arr)
            val_obj[nan_v] = ""
            val_obj[~nan_v] = val_arr[~nan_v].astype(float)
            out[col_name] = val_obj
            step_arr = pd.to_numeric(out[f"step_{tn}"], errors="coerce").to_numpy(dtype=float, copy=False)
            step_obj = np.empty(len(step_arr), dtype=object)
            nan_s = np.isnan(step_arr)
            step_obj[nan_s] = ""
            step_obj[~nan_s] = step_arr[~nan_s].astype(np.int64)
            out[f"step_{tn}"] = step_obj
        col_order: List[str] = ["index"]
        if not normalize_x:
            col_order.append("timestamp")
        for col_name, (_dff, tn) in series.items():
            col_order.extend([col_name, f"step_{tn}"])
        out = out[col_order]
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_var = "".join(ch for ch in (selected_var or "var") if ch.isalnum() or ch in ("-", "_"))
        filename = f"analysis_{safe_var}_{stamp}.csv"
        return dcc.send_data_frame(out.to_csv, filename, index=False)
