"""Load a library into another process (LoadLibraryW)."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
psapi = ctypes.WinDLL("psapi", use_last_error=True)

PROCESS_CREATE_THREAD = 0x0002
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
PROCESS_VM_OPERATION = 0x0008
PROCESS_VM_WRITE = 0x0020
PROCESS_VM_READ = 0x0010
PROCESS_ACCESS = (
    PROCESS_CREATE_THREAD
    | PROCESS_QUERY_INFORMATION
    | PROCESS_QUERY_LIMITED_INFORMATION
    | PROCESS_VM_OPERATION
    | PROCESS_VM_WRITE
    | PROCESS_VM_READ
)

MEM_COMMIT = 0x1000
MEM_RESERVE = 0x2000
MEM_RELEASE = 0x8000
PAGE_READWRITE = 0x04
INFINITE = 0xFFFFFFFF
TH32CS_SNAPPROCESS = 0x00000002
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
MAX_PATH = 260
LIST_MODULES_ALL = 0x03


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", wintypes.WCHAR * MAX_PATH),
    ]


kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
kernel32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
kernel32.Process32FirstW.restype = wintypes.BOOL
kernel32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
kernel32.Process32NextW.restype = wintypes.BOOL
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL
kernel32.VirtualAllocEx.argtypes = [
    wintypes.HANDLE,
    wintypes.LPVOID,
    ctypes.c_size_t,
    wintypes.DWORD,
    wintypes.DWORD,
]
kernel32.VirtualAllocEx.restype = wintypes.LPVOID
kernel32.VirtualFreeEx.argtypes = [
    wintypes.HANDLE,
    wintypes.LPVOID,
    ctypes.c_size_t,
    wintypes.DWORD,
]
kernel32.VirtualFreeEx.restype = wintypes.BOOL
kernel32.WriteProcessMemory.argtypes = [
    wintypes.HANDLE,
    wintypes.LPVOID,
    wintypes.LPCVOID,
    ctypes.c_size_t,
    ctypes.POINTER(ctypes.c_size_t),
]
kernel32.WriteProcessMemory.restype = wintypes.BOOL
kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
kernel32.GetModuleHandleW.restype = wintypes.HMODULE
kernel32.GetProcAddress.argtypes = [wintypes.HMODULE, wintypes.LPCSTR]
kernel32.GetProcAddress.restype = ctypes.c_void_p
kernel32.CreateRemoteThread.argtypes = [
    wintypes.HANDLE,
    wintypes.LPVOID,
    ctypes.c_size_t,
    ctypes.c_void_p,
    wintypes.LPVOID,
    wintypes.DWORD,
    wintypes.LPDWORD,
]
kernel32.CreateRemoteThread.restype = wintypes.HANDLE
kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
kernel32.WaitForSingleObject.restype = wintypes.DWORD
kernel32.GetExitCodeThread.argtypes = [wintypes.HANDLE, wintypes.LPDWORD]
kernel32.GetExitCodeThread.restype = wintypes.BOOL
kernel32.IsWow64Process.argtypes = [wintypes.HANDLE, wintypes.PBOOL]
kernel32.IsWow64Process.restype = wintypes.BOOL

psapi.EnumProcessModulesEx.argtypes = [
    wintypes.HANDLE,
    ctypes.POINTER(wintypes.HMODULE),
    wintypes.DWORD,
    wintypes.LPDWORD,
    wintypes.DWORD,
]
psapi.EnumProcessModulesEx.restype = wintypes.BOOL
psapi.GetModuleFileNameExW.argtypes = [
    wintypes.HANDLE,
    wintypes.HMODULE,
    wintypes.LPWSTR,
    wintypes.DWORD,
]
psapi.GetModuleFileNameExW.restype = wintypes.DWORD


@dataclass(frozen=True)
class ProcessInfo:
    pid: int
    name: str

    @property
    def label(self) -> str:
        return f"{self.name}    PID {self.pid}"


@dataclass(frozen=True)
class InjectResult:
    ok: bool
    message: str


def _last_error() -> int:
    return ctypes.get_last_error()


def list_processes() -> list[ProcessInfo]:
    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snapshot == INVALID_HANDLE_VALUE or not snapshot:
        raise OSError(f"Unable to enumerate processes (error {_last_error()})")

    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
        processes: list[ProcessInfo] = []

        if not kernel32.Process32FirstW(snapshot, ctypes.byref(entry)):
            raise OSError(f"Unable to read process list (error {_last_error()})")

        while True:
            name = entry.szExeFile.strip()
            pid = int(entry.th32ProcessID)
            if name and pid > 0:
                processes.append(ProcessInfo(pid=pid, name=name))
            if not kernel32.Process32NextW(snapshot, ctypes.byref(entry)):
                break

        processes.sort(key=lambda p: (p.name.lower(), p.pid))
        return processes
    finally:
        kernel32.CloseHandle(snapshot)


def _is_wow64(handle: wintypes.HANDLE) -> bool | None:
    flag = wintypes.BOOL()
    if not kernel32.IsWow64Process(handle, ctypes.byref(flag)):
        return None
    return bool(flag.value)


def process_architecture(pid: int) -> str:
    """Return 'x86', 'x64', or 'unknown' for the target process."""
    handle = kernel32.OpenProcess(
        PROCESS_QUERY_INFORMATION | PROCESS_QUERY_LIMITED_INFORMATION,
        False,
        pid,
    )
    if not handle:
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return "unknown"
    try:
        wow64 = _is_wow64(handle)
        if wow64 is None:
            return "unknown"
        if ctypes.sizeof(ctypes.c_void_p) == 8:
            return "x86" if wow64 else "x64"
        return "x86"
    finally:
        kernel32.CloseHandle(handle)


def injector_architecture() -> str:
    return "x64" if ctypes.sizeof(ctypes.c_void_p) == 8 else "x86"


def _module_loaded(h_process: wintypes.HANDLE, dll_path: Path) -> bool:
    target = str(dll_path.resolve()).lower()
    target_name = dll_path.name.lower()

    needed = wintypes.DWORD(0)
    psapi.EnumProcessModulesEx(h_process, None, 0, ctypes.byref(needed), LIST_MODULES_ALL)
    if needed.value == 0:
        return False

    count = needed.value // ctypes.sizeof(wintypes.HMODULE)
    modules = (wintypes.HMODULE * count)()
    if not psapi.EnumProcessModulesEx(
        h_process,
        modules,
        needed.value,
        ctypes.byref(needed),
        LIST_MODULES_ALL,
    ):
        return False

    buf = ctypes.create_unicode_buffer(MAX_PATH * 2)
    for mod in modules:
        if not mod:
            continue
        n = psapi.GetModuleFileNameExW(h_process, mod, buf, len(buf))
        if not n:
            continue
        path = buf.value.lower()
        if path == target or path.endswith("\\" + target_name) or path.endswith("/" + target_name):
            return True
    return False


def inject_dll(pid: int, dll_path: str | Path) -> InjectResult:
    path = Path(dll_path).resolve()
    if not path.is_file():
        return InjectResult(False, f"Library not found: {path}")
    if path.suffix.lower() != ".dll":
        return InjectResult(False, "Selected file is not a library (.dll)")

    abs_path = str(path)
    path_bytes = abs_path.encode("utf-16-le") + b"\x00\x00"
    path_size = len(path_bytes)

    target_arch = process_architecture(pid)
    host_arch = injector_architecture()
    if target_arch != "unknown" and target_arch != host_arch:
        return InjectResult(
            False,
            f"Architecture mismatch: host is {host_arch}, target is {target_arch}",
        )

    h_process = kernel32.OpenProcess(PROCESS_ACCESS, False, pid)
    if not h_process:
        err = _last_error()
        hint = " — elevated access required" if err in (5, 87) else ""
        return InjectResult(False, f"Could not open process (error {err}){hint}")

    remote_mem = None
    h_thread = None
    try:
        already = _module_loaded(h_process, path)

        remote_mem = kernel32.VirtualAllocEx(
            h_process,
            None,
            path_size,
            MEM_COMMIT | MEM_RESERVE,
            PAGE_READWRITE,
        )
        if not remote_mem:
            return InjectResult(False, f"Memory allocation failed (error {_last_error()})")

        written = ctypes.c_size_t(0)
        ok = kernel32.WriteProcessMemory(
            h_process,
            remote_mem,
            path_bytes,
            path_size,
            ctypes.byref(written),
        )
        if not ok or written.value != path_size:
            return InjectResult(False, f"Memory write failed (error {_last_error()})")

        h_kernel = kernel32.GetModuleHandleW("kernel32.dll")
        if not h_kernel:
            return InjectResult(False, f"kernel32 lookup failed (error {_last_error()})")

        load_library = kernel32.GetProcAddress(h_kernel, b"LoadLibraryW")
        if not load_library:
            return InjectResult(False, f"LoadLibraryW lookup failed (error {_last_error()})")

        thread_id = wintypes.DWORD(0)
        h_thread = kernel32.CreateRemoteThread(
            h_process,
            None,
            0,
            load_library,
            remote_mem,
            0,
            ctypes.byref(thread_id),
        )
        if not h_thread:
            return InjectResult(False, f"Remote thread failed (error {_last_error()})")

        wait = kernel32.WaitForSingleObject(h_thread, 15_000)
        if wait != 0:  # WAIT_OBJECT_0
            return InjectResult(False, "Timed out waiting for module load")

        exit_code = wintypes.DWORD(0)
        kernel32.GetExitCodeThread(h_thread, ctypes.byref(exit_code))

        verified = _module_loaded(h_process, path)
        if verified or (exit_code.value != 0):
            note = " (already present)" if already and verified else ""
            return InjectResult(
                True,
                f"Module loaded in PID {pid}{note}",
            )

        return InjectResult(
            False,
            "Module load returned no handle — path, dependencies, or access blocked",
        )
    finally:
        if h_thread:
            kernel32.CloseHandle(h_thread)
        if remote_mem:
            kernel32.VirtualFreeEx(h_process, remote_mem, 0, MEM_RELEASE)
        kernel32.CloseHandle(h_process)
