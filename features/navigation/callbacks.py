from __future__ import annotations

from dash import Input, Output, callback_context


def register_navigation_callbacks(app) -> None:
    # --- Dashboard tabs (Live Monitor vs Data Analysis vs O-TKPH) ---
    @app.callback(
        Output("main-tab-store", "data"),
        Input("tab-monitor-btn", "n_clicks"),
        Input("tab-analysis-btn", "n_clicks"),
        Input("tab-otkph-btn", "n_clicks"),
    )
    def switch_main_tab(_n_mon, _n_an, _n_ot):
        ctx = callback_context
        if not ctx.triggered_id:
            return "monitor"
        tid = ctx.triggered_id
        if tid == "tab-monitor-btn":
            return "monitor"
        if tid == "tab-otkph-btn":
            return "otkph"
        return "analysis"


    @app.callback(
        Output("monitor-page", "style"),
        Output("analysis-page", "style"),
        Output("otkph-page", "style"),
        Input("main-tab-store", "data"),
    )
    def toggle_tab_pages(tab):
        hide = {"display": "none"}
        show = {"display": "block"}
        if tab == "analysis":
            return hide, show, hide
        if tab == "otkph":
            return hide, hide, show
        return show, hide, hide


    @app.callback(
        Output("tab-monitor-btn", "className"),
        Output("tab-analysis-btn", "className"),
        Output("tab-otkph-btn", "className"),
        Input("main-tab-store", "data"),
    )
    def style_tab_buttons(tab):
        base = "nav-tab"
        a = f"{base} active"
        if tab == "analysis":
            return base, a, base
        if tab == "otkph":
            return base, base, a
        return a, base, base


