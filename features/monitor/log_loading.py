from __future__ import annotations

from typing import Callable, Dict, List, Optional

import pandas as pd

from domain.models import make_loaded_log_entry


def load_logs_for_test_inputs(
    machines: List[str],
    tA1: str,
    tA2: str,
    tB1: str,
    tB2: str,
    tC1: str,
    tC2: str,
    *,
    find_log_path_for_test_number: Callable[[str], Optional[str]],
    parse_log_header_metadata: Callable,
    cached_parse_log: Callable,
    display_to_machine_id: Dict[str, str],
    serialize_df_rows: Callable,
) -> Dict[str, dict]:
    slots = {
        f"{machines[0]}|1": (machines[0], 1, tA1),
        f"{machines[0]}|2": (machines[0], 2, tA2),
        f"{machines[1]}|1": (machines[1], 1, tB1),
        f"{machines[1]}|2": (machines[1], 2, tB2),
        f"{machines[2]}|1": (machines[2], 1, tC1),
        f"{machines[2]}|2": (machines[2], 2, tC2),
    }

    loaded: Dict[str, dict] = {}
    for slot_key, (machine_label, pos, raw_test) in slots.items():
        test_number = str(raw_test).strip() if raw_test else ""
        if not test_number:
            continue

        log_path = find_log_path_for_test_number(test_number)
        if not log_path:
            loaded[slot_key] = make_loaded_log_entry(
                test_number=test_number,
                status="not_found",
                message=f"file {test_number} not found",
                rows=[],
                load_debug={"reason": "no folder ending with .00a or .log found", "test_number": test_number},
            )
            continue

        try:
            header_meta = parse_log_header_metadata(log_path)
            df = cached_parse_log(log_path)
            machine_id = display_to_machine_id[machine_label]
            df_filt = df[(df["machine_id"] == machine_id) & (df["position"] == pos)].copy()
            df_use = df.copy()
            used_fallback = df_filt.empty and not df.empty

            latest_mid: Optional[str] = None
            latest_pos: Optional[int] = None
            slot_eligible = False
            if not df.empty:
                last = df.sort_values("timestamp").iloc[-1]
                lm = last.get("machine_id")
                lp = last.get("position")
                if lm is not None and lp is not None and not (pd.isna(lm) or pd.isna(lp)):
                    latest_mid = str(lm)
                    latest_pos = int(lp)
                    slot_eligible = latest_mid == str(machine_id) and latest_pos == int(pos)

            load_debug = {
                "log_path": log_path,
                "parsed_rows": int(len(df)),
                "filtered_rows": int(len(df_filt)),
                "rows_plotted": int(len(df_use)),
                "expected": f"{machine_id} position {pos}",
                "used_full_log_fallback": used_fallback,
                "latest_machine_id": latest_mid,
                "latest_position": latest_pos,
                "slot_eligible": slot_eligible,
            }

            loaded[slot_key] = make_loaded_log_entry(
                test_number=test_number,
                status="ok",
                rows=serialize_df_rows(df_use),
                tire_size=header_meta.get("tire_size"),
                test_name=header_meta.get("test_name"),
                load_debug=load_debug,
                slot_eligible=slot_eligible,
                latest_machine_id=latest_mid,
                latest_position=latest_pos,
            )
        except Exception as e:
            loaded[slot_key] = make_loaded_log_entry(
                test_number=test_number,
                status="error",
                message=str(e),
                rows=[],
                load_debug={"log_path": log_path, "error": str(e)},
            )

    return loaded
