"""
converter.py — Video Converter main application window.

All Tkinter widget interactions happen exclusively on the main thread.
Background work (FFmpeg process) runs in a daemon thread and communicates
back to the UI only through `self.after()` calls.
"""

from __future__ import annotations

import logging
import os
import threading
import time
import tkinter as tk
from dataclasses import dataclass, field
from tkinter import filedialog, scrolledtext, ttk
from typing import Dict, List, Optional, Set

import app_utils
import ffmpeg_engine
import gui_components
import hardware
from about import AboutWindow
from batch_processor import BatchProcessor
from error_window import FFmpegMissingWindow

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Encoding option maps
# ---------------------------------------------------------------------------

AUDIO_MAP: Dict[str, List[str]] = {
    "0": ["-c:a", "aac", "-b:a", "96k",  "-ac", "2", "-ar", "48000"],
    "1": ["-c:a", "aac", "-b:a", "128k", "-ac", "2", "-ar", "48000"],
    "2": ["-c:a", "aac", "-b:a", "192k", "-ac", "2", "-ar", "48000"],
    "3": ["-c:a", "copy"],
}

SCALE_MAP: Dict[str, str] = {
    "2": "scale=1920:1080",
    "3": "scale=1280:720",
    "4": "scale=960:540",
    "5": "scale=720:480",
}

FPS_MAP: Dict[str, str] = {
    "2": "fps=30",
    "3": "fps=24",
}


# ---------------------------------------------------------------------------
# Conversion state — replaces scattered self._x attributes
# ---------------------------------------------------------------------------

@dataclass
class _ConversionState:
    """Mutable state for a single file conversion.  Reset before each file."""
    input_file: str = ""
    output_file: str = ""
    encoder_kind: str = ""
    decode_tech: str = ""
    encode_tech: str = ""
    progress_prefix: str = ""
    quality_value: int = 0
    duration_s: int = 0
    t_start: float = 0.0

    def reset(self) -> None:
        for f in self.__dataclass_fields__:
            setattr(self, f, self.__dataclass_fields__[f].default)


# ---------------------------------------------------------------------------
# Main application
# ---------------------------------------------------------------------------

