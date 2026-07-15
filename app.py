import logging
import os
import platform

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)

import diskcache
from dash import Dash, DiskcacheManager, dcc, html
from flask_caching import Cache

from config import (
    APP_ROOT,
    DATA_SMB_SERVER,
    DISPLAY_TO_MACHINE_ID,
    LOGS_DEST_ROOT,
    MACHINE_BADGE,
    MACHINES,
    PROJECT_ROOT,
    SLOT_ASSIGNMENTS_PATH,
    SMB_SERVER,
    STEP_COLORS,
    TEST_REGISTRY_PATH,
    VARIABLE_CONFIG,
)
from log_parser import parse_log_file, parse_log_header_metadata
from services.test_registry import TestRegistry
from services.slot_assignments import SlotAssignments
from services.log_archive import copy_test_folder, copy_test_folder_smb

from features.analysis.layout import build_analysis_layout
from features.otkph import build_otkph_layout, register_otkph_callbacks
from services.log_service import (
    build_cached_parse_log,
    build_cached_parse_log_smb,
    find_log_path_for_test_number,
    find_log_path_smb,
    parse_log_file_smb,
    parse_log_header_metadata_smb,
)

from features.monitor.auto_refresh import register_monitor_auto_refresh_callbacks
from features.monitor.callbacks import register_monitor_callbacks
from features.monitor.end_test.callbacks import register_end_test_callbacks
from features.monitor.occupation.callbacks import register_occupation_callbacks
from features.navigation.callbacks import register_navigation_callbacks
from features.analysis.callbacks import register_analysis_callbacks
from features.monitor.layout import _input_id, build_monitor_layout
from features.monitor.icons import (
    _ICON_TAB_MONITOR,
    _ICON_TAB_ANALYSIS,
    _ICON_TAB_OTKPH,
    _img_tab_style,
    ICON_REGISTRY,
)


_background_cache = diskcache.Cache(os.path.join(APP_ROOT, ".diskcache"))
background_callback_manager = DiskcacheManager(_background_cache)

app = Dash(
    __name__,
    assets_folder="assets",
    suppress_callback_exceptions=True,
    background_callback_manager=background_callback_manager,
)
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

if platform.system() == "Windows":
    _find_log_path_primary = lambda tn: find_log_path_for_test_number(tn, PROJECT_ROOT)
    _find_log_path_fallback = lambda tn: find_log_path_for_test_number(tn, LOGS_DEST_ROOT)
    _parse_log_fn = parse_log_file
    _parse_meta_fn = parse_log_header_metadata
    cached_parse_log = build_cached_parse_log(cache, _parse_log_fn)
    _copy_test_folder = copy_test_folder
else:
    _smb_user = os.environ.get("GTT_SERVER_USER", "")
    _smb_pass = os.environ.get("GTT_SERVER_PASS", "")
    if _smb_user and _smb_pass:
        try:
            import smbclient as _smbc
            _smbc.register_session(server=SMB_SERVER, username=_smb_user, password=_smb_pass)
            logging.getLogger(__name__).info("SMB session registered for %s", SMB_SERVER)
        except Exception as _e:
            logging.getLogger(__name__).warning("SMB session failed at startup: %s", _e)

        try:
            import smbclient as _smbc
            _smbc.register_session(server=DATA_SMB_SERVER, username=_smb_user, password=_smb_pass)
            logging.getLogger(__name__).info("SMB session registered for %s (data share)", DATA_SMB_SERVER)
        except Exception as _e:
            logging.getLogger(__name__).warning(
                "SMB session failed at startup for %s (data share) — registry/slot persistence will fail "
                "until this is resolved: %s", DATA_SMB_SERVER, _e,
            )
    else:
        logging.getLogger(__name__).warning("GTT_SERVER_USER / GTT_SERVER_PASS not set — SMB reads will fail")
    _find_log_path_primary = lambda tn: find_log_path_smb(tn, PROJECT_ROOT)
    _find_log_path_fallback = lambda tn: find_log_path_smb(tn, LOGS_DEST_ROOT)
    _parse_log_fn = parse_log_file_smb
    _parse_meta_fn = parse_log_header_metadata_smb
    cached_parse_log = build_cached_parse_log_smb(cache, _parse_log_fn)
    _copy_test_folder = copy_test_folder_smb

