from __future__ import annotations

from typing import List, Optional, Tuple

import numpy as np
import pandas as pd

from services.data_utils import (
    _apply_chart_filters,
    _df_after_ignore_stopped,
    _filter_by_steps,
    _rows_to_df,
    _serialize_df_rows,
)

__all__ = [
    "_rows_to_df",
    "_serialize_df_rows",
    "_filter_by_steps",
    "_df_after_ignore_stopped",
    "_apply_chart_filters",
]


def _placement_key(machine_id: object, pos: object) -> Optional[Tuple[str, int]]:
    if machine_id is None or pos is None:
        return None
    try:
        if pd.isna(machine_id) or pd.isna(pos):
            return None
    except (ValueError, TypeError):
        return None
    try:
        return (str(machine_id), int(pos))
    except (ValueError, TypeError):
        return None


def _primary_placement_match_numpy(df: pd.DataFrame, primary: Tuple[str, int]) -> np.ndarray:
    """Row-wise boolean mask: True where (machine_id, position) matches primary."""
    mid = df["machine_id"].astype(str).to_numpy()
    pos = pd.to_numeric(df["position"], errors="coerce").fillna(-1).astype(int).to_numpy()
    return (mid == str(primary[0])) & (pos == int(primary[1]))


def _segment_run_bounds(is_prim: np.ndarray) -> List[Tuple[int, int, bool]]:
    """Contiguous True/False runs as (lo, hi, is_primary) index triples."""
    n = len(is_prim)
    if n == 0:
        return []
    starts = np.concatenate([[0], np.flatnonzero(is_prim[1:] != is_prim[:-1]) + 1])
    ends = np.concatenate([starts[1:] - 1, [n - 1]])
    return [(int(lo), int(hi), bool(is_prim[lo])) for lo, hi in zip(starts, ends)]