class VideoConverterApp(tk.Tk):
    """Main application window for batch video conversion via FFmpeg."""

    def __init__(self) -> None:
        super().__init__()
        self.title("Video Converter")
        self.resizable(False, False)
        self._set_icon()

        self.processor = BatchProcessor()
        self.queue_files: List[str] = []
        self.current_index: int = 0

        self._conv = _ConversionState()
        self._log_lines: List[str] = []
        self._log_window: Optional[tk.Toplevel] = None
        self._log_widget: Optional[scrolledtext.ScrolledText] = None
        self._tools_detected: bool = False

        self.encoders: Set[str] = set()
        self.hwaccels: Set[str] = set()

        self._build_ui()
        self.after(100, self._on_startup_check)

    # ------------------------------------------------------------------
    # Startup
    # ------------------------------------------------------------------

    def _set_icon(self) -> None:
        icon_path = hardware.find_resource("converter.ico")
        if icon_path:
            try:
                self.iconbitmap(icon_path)
            except tk.TclError:
                pass

    def _on_startup_check(self) -> None:
        """Detect FFmpeg tools once, shortly after the window appears."""
        if self._tools_detected:
            return

        if not hardware.FFMPEG or not hardware.FFPROBE:
            self._tools_detected = True
            logger.error("FFmpeg / FFprobe not found.")
            FFmpegMissingWindow(self)
            return

        self.encoders = hardware.get_ffmpeg_encoders()
        self.hwaccels = hardware.get_ffmpeg_hwaccels()
        self._tools_detected = True
        self._update_cq_hint()
        logger.info("Detected video encoders: %s", ", ".join(sorted(self.encoders)))
        self._log(f"Detected video encoders: {', '.join(sorted(self.encoders))}")

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        style = ttk.Style(self)
        style.theme_use("winnative")
        style.configure(".", font=("Segoe UI", 8))
        style.configure("TScale", borderwidth=0)
        style.configure("App.Horizontal.TProgressbar", thickness=6, borderwidth=0)

        pad = {"padx": 8, "pady": 4, "fill": "x"}

        self._build_source_section(pad)
        self._build_codec_section(pad)
        self._build_output_section(pad)
        self._build_progress_section(pad)
        self._build_button_row()

    def _build_source_section(self, pad: dict) -> None:
        sec = gui_components.create_section(self, "Source")
        sec.pack(**pad)
        row = tk.Frame(sec)
        row.pack(fill="x", pady=2)

        self.btn_select_file = gui_components.create_button(row, "File", self._select_file)
        self.btn_select_file.pack(side="left", padx=(0, 5))

        self.btn_select_dir = gui_components.create_button(row, "Folder", self._select_directory)
        self.btn_select_dir.pack(side="left", padx=(0, 8))

        self.lbl_source_status = gui_components.create_label(row, "No source selected")
        self.lbl_source_status.pack(side="left", fill="x", expand=True)

    def _build_codec_section(self, pad: dict) -> None:
        sec = gui_components.create_section(self, "Codec and quality")
        sec.pack(**pad)

        codec_row = tk.Frame(sec)
        codec_row.pack(fill="x", pady=2)
        self.codec_var = tk.IntVar(value=1)
        gui_components.create_radio(codec_row, "H.264 / AVC",  self.codec_var, 1, self._update_cq_hint).pack(side="left", padx=(0, 14))
        gui_components.create_radio(codec_row, "H.265 / HEVC", self.codec_var, 2, self._update_cq_hint).pack(side="left", padx=(0, 14))
        self.encoder_status = gui_components.create_label(codec_row, "")
        self.encoder_status.pack(side="left", fill="x", expand=True)

        self._qmode_row = tk.Frame(sec)
        self._qmode_row.pack(fill="x", pady=2)
        self.quality_mode = tk.StringVar(value="cq")
        gui_components.create_radio(self._qmode_row, "CQ (quality)", self.quality_mode, "cq",     self._on_quality_mode_change).pack(side="left", padx=(0, 14))
        gui_components.create_radio(self._qmode_row, "Avg bitrate", self.quality_mode, "bitrate", self._on_quality_mode_change).pack(side="left")

        # CQ row
        self.cq_row_frame = tk.Frame(sec)
        self.cq_hint = gui_components.create_label(self.cq_row_frame, "", gui_components.FONT_SMALL)
        self.cq_hint.pack(side="left", padx=(0, 8))
        self.cq_var = tk.IntVar(value=30)
        self.cq_scale = ttk.Scale(
            self.cq_row_frame, from_=18, to=40, variable=self.cq_var,
            orient="horizontal", length=210, command=self._on_cq_scale_moved,
        )
        self.cq_scale.pack(side="left")
        self.cq_label = gui_components.create_label(self.cq_row_frame, "30", gui_components.FONT_UI_BOLD)
        self.cq_label.pack(side="left", padx=(8, 0))

        # Bitrate row
        self.br_row_frame = tk.Frame(sec)
        gui_components.create_label(self.br_row_frame, "Video bitrate:", gui_components.FONT_SMALL).pack(side="left", padx=(0, 6))
        self.bitrate_var = tk.IntVar(value=2000)
        self.bitrate_scale = ttk.Scale(
            self.br_row_frame, from_=500, to=8000, variable=self.bitrate_var,
            orient="horizontal", length=210, command=self._on_bitrate_scale_moved,
        )
        self.bitrate_scale.pack(side="left")
        self.bitrate_label = gui_components.create_label(self.br_row_frame, "2000 kbps", gui_components.FONT_UI_BOLD)
        self.bitrate_label.pack(side="left", padx=(8, 0))

        # Initial visibility
        self.cq_row_frame.pack_forget()
        self.br_row_frame.pack_forget()
        self._on_quality_mode_change()

    def _build_output_section(self, pad: dict) -> None:
        sec = gui_components.create_section(self, "Output options")
        sec.pack(**pad)
        row = tk.Frame(sec)
        row.pack(fill="x", pady=2)

        self.audio_var = tk.StringVar(value="1")
        self.res_var   = tk.StringVar(value="1")
        self.fps_var   = tk.StringVar(value="1")

        gui_components.create_combo(row, "Audio",      ["AAC 96k", "AAC 128k", "AAC 192k", "Copy"],                     ["0", "1", "2", "3"],       self.audio_var, 1)
        gui_components.create_combo(row, "Resolution", ["Original", "1920x1080", "1280x720", "960x540", "720x480"],     ["1", "2", "3", "4", "5"],  self.res_var,   0)
        gui_components.create_combo(row, "FPS",        ["Original", "30 fps", "24 fps"],                                ["1", "2", "3"],             self.fps_var,   0)

    def _build_progress_section(self, pad: dict) -> None:
        sec = gui_components.create_section(self, "Progress")
        sec.pack(**pad)

        self.lbl_batch_progress = gui_components.create_label(sec, "Ready", gui_components.FONT_UI_BOLD)
        self.lbl_batch_progress.pack(anchor="w", pady=(0, 3))

        self.progress_var = tk.DoubleVar(value=0.0)
        ttk.Progressbar(
            sec, variable=self.progress_var, maximum=100, length=420,
            style="App.Horizontal.TProgressbar",
        ).pack(fill="x", pady=(0, 3))

        stat_row = tk.Frame(sec)
        stat_row.pack(fill="x", pady=2)
        self.stat_fps   = gui_components.create_label(stat_row, "fps: -",   gui_components.FONT_SMALL)
        self.stat_speed = gui_components.create_label(stat_row, "speed: -", gui_components.FONT_SMALL)
        self.stat_size  = gui_components.create_label(stat_row, "size: -",  gui_components.FONT_SMALL)
        self.stat_eta   = gui_components.create_label(stat_row, "ETA: -",   gui_components.FONT_SMALL)
        for w in (self.stat_fps, self.stat_speed, self.stat_size, self.stat_eta):
            w.pack(side="left", padx=(0, 16))

        self.stat_tech = gui_components.create_label(sec, "decode: -, encode: -", gui_components.FONT_SMALL)
        self.stat_tech.pack(anchor="w", pady=(0, 2))

    def _build_button_row(self) -> None:
        row = tk.Frame(self)
        row.pack(padx=8, pady=(5, 8), fill="x")

        self.btn_convert = gui_components.create_button(row, "Start", self._start_batch_conversion)
        self.btn_convert.pack(side="left")

        self.btn_cancel = gui_components.create_button(row, "Cancel", self._cancel_conversion)
        self.btn_cancel.config(state="disabled")

        gui_components.create_button(row, "Log",   self._open_log_window).pack(side="right")
        gui_components.create_button(row, "About", self._show_about).pack(side="right", padx=(4, 0))

    # ------------------------------------------------------------------
    # UI event handlers — all run on main thread
    # ------------------------------------------------------------------

    def _on_quality_mode_change(self) -> None:
        self.cq_row_frame.pack_forget()
        self.br_row_frame.pack_forget()
        if self.quality_mode.get() == "cq":
            self.cq_row_frame.pack(fill="x", pady=2, after=self._qmode_row)
        else:
            self.br_row_frame.pack(fill="x", pady=2, after=self._qmode_row)
        self._update_cq_hint()

    def _on_cq_scale_moved(self, _event=None) -> None:
        self.cq_label.config(text=str(self.cq_var.get()))
        self._update_cq_hint()

    def _on_bitrate_scale_moved(self, _event=None) -> None:
        snapped = round(self.bitrate_var.get() / 100) * 100
        self.bitrate_var.set(snapped)
        self.bitrate_label.config(text=f"{snapped} kbps")

    def _update_cq_hint(self) -> None:
        if self.quality_mode.get() == "bitrate":
            self.encoder_status.config(text="Avg bitrate mode (2-pass not used)")
            return
        hint = (
            "Quality: 28-32 for 1080p, 24-28 for 720p"
            if self.codec_var.get() == 1
            else "Quality: 26-30 for 1080p, 22-26 for 720p"
        )
        self.cq_hint.config(text=hint)
        if not self._tools_detected:
            self.encoder_status.config(text="Will detect encoder on Start")
            return
        encoder = ffmpeg_engine.select_encoder(
            self.codec_var.get(), self._get_quality_opt(), self.encoders, self.hwaccels
        )
        self.encoder_status.config(text=f"Will use: {encoder.name}")

    def _select_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Select video file",
            filetypes=[("Video files", "*.mp4 *.avi *.mkv *.m2ts *.ts")],
        )
        if path:
            self.queue_files = [os.path.normpath(path)]
            self.lbl_source_status.config(text=f"File: {os.path.basename(path)}")

    def _select_directory(self) -> None:
        dir_path = filedialog.askdirectory(title="Select folder")
        if not dir_path:
            return
        self.queue_files = app_utils.scan_directory(dir_path)
        name = os.path.basename(dir_path)
        if self.queue_files:
            self.lbl_source_status.config(text=f"Folder: {name} ({len(self.queue_files)} files)")
        else:
            self.lbl_source_status.config(text=f"Folder: {name} (no supported videos)")

    def _show_about(self) -> None:
        AboutWindow(self)

    def _cancel_conversion(self) -> None:
        self.processor.terminate()

    # ------------------------------------------------------------------
    # Batch conversion — entry point
    # ------------------------------------------------------------------

    def _start_batch_conversion(self) -> None:
        if not self.queue_files:
            self._log("Warning: no file or folder selected.")
            self._open_log_window()
            return

        self.processor.cancel_requested = False
        self.current_index = 0

        self.btn_convert.config(state="disabled")
        self.btn_cancel.config(state="normal")
        self.btn_cancel.pack(side="left", padx=6, after=self.btn_convert)
        self.btn_select_file.config(state="disabled")
        self.btn_select_dir.config(state="disabled")

        threading.Thread(target=self._process_queue, daemon=True).start()

    # ------------------------------------------------------------------
    # Background thread — NO direct Tkinter calls allowed here
    # ------------------------------------------------------------------

    def _process_queue(self) -> None:
        """Worker: runs entirely on the background thread."""
        if not self.encoders:
            self.after(0, self._batch_done)
            return

        total = len(self.queue_files)
        while self.current_index < total and not self.processor.cancel_requested:
            self._convert_single_file(
                self.queue_files[self.current_index],
                current=self.current_index + 1,
                total=total,
            )
            self.current_index += 1

        self.after(0, self._batch_done)

    def _convert_single_file(self, input_file: str, current: int, total: int) -> None:
        """Prepare and execute FFmpeg for one file, with GPU→CPU fallback."""
        codec_id   = self.codec_var.get()
        quality    = self._get_quality_opt()
        audio_opts = AUDIO_MAP[self.audio_var.get()]
        vf_filter  = self._build_vf_filter()
        output_file = f"{os.path.splitext(input_file)[0]}_OPT_{{codec}}.mp4"

        encoder = ffmpeg_engine.select_encoder(codec_id, quality, self.encoders, self.hwaccels)
        output_file = output_file.format(codec=encoder.codec_label)

        self._conv.input_file      = input_file
        self._conv.output_file     = output_file
        self._conv.quality_value   = quality
        self._conv.duration_s      = hardware.get_duration(input_file)
        self._conv.progress_prefix = f"File {current}/{total}: {os.path.basename(input_file)}"
        self._apply_encoder_to_state(encoder)

        self.after(0, self._refresh_progress_label)
        self.after(0, self.progress_var.set, 0.0)

        self._log(f"Starting: {os.path.basename(input_file)}")
        logger.debug("Command encoder: %s", encoder.name)

        self._conv.t_start = time.time()
        cmd = self._build_cmd(input_file, output_file, encoder, audio_opts, vf_filter)
        rc  = self._run_ffmpeg(cmd)

        # GPU → CPU fallback
        if rc != 0 and not self.processor.cancel_requested and encoder.kind in {"nvenc", "amf"}:
            self._log(f"{encoder.kind.upper()} failed. Retrying with CPU encoder.")
            logger.warning("%s failed, falling back to CPU.", encoder.kind.upper())
            self.encoders.discard(encoder.name)
            encoder = ffmpeg_engine.select_encoder(codec_id, quality, self.encoders, self.hwaccels)
            self._apply_encoder_to_state(encoder)
            self.after(0, self._refresh_progress_label)
            self._conv.t_start = time.time()
            cmd = self._build_cmd(input_file, output_file, encoder, audio_opts, vf_filter)
            rc  = self._run_ffmpeg(cmd)

        self.after(0, self._on_single_conversion_done, rc)

    def _run_ffmpeg(self, cmd: List[str]) -> int:
        """Execute one FFmpeg command and return its return code."""
        return self.processor.run_ffmpeg_sync(
            cmd,
            log_callback=lambda msg: self.after(0, self._log, msg),
            progress_callback=lambda data: self.after(0, self._apply_progress, data),
        )

    # ------------------------------------------------------------------
    # Main-thread UI update callbacks
    # ------------------------------------------------------------------

    def _apply_progress(self, data: Dict[str, str]) -> None:
        """Update progress bar and stats — MUST be called on main thread via after()."""
        try:
            out_time_us = int(data.get("out_time_us", 0) or 0)
        except ValueError:
            out_time_us = 0

        elapsed_s = out_time_us / 1_000_000
        pct = min(100.0, elapsed_s / self._conv.duration_s * 100) if self._conv.duration_s else 0.0
        self.progress_var.set(pct)

        self.stat_fps.config(  text=f"fps: {data.get('fps', '-')}")
        self.stat_speed.config(text=f"speed: {data.get('speed', '-')}")
        self.stat_size.config( text=f"size: {hardware.bytes_to_mb(data.get('total_size', '-'))}")
        self.stat_eta.config(  text=f"ETA: {app_utils.calculate_eta(pct, self._conv.t_start)}")

    def _on_single_conversion_done(self, rc: int) -> None:
        """Show per-file result — runs on main thread."""
        if rc == 0:
            elapsed = int(time.time() - self._conv.t_start)
            self._log(app_utils.generate_report_text(self._conv.input_file, self._conv.output_file, elapsed))
            self.progress_var.set(100.0)
        else:
            msg = "Cancelled" if self.processor.cancel_requested else f"Failed | Code: {rc}"
            self._log(msg)
            self.progress_var.set(0.0)

    def _batch_done(self) -> None:
        """Restore UI after the full batch — runs on main thread."""
        self.btn_convert.config(state="normal")
        self.btn_cancel.config(state="disabled")
        self.btn_cancel.pack_forget()
        self.btn_select_file.config(state="normal")
        self.btn_select_dir.config(state="normal")
        summary = "Task cancelled." if self.processor.cancel_requested else "All files processed."
        self.lbl_batch_progress.config(text=summary)

    def _refresh_progress_label(self) -> None:
        self.lbl_batch_progress.config(text=self._conv.progress_prefix or "Ready")
        if self._conv.decode_tech:
            self.stat_tech.config(text=f"decode: {self._conv.decode_tech}, encode: {self._conv.encode_tech}")
        else:
            self.stat_tech.config(text="decode: -, encode: -")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_quality_opt(self) -> int:
        return self.cq_var.get()

    def _build_vf_filter(self) -> str:
        filters = []
        if self.res_var.get() in SCALE_MAP:
            filters.append(SCALE_MAP[self.res_var.get()])
        if self.fps_var.get() in FPS_MAP:
            filters.append(FPS_MAP[self.fps_var.get()])
        return ",".join(filters)

    def _apply_encoder_to_state(self, encoder: ffmpeg_engine.VideoEncoder) -> None:
        """Update _ConversionState with labels from the chosen encoder."""
        self._conv.encoder_kind = encoder.kind
        self._conv.decode_tech, self._conv.encode_tech = ffmpeg_engine.get_encoder_labels(encoder, self.hwaccels)

    def _build_cmd(
        self,
        input_file: str,
        output_file: str,
        encoder: ffmpeg_engine.VideoEncoder,
        audio_opts: List[str],
        vf_filter: str,
    ) -> List[str]:
        return ffmpeg_engine.build_ffmpeg_cmd(
            input_file, output_file, encoder, audio_opts, vf_filter,
            self.quality_mode.get(), self.bitrate_var.get(), self.hwaccels,
        )

    # ------------------------------------------------------------------
    # Log window
    # ------------------------------------------------------------------

    def _log(self, text: str) -> None:
        """Append a line to the in-memory log and the log window (if open)."""
        self._log_lines.append(text)
        if self._log_widget:
            self._log_widget.config(state="normal")
            self._log_widget.insert("end", text + "\n")
            self._log_widget.see("end")
            self._log_widget.config(state="disabled")

    def _open_log_window(self) -> None:
        if self._log_window and self._log_window.winfo_exists():
            self._log_window.lift()
            return
        self._log_window = tk.Toplevel(self)
        self._log_window.title("Log")
        self._log_window.geometry("720x360")
        self._log_widget = scrolledtext.ScrolledText(
            self._log_window, font=("Consolas", 8), relief="flat", borderwidth=0
        )
        self._log_widget.pack(fill="both", expand=True, padx=8, pady=8)
        self._log_widget.insert("end", "\n".join(self._log_lines) + ("\n" if self._log_lines else ""))
        self._log_widget.see("end")
        self._log_widget.config(state="disabled")
        self._log_window.protocol("WM_DELETE_WINDOW", self._close_log_window)

    def _close_log_window(self) -> None:
        if self._log_window:
            self._log_window.destroy()
        self._log_window = None
        self._log_widget = None


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format="%(levelname)s %(name)s: %(message)s")
    VideoConverterApp().mainloop()