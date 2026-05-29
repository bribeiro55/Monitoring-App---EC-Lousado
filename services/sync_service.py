from __future__ import annotations

import logging
import os
import platform
import shutil
import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class SyncResult:
    copied: int = 0
    deleted: int = 0
    unchanged: int = 0
    errors: int = 0


@dataclass
class TestSyncResult:
    test_number: str
    found: bool
    source_folder: Optional[str]
    result: Optional[SyncResult]
    error: Optional[str]


@dataclass
class SyncState:
    last_sync_time: Optional[datetime]
    next_sync_time: Optional[datetime]
    results: List[TestSyncResult]
    running: bool
    error: Optional[str]
    enabled: bool


def _digits_only(s: str) -> str:
    return "".join(ch for ch in s if ch.isdigit())


def load_credentials() -> tuple[str, str]:
    user = os.environ.get("GTT_SERVER_USER", "")
    password = os.environ.get("GTT_SERVER_PASS", "")
    if not user or not password:
        raise RuntimeError(
            "SMB credentials missing. Set GTT_SERVER_USER and GTT_SERVER_PASS."
        )
    return user, password


def find_source_folder_smb(smb_root: str, test_number: str) -> Optional[str]:
    import smbclient
    raw = test_number.strip()
    if not raw:
        return None
    candidates = [raw]
    digits = _digits_only(raw)
    if digits and digits != raw:
        candidates.append(digits)
    try:
        dirs = [e for e in smbclient.scandir(smb_root) if e.is_dir()]
    except Exception:
        return None
    for cand in candidates:
        suffix_dir = f"{cand}.00a".lower()
        suffix_log = f"{cand}.log".lower()
        for entry in dirs:
            if entry.name.lower().endswith(suffix_dir):
                try:
                    for f in smbclient.scandir(entry.path):
                        if f.is_file() and f.name.lower().endswith(suffix_log):
                            return entry.path
                except Exception:
                    continue
    return None


def mirror_folder_smb(smb_src: str, dest: Path) -> SyncResult:
    import smbclient
    result = SyncResult()
    try:
        dest.mkdir(parents=True, exist_ok=True)
    except OSError:
        result.errors += 1
        return result
    try:
        src_entries = {e.name: e for e in smbclient.scandir(smb_src) if e.is_file()}
    except Exception:
        result.errors += 1
        return result
    try:
        dest_files = {f.name: f for f in dest.iterdir() if f.is_file()}
    except OSError:
        dest_files = {}

    for name in list(dest_files):
        if name not in src_entries:
            try:
                dest_files[name].unlink()
                result.deleted += 1
            except OSError:
                result.errors += 1

    for name, src_e in src_entries.items():
        dest_f = dest / name
        try:
            src_stat = src_e.stat()
        except Exception:
            result.errors += 1
            continue
        needs_copy = True
        if dest_f.exists():
            try:
                dest_stat = dest_f.stat()
                if (
                    int(src_stat.st_mtime) == int(dest_stat.st_mtime)
                    and src_stat.st_size == dest_stat.st_size
                ):
                    needs_copy = False
            except OSError:
                pass
        if needs_copy:
            try:
                with smbclient.open_file(src_e.path, mode="rb") as smb_f:
                    dest_f.write_bytes(smb_f.read())
                os.utime(dest_f, (src_stat.st_mtime, src_stat.st_mtime))
                result.copied += 1
            except Exception:
                result.errors += 1
        else:
            result.unchanged += 1
    return result


def sync_tests_smb(
    test_numbers: List[str],
    smb_server: str,
    smb_share_folder: str,
    dest_root: Path,
) -> List[TestSyncResult]:
    smb_root = f"//{smb_server}/{smb_share_folder}"
    seen: set = set()
    results: List[TestSyncResult] = []
    for tn in test_numbers:
        tn = tn.strip()
        if not tn or tn in seen:
            continue
        seen.add(tn)
        try:
            src_path = find_source_folder_smb(smb_root, tn)
            if src_path is None:
                results.append(TestSyncResult(
                    test_number=tn, found=False,
                    source_folder=None, result=None, error=None,
                ))
                continue
            folder_name = src_path.rstrip("/").split("/")[-1]
            sync_result = mirror_folder_smb(src_path, dest_root / folder_name)
            results.append(TestSyncResult(
                test_number=tn, found=True,
                source_folder=src_path, result=sync_result, error=None,
            ))
        except Exception as e:
            results.append(TestSyncResult(
                test_number=tn, found=False,
                source_folder=None, result=None, error=str(e),
            ))
    return results


def find_source_folder(source_root: Path, test_number: str) -> Optional[Path]:
    raw = test_number.strip()
    if not raw:
        return None
    candidates = [raw]
    digits = _digits_only(raw)
    if digits and digits != raw:
        candidates.append(digits)

    try:
        dirs = [p for p in source_root.iterdir() if p.is_dir()]
    except OSError:
        return None

    for cand in candidates:
        suffix_dir = f"{cand}.00a".lower()
        suffix_log = f"{cand}.log".lower()
        for d in dirs:
            if d.name.lower().endswith(suffix_dir):
                try:
                    for f in d.iterdir():
                        if f.is_file() and f.name.lower().endswith(suffix_log):
                            return d
                except OSError:
                    continue
    return None


