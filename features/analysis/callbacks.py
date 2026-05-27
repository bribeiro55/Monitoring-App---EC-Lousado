from __future__ import annotations

from features.analysis.callbacks_data_loading import register_analysis_data_loading_callbacks
from features.analysis.callbacks_export import register_analysis_export_callbacks
from features.analysis.callbacks_filters import register_analysis_filter_callbacks
from features.analysis.callbacks_rendering import register_analysis_rendering_callbacks


def register_analysis_callbacks(
    app,
    *,
    VARIABLE_CONFIG,
    find_log_path_for_test_number,
    cached_parse_log,
) -> None:
    register_analysis_filter_callbacks(app)
    register_analysis_data_loading_callbacks(
        app,
        find_log_path_for_test_number=find_log_path_for_test_number,
        cached_parse_log=cached_parse_log,
    )
    register_analysis_rendering_callbacks(app, VARIABLE_CONFIG=VARIABLE_CONFIG)
    register_analysis_export_callbacks(app, VARIABLE_CONFIG=VARIABLE_CONFIG)


