from __future__ import annotations

import threading
from typing import List

from services.json_store import read_json, write_json


class TestRegistry:
    def __init__(self, path: str) -> None:
        self._path = path
        self._use_smb = path.startswith("//")
        self._lock = threading.Lock()
        self._entries: List[dict] = []

    def load(self) -> None:
        data = read_json(self._path, default=[], use_smb=self._use_smb)
        if isinstance(data, list):
            self._entries = [
                {"test_number": str(e["test_number"]), "status": str(e.get("status", "active"))}
                for e in data
                if isinstance(e, dict) and e.get("test_number")
            ]
        else:
            self._entries = []

    def save(self) -> None:
        write_json(self._path, self._entries, use_smb=self._use_smb)

    def add(self, test_number: str, status: str = "active") -> None:
        test_number = test_number.strip()
        if not test_number:
            return
        status = status if status in ("active", "planned") else "active"
        with self._lock:
            for e in self._entries:
                if e["test_number"] == test_number:
                    return
            self._entries.append({"test_number": test_number, "status": status})
            self.save()

    def remove(self, test_number: str) -> None:
        test_number = test_number.strip()
        with self._lock:
            self._entries = [e for e in self._entries if e["test_number"] != test_number]
            self.save()

    def set_status(self, test_number: str, status: str) -> None:
        test_number = test_number.strip()
        status = status if status in ("active", "planned") else "active"
        with self._lock:
            for e in self._entries:
                if e["test_number"] == test_number:
                    e["status"] = status
                    break
            self.save()

    def get_all(self) -> List[dict]:
        with self._lock:
            return list(self._entries)

    def get_active(self) -> List[str]:
        with self._lock:
            return [e["test_number"] for e in self._entries if e.get("status") == "active"]
