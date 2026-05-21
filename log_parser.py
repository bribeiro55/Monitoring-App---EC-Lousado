import os
import re
from io import StringIO
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


MACHINE_LOOKUP: Dict[str, str] = {
    "7900": "M7900",
    "7950": "M7950",
    "7960": "M7960",
}

# Unified output column order (thermo columns after machine_running).
OUTPUT_COLUMNS: List[str] = [
    "timestamp",
    "machine_id",
    "position",
    "step",
    "speed",
    "load_kg",
    "deflection_mm",
    "inflation_pressure_kpa",
    "room_temp_c",
    "cpc_temp_c",
    "circumference_mm",
    "torque_nm",
    "machine_running",
    "thermo_cam_1",
    "thermo_cam_2",
    "thermo_cam_3",
    "thermo_cam_4",
    "thermo_cam_5",
]

_LOCALE_TS_PATTERN = re.compile(
    r"^\s*(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+[A-Za-z]{3}\s+\d{1,2}\s+\d{1,2}:\d{2}:\d{2}",
    re.IGNORECASE,
)

# "Fri Mar 06 01:24:29 WET 2026" — pandas warns/fails on WET/CEST/WEST as tz names; strip the
# token so we parse naive wall-clock time (consistent with Datum/Uhrzeit fallback).
_TZ_TOKEN_BEFORE_YEAR_AT_EOL = re.compile(
    r"(\d{1,2}:\d{2}:\d{2})\s+[A-Za-z]{2,5}\s+(\d{4})\s*$",
    re.UNICODE,
)


def _strip_ambiguous_tz_before_year(val: object) -> object:
    if val is None:
        return val
    try:
        if pd.isna(val):
            return val
    except (ValueError, TypeError):
        pass
    s = str(val).strip()
    if not s or "DATA NOT VALID" in s.upper():
        return val
    return _TZ_TOKEN_BEFORE_YEAR_AT_EOL.sub(r"\1 \2", s)


def _prepare_raw_timestamp_series(raw_ts_series: pd.Series) -> pd.Series:
    return raw_ts_series.map(_strip_ambiguous_tz_before_year)


# English weekday/month tokens as emitted by logs after TZ strip.
_RAW_TS_FORMAT = "%a %b %d %H:%M:%S %Y"

# Header lines are fixed-format but the numeric prefix length varies by export
# (e.g. "...000101..." / "...000301..."). Match the first relevant segment code
# after the leading numeric prefix.
_HEADER_REC_RE = re.compile(r"^\s*\d+?(0101|0301)(.*)$")
_TIRE_SIZE_PATTERNS = [
    # No left word boundary: size can be glued to numeric fields in 0301 payload.
    # Decimal notation (dot or comma): XX.X / XX.XX with R or dash and 2-3 digit rim.
    re.compile(r"\d{2}[.,]\d{1,2}\s*R\s*\d{2,3}\b", re.IGNORECASE),
    re.compile(r"\d{2}[.,]\d{1,2}\s*-\s*\d{2,3}\b", re.IGNORECASE),
    # Aspect-ratio notation: XX/XX or XXX/XX with R or dash and 2-3 digit rim.
    re.compile(r"\d{2,3}/\d{2}\s*R\s*\d{2,3}\b", re.IGNORECASE),
    re.compile(r"\d{2,3}/\d{2}\s*-\s*\d{2,3}\b", re.IGNORECASE),
]


def _parse_locale_timestamp_strings(series: pd.Series) -> pd.Series:
    """Vectorized parse; explicit format avoids slow per-row dateutil + warning storms."""
    return pd.to_datetime(series, format=_RAW_TS_FORMAT, errors="coerce", utc=False)


