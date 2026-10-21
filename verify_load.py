"""End-to-end check: load a benign system DLL into notepad."""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

from elevate import enable_debug_privilege, is_admin
from loader import inject_dll, process_architecture


def main() -> int:
    if is_admin():
        enable_debug_privilege()
        print("admin: yes")
    else:
        print("admin: no (some targets may fail)")

    dll = Path(r"C:\Windows\System32\version.dll")
    if not dll.is_file():
        print("missing test dll")
        return 1

    proc = subprocess.Popen(["notepad.exe"])
    time.sleep(0.8)
    try:
        arch = process_architecture(proc.pid)
        print(f"target: notepad.exe pid={proc.pid} arch={arch}")
        result = inject_dll(proc.pid, dll)
        print(("OK" if result.ok else "FAIL"), result.message)
        return 0 if result.ok else 2
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    sys.exit(main())