def mirror_folder(src: Path, dest: Path) -> SyncResult:
    result = SyncResult()
    try:
        dest.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        result.errors += 1
        return result

    try:
        src_files = {f.name: f for f in src.iterdir() if f.is_file()}
    except OSError:
        result.errors += 1
        return result

    try:
        dest_files = {f.name: f for f in dest.iterdir() if f.is_file()}
    except OSError:
        dest_files = {}

    # Delete files in dest that no longer exist in src.
    for name in list(dest_files):
        if name not in src_files:
            try:
                dest_files[name].unlink()
                result.deleted += 1
            except OSError:
                result.errors += 1

    # Copy new or changed files.
    for name, src_f in src_files.items():
        dest_f = dest / name
        try:
            src_stat = src_f.stat()
        except OSError:
            result.errors += 1
            continue

        needs_copy = True
        if dest_f.exists():
            try:
                dest_stat = dest_f.stat()
                if (
                    int(src_stat.st_mtime) == int(dest_stat.st_mtime)
                    and src_stat.st_size == dest_stat.st_size
                ):
                    needs_copy = False
            except OSError:
                pass

        if needs_copy:
            try:
                shutil.copy2(str(src_f), str(dest_f))
                result.copied += 1
            except OSError:
                result.errors += 1
        else:
            result.unchanged += 1

    return result


def sync_tests(
    test_numbers: List[str],
    source_root: Path,
    dest_root: Path,
) -> List[TestSyncResult]:
    seen: set = set()
    results: List[TestSyncResult] = []
    for tn in test_numbers:
        tn = tn.strip()
        if not tn or tn in seen:
            continue
        seen.add(tn)
        try:
            src = find_source_folder(source_root, tn)
            if src is None:
                results.append(TestSyncResult(
                    test_number=tn, found=False,
                    source_folder=None, result=None, error=None,
                ))
                continue
            dest = dest_root / src.name
            sync_result = mirror_folder(src, dest)
            results.append(TestSyncResult(
                test_number=tn, found=True,
                source_folder=str(src), result=sync_result, error=None,
            ))
        except Exception as e:
            results.append(TestSyncResult(
                test_number=tn, found=False,
                source_folder=None, result=None, error=str(e),
            ))
    return results


def _seconds_until_next_boundary(now: datetime, schedule_minutes: List[int]) -> float:
    minutes = sorted(schedule_minutes)
    m = now.minute
    s = now.second
    us = now.microsecond

    for target in minutes:
        if m < target:
            delta_min = target - m
            return delta_min * 60 - s - us / 1_000_000

    # Past the last boundary — wrap to first boundary of next hour.
    delta_min = (60 - m) + minutes[0]
    return delta_min * 60 - s - us / 1_000_000


class SyncScheduler:
    def __init__(
        self,
        source_root: Path,
        dest_root: Path,
        get_active_tests: Callable[[], List[str]],
        schedule_minutes: List[int] = None,
        enabled: bool = True,
        smb_server: Optional[str] = None,
        smb_share_folder: Optional[str] = None,
    ) -> None:
        self._source_root = source_root
        self._dest_root = dest_root
        self._get_active_tests = get_active_tests
        self._schedule_minutes = schedule_minutes if schedule_minutes is not None else [20, 50]
        self._enabled = enabled
        self._smb_server = smb_server
        self._smb_share_folder = smb_share_folder
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._trigger_event = threading.Event()
        self._state = SyncState(
            last_sync_time=None,
            next_sync_time=None,
            results=[],
            running=False,
            error=None,
            enabled=enabled,
        )
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="SyncScheduler")
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self._trigger_event.set()

    def trigger_now(self) -> None:
        self._trigger_event.set()

    def set_enabled(self, enabled: bool) -> None:
        with self._lock:
            self._enabled = enabled
            self._state.enabled = enabled

    def get_state(self) -> SyncState:
        with self._lock:
            return SyncState(
                last_sync_time=self._state.last_sync_time,
                next_sync_time=self._state.next_sync_time,
                results=list(self._state.results),
                running=self._state.running,
                error=self._state.error,
                enabled=self._state.enabled,
            )

    def _update_next_sync_time(self) -> None:
        now = datetime.now()
        secs = _seconds_until_next_boundary(now, self._schedule_minutes)
        next_dt = datetime.fromtimestamp(now.timestamp() + secs)
        with self._lock:
            self._state.next_sync_time = next_dt

    def _run(self) -> None:
        self._update_next_sync_time()
        while not self._stop_event.is_set():
            wait = _seconds_until_next_boundary(datetime.now(), self._schedule_minutes)
            self._trigger_event.wait(timeout=max(wait, 1.0))
            self._trigger_event.clear()

            if self._stop_event.is_set():
                break

            with self._lock:
                enabled = self._enabled

            if not enabled:
                self._update_next_sync_time()
                continue

            with self._lock:
                self._state.running = True

            try:
                tests = self._get_active_tests()
                if platform.system() == "Windows":
                    results = sync_tests(tests, self._source_root, self._dest_root)
                else:
                    import smbclient
                    try:
                        user, password = load_credentials()
                        smbclient.register_session(
                            server=self._smb_server,
                            username=user,
                            password=password,
                        )
                        logger.info("SMB session registered for %s", self._smb_server)
                    except Exception as e:
                        logger.error("SMB session failed: %s", e)
                        raise
                    results = sync_tests_smb(
                        tests, self._smb_server, self._smb_share_folder, self._dest_root
                    )
                now = datetime.now()
                self._update_next_sync_time()
                with self._lock:
                    self._state.last_sync_time = now
                    self._state.results = results
                    self._state.running = False
                    self._state.error = None
            except Exception as e:
                with self._lock:
                    self._state.running = False
                    self._state.error = str(e)
                self._update_next_sync_time()
