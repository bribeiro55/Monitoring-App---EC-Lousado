from __future__ import annotations

import time
from pathlib import Path

import pytest

from services.sync_service import (
    SyncScheduler,
    find_source_folder,
    mirror_folder,
    sync_tests,
)


def _make_test_tree(root: Path, test_number: str) -> Path:
    folder = root / f"{test_number}.00a"
    folder.mkdir(parents=True)
    (folder / f"{test_number}.log").write_text("data")
    return folder


def test_find_source_folder_found(tmp_path):
    _make_test_tree(tmp_path, "12345")
    result = find_source_folder(tmp_path, "12345")
    assert result is not None
    assert result.name == "12345.00a"


def test_find_source_folder_digits_only(tmp_path):
    _make_test_tree(tmp_path, "12345")
    result = find_source_folder(tmp_path, "T12345")
    assert result is not None
    assert result.name == "12345.00a"


def test_find_source_folder_missing(tmp_path):
    result = find_source_folder(tmp_path, "99999")
    assert result is None


def test_find_source_folder_source_unreachable():
    result = find_source_folder(Path(r"\\nonexistent\share"), "12345")
    assert result is None


def test_mirror_folder_copies(tmp_path):
    src = tmp_path / "src"
    dest = tmp_path / "dest"
    src.mkdir()
    (src / "file.txt").write_text("hello")

    result = mirror_folder(src, dest)

    assert result.copied == 1
    assert result.deleted == 0
    assert result.unchanged == 0
    assert (dest / "file.txt").read_text() == "hello"


def test_mirror_folder_deletes(tmp_path):
    src = tmp_path / "src"
    dest = tmp_path / "dest"
    src.mkdir()
    dest.mkdir()
    (dest / "extra.txt").write_text("old")

    result = mirror_folder(src, dest)

    assert result.deleted == 1
    assert not (dest / "extra.txt").exists()


def test_mirror_folder_unchanged(tmp_path):
    src = tmp_path / "src"
    dest = tmp_path / "dest"
    src.mkdir()
    dest.mkdir()
    content = "same"
    src_f = src / "file.txt"
    src_f.write_text(content)
    dest_f = dest / "file.txt"
    dest_f.write_text(content)
    # Sync mtime so mirror sees them as identical.
    import os
    src_mtime = src_f.stat().st_mtime
    os.utime(str(dest_f), (src_mtime, src_mtime))

    result = mirror_folder(src, dest)

    assert result.unchanged == 1
    assert result.copied == 0


def test_sync_tests_found(tmp_path):
    src_root = tmp_path / "share"
    src_root.mkdir()
    dest_root = tmp_path / "logs"
    dest_root.mkdir()
    _make_test_tree(src_root, "42000")

    results = sync_tests(["42000"], src_root, dest_root)

    assert len(results) == 1
    assert results[0].found is True
    assert results[0].error is None


def test_sync_tests_not_found(tmp_path):
    src_root = tmp_path / "share"
    src_root.mkdir()
    dest_root = tmp_path / "logs"
    dest_root.mkdir()

    results = sync_tests(["99999"], src_root, dest_root)

    assert len(results) == 1
    assert results[0].found is False


def test_sync_tests_deduplicates(tmp_path):
    src_root = tmp_path / "share"
    src_root.mkdir()
    dest_root = tmp_path / "logs"
    dest_root.mkdir()
    _make_test_tree(src_root, "11111")

    results = sync_tests(["11111", "11111"], src_root, dest_root)

    assert len(results) == 1


def test_trigger_now(tmp_path):
    src_root = tmp_path / "share"
    src_root.mkdir()
    dest_root = tmp_path / "logs"
    dest_root.mkdir()
    _make_test_tree(src_root, "55555")
    synced = []

    def get_tests():
        return ["55555"]

    sched = SyncScheduler(
        source_root=src_root,
        dest_root=dest_root,
        get_active_tests=get_tests,
        schedule_minutes=[20, 50],
        enabled=True,
    )
    sched.start()
    sched.trigger_now()

    deadline = time.time() + 5.0
    while time.time() < deadline:
        state = sched.get_state()
        if state.last_sync_time is not None:
            break
        time.sleep(0.1)

    sched.stop()
    state = sched.get_state()
    assert state.last_sync_time is not None
    assert len(state.results) == 1
    assert state.results[0].found is True