def parse_log_header_metadata(filepath: str) -> Dict[str, Optional[str]]:
    """
    Extract lightweight metadata from fixed-format header records.

    Currently captures:
    - test_name from 0101 records (e.g. "O END")
    - tire_size from 0301 records (e.g. "24.00 R 35", "18.00 - 25", "450/95 R 25")

    Note: keep this intentionally simple for now; more fields from 0101..0601 can be
    added later without changing parse_log_file() output columns.
    """
    out: Dict[str, Optional[str]] = {"test_name": None, "tire_size": None}
    if not os.path.exists(filepath):
        return out

    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                # Header block ends before the semicolon/tab data table starts.
                if re.match(r"^\s*Pos\s*(;|\t)", line, re.IGNORECASE):
                    break

                m = _HEADER_REC_RE.match(line.rstrip("\n"))
                if not m:
                    continue
                rec_type = m.group(1)
                payload = (m.group(2) or "").strip()
                if not payload:
                    continue

                if rec_type == "0101" and out["test_name"] is None:
                    name_match = re.match(r"\s*([A-Za-z][A-Za-z0-9\s/_().,+&-]*?)\s{2,}\d", payload)
                    if name_match:
                        out["test_name"] = re.sub(r"\s+", " ", name_match.group(1).strip())

                if rec_type == "0301" and out["tire_size"] is None:
                    for pat in _TIRE_SIZE_PATTERNS:
                        tsm = pat.search(payload)
                        if tsm:
                            out["tire_size"] = re.sub(r"\s+", " ", tsm.group(0).strip()).upper()
                            break

                if out["test_name"] and out["tire_size"]:
                    break
    except OSError:
        return out

    return out


def _digits_only(s: object) -> str:
    return "".join(c for c in str(s).strip() if c.isdigit())


def _machine_key_and_position_from_raw(position_raw: object) -> Tuple[Optional[str], Optional[int]]:
    """
    Examples from real logs:
    - 79601 (5 digits) -> machine 7960, position 1
    - 7961  (4 digits) -> machine 7960, position 1  (same encoding, leading zero omitted)
    """
    s = _digits_only(position_raw)
    if not s:
        return None, None
    if len(s) >= 5:
        return s[:4], int(s[-1])
    if len(s) == 4:
        return s[:3] + "0", int(s[-1])
    return None, None


def _normalize_col(col: object) -> str:
    return re.sub(r"\s+", "", str(col)).strip()


def _find_column(df: pd.DataFrame, *, contains: Optional[str] = None, equals_norm: Optional[str] = None):
    """
    Helper for tolerating minor whitespace/unit differences in the raw headers.
    """
    if equals_norm is not None:
        for c in df.columns:
            if _normalize_col(c) == equals_norm:
                return c
    if contains is not None:
        contains_norm = re.sub(r"\s+", "", str(contains)).strip().lower()
        for c in df.columns:
            if contains_norm in str(c).replace(" ", "").lower():
                return c
    return None


def _find_inflation_column(columns) -> Optional[str]:
    for c in columns:
        n = str(c).replace(" ", "").lower()
        if "reif" in n and ("fuell" in n or "druck" in n or "kpa" in n):
            return c
    for c in columns:
        nn = _normalize_col(c).lower()
        if nn in ("pressurekpa", "pressurekp"):
            return c
    return None


def _find_thermo_kameras_column(columns) -> Optional[str]:
    for c in columns:
        n = _normalize_col(c).lower()
        if "thermo" in n and "kam" in n:
            return c
    return None


def _find_raw_timestamp_column(df: pd.DataFrame) -> Optional[str]:
    """
    Optional locale-style column, e.g. 'Thu Aug 21 11:45:42 WEST 2025'.
    Prefer explicit names containing 'timestamp'; else first column whose sample values match weekday pattern.
    """
    for c in df.columns:
        cn = re.sub(r"\s+", "", str(c).lower())
        if "timestamp" in cn:
            return c
    for c in df.columns:
        ser = df[c].dropna().head(30)
        for v in ser:
            if isinstance(v, str) and _LOCALE_TS_PATTERN.search(v):
                return c
    return None


def _split_thermo_five(val: object) -> List[float]:
    """Split 'a/b/c/d/e' into five floats; pad with NaN; empty string -> all NaN."""
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return [np.nan] * 5
    s = str(val).strip()
    if not s:
        return [np.nan] * 5
    parts = s.split("/")
    out: List[float] = []
    for i in range(5):
        if i < len(parts):
            out.append(float(pd.to_numeric(parts[i].strip(), errors="coerce")))
        else:
            out.append(np.nan)
    return out