def _find_log_path(tn):
    return _find_log_path_primary(tn) or _find_log_path_fallback(tn)

registry = TestRegistry(TEST_REGISTRY_PATH)
registry.load()

slot_store = SlotAssignments(SLOT_ASSIGNMENTS_PATH)
slot_store.load()


def serve_layout():
    return html.Div(
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
                        html.Button(
                            id="registry-open-btn",
                            className="icon-btn",
                            title="Test Registry",
                            n_clicks=0,
                            style={"display": "flex", "alignItems": "center", "padding": "0", "marginRight": "8px"},
                            children=[
                                html.Img(
                                    src=ICON_REGISTRY,
                                    alt="",
                                    style={"width": "15px", "height": "15px", "display": "block"},
                                )
                            ],
                        ),
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
        build_monitor_layout(MACHINES, _input_id, initial_values=slot_store.get_all()),
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
        html.Div(
            id="registry-modal-overlay",
            className="modal-overlay",
            children=[
                html.Div(
                    className="modal",
                    style={"maxWidth": "640px", "width": "90%"},
                    children=[
                        html.Div(
                            className="modal-header",
                            children=[
                                html.Div(html.Div("Test Registry", className="modal-title")),
                                html.Div(
                                    className="modal-actions",
                                    children=[
                                        html.Button("✕", id="registry-modal-close-btn", className="modal-close", n_clicks=0),
                                    ],
                                ),
                            ],
                        ),
                        html.Div(id="registry-modal-body"),
                        html.Div(
                            style={"display": "flex", "gap": "8px", "alignItems": "center",
                                   "paddingTop": "12px", "borderTop": "1px solid var(--border)"},
                            children=[
                                dcc.Input(
                                    id="registry-add-input",
                                    className="test-input",
                                    placeholder="Test number",
                                    type="text",
                                    value="",
                                    debounce=False,
                                    style={"width": "140px"},
                                ),
                                html.Button(
                                    "Add Active",
                                    id="registry-add-btn",
                                    className="refresh-btn",
                                    n_clicks=0,
                                    style={"fontSize": "12px"},
                                ),
                            ],
                        ),
                    ],
                ),
            ],
        ),
    ],
    )


app.layout = serve_layout

register_monitor_callbacks(
    app,
    VARIABLE_CONFIG=VARIABLE_CONFIG,
    MACHINES=MACHINES,
    MACHINE_BADGE=MACHINE_BADGE,
    STEP_COLORS=STEP_COLORS,
    input_id_fn=_input_id,
    find_log_path_for_test_number=_find_log_path,
    parse_log_header_metadata=_parse_meta_fn,
    cached_parse_log=cached_parse_log,
    DISPLAY_TO_MACHINE_ID=DISPLAY_TO_MACHINE_ID,
    registry=registry,
    slot_store=slot_store,
)

register_occupation_callbacks(
    app,
    MACHINES=MACHINES,
    DISPLAY_TO_MACHINE_ID=DISPLAY_TO_MACHINE_ID,
    input_id_fn=_input_id,
    find_log_path=_find_log_path,
    cached_parse_log=cached_parse_log,
)

register_end_test_callbacks(
    app,
    copy_test_folder=_copy_test_folder,
    dest_root=LOGS_DEST_ROOT,
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
    find_log_path_for_test_number=_find_log_path,
    cached_parse_log=cached_parse_log,
)

register_otkph_callbacks(
    app,
    step_colors=STEP_COLORS,
    find_log_path=_find_log_path,
    cached_parse=cached_parse_log,
)

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=8050)
