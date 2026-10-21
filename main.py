"""Aether — process module tooling."""

from elevate import ensure_admin
from ui import run

if __name__ == "__main__":
    ensure_admin()
    run()
