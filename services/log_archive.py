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
    Create '<test>.00a' under dest_root (mirroring the source folder name, so
    fallback search still finds it) and copy only the '<test>.log' file into it,
    overwriting an existing file of the same name. The source is never modified
    or deleted — local/Windows variant (mapped drives).
    """
    src_dir = os.path.dirname(os.path.abspath(log_path))
    dest_dir = os.path.join(dest_root, os.path.basename(src_dir))
    try:
        os.makedirs(dest_dir, exist_ok=True)
        dest_file = os.path.join(dest_dir, os.path.basename(log_path))
        shutil.copy2(log_path, dest_file)
        return CopyResult(dest_folder=dest_dir, copied_files=1)
    except OSError as e:
        return CopyResult(dest_folder=dest_dir, copied_files=0, error=str(e))


def _smb_dirname(p: str) -> str:
    return posixpath.dirname(p.replace("\\", "/"))


def _smb_basename(p: str) -> str:
    return posixpath.basename(p.replace("\\", "/"))


def copy_test_folder_smb(log_path: str, dest_root: str) -> CopyResult:
    """
    Create '<test>.00a' under dest_root (mirroring the source folder name, so
    fallback search still finds it) and copy only the '<test>.log' file into it,
    overwriting an existing file of the same name. The source is never modified
    or deleted — SMB variant (Linux / Pergola).
    """
    import smbclient

    src_dir = _smb_dirname(log_path)
    dest_dir = f"{dest_root.rstrip('/')}/{_smb_basename(src_dir)}"
    try:
        smbclient.makedirs(dest_dir, exist_ok=True)
        dest_file = f"{dest_dir}/{_smb_basename(log_path)}"
        with smbclient.open_file(log_path, mode="rb") as fsrc:
            data = fsrc.read()
        with smbclient.open_file(dest_file, mode="wb") as fdst:
            fdst.write(data)
        return CopyResult(dest_folder=dest_dir, copied_files=1)
    except Exception as e:
        return CopyResult(dest_folder=dest_dir, copied_files=0, error=str(e))
