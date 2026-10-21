"""Desktop shell for remote module loading."""

from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from elevate import is_admin
from loader import (
    InjectResult,
    ProcessInfo,
    inject_dll,
    injector_architecture,
    list_processes,
    process_architecture,
)

COLORS = {
    "bg": "#101214",
    "panel": "#171a1e",
    "panel_2": "#1e2329",
    "border": "#2a313a",
    "text": "#e6e9ed",
    "muted": "#8b949e",
    "accent": "#6b9bd1",
    "accent_dim": "#4f7fad",
    "danger": "#d87979",
    "ok": "#6fbf8f",
    "warn": "#c9a45c",
    "input": "#0e1114",
}


class App(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        self.title("Aether")
        self.geometry("700x540")
        self.minsize(620, 480)
        self.configure(fg_color=COLORS["bg"])

        self._processes: list[ProcessInfo] = []
        self._filtered: list[ProcessInfo] = []
        self._busy = False

        self._build()
        self.after(80, self.refresh_processes)

    def _build(self) -> None:
        root = ctk.CTkFrame(self, fg_color=COLORS["bg"], corner_radius=0)
        root.pack(fill="both", expand=True, padx=28, pady=24)
        root.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(root, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 16))
        header.grid_columnconfigure(0, weight=1)

        brand = ctk.CTkLabel(
            header,
            text="Aether",
            font=ctk.CTkFont(family="Segoe UI Semibold", size=26, weight="bold"),
            text_color=COLORS["text"],
            anchor="w",
        )
        brand.grid(row=0, column=0, sticky="w")

        subtitle = ctk.CTkLabel(
            header,
            text="Module tools",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=COLORS["muted"],
            anchor="w",
        )
        subtitle.grid(row=1, column=0, sticky="w", pady=(2, 0))

        priv = "elevated" if is_admin() else "limited"
        badge = ctk.CTkLabel(
            header,
            text=f"  {injector_architecture()}  ·  {priv}  ",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=COLORS["ok"] if is_admin() else COLORS["warn"],
            fg_color=COLORS["panel_2"],
            corner_radius=6,
        )
        badge.grid(row=0, column=1, rowspan=2, sticky="e")

        line = ctk.CTkFrame(root, fg_color=COLORS["border"], height=1, corner_radius=0)
        line.grid(row=1, column=0, sticky="ew", pady=(0, 18))

        # Application picker
        proc_block = ctk.CTkFrame(
            root,
            fg_color=COLORS["panel"],
            corner_radius=10,
            border_width=1,
            border_color=COLORS["border"],
        )
        proc_block.grid(row=2, column=0, sticky="ew", pady=(0, 12))

        inner = ctk.CTkFrame(proc_block, fg_color="transparent")
        inner.pack(fill="x", padx=18, pady=16)
        inner.grid_columnconfigure(0, weight=1)

        proc_label = ctk.CTkLabel(
            inner,
            text="APPLICATION",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=COLORS["muted"],
            anchor="w",
        )
        proc_label.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))

        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._apply_filter())

        search = ctk.CTkEntry(
            inner,
            textvariable=self.search_var,
            placeholder_text="Search by name or PID",
            height=36,
            corner_radius=8,
            border_width=1,
            border_color=COLORS["border"],
            fg_color=COLORS["input"],
            text_color=COLORS["text"],
            placeholder_text_color=COLORS["muted"],
            font=ctk.CTkFont(family="Segoe UI", size=13),
        )
        search.grid(row=1, column=0, sticky="ew", padx=(0, 8))

        refresh_btn = ctk.CTkButton(
            inner,
            text="Refresh",
            width=96,
            height=36,
            corner_radius=8,
            fg_color=COLORS["panel_2"],
            hover_color=COLORS["border"],
            text_color=COLORS["text"],
            border_width=1,
            border_color=COLORS["border"],
            font=ctk.CTkFont(family="Segoe UI", size=12),
            command=self.refresh_processes,
        )
        refresh_btn.grid(row=1, column=1, sticky="e")

        self.process_menu = ctk.CTkOptionMenu(
            inner,
            values=["Loading…"],
            height=40,
            corner_radius=8,
            fg_color=COLORS["input"],
            button_color=COLORS["accent_dim"],
            button_hover_color=COLORS["accent"],
            dropdown_fg_color=COLORS["panel_2"],
            dropdown_hover_color=COLORS["border"],
            dropdown_text_color=COLORS["text"],
            text_color=COLORS["text"],
            font=ctk.CTkFont(family="Segoe UI", size=13),
            dropdown_font=ctk.CTkFont(family="Consolas", size=12),
            anchor="w",
            command=self._on_process_selected,
        )
        self.process_menu.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))

        self.arch_label = ctk.CTkLabel(
            inner,
            text="",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=COLORS["muted"],
            anchor="w",
        )
        self.arch_label.grid(row=3, column=0, columnspan=2, sticky="w", pady=(8, 0))

        # Library path
        dll_block = ctk.CTkFrame(
            root,
            fg_color=COLORS["panel"],
            corner_radius=10,
            border_width=1,
            border_color=COLORS["border"],
        )
        dll_block.grid(row=3, column=0, sticky="ew", pady=(0, 12))

        dll_inner = ctk.CTkFrame(dll_block, fg_color="transparent")
        dll_inner.pack(fill="x", padx=18, pady=16)
        dll_inner.grid_columnconfigure(0, weight=1)

        dll_label = ctk.CTkLabel(
            dll_inner,
            text="LIBRARY",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=COLORS["muted"],
            anchor="w",
        )
        dll_label.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))

        self.dll_var = tk.StringVar()
        dll_entry = ctk.CTkEntry(
            dll_inner,
            textvariable=self.dll_var,
            placeholder_text="Path to library (.dll)",
            height=40,
            corner_radius=8,
            border_width=1,
            border_color=COLORS["border"],
            fg_color=COLORS["input"],
            text_color=COLORS["text"],
            placeholder_text_color=COLORS["muted"],
            font=ctk.CTkFont(family="Consolas", size=12),
        )
        dll_entry.grid(row=1, column=0, sticky="ew", padx=(0, 8))

        browse_btn = ctk.CTkButton(
            dll_inner,
            text="Browse",
            width=96,
            height=40,
            corner_radius=8,
            fg_color=COLORS["panel_2"],
            hover_color=COLORS["border"],
            text_color=COLORS["text"],
            border_width=1,
            border_color=COLORS["border"],
            font=ctk.CTkFont(family="Segoe UI", size=12),
            command=self._browse_dll,
        )
        browse_btn.grid(row=1, column=1, sticky="e")

        self.action_btn = ctk.CTkButton(
            root,
            text="Load module",
            height=46,
            corner_radius=8,
            fg_color=COLORS["accent_dim"],
            hover_color=COLORS["accent"],
            text_color="#0b1016",
            font=ctk.CTkFont(family="Segoe UI Semibold", size=14, weight="bold"),
            command=self._start_load,
        )
        self.action_btn.grid(row=4, column=0, sticky="ew", pady=(4, 14))

        status_block = ctk.CTkFrame(
            root,
            fg_color=COLORS["panel"],
            corner_radius=10,
            border_width=1,
            border_color=COLORS["border"],
        )
        status_block.grid(row=5, column=0, sticky="nsew")
        root.grid_rowconfigure(5, weight=1)

        status_inner = ctk.CTkFrame(status_block, fg_color="transparent")
        status_inner.pack(fill="both", expand=True, padx=18, pady=14)

        status_label = ctk.CTkLabel(
            status_inner,
            text="ACTIVITY",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=COLORS["muted"],
            anchor="w",
        )
        status_label.pack(anchor="w", pady=(0, 6))

        self.status = ctk.CTkTextbox(
            status_inner,
            height=110,
            corner_radius=8,
            border_width=1,
            border_color=COLORS["border"],
            fg_color=COLORS["input"],
            text_color=COLORS["text"],
            font=ctk.CTkFont(family="Consolas", size=12),
            activate_scrollbars=True,
            wrap="word",
        )
        self.status.pack(fill="both", expand=True)
        self.status.configure(state="disabled")

        if is_admin():
            self._log("Ready.", kind="info")
        else:
            self._log("Running with limited rights — elevate for full access.", kind="warn")

    def _log(self, message: str, kind: str = "info") -> None:
        prefix = {"ok": "ok   ", "err": "err  ", "warn": "warn ", "info": "     "}.get(kind, "     ")
        self.status.configure(state="normal")
        self.status.insert("end", prefix + message + "\n")
        self.status.see("end")
        self.status.configure(state="disabled")

    def refresh_processes(self) -> None:
        if self._busy:
            return
        try:
            self._processes = list_processes()
            self._apply_filter()
            self._log(f"{len(self._processes)} applications available", kind="info")
        except OSError as exc:
            self._log(str(exc), kind="err")

    def _apply_filter(self) -> None:
        query = self.search_var.get().strip().lower()
        if query:
            self._filtered = [
                p
                for p in self._processes
                if query in p.name.lower() or query in str(p.pid)
            ]
        else:
            self._filtered = list(self._processes)

        if not self._filtered:
            self.process_menu.configure(values=["No matches"])
            self.process_menu.set("No matches")
            self.arch_label.configure(text="")
            return

        labels = [p.label for p in self._filtered]
        current = self.process_menu.get()
        self.process_menu.configure(values=labels)
        if current in labels:
            self.process_menu.set(current)
        else:
            self.process_menu.set(labels[0])
        self._on_process_selected(self.process_menu.get())

    def _selected_process(self) -> ProcessInfo | None:
        label = self.process_menu.get()
        for proc in self._filtered:
            if proc.label == label:
                return proc
        return None

    def _on_process_selected(self, _value: str | None = None) -> None:
        proc = self._selected_process()
        if not proc:
            self.arch_label.configure(text="")
            return
        arch = process_architecture(proc.pid)
        host = injector_architecture()
        if arch == "unknown":
            color = COLORS["warn"]
            note = "Architecture unavailable"
        elif arch != host:
            color = COLORS["danger"]
            note = f"{arch} target — host is {host}"
        else:
            color = COLORS["ok"]
            note = f"{arch} — compatible"
        self.arch_label.configure(text=note, text_color=color)

    def _browse_dll(self) -> None:
        path = filedialog.askopenfilename(
            title="Select library",
            filetypes=[("Libraries", "*.dll"), ("All files", "*.*")],
        )
        if path:
            self.dll_var.set(path)
            self._log(f"Selected {Path(path).name}", kind="info")

    def _start_load(self) -> None:
        if self._busy:
            return

        proc = self._selected_process()
        dll = self.dll_var.get().strip()

        if not proc:
            self._log("Choose an application first", kind="err")
            return
        if not dll:
            self._log("Choose a library first", kind="err")
            return

        self._busy = True
        self.action_btn.configure(state="disabled", text="Working…")
        self._log(f"Loading into {proc.name} ({proc.pid})", kind="info")

        def worker() -> None:
            result = inject_dll(proc.pid, dll)
            self.after(0, lambda: self._finish_load(result))

        threading.Thread(target=worker, daemon=True).start()

    def _finish_load(self, result: InjectResult) -> None:
        self._busy = False
        self.action_btn.configure(state="normal", text="Load module")
        self._log(result.message, kind="ok" if result.ok else "err")


def run() -> None:
    app = App()
    app.mainloop()
