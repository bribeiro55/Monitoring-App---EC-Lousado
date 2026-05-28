from __future__ import annotations

import json
import os
import threading
from typing import List


class TestRegistry:
    def __init__(self, path: str) -> None:
        self._path = path
        self._lock = threading.Lock()
        self._entries: List[dict] = []

    def load(self) -> None:
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        if not os.path.exists(self._path):
            self._entries = []
            return
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                self._entries = [
                    {"test_number": str(e["test_number"]), "status": str(e.get("status", "active"))}
                    for e in data
                    if isinstance(e, dict) and e.get("test_number")
                ]
            else:
                self._entries = []
        except Exception:
            self._entries = []

    def save(self) -> None:
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(self._entries, f, indent=2)

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
