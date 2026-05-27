import os

from dash import Dash, dcc, html
from flask_caching import Cache

from config import (
    APP_ROOT,
    DISPLAY_TO_MACHINE_ID,
    MACHINE_BADGE,
    MACHINES,
    PROJECT_ROOT,
    STEP_COLORS,
    VARIABLE_CONFIG,
)
from log_parser import parse_log_file, parse_log_header_metadata

from features.analysis.layout import build_analysis_layout
from features.otkph import build_otkph_layout, register_otkph_callbacks
from services.log_service import build_cached_parse_log, find_log_path_for_test_number

from features.monitor.auto_refresh import register_monitor_auto_refresh_callbacks
from features.monitor.callbacks import register_monitor_callbacks
from features.navigation.callbacks import register_navigation_callbacks
from features.analysis.callbacks import register_analysis_callbacks
from features.monitor.layout import _input_id, build_monitor_layout
from features.monitor.icons import (
    _ICON_TAB_MONITOR,
    _ICON_TAB_ANALYSIS,
    _ICON_TAB_OTKPH,
    _img_tab_style,
)


app = Dash(__name__, assets_folder="assets", suppress_callback_exceptions=True)
server = app.server
cache = Cache(
    server,
    config={
        "CACHE_TYPE": "FileSystemCache",
        "CACHE_DIR": os.path.join(APP_ROOT, ".cache"),
        "CACHE_DEFAULT_TIMEOUT": 600,
    },
)
os.makedirs(os.path.join(APP_ROOT, ".cache"), exist_ok=True)

cached_parse_log = build_cached_parse_log(cache, parse_log_file)


app.layout = html.Div(
    children=[
        html.Div(
            className="topbar",
            children=[
                html.Div(
                    className="topbar-left",
                    children=[
                        html.Div(
                            className="brand",
                            children=[html.Div(className="brand-dot"), "TireTherm"],
                        ),
                        html.Div(
                            className="nav-tabs",
                            children=[
                                html.Button(
                                    id="tab-monitor-btn",
                                    className="nav-tab active",
                                    n_clicks=0,
                                    type="button",
                                    children=[
                                        html.Img(src=_ICON_TAB_MONITOR, alt="", style=_img_tab_style),
                                        "Live Monitor",
                                    ],
                                ),
                                html.Button(
                                    id="tab-analysis-btn",
                                    className="nav-tab",
                                    n_clicks=0,
                                    type="button",
                                    children=[
                                        html.Img(src=_ICON_TAB_ANALYSIS, alt="", style=_img_tab_style),
                                        "Data Analysis",
                                    ],
                                ),
                                html.Button(
                                    id="tab-otkph-btn",
                                    className="nav-tab",
                                    n_clicks=0,
                                    type="button",
                                    children=[
                                        html.Img(src=_ICON_TAB_OTKPH, alt="", style=_img_tab_style),
                                        "O-TKPH Analysis",
                                    ],
                                ),
                            ],
                        ),
                    ],
                ),
                html.Div(
                    className="topbar-right",
                    children=[
                        html.Div(className="live-pill", children=[html.Div(className="live-dot"), html.Span("LIVE")]),
                        html.Div(
                            id="clock",
                            style={"fontFamily": "'DM Mono', monospace", "fontSize": "11px", "color": "var(--muted)"},
                        ),
                    ],
                ),
            ],
        ),
        dcc.Store(id="main-tab-store", data="monitor"),
        dcc.Store(id="auto-refresh-enabled-store", data=True),
        dcc.Store(id="auto-refresh-cycle-store", data={}),
        dcc.Store(id="auto-refresh-trigger-store", data=0),
        dcc.Interval(id="clock-interval", interval=1000, n_intervals=0),
        build_monitor_layout(MACHINES, _input_id),
        html.Div(
            id="analysis-page",
            className="tab-page",
            style={"display": "none"},
            children=[
                html.Div(
                    className="main",
                    children=[build_analysis_layout()],
                ),
            ],
        ),
        html.Div(
            id="otkph-page",
            className="tab-page",
            style={"display": "none"},
            children=[
                html.Div(
                    className="main",
                    children=[build_otkph_layout()],
                ),
            ],
        ),
    ],
)

register_monitor_callbacks(
    app,
    VARIABLE_CONFIG=VARIABLE_CONFIG,
    MACHINES=MACHINES,
    MACHINE_BADGE=MACHINE_BADGE,
    STEP_COLORS=STEP_COLORS,
    input_id_fn=_input_id,
    find_log_path_for_test_number=lambda test_number: find_log_path_for_test_number(test_number, PROJECT_ROOT),
    parse_log_header_metadata=parse_log_header_metadata,
    cached_parse_log=cached_parse_log,
    DISPLAY_TO_MACHINE_ID=DISPLAY_TO_MACHINE_ID,
)

register_monitor_auto_refresh_callbacks(
    app,
    MACHINES=MACHINES,
    input_id_fn=_input_id,
)

register_navigation_callbacks(app)

register_analysis_callbacks(
    app,
    VARIABLE_CONFIG=VARIABLE_CONFIG,
    find_log_path_for_test_number=lambda tn: find_log_path_for_test_number(tn, PROJECT_ROOT),
    cached_parse_log=cached_parse_log,
)

register_otkph_callbacks(
    app,
    step_colors=STEP_COLORS,
    find_log_path=lambda test_number: find_log_path_for_test_number(test_number, PROJECT_ROOT),
    cached_parse=cached_parse_log,
)

if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=8050)
