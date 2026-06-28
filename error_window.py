"""
error_window.py — Styled critical error dialog for missing FFmpeg tools.

Replaces the plain messagebox + log window combination with a single,
professional Toplevel window that blocks interaction until dismissed.
"""

from __future__ import annotations

import tkinter as tk

_INSTRUCTIONS = (
    "1. Atsisiųskite FFmpeg iš oficialios svetainės:\n"
    "   https://www.gyan.dev/ffmpeg/builds/\n"
    "   (Rekomenduojama: ffmpeg-release-full-shared.7z)\n\n"
    "2. Išpakuokite atsisiųstą archyvą ir atidarykite 'bin' aplanką.\n\n"
    "3. Nukopijuokite VISUS jame esančius failus ir įkelkite juos\n"
    "   TIESIAI ŠALIA ŠIOS PROGRAMOS EXE failo.\n\n"
    "Būtini failai:\n"
    "  ffmpeg.exe, ffprobe.exe\n"
    "  avcodec-*.dll, avdevice-*.dll, avfilter-*.dll\n"
    "  avformat-*.dll, avutil-*.dll, swresample-*.dll, swscale-*.dll"
)

_RED   = "#c0392b"
_WHITE = "#ffffff"
_BG    = "#f8f8f8"
_BORDER = "#dcdcdc"


class FFmpegMissingWindow(tk.Toplevel):
    """Modal dialog shown when ffmpeg.exe / ffprobe.exe cannot be located."""

    def __init__(self, parent: tk.Widget) -> None:
        super().__init__(parent)
        self.title("FFmpeg not found")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self.configure(bg=_BG)

        self._build_header()
        self._build_body()
        self._build_footer()

        self.update_idletasks()
        self._center_on_parent(parent)

    # ------------------------------------------------------------------

    def _build_header(self) -> None:
        header = tk.Frame(self, bg=_RED, pady=14)
        header.pack(fill="x")

        tk.Label(
            header,
            text="⚠",
            font=("Segoe UI", 20),
            bg=_RED, fg=_WHITE,
        ).pack(side="left", padx=(18, 8))

        text_col = tk.Frame(header, bg=_RED)
        text_col.pack(side="left", fill="x", expand=True)

        tk.Label(
            text_col,
            text="Nerastas FFmpeg",
            font=("Segoe UI", 11, "bold"),
            bg=_RED, fg=_WHITE,
            anchor="w",
        ).pack(fill="x")

        tk.Label(
            text_col,
            text="Programa negali konvertuoti vaizdo failų be FFmpeg.",
            font=("Segoe UI", 8),
            bg=_RED, fg=_WHITE,
            anchor="w",
        ).pack(fill="x")

    def _build_body(self) -> None:
        body = tk.Frame(self, bg=_BG, padx=18, pady=14)
        body.pack(fill="both", expand=True)

        tk.Label(
            body,
            text="KAIP SUTVARKYTI:",
            font=("Segoe UI", 8, "bold"),
            bg=_BG, anchor="w",
        ).pack(fill="x", pady=(0, 6))

        box = tk.Frame(body, bg=_WHITE, relief="flat", bd=1,
                       highlightbackground=_BORDER, highlightthickness=1)
        box.pack(fill="both", expand=True)

        txt = tk.Text(
            box,
            font=("Segoe UI", 8),
            bg=_WHITE, relief="flat", bd=0,
            wrap="word", padx=10, pady=10,
            width=52, height=14,
            state="normal",
        )
        txt.insert("end", _INSTRUCTIONS)
        txt.config(state="disabled")
        txt.pack(fill="both", expand=True)

    def _build_footer(self) -> None:
        sep = tk.Frame(self, bg=_BORDER, height=1)
        sep.pack(fill="x")

        footer = tk.Frame(self, bg=_BG, padx=18, pady=10)
        footer.pack(fill="x")

        tk.Button(
            footer,
            text="Uždaryti",
            font=("Segoe UI", 8, "bold"),
            width=12, padx=10,
            relief="flat",
            bg=_RED, fg=_WHITE,
            activebackground="#a93226",
            activeforeground=_WHITE,
            cursor="hand2",
            command=self.destroy,
        ).pack(side="right")

    def _center_on_parent(self, parent: tk.Widget) -> None:
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()
        w  = self.winfo_reqwidth()
        h  = self.winfo_reqheight()
        x  = px + (pw - w) // 2
        y  = py + (ph - h) // 2
        self.geometry(f"+{x}+{y}")
