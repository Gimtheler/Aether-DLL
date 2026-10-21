"""Silent privilege check and UAC relaunch."""

from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes
from pathlib import Path


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def enable_debug_privilege() -> bool:
    """Enable SeDebugPrivilege so elevated sessions can open more processes."""
    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    TOKEN_ADJUST_PRIVILEGES = 0x0020
    TOKEN_QUERY = 0x0008
    SE_PRIVILEGE_ENABLED = 0x00000002

    class LUID(ctypes.Structure):
        _fields_ = [("LowPart", wintypes.DWORD), ("HighPart", wintypes.LONG)]

    class LUID_AND_ATTRIBUTES(ctypes.Structure):
        _fields_ = [("Luid", LUID), ("Attributes", wintypes.DWORD)]

    class TOKEN_PRIVILEGES(ctypes.Structure):
        _fields_ = [("PrivilegeCount", wintypes.DWORD), ("Privileges", LUID_AND_ATTRIBUTES * 1)]

    h_token = wintypes.HANDLE()
    if not advapi32.OpenProcessToken(
        kernel32.GetCurrentProcess(),
        TOKEN_ADJUST_PRIVILEGES | TOKEN_QUERY,
        ctypes.byref(h_token),
    ):
        return False

    try:
        luid = LUID()
        if not advapi32.LookupPrivilegeValueW(None, "SeDebugPrivilege", ctypes.byref(luid)):
            return False

        tp = TOKEN_PRIVILEGES()
        tp.PrivilegeCount = 1
        tp.Privileges[0].Luid = luid
        tp.Privileges[0].Attributes = SE_PRIVILEGE_ENABLED

        if not advapi32.AdjustTokenPrivileges(h_token, False, ctypes.byref(tp), 0, None, None):
            return False
        return ctypes.get_last_error() != 1300  # ERROR_NOT_ALL_ASSIGNED
    finally:
        kernel32.CloseHandle(h_token)


def ensure_admin() -> None:
    """Relaunch elevated via UAC when not already admin. Exits the unelevated copy."""
    if is_admin():
        enable_debug_privilege()
        return

    # Absolute paths so the elevated copy finds the script after the cwd changes.
    argv = [str(Path(a).resolve()) if i == 0 or Path(a).exists() else a for i, a in enumerate(sys.argv)]
    # Ensure argv[0] is the script even when frozen differently
    if not argv:
        argv = [str(Path(__file__).resolve().parent / "main.py")]
    elif not argv[0].lower().endswith((".py", ".pyw")):
        script = Path(__file__).resolve().parent / "main.py"
        argv = [str(script), *argv[1:]]

    params = " ".join(f'"{arg}"' for arg in argv)
    workdir = str(Path(argv[0]).resolve().parent)
    rc = ctypes.windll.shell32.ShellExecuteW(
        None,
        "runas",
        sys.executable,
        params,
        workdir,
        1,  # SW_SHOWNORMAL
    )
    # ShellExecute returns > 32 on success
    if rc <= 32:
        sys.exit(1)
    sys.exit(0)
