from __future__ import annotations

from pathlib import Path

from services.log_archive import copy_test_folder


def _make_test_tree(root: Path, test_number: str) -> Path:
    folder = root / f"{test_number}.00a"
    folder.mkdir(parents=True)
    (folder / f"{test_number}.log").write_text("data")
    (folder / "extra_channel.csv").write_text("a,b,c")
    (folder / "sub").mkdir()
    (folder / "sub" / "nested.txt").write_text("nested")
    return folder


def test_copy_test_folder_copies_all_files(tmp_path):
    src_root = tmp_path / "prstruh"
    dest_root = tmp_path / "logs"
    src_folder = _make_test_tree(src_root, "12345")

    result = copy_test_folder(str(src_folder / "12345.log"), str(dest_root))

    dest_folder = dest_root / "12345.00a"
    assert result.error is None
    assert result.copied_files == 3
    assert result.dest_folder == str(dest_folder)
    assert (dest_folder / "12345.log").read_text() == "data"
    assert (dest_folder / "extra_channel.csv").read_text() == "a,b,c"
    assert (dest_folder / "sub" / "nested.txt").read_text() == "nested"


def test_copy_test_folder_does_not_touch_source(tmp_path):
    src_root = tmp_path / "prstruh"
    dest_root = tmp_path / "logs"
    src_folder = _make_test_tree(src_root, "12345")
    log_path = src_folder / "12345.log"
    before_mtime = log_path.stat().st_mtime

    copy_test_folder(str(log_path), str(dest_root))

    assert log_path.exists()
    assert log_path.read_text() == "data"
    assert log_path.stat().st_mtime == before_mtime
    assert sorted(p.name for p in src_folder.iterdir()) == ["12345.log", "extra_channel.csv", "sub"]


def test_copy_test_folder_overwrites_existing_destination_file(tmp_path):
    src_root = tmp_path / "prstruh"
    dest_root = tmp_path / "logs"
    src_folder = _make_test_tree(src_root, "12345")

    dest_folder = dest_root / "12345.00a"
    dest_folder.mkdir(parents=True)
    (dest_folder / "12345.log").write_text("stale-old-data")

    result = copy_test_folder(str(src_folder / "12345.log"), str(dest_root))

    assert result.error is None
    assert (dest_folder / "12345.log").read_text() == "data"


def test_copy_test_folder_reports_error_when_source_missing(tmp_path):
    dest_root = tmp_path / "logs"
    missing_log = tmp_path / "prstruh" / "99999.00a" / "99999.log"

    result = copy_test_folder(str(missing_log), str(dest_root))

    assert result.error is not None
    assert result.copied_files == 0
