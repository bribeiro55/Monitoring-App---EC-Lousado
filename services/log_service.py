from __future__ import annotations

import functools
import os
from typing import Callable, Optional

import pandas as pd


def _digits_only(s: str) -> str:
    return "".join(ch for ch in str(s) if ch.isdigit())


@functools.lru_cache(maxsize=512)
def _find_log_path_cached(norm_root: str, raw_test: str, root_mtime_ns: int) -> Optional[str]:
    """
    Scan project_root for matching folder/file. Cached until project_root mtime changes.
    """
    candidates = [raw_test]
    digits = _digits_only(raw_test)
    if digits and digits not in candidates:
        candidates.append(digits)

    for cand in candidates:
        folder_suffix = f"{cand}.00a"
        file_suffix = f"{cand}.log"

        try:
            for entry in os.scandir(norm_root):
                if not entry.is_dir():
                    continue
                if not entry.name.lower().endswith(folder_suffix.lower()):
                    continue
                for f in os.scandir(entry.path):
                    if not f.is_file():
                        continue
                    if f.name.lower().endswith(file_suffix.lower()):
                        return f.path
        except FileNotFoundError:
            return None

    return None


def find_log_path_for_test_number(test_number: str, project_root: str) -> Optional[str]:
    """
    Search for a folder ending with '<TEST_NUMBER>.00a' and inside it a log ending with '<TEST_NUMBER>.log'.
    """
    raw = str(test_number).strip()
    if not raw:
        return None

    try:
        norm_root = os.path.normcase(os.path.abspath(os.path.normpath(project_root)))
        st = os.stat(norm_root)
        root_mtime_ns = int(getattr(st, "st_mtime_ns", int(st.st_mtime * 1e9)))
    except OSError:
        return None

    return _find_log_path_cached(norm_root, raw, root_mtime_ns)


def build_cached_parse_log(cache, parse_log_file: Callable[[str], pd.DataFrame]) -> Callable[[str], pd.DataFrame]:
    @cache.memoize()
    def _cached_parse_log_abs(abs_log_path: str, mtime: float, fsize: int) -> pd.DataFrame:
        return parse_log_file(abs_log_path)

    def cached_parse_log(log_path: str) -> pd.DataFrame:
        abs_path = os.path.abspath(os.path.normpath(log_path))
        mtime = os.path.getmtime(abs_path)
        fsize = os.path.getsize(abs_path)
        return _cached_parse_log_abs(abs_path, mtime, fsize)

    return cached_parse_log
