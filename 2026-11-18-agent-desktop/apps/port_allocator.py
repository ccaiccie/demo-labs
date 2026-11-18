#!/usr/bin/env python3
"""Lab Port Allocator - a tiny Tk app for an agent-desktop demo.

BUG (intentional): allocate_next() increments the next-port counter BEFORE
returning a value, so the first allocation skips the starting port (off-by-one).
Fix: return the current value, then increment.

The '+' control is an image-only button with no accessible name, so an agent
must find it by role (or position) rather than by name.
"""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path

# Flip this to False after confirming the bug, then restart to re-verify.
OFF_BY_ONE = True

TITLE = "Lab Port Allocator - 2026-11-18-agent-desktop"
BG = "#f7f4ee"
FG = "#1b1b1b"
ACCENT = "#1f6feb"

def _plus_image(root: tk.Tk) -> tk.PhotoImage:
    # 24x24 plus sign, no text on the button itself.
    img = tk.PhotoImage(width=24, height=24)
    for x in range(24):
        for y in range(24):
            img.put("#e8eef8", (x, y))
    for x in range(6, 18):
        for y in range(10, 14):
            img.put(ACCENT, (x, y))
    for x in range(10, 14):
        for y in range(6, 18):
            img.put(ACCENT, (x, y))
    return img


class PortAllocator(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(TITLE)
        self.configure(bg=BG)
        self.geometry("820x640+1020+80")
        self.minsize(720, 560)
        self.option_add("*Font", "{Segoe UI} 16")
        self.next_port = 8000
        self.allocations: list[int] = []
        self.skip_even = tk.BooleanVar(value=False)
        self._build_menu()
        self._build()
        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def _build_menu(self) -> None:
        menubar = tk.Menu(self)
        filem = tk.Menu(menubar, tearoff=0)
        filem.add_command(label="Export log...", command=self.export_log)
        filem.add_separator()
        filem.add_command(label="Quit", command=self.destroy)
        menubar.add_cascade(label="File", menu=filem)
        helpm = tk.Menu(menubar, tearoff=0)
        helpm.add_command(label="About", command=self.show_about)
        menubar.add_cascade(label="Help", menu=helpm)
        self.config(menu=menubar)

    def _build(self) -> None:
        pad = dict(padx=16, pady=8)
        hdr = tk.Label(self, text="Lab Port Allocator", font=("Segoe UI", 22, "bold"),
                       bg=BG, fg=FG)
        hdr.pack(anchor="w", **pad)
        sub = tk.Label(self, text="Allocate the next free TCP port for a local lab service.",
                       bg=BG, fg="#444")
        sub.pack(anchor="w", padx=16)

        row = tk.Frame(self, bg=BG)
        row.pack(fill="x", padx=16, pady=16)
        tk.Label(row, text="Starting port", bg=BG).pack(side="left")
        self.port_var = tk.StringVar(value=str(self.next_port))
        self.port_entry = ttk.Entry(row, textvariable=self.port_var, width=10)
        self.port_entry.pack(side="left", padx=10)
        self.plus_img = _plus_image(self)
        # Image-only, empty text -> typically no accessible Name in UIA.
        self.plus_btn = tk.Button(row, image=self.plus_img, text="",
                                  command=self.bump_start, bd=2, relief="raised",
                                  width=28, height=28)
        self.plus_btn.pack(side="left", padx=6)

        self.skip = ttk.Checkbutton(self, text="Skip even ports",
                                    variable=self.skip_even, command=self.refresh)
        self.skip.pack(anchor="w", padx=16)

        btns = tk.Frame(self, bg=BG)
        btns.pack(fill="x", padx=16, pady=10)
        self.alloc_btn = ttk.Button(btns, text="Allocate next port", command=self.allocate)
        self.alloc_btn.pack(side="left")
        ttk.Button(btns, text="Reset", command=self.reset).pack(side="left", padx=8)

        tk.Label(self, text="Last allocated", bg=BG).pack(anchor="w", padx=16)
        self.result = tk.StringVar(value="(none yet)")
        tk.Label(self, textvariable=self.result, font=("Cascadia Mono", 28, "bold"),
                 bg=BG, fg=ACCENT, name="resultlabel").pack(anchor="w", padx=16, pady=(0, 8))
        self.result_label = self.children.get("resultlabel")

        tk.Label(self, text="Allocation log", bg=BG).pack(anchor="w", padx=16)
        self.log = tk.Text(self, height=8, font=("Cascadia Mono", 14), bg="white", fg=FG)
        self.log.pack(fill="both", expand=True, padx=16, pady=(0, 12))
        self._log(f"Ready. OFF_BY_ONE={OFF_BY_ONE}. Starting port {self.next_port}.")

    def _current_start(self) -> int:
        try:
            return int(self.port_var.get().strip())
        except ValueError:
            return self.next_port

    def bump_start(self) -> None:
        n = self._current_start() + 1
        self.next_port = n
        self.port_var.set(str(n))
        self._log(f"Starting port bumped to {n}.")

    def allocate_next(self) -> int:
        # Keep the entry and the counter in sync if the user edited the field.
        self.next_port = self._current_start()
        if OFF_BY_ONE:
            # BUG: increment first, so we skip the starting port.
            self.next_port += 1
            value = self.next_port
        else:
            value = self.next_port
            self.next_port += 1
        if self.skip_even.get() and value % 2 == 0:
            value = self.allocate_next()
        self.port_var.set(str(self.next_port))
        return value

    def allocate(self) -> None:
        value = self.allocate_next()
        self.allocations.append(value)
        self.result.set(str(value))
        self._log(f"Allocated port {value}. Next start would be {self.next_port}.")

    def reset(self) -> None:
        self.next_port = 8000
        self.allocations.clear()
        self.port_var.set("8000")
        self.result.set("(none yet)")
        self.skip_even.set(False)
        self._log("Reset to starting port 8000.")

    def refresh(self) -> None:
        self._log(f"Skip even ports = {self.skip_even.get()}.")

    def _log(self, line: str) -> None:
        self.log.insert("end", line + "\n")
        self.log.see("end")

    def export_log(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Export allocation log",
            defaultextension=".txt",
            initialfile="port-allocations.txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if not path:
            return
        Path(path).write_text(self.log.get("1.0", "end"), encoding="utf-8")
        self._log(f"Exported log to {path}.")
        messagebox.showinfo("Export complete", f"Wrote {path}")

    def show_about(self) -> None:
        messagebox.showinfo(
            "About Lab Port Allocator",
            "A harmless local demo app for agent-desktop.\n"
            f"OFF_BY_ONE is currently {OFF_BY_ONE}.",
        )


if __name__ == "__main__":
    PortAllocator().mainloop()
