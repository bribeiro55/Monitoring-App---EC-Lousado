from __future__ import annotations

from typing import Any, List, Optional, TypedDict


class LoadDebugPayload(TypedDict, total=False):
    log_path: str
    parsed_rows: int
    filtered_rows: int
    rows_plotted: int
    expected: str
    used_full_log_fallback: bool
    latest_machine_id: Optional[str]
    latest_position: Optional[int]
    slot_eligible: bool
    reason: str
    test_number: str
    error: str


class LoadedLogEntry(TypedDict, total=False):
    test_number: str
    status: str
    message: str
    rows: List[dict]
    load_debug: LoadDebugPayload
    tire_size: Optional[str]
    test_name: Optional[str]
    slot_eligible: bool
    latest_machine_id: Optional[str]
    latest_position: Optional[int]


class ModalSelection(TypedDict, total=False):
    slot: str
    test_number: str


class AnalysisTestRef(TypedDict):
    test_number: str
    color_index: int


class AnalysisDataEntry(TypedDict, total=False):
    test_number: str
    status: str
    message: str
    rows: List[dict]
    load_debug: LoadDebugPayload


class AnalysisBandLimits(TypedDict):
    upper: Optional[float]
    lower: Optional[float]


class AnalysisFilterState(TypedDict, total=False):
    variable_filters: List[Any]
    time_mode: str
    time_date_a: Optional[str]
    time_date_b: Optional[str]
    time_time_a: str
    time_time_b: str


def make_loaded_log_entry(**kwargs: Any) -> LoadedLogEntry:
    # Keep JSON payload backward-compatible with existing dcc.Store consumers.
    return LoadedLogEntry(**kwargs)


def make_modal_selection(slot: str, test_number: str) -> ModalSelection:
    return ModalSelection(slot=slot, test_number=test_number)


def make_analysis_test_ref(test_number: str, color_index: int) -> AnalysisTestRef:
    return AnalysisTestRef(test_number=test_number, color_index=int(color_index))


def make_analysis_data_entry(**kwargs: Any) -> AnalysisDataEntry:
    return AnalysisDataEntry(**kwargs)


def make_analysis_band_limits(upper: Optional[float], lower: Optional[float]) -> AnalysisBandLimits:
    return AnalysisBandLimits(upper=upper, lower=lower)


