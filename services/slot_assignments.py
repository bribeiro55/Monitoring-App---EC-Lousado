from __future__ import annotations

import threading
from typing import Dict

from services.json_store import normalize_dict, read_json, write_json


class SlotAssignments:
    def __init__(self, path: str) -> None:
        self._path = path
        self._use_smb = path.startswith("//")
        self._lock = threading.Lock()
        self._values: Dict[str, str] = {}

    def load(self) -> None:
        data = normalize_dict(read_json(self._path, default={}, use_smb=self._use_smb))
        self._values = {str(k): str(v) for k, v in data.items() if v not in (None, "")}

    def save(self) -> None:
        write_json(self._path, self._values, use_smb=self._use_smb)

    def get_all(self) -> Dict[str, str]:
        with self._lock:
            return dict(self._values)

    def set_many(self, values: Dict[str, str]) -> None:
        with self._lock:
            for slot_key, test_number in values.items():
                test_number = (test_number or "").strip()
                if test_number:
                    self._values[slot_key] = test_number
                else:
                    self._values.pop(slot_key, None)
            self.save()
