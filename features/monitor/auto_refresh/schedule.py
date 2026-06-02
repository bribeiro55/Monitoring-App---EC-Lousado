from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence

COUNTDOWN_SECONDS = 30
BOUNDARY_OPEN_GRACE_SECONDS = 5


def boundary_key(now: datetime) -> str:
    if now.minute < 30:
        return now.replace(minute=0, second=0, microsecond=0).strftime("%Y-%m-%dT%H:%M")
    else:
        return now.replace(minute=30, second=0, microsecond=0).strftime("%Y-%m-%dT%H:%M")


def is_boundary_opening(now: datetime) -> bool:
    return now.minute in (0, 30) and now.second < BOUNDARY_OPEN_GRACE_SECONDS


def has_any_test_input(values: Sequence[Optional[str]]) -> bool:
    return any(str(v).strip() if v else "" for v in values)


def default_cycle() -> Dict[str, Any]:
    return {
        "handled_boundary": "",
        "phase": "idle",
        "seconds_remaining": COUNTDOWN_SECONDS,
        "dismissed": False,
    }


def skipped_cycle(boundary: str) -> Dict[str, Any]:
    return {
        "handled_boundary": boundary,
        "phase": "skipped",
        "seconds_remaining": COUNTDOWN_SECONDS,
        "dismissed": False,
    }


@dataclass(frozen=True)
class CycleTickResult:
    cycle: Dict[str, Any]
    fire_refresh: bool


def next_cycle_state(
    now: datetime,
    cycle: Optional[Dict[str, Any]],
    enabled: bool,
    tab: str,
    input_values: Sequence[Optional[str]],
) -> CycleTickResult:
    current_boundary = boundary_key(now)
    state = dict(cycle or default_cycle())
    handled_boundary = str(state.get("handled_boundary") or "")
    phase = str(state.get("phase") or "idle")
    has_inputs = has_any_test_input(input_values)
    on_monitor = tab == "monitor"

    if handled_boundary == current_boundary and phase in ("completed", "skipped"):
        return CycleTickResult(state, False)

    if phase == "countdown" and handled_boundary == current_boundary:
        if not enabled or state.get("dismissed"):
            return CycleTickResult(skipped_cycle(current_boundary), False)

        seconds_remaining = int(state.get("seconds_remaining") or COUNTDOWN_SECONDS) - 1
        if seconds_remaining > 0:
            updated = {**state, "seconds_remaining": seconds_remaining}
            return CycleTickResult(updated, False)

        if not has_inputs:
            return CycleTickResult(skipped_cycle(current_boundary), False)

        completed = {
            **state,
            "phase": "completed",
            "seconds_remaining": 0,
        }
        return CycleTickResult(completed, True)

    if handled_boundary != current_boundary:
        if not is_boundary_opening(now):
            return CycleTickResult(skipped_cycle(current_boundary), False)

        if not enabled or not has_inputs:
            return CycleTickResult(skipped_cycle(current_boundary), False)

        if on_monitor:
            countdown = {
                "handled_boundary": current_boundary,
                "phase": "countdown",
                "seconds_remaining": COUNTDOWN_SECONDS,
                "dismissed": False,
            }
            return CycleTickResult(countdown, False)

        completed = {
            "handled_boundary": current_boundary,
            "phase": "completed",
            "seconds_remaining": COUNTDOWN_SECONDS,
            "dismissed": False,
        }
        return CycleTickResult(completed, True)

    return CycleTickResult(state, False)


def dismiss_cycle(cycle: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    state = dict(cycle or default_cycle())
    state["dismissed"] = True
    state["phase"] = "skipped"
    return state
