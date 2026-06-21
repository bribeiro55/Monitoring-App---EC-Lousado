from __future__ import annotations

import logging
import platform

_log = logging.getLogger(__name__)

_SMB_SERVER = "lofs010.tiretech2.contiwan.com"
_SMB_SHARE = "cmip_groups"


def ensure_session(username: str, password: str) -> None:
    """Register an SMB session for the occupation Excel server (no-op on Windows)."""
    if platform.system() == "Windows":
        return
    import smbclient
    smbclient.register_session(server=_SMB_SERVER, username=username, password=password)
    _log.info("SMB session registered for %s", _SMB_SERVER)


def read_excel_bytes(rel_path: str) -> bytes:
    """Read the Excel file at rel_path (relative to share root) and return raw bytes."""
    if platform.system() == "Windows":
        win_path = "O:\\" + rel_path.replace("/", "\\")
        _log.debug("Reading Excel from local path: %s", win_path)
        with open(win_path, "rb") as fh:
            return fh.read()
    import smbclient
    smb_path = f"//{_SMB_SERVER}/{_SMB_SHARE}/{rel_path}"
    _log.debug("Reading Excel via SMB: %s", smb_path)
    with smbclient.open_file(smb_path, mode="rb") as fh:
        return fh.read()


def get_win_path(rel_path: str) -> "str | None":
    """Return the Windows mapped-drive path for rel_path, or None on non-Windows."""
    if platform.system() != "Windows":
        return None
    return "O:\\" + rel_path.replace("/", "\\")


def write_excel_bytes(rel_path: str, data: bytes) -> None:
    """Write raw bytes back to the Excel file at rel_path (relative to share root)."""
    if platform.system() == "Windows":
        win_path = "O:\\" + rel_path.replace("/", "\\")
        _log.info("Writing Excel to local path: %s", win_path)
        with open(win_path, "wb") as fh:
            fh.write(data)
        return
    import smbclient
    smb_path = f"//{_SMB_SERVER}/{_SMB_SHARE}/{rel_path}"
    _log.info("Writing Excel via SMB: %s", smb_path)
    with smbclient.open_file(smb_path, mode="wb") as fh:
        fh.write(data)
