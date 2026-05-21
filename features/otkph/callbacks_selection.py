from __future__ import annotations

from typing import Callable, Dict, List

import pandas as pd
from dash import ALL, Input, Output, State, callback_context
from dash.exceptions import PreventUpdate

from .services import CAM_DEFS, _camera_health, _thermo_col


def _default_active_cameras(df: pd.DataFrame) -> List[int]:
    selected: List[int] = []
    if df.empty:
        return [1, 2, 3]
    for cd in CAM_DEFS:
        i = cd["i"]
        col = _thermo_col(i)
        if col not in df.columns:
            continue
        ser = pd.to_numeric(df[col], errors="coerce")
        if ser.dropna().empty:
            continue
        if not _camera_health(ser):
            continue
        selected.append(i)
        if len(selected) == 3:
            break
    return selected or [1, 2, 3]


def register_otkph_selection_callbacks(
    app,
    *,
    step_colors: Dict[int, str],
    rows_to_df: Callable,
    find_log_path: Callable,
    cached_parse: Callable,
    serialize_df_rows: Callable,
) -> None:
    @app.callback(
        Output("otkph-active-cameras-store", "data", allow_duplicate=True),
        Output("otkph-cam-warning", "children", allow_duplicate=True),
        Input("otkph-resolved-rows-store", "data"),
        prevent_initial_call=True,
    )
    def otkph_autoselect_cams_on_test(rows):
        d0 = rows_to_df(list(rows or []))
        return _default_active_cameras(d0), ""

    @app.callback(
        Output("otkph-active-cameras-store", "data"),
        Output("otkph-cam-warning", "children"),
        Input({"type": "otkph-cam", "i": ALL}, "n_clicks"),
        Input("otkph-filtered-rows-store", "data"),
        State({"type": "otkph-cam", "i": ALL}, "id"),
        State("otkph-active-cameras-store", "data"),
        prevent_initial_call=True,
    )
    def otkph_toggle_cam(_n, filtered_rows, ids, active):
        ctx = callback_context
        if not ctx.triggered_id or not isinstance(ctx.triggered_id, dict):
            raise PreventUpdate
        cam_i = int(ctx.triggered_id["i"])
        active = list(active or [1, 2, 3])
        set_a = set(active)
        d0 = rows_to_df(list(filtered_rows or []))
        col = _thermo_col(cam_i)
        if col in d0.columns and not _camera_health(d0[col]):
            return active, "This camera is flagged faulty (sensor data) and cannot be selected."

        if cam_i in set_a:
            if len(set_a) <= 1:
                return active, ""
            set_a.remove(cam_i)
            return sorted(set_a), ""
        if len(set_a) >= 3:
            return active, "Maximum 3 cameras can be selected at once."
        set_a.add(cam_i)
        return sorted(set_a), ""

    @app.callback(
        Output({"type": "otkph-cam", "i": ALL}, "className"),
        Input("otkph-active-cameras-store", "data"),
        Input("otkph-filtered-rows-store", "data"),
        State({"type": "otkph-cam", "i": ALL}, "id"),
    )
    def otkph_style_cards(active, filtered_rows, id_list):
        active = list(active or [1, 2, 3])
        set_a = set(active)
        d0 = rows_to_df(list(filtered_rows or []))
        classes = []
        for ido in id_list or []:
            i = int(ido["i"])
            base = "cam-card card"
            ok = _camera_health(d0[_thermo_col(i)]) if _thermo_col(i) in d0.columns else True
            if not ok:
                classes.append(f"{base} disabled")
            elif i in set_a:
                classes.append(f"{base} active")
            else:
                classes.append(base)
        return classes

    @app.callback(
        Output("otkph-smooth-store", "data"),
        Output("otkph-smooth-toggle", "className"),
        Input("otkph-smooth-toggle", "n_clicks"),
        State("otkph-smooth-store", "data"),
        prevent_initial_call=True,
    )
    def otkph_smooth_toggle(_n, cur):
        if not _n:
            raise PreventUpdate
        cur_b = bool(cur)
        new_b = not cur_b
        return new_b, "toggle on" if new_b else "toggle"

    @app.callback(
        Output("otkph-ignore-interrupted-store", "data"),
        Output("otkph-ignore-interrupted-toggle", "className"),
        Input("otkph-ignore-interrupted-toggle", "n_clicks"),
        State("otkph-ignore-interrupted-store", "data"),
        prevent_initial_call=True,
    )
    def otkph_ignore_interrupted_toggle(_n, cur):
        if not _n:
            raise PreventUpdate
        cur_b = bool(cur)
        new_b = not cur_b
        return new_b, "toggle on" if new_b else "toggle"

    @app.callback(
        Output("otkph-corr-a", "options"),
        Output("otkph-corr-a", "value"),
        Output("otkph-corr-b", "options"),
        Output("otkph-corr-b", "value"),
        Input("otkph-active-cameras-store", "data"),
        State("otkph-corr-a", "value"),
        State("otkph-corr-b", "value"),
    )
    def otkph_corr_opts(active, va, vb):
        active = list(active or [1, 2, 3])
        opts = [{"label": CAM_DEFS[i - 1]["code"], "value": i} for i in active]
        va = va if va in active else (active[0] if active else None)
        vb = vb if vb in active and vb != va else (active[1] if len(active) > 1 else va)
        if va == vb and len(active) > 1:
            vb = active[1] if active[1] != va else active[0]
        return opts, va, opts, vb

