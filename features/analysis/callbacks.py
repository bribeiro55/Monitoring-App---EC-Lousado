from __future__ import annotations

from features.analysis.callbacks_data_loading import register_analysis_data_loading_callbacks
from features.analysis.callbacks_export import register_analysis_export_callbacks
from features.analysis.callbacks_filters import register_analysis_filter_callbacks
from features.analysis.callbacks_rendering import register_analysis_rendering_callbacks


def register_analysis_callbacks(app, deps: dict) -> None:
    register_analysis_filter_callbacks(app, deps)
    register_analysis_data_loading_callbacks(app, deps)
    register_analysis_rendering_callbacks(app, deps)
    register_analysis_export_callbacks(app, deps)


