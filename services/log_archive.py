from __future__ import annotations

import os
import posixpath
import shutil
from dataclasses import dataclass
from typing import Optional


@dataclass
class CopyResult:
    dest_folder: str
    copied_files: int
    error: Optional[str] = None


def copy_test_folder(log_path: str, dest_root: str) -> CopyResult:
    """
    Copy the source test folder (the parent directory of log_path, e.g. '<test>.00a')
    to dest_root, overwriting any existing files there. The source is never modified
    or deleted — local/Windows variant (mapped drives).
    """
    src_dir = os.path.dirname(os.path.abspath(log_path))
    dest_dir = os.path.join(dest_root, os.path.basename(src_dir))
    try:
        copied = sum(len(files) for _root, _dirs, files in os.walk(src_dir))
        shutil.copytree(src_dir, dest_dir, dirs_exist_ok=True)
        return CopyResult(dest_folder=dest_dir, copied_files=copied)
    except OSError as e:
        return CopyResult(dest_folder=dest_dir, copied_files=0, error=str(e))


def _smb_dirname(p: str) -> str:
    return posixpath.dirname(p.replace("\\", "/"))


def _smb_basename(p: str) -> str:
    return posixpath.basename(p.replace("\\", "/"))


def copy_test_folder_smb(log_path: str, dest_root: str) -> CopyResult:
    """
    Copy the source test folder (the parent directory of log_path, e.g. '<test>.00a')
    to dest_root over SMB, overwriting any existing files there. The source is never
    modified or deleted — SMB variant (Linux / Pergola).
    """
    import smbclient

    src_dir = _smb_dirname(log_path)
    dest_dir = f"{dest_root.rstrip('/')}/{_smb_basename(src_dir)}"
    try:
        copied = 0
        for root, _dirs, files in smbclient.walk(src_dir):
            rel = root.replace("\\", "/")[len(src_dir.replace("\\", "/")):].strip("/")
            target_root = dest_dir if not rel else f"{dest_dir}/{rel}"
            smbclient.makedirs(target_root, exist_ok=True)
            for name in files:
                src_file = f"{root.rstrip(chr(92) + '/')}/{name}"
                dest_file = f"{target_root.rstrip('/')}/{name}"
                with smbclient.open_file(src_file, mode="rb") as fsrc:
                    data = fsrc.read()
                with smbclient.open_file(dest_file, mode="wb") as fdst:
                    fdst.write(data)
                copied += 1
        return CopyResult(dest_folder=dest_dir, copied_files=copied)
    except Exception as e:
        return CopyResult(dest_folder=dest_dir, copied_files=0, error=str(e))
