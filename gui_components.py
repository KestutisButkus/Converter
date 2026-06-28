import tkinter as tk
from tkinter import ttk
from typing import Any, List, Tuple

FONT_UI: Tuple[str, int] = ("Segoe UI", 8)
FONT_UI_BOLD: Tuple[str, int] = ("Segoe UI", 8, "bold")
FONT_SMALL: Tuple[str, int] = ("Segoe UI", 7)


def create_section(parent: tk.Widget, title: str) -> tk.Frame:
    frame = tk.Frame(parent, padx=8, pady=6)
    tk.Label(frame, text=title, font=FONT_UI_BOLD).pack(anchor="w", pady=(0, 4))
    return frame


def create_label(parent: tk.Widget, text: str, font: Tuple[str, int] = FONT_UI) -> tk.Label:
    return tk.Label(parent, text=text, font=font)


def create_button(parent: tk.Widget, text: str, command: Any) -> tk.Button:
    return tk.Button(parent, text=text, font=FONT_UI_BOLD, padx=10, pady=2, command=command)


def create_radio(parent: tk.Widget, text: str, variable: tk.Variable, value: Any, command: Any) -> tk.Radiobutton:
    return tk.Radiobutton(parent, text=text, variable=variable, value=value, font=FONT_UI, command=command)


def create_combo(parent: tk.Widget, label: str, labels: List[str], values: List[str], target: tk.StringVar, current: int) -> None:
    tk.Label(parent, text=f"{label}:", font=FONT_SMALL).pack(side="left", padx=(0, 3))
    combo = ttk.Combobox(parent, values=labels, state="readonly", width=11, font=FONT_UI)
    combo.current(current)
    combo.pack(side="left", padx=(0, 10))
    combo.bind("<<ComboboxSelected>>", lambda _e: target.set(values[combo.current()]))