def _detect_dot_date_format(sample_dates: pd.Series) -> bool:
    """True if primary date style looks like DD.MM.YY (O-TKPH / new export)."""
    sample = sample_dates.dropna().head(15).astype(str).str.strip()
    if sample.empty:
        return False
    dot_match = sample.str.match(r"\d{1,2}\.\d{1,2}\.\d{2}$", na=False)
    return bool(dot_match.any())


def parse_log_file(filepath: str) -> pd.DataFrame:
    """
    Parse a raw .log file into a cleaned DataFrame ( O-TKPH / new machine export).

    Unified columns (see OUTPUT_COLUMNS):
    - timestamp, machine_id, position, step, load_kg, deflection_mm,
      inflation_pressure_kpa, room_temp_c, cpc_temp_c,
      circumference_mm, torque_nm (optional: all NaN when absent in source),
      machine_running,
      thermo_cam_1 … thermo_cam_5 (optional: from Thermo-Kameras-style column or all NaN).

    Timestamp:
    - Optional raw locale column: if pd.to_datetime succeeds, preferred over Datum+Uhrzeit per row.
    - Legacy: Datum YYMMDD + Uhrzeit HHMMSS compact.
    - New: Datum DD.MM.YY + Uhrzeit HH:MM:SS.

    invalid_marker: True if legacy date+time text or raw timestamp contains 'DATA NOT VALID' (case-insensitive).
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(filepath)

    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    header_idx = None
    header_line = None
    header_re = re.compile(r"^\s*Pos\s*(;|\t)", re.IGNORECASE)
    for i, line in enumerate(lines):
        if header_re.search(line):
            header_idx = i
            header_line = line
            break

    if header_idx is None or header_line is None:
        raise ValueError("Could not find data header row starting with 'Pos ;' or 'Pos\\t'.")

    delimiter = "\t" if ("\t" in header_line and ";" not in header_line) else ";"

    csv_text = "".join(lines[header_idx:])
    df_raw = pd.read_csv(
        StringIO(csv_text),
        sep=delimiter,
        header=0,
        engine="python",
    )

    df_raw.columns = [str(c).strip() for c in df_raw.columns]

    pos_col = _find_column(df_raw, equals_norm="Pos") or _find_column(df_raw, contains="Pos")
    date_col = _find_column(df_raw, equals_norm="Datum") or _find_column(df_raw, contains="Datum")
    time_col = _find_column(df_raw, equals_norm="Uhrzeit") or _find_column(df_raw, contains="Uhrzeit")

    step_col = _find_column(df_raw, equals_norm="Pruefstufe") or _find_column(df_raw, contains="Pruefstufe")
    if step_col is None:
        step_col = _find_column(df_raw, equals_norm="Stufe") or _find_column(df_raw, contains="Stufe")

    load_col = _find_column(df_raw, equals_norm="Radlast") or _find_column(df_raw, contains="Radlast")
    if load_col is None:
        load_col = _find_column(df_raw, equals_norm="Last")

    defl_col = _find_column(df_raw, equals_norm="Einfederung") or _find_column(df_raw, contains="Einfederung")
    speed_col = _find_column(df_raw, equals_norm="Geschwindigkeit") or _find_column(df_raw, contains="Geschwindigkeit")

    inflation_col = _find_inflation_column(df_raw.columns)

    room_col = _find_column(df_raw, equals_norm="Lufttemperatur") or _find_column(df_raw, contains="Lufttemperatur")
    if room_col is None:
        room_col = _find_column(df_raw, equals_norm="Raumtemperatur") or _find_column(
            df_raw, contains="Raumtemperatur"
        )

    cpc_col = _find_column(df_raw, equals_norm="temperatureC") or _find_column(df_raw, equals_norm="temperaturec")
    if cpc_col is None:
        for c in df_raw.columns:
            n = str(c).replace(" ", "").lower()
            if "temperature" in n and n.endswith("c"):
                cpc_col = c
                break

    circ_col = _find_column(df_raw, equals_norm="Circumference") or _find_column(df_raw, contains="Circumference")
    torque_col = _find_column(df_raw, equals_norm="Torque") or _find_column(df_raw, contains="Torque")

    thermo_src_col = _find_thermo_kameras_column(df_raw.columns)

    required_map = {
        "position_raw": pos_col,
        "date_str": date_col,
        "time_str": time_col,
        "step": step_col,
        "load_kg": load_col,
        "deflection_mm": defl_col,
        "speed": speed_col,
        "inflation_pressure_kpa": inflation_col,
        "room_temp_c": room_col,
        "cpc_temp_c": cpc_col,
    }
    missing = [k for k, v in required_map.items() if v is None]
    if missing:
        raise ValueError(f"Missing expected columns in log: {missing}. Columns found: {list(df_raw.columns)}")

    use_cols = list(required_map.values())
    optional_meta: List[Tuple[str, Optional[str]]] = [
        ("circumference_mm", circ_col),
        ("torque_nm", torque_col),
    ]
    for alias, col in optional_meta:
        if col is not None:
            use_cols.append(col)

    df = df_raw[use_cols].copy()
    rename_map = {v: k for k, v in required_map.items()}
    for alias, col in optional_meta:
        if col is not None:
            rename_map[col] = alias
    df.rename(columns=rename_map, inplace=True)

    if "circumference_mm" not in df.columns:
        df["circumference_mm"] = np.nan
    if "torque_nm" not in df.columns:
        df["torque_nm"] = np.nan

    if thermo_src_col is not None:
        thermo_src = df_raw[thermo_src_col].reindex(df.index)
        split = thermo_src.astype("string").str.split("/", expand=True)
        split = split.iloc[:, :5].reindex(columns=range(5))
        split = split.apply(lambda c: c.str.strip())
        for i in range(5):
            df[f"thermo_cam_{i + 1}"] = pd.to_numeric(split[i], errors="coerce")
    else:
        for i in range(5):
            df[f"thermo_cam_{i + 1}"] = np.nan

    raw_ts_col_name = _find_raw_timestamp_column(df_raw)
    if raw_ts_col_name is not None:
        raw_ts_series = df_raw[raw_ts_col_name].reindex(df.index)
    else:
        raw_ts_series = pd.Series([pd.NA] * len(df), index=df.index)

    # Vectorized equivalent of _machine_key_and_position_from_raw:
    # - len >= 5 => machine key first 4 digits, position last digit
    # - len == 4 => machine key first 3 digits + "0", position last digit
    # - else invalid
    pos_digits = df["position_raw"].astype("string").str.replace(r"\D", "", regex=True)
    digit_len = pos_digits.str.len().fillna(0).astype(int)
    machine_key_raw = pd.Series(pd.NA, index=df.index, dtype="string")
    mask_ge5 = digit_len >= 5
    mask_eq4 = digit_len == 4
    machine_key_raw = machine_key_raw.where(~mask_ge5, pos_digits.str.slice(0, 4))
    machine_key_raw = machine_key_raw.where(~mask_eq4, pos_digits.str.slice(0, 3) + "0")
    position_digit = pos_digits.str[-1].where(digit_len >= 4)
    df["position"] = pd.to_numeric(position_digit, errors="coerce").astype("Int64")
    df["machine_id"] = machine_key_raw.map(MACHINE_LOOKUP)

    df["date_str"] = df["date_str"].astype(str).str.strip()
    df["time_str"] = df["time_str"].astype(str).str.strip()

    raw_timestamp_text = df["date_str"].fillna("") + " " + df["time_str"].fillna("")
    invalid_concat = raw_timestamp_text.str.contains("DATA NOT VALID", case=False, na=False)
    raw_str = raw_ts_series.astype(str)
    invalid_raw = raw_str.str.contains("DATA NOT VALID", case=False, na=False)
    invalid_marker = invalid_concat | invalid_raw

    use_dot_date = _detect_dot_date_format(df["date_str"])

    # Compact legacy path
    date_z = df["date_str"].str.replace(r"\D", "", regex=True).str.zfill(6)
    time_z = df["time_str"].str.replace(r"\D", "", regex=True).str.zfill(6)
    ts_compact = date_z + time_z
    ts_legacy = pd.to_datetime(ts_compact, format="%y%m%d%H%M%S", errors="coerce")

    # DD.MM.YY + HH:MM:SS
    dt_combined = df["date_str"] + " " + df["time_str"]
    ts_new = pd.to_datetime(dt_combined, format="%d.%m.%y %H:%M:%S", errors="coerce")

    if use_dot_date:
        ts_fallback = ts_new
    else:
        ts_fallback = ts_legacy
        # If legacy failed but new parses (mixed file), backfill
        ts_fallback = ts_fallback.where(ts_fallback.notna(), ts_new)

    # Avoid element-by-element parsing on 10k+ rows when the column is present but
    # mostly non-parsable. Strip WET/CEST/... before parse (see _strip_ambiguous_tz_before_year).
    raw_for_parse = _prepare_raw_timestamp_series(raw_ts_series)
    nz = raw_for_parse.dropna()
    try:
        nz = nz[nz.astype(str).str.strip() != ""]
    except Exception:
        pass
    if len(nz) == 0:
        ts_from_raw = pd.Series(pd.NaT, index=df.index)
    else:
        quick = _parse_locale_timestamp_strings(nz.head(80))
        if quick.notna().sum() == 0:
            ts_from_raw = pd.Series(pd.NaT, index=df.index)
        else:
            ts_from_raw = _parse_locale_timestamp_strings(raw_for_parse)

    df["timestamp"] = ts_from_raw.where(ts_from_raw.notna(), ts_fallback)

    raw_cpc = df["cpc_temp_c"]
    raw_cpc_str = raw_cpc.astype(str)
    raw_cpc_num = pd.to_numeric(raw_cpc_str, errors="coerce")
    raw_cpc_is_empty_or_zero = raw_cpc.isna() | (raw_cpc_str.str.strip() == "") | (raw_cpc_num.fillna(0) == 0)
    df["cpc_temp_c"] = raw_cpc_num
    df.loc[raw_cpc_is_empty_or_zero & invalid_marker, "cpc_temp_c"] = np.nan

    numeric_cols = [
        "step",
        "load_kg",
        "deflection_mm",
        "speed",
        "inflation_pressure_kpa",
        "room_temp_c",
        "cpc_temp_c",
        "circumference_mm",
        "torque_nm",
    ]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["step"] = df["step"].round().astype("Int64")

    # machine_running: NaN-safe speed/load vs step average.
    # When speed is NaN or <= 0, row does not contribute to step average load.
    # When all speeds in a step are NaN/<=0, avg_load_step is NaN -> treat as running (spec: visible rows).
    spd = pd.to_numeric(df["speed"], errors="coerce")
    load_num = pd.to_numeric(df["load_kg"], errors="coerce")
    load_for_avg = np.where(spd.notna() & (spd > 0), load_num, np.nan)
    load_series = pd.Series(load_for_avg, index=df.index)
    df["avg_load_step"] = load_series.groupby([df["machine_id"], df["position"], df["step"]]).transform("mean")
    threshold = 0.95 * df["avg_load_step"]
    machine_ok_by_load = df["avg_load_step"].isna() | (load_num >= threshold)
    df["machine_running"] = (machine_ok_by_load & (~invalid_marker)).astype(bool)

    df_non_null_ts = df.dropna(subset=["timestamp", "machine_id", "position"]).copy()
    df_null_ts = df[df["timestamp"].isna()].copy()
    df_non_null_ts = df_non_null_ts.sort_values("timestamp").drop_duplicates(
        subset=["machine_id", "position", "timestamp"], keep="last"
    )

    df_clean = pd.concat([df_non_null_ts, df_null_ts], ignore_index=True)

    drop_int = [c for c in ["avg_load_step", "position_raw", "date_str", "time_str"] if c in df_clean.columns]
    if drop_int:
        df_clean = df_clean.drop(columns=drop_int)

    for c in OUTPUT_COLUMNS:
        if c not in df_clean.columns:
            df_clean[c] = np.nan

    df_clean = df_clean[OUTPUT_COLUMNS].sort_values(["machine_id", "position", "timestamp"])

    return df_clean
