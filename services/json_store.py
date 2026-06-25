from __future__ import annotations

import json
import logging
import os
from typing import Any


def read_json(path: str, default: Any, *, use_smb: bool) -> Any:
    if use_smb:
        try:
            import smbclient
            with smbclient.open_file(path, mode="r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default

    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def write_json(path: str, data: Any, *, use_smb: bool) -> None:
    if use_smb:
        try:
            import smbclient
            with smbclient.open_file(path, mode="w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logging.getLogger(__name__).warning("SMB write failed for %s: %s", path, e)
        return

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def normalize_dict(data: Any) -> dict:
    return data if isinstance(data, dict) else {}
