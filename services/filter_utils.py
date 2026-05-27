from __future__ import annotations

import re
from typing import Optional, Tuple

import pandas as pd


def to_opt_date(v: object) -> Optional[pd.Timestamp]:
    if v in (None, ""):
        return None
    ts = pd.to_datetime(v, errors="coerce")
    if pd.isna(ts):
        return None
    return pd.Timestamp(ts).normalize()


def parse_hhmm(v: object, default: Optional[str] = None) -> Optional[Tuple[int, int]]:
    txt = str(v if v not in (None, "") else (default or "")).strip()
    m = re.fullmatch(r"([01]?\d|2[0-3]):([0-5]\d)", txt)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def to_opt_datetime(date_value: object, hhmm_value: object, default_hhmm: str) -> Optional[pd.Timestamp]:
    d = to_opt_date(date_value)
    hm = parse_hhmm(hhmm_value, default_hhmm)
    if d is None or hm is None:
        return None
    return d + pd.Timedelta(hours=hm[0], minutes=hm[1])
