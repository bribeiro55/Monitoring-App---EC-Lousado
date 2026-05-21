"""
Compatibility shim for legacy OTKPH imports.
"""

from __future__ import annotations

from features.otkph.callbacks import register_otkph_callbacks
from features.otkph.figures import (
    _blank_fig,
    _compute_max_delta,
    build_camera_time_figure,
    build_delta_figure,
    build_scatter_figure,
    build_speed_figure,
)
from features.otkph.layout import build_otkph_layout
from features.otkph.services import (
    CAM_DEFS,
    _apply_otkph_data_filters,
    _build_effective_elapsed_seconds,
    _camera_health,
    _default_otkph_filter_state,
    _filter_otkph_frame,
    _format_frozen_period,
    _normalize_otkph_filter_state,
    _thermo_col,
    _to_opt_datetime,
    _with_plot_axis,
    collect_frozen_periods,
)

__all__ = [
    "CAM_DEFS",
    "_thermo_col",
    "_camera_health",
    "_filter_otkph_frame",
    "_default_otkph_filter_state",
    "_normalize_otkph_filter_state",
    "_to_opt_datetime",
    "_apply_otkph_data_filters",
    "_build_effective_elapsed_seconds",
    "_with_plot_axis",
    "_format_frozen_period",
    "collect_frozen_periods",
    "_blank_fig",
    "_compute_max_delta",
    "build_camera_time_figure",
    "build_delta_figure",
    "build_speed_figure",
    "build_scatter_figure",
    "build_otkph_layout",
    "register_otkph_callbacks",
]
