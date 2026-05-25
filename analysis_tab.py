# Legacy re-export shim — do not add logic here.
from services.chart_utils import (
    _downsample,
    _index_bounds_for_timestamp_window,
    _x_at_step_transition,
    build_step_ranges,
    build_step_transitions,
)
from features.analysis.figures import (
    build_comparison_figure,
    build_distribution_figure,
    build_step_average_figure,
)
from features.analysis.services import collect_band_crossing_violations, summary_status_for_band
from features.analysis.layout import build_analysis_layout
from config import COMPARE_PALETTE, LIMIT_PALETTE, BAND_UPPER_LINE_COLOR, BAND_LOWER_LINE_COLOR

__all__ = [
    "_downsample",
    "_index_bounds_for_timestamp_window",
    "_x_at_step_transition",
    "build_step_ranges",
    "build_step_transitions",
    "build_comparison_figure",
    "build_distribution_figure",
    "build_step_average_figure",
    "collect_band_crossing_violations",
    "summary_status_for_band",
    "build_analysis_layout",
    "COMPARE_PALETTE",
    "LIMIT_PALETTE",
    "BAND_UPPER_LINE_COLOR",
    "BAND_LOWER_LINE_COLOR",
]
