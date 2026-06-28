import os
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk
from typing import Dict, List, Tuple, Optional

import ffmpeg_engine
import hardware
import gui_components
import app_utils
from about import AboutWindow
from batch_processor import BatchProcessor

AUDIO_MAP: Dict[str, List[str]] = {
    "0": ["-c:a", "aac", "-b:a", "96k", "-ac", "2", "-ar", "48000"],
    "1": ["-c:a", "aac", "-b:a", "128k", "-ac", "2", "-ar", "48000"],
    "2": ["-c:a", "aac", "-b:a", "192k", "-ac", "2", "-ar", "48000"],
    "3": ["-c:a", "copy"],
}
SCALE_MAP: Dict[str, str] = {"2": "scale=1920:1080", "3": "scale=1280:720", "4": "scale=960:540", "5": "scale=720:480"}
FPS_MAP: Dict[str, str] = {"2": "fps=30", "3": "fps=24"}


class VideoConverterApp(tk.Tk):

    def __init__(self) -> None:
        super().__init__()
        self.title("Video Converter")
        self.resizable(False, False)
        self._set_icon()

        self.processor = BatchProcessor()
        self.queue_files: List[str] = []
        self.current_index: int = 0
        self.vdur: int = 0
        self.t_start: float = 0.0

        self._input_file: str = ""
        self._output_file: str = ""
        self._vcodec: str = ""
        self._encoder_kind: str = ""
        self._decode_tech: str = ""
        self._encode_tech: str = ""
        self._progress_prefix: str = ""
        self._quality_value: int = 0
        self._log_lines: List[str] = []
        self._log_window: Optional[tk.Toplevel] = None
        self._log_widget: Optional[scrolledtext.ScrolledText] = None
        self._tools_detected: bool = False

        self.encoders: set = set()
        self.hwaccels: set = set()

        self._build_ui()

    def _set_icon(self) -> None:
        icon_path = hardware.find_resource("converter.ico")
        if icon_path:
            try:
                self.iconbitmap(icon_path)
            except tk.TclError:
                pass

    def _build_ui(self) -> None:
        style = ttk.Style(self)
        style.theme_use("winnative")
        style.configure(".", font=("Segoe UI", 8))
        style.configure("TScale", borderwidth=0)
        style.configure("App.Horizontal.TProgressbar", thickness=6, borderwidth=0)

        pad = {"padx": 8, "pady": 4, "fill": "x"}

        # Source Section
        sec1 = gui_components.create_section(self, "Source")
        sec1.pack(**pad)
        row1 = tk.Frame(sec1)
        row1.pack(fill="x", pady=2)
        self.btn_select_file = gui_components.create_button(row1, "File", self._select_file)
        self.btn_select_file.pack(side="left", padx=(0, 5))
        self.btn_select_dir = gui_components.create_button(row1, "Folder", self._select_directory)
        self.btn_select_dir.pack(side="left", padx=(0, 8))
        self.lbl_source_status = gui_components.create_label(row1, "No source selected")
        self.lbl_source_status.pack(side="left", fill="x", expand=True)

        # Codec & Quality Section
        sec2 = gui_components.create_section(self, "Codec and quality")
        sec2.pack(**pad)
        row2 = tk.Frame(sec2)
        row2.pack(fill="x", pady=2)
        self.codec_var = tk.IntVar(value=1)
        gui_components.create_radio(row2, "H.264 / AVC", self.codec_var, 1, self._update_cq_hint).pack(side="left",
                                                                                                       padx=(0, 14))
        gui_components.create_radio(row2, "H.265 / HEVC", self.codec_var, 2, self._update_cq_hint).pack(side="left",
                                                                                                        padx=(0, 14))
        self.encoder_status = gui_components.create_label(row2, "")
        self.encoder_status.pack(side="left", fill="x", expand=True)

        qmode_row = self._qmode_row = tk.Frame(sec2)
        qmode_row.pack(fill="x", pady=2)
        self.quality_mode = tk.StringVar(value="cq")
        gui_components.create_radio(qmode_row, "CQ (quality)", self.quality_mode, "cq",
                                    self._on_quality_mode_change).pack(side="left", padx=(0, 14))
        gui_components.create_radio(qmode_row, "Avg bitrate", self.quality_mode, "bitrate",
                                    self._on_quality_mode_change).pack(side="left")

        self.cq_row_frame = tk.Frame(sec2)
        self.cq_row_frame.pack(fill="x", pady=2)
        self.cq_hint = gui_components.create_label(self.cq_row_frame, "", gui_components.FONT_SMALL)
        self.cq_hint.pack(side="left", padx=(0, 8))
        self.cq_var = tk.IntVar(value=30)
        self.cq_scale = ttk.Scale(self.cq_row_frame, from_=18, to=40, variable=self.cq_var, orient="horizontal",
                                  length=210, command=lambda _e: self._update_cq_label())
        self.cq_scale.pack(side="left")
        self.cq_label = gui_components.create_label(self.cq_row_frame, "30", gui_components.FONT_UI_BOLD)
        self.cq_label.pack(side="left", padx=(8, 0))

        self.br_row_frame = tk.Frame(sec2)
        gui_components.create_label(self.br_row_frame, "Video bitrate:", gui_components.FONT_SMALL).pack(side="left",
                                                                                                         padx=(0, 6))
        self.bitrate_var = tk.IntVar(value=2000)
        self.bitrate_scale = ttk.Scale(self.br_row_frame, from_=500, to=8000, variable=self.bitrate_var,
                                       orient="horizontal", length=210, command=lambda _e: self._update_bitrate_label())
        self.bitrate_scale.pack(side="left")
        self.bitrate_label = gui_components.create_label(self.br_row_frame, "2000 kbps", gui_components.FONT_UI_BOLD)
        self.bitrate_label.pack(side="left", padx=(8, 0))

        self.cq_row_frame.pack_forget()
        self.br_row_frame.pack_forget()
        self._on_quality_mode_change()

        # Output Options Section
        sec3 = gui_components.create_section(self, "Output options")
        sec3.pack(**pad)
        row3 = tk.Frame(sec3)
        row3.pack(fill="x", pady=2)
        self.audio_var, self.res_var, self.fps_var = tk.StringVar(value="1"), tk.StringVar(value="1"), tk.StringVar(
            value="1")
        gui_components.create_combo(row3, "Audio", ["AAC 96k", "AAC 128k", "AAC 192k", "Copy"], ["0", "1", "2", "3"],
                                    self.audio_var, 1)
        gui_components.create_combo(row3, "Resolution", ["Original", "1920x1080", "1280x720", "960x540", "720x480"],
                                    ["1", "2", "3", "4", "5"], self.res_var, 0)
        gui_components.create_combo(row3, "FPS", ["Original", "30 fps", "24 fps"], ["1", "2", "3"], self.fps_var, 0)

        # Progress Section
        sec4 = gui_components.create_section(self, "Progress")
        sec4.pack(**pad)
        self.lbl_batch_progress = gui_components.create_label(sec4, "Ready", gui_components.FONT_UI_BOLD)
        self.lbl_batch_progress.pack(anchor="w", pady=(0, 3))
        self.progress_var = tk.DoubleVar(value=0.0)
        ttk.Progressbar(sec4, variable=self.progress_var, maximum=100, length=420,
                        style="App.Horizontal.TProgressbar").pack(fill="x", pady=(0, 3))

        stat_row = tk.Frame(sec4)
        stat_row.pack(fill="x", pady=2)
        self.stat_fps = gui_components.create_label(stat_row, "fps: -", gui_components.FONT_SMALL)
        self.stat_speed = gui_components.create_label(stat_row, "speed: -", gui_components.FONT_SMALL)
        self.stat_size = gui_components.create_label(stat_row, "size: -", gui_components.FONT_SMALL)
        self.stat_eta = gui_components.create_label(stat_row, "ETA: -", gui_components.FONT_SMALL)
        for w in (self.stat_fps, self.stat_speed, self.stat_size, self.stat_eta): w.pack(side="left", padx=(0, 16))
        self.stat_tech = gui_components.create_label(sec4, "decode: -, encode: -", gui_components.FONT_SMALL)
        self.stat_tech.pack(anchor="w", pady=(0, 2))

        # Action Buttons Row
        btn_row = tk.Frame(self)
        btn_row.pack(padx=8, pady=(5, 8), fill="x")
        self.btn_convert = gui_components.create_button(btn_row, "Start", self._start_batch_conversion)
        self.btn_convert.pack(side="left")
        self.btn_cancel = gui_components.create_button(btn_row, "Cancel", self._cancel_conversion)
        self.btn_cancel.config(state="disabled")

        gui_components.create_button(btn_row, "About", self._show_about_info).pack(side="right", padx=(4, 0))
        gui_components.create_button(btn_row, "Log", self._open_log_window).pack(side="right")

    def _on_quality_mode_change(self) -> None:
        self.cq_row_frame.pack_forget()
        self.br_row_frame.pack_forget()
        if self.quality_mode.get() == "cq":
            self.cq_row_frame.pack(fill="x", pady=2, after=self._qmode_row)
        else:
            self.br_row_frame.pack(fill="x", pady=2, after=self._qmode_row)
        self._update_cq_hint()

    def _update_cq_hint(self) -> None:
        if self.quality_mode.get() == "bitrate":
            self.encoder_status.config(text="Avg bitrate mode (2-pass not used)")
            return
        self.cq_hint.config(
            text="Quality: 28-32 for 1080p, 24-28 for 720p" if self.codec_var.get() == 1 else "Quality: 26-30 for 1080p, 22-26 for 720p")
        if not self._tools_detected:
            self.encoder_status.config(text="Will detect encoder on Start")
            return
        encoder = ffmpeg_engine.select_encoder(self.codec_var.get(), self._get_quality_opts(), self.encoders,
                                               self.hwaccels)
        self.encoder_status.config(text=f"Will use: {encoder.name}")

    def _update_cq_label(self) -> None:
        self.cq_label.config(text=str(self.cq_var.get()))
        self._update_cq_hint()

    def _update_bitrate_label(self) -> None:
        snapped = round(self.bitrate_var.get() / 100) * 100
        self.bitrate_var.set(snapped)
        self.bitrate_label.config(text=f"{snapped} kbps")

    def _get_quality_opts(self) -> int:
        return self.cq_var.get()

    def _select_file(self) -> None:
        file_path = filedialog.askopenfilename(title="Select video file",
                                               filetypes=[("Video files", "*.mp4 *.avi *.mkv *.m2ts *.ts")])
        if file_path:
            self.queue_files = [os.path.normpath(file_path)]
            self.lbl_source_status.config(text=f"File: {os.path.basename(file_path)}")

    def _select_directory(self) -> None:
        dir_path = filedialog.askdirectory(title="Select folder")
        if not dir_path: return
        self.queue_files = app_utils.scan_directory(dir_path)
        self.lbl_source_status.config(
            text=f"Folder: {os.path.basename(dir_path)} ({len(self.queue_files)} files)" if self.queue_files else f"Folder: {os.path.basename(dir_path)} (no supported videos)")

    def _set_active_encoder(self, encoder: ffmpeg_engine.VideoEncoder) -> None:
        self._vcodec = encoder.name
        self._encoder_kind = encoder.kind
        self._decode_tech = ffmpeg_engine._decode_label_for(encoder, self.hwaccels)
        self._encode_tech = ffmpeg_engine._encode_label_for(encoder)

    def _refresh_progress_label(self) -> None:
        self.lbl_batch_progress.config(text=self._progress_prefix or "Ready")
        self.stat_tech.config(
            text=f"decode: {self._decode_tech}, encode: {self._encode_tech}" if self._decode_tech else "decode: -, encode: -")

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

    def _process_queue(self) -> None:
        if not self._ensure_tools_detected():
            self.after(0, self._batch_done)
            return
        total = len(self.queue_files)
        while self.current_index < total and not self.processor.cancel_requested:
            self._prepare_and_run_single(self.queue_files[self.current_index], self.current_index + 1, total)
            self.current_index += 1
        self.after(0, self._batch_done)

    def _prepare_and_run_single(self, input_file: str, current: int, total: int) -> None:
        codec_id = self.codec_var.get()
        quality = self._get_quality_opts()
        encoder = ffmpeg_engine.select_encoder(codec_id, quality, self.encoders, self.hwaccels)
        audio_opts = AUDIO_MAP[self.audio_var.get()]

        filters = []
        if self.res_var.get() in SCALE_MAP: filters.append(SCALE_MAP[self.res_var.get()])
        if self.fps_var.get() in FPS_MAP: filters.append(FPS_MAP[self.fps_var.get()])
        vf_filter = ",".join(filters)

        output_file = f"{os.path.splitext(input_file)[0]}_OPT_{encoder.codec_label}.mp4"
        self.vdur = hardware.get_duration(input_file)
        cmd = ffmpeg_engine.build_ffmpeg_cmd(input_file, output_file, encoder, audio_opts, vf_filter,
                                             self.quality_mode.get(), self.bitrate_var.get(), self.hwaccels)

        self._progress_prefix = f"File {current}/{total}: {os.path.basename(input_file)}"
        self._set_active_encoder(encoder)
        self.after(0, self._refresh_progress_label)
        self.after(0, lambda: self.progress_var.set(0.0))
        self.t_start = time.time()

        self._output_file, self._input_file, self._quality_value = output_file, input_file, quality
        self._log(f"Starting: {os.path.basename(input_file)}")

        rc = self.processor.run_ffmpeg_sync(cmd, lambda msg: self.after(0, self._log, msg), self._update_progress)

        if rc != 0 and not self.processor.cancel_requested and encoder.kind in {"nvenc", "amf"}:
            self._log(f"{encoder.kind.upper()} failed. Retrying with CPU encoder.")
            self.encoders.discard(encoder.name)
            cpu_enc = ffmpeg_engine.select_encoder(codec_id, quality, self.encoders, self.hwaccels)
            self._set_active_encoder(cpu_enc)
            self.after(0, self._refresh_progress_label)
            cmd = ffmpeg_engine.build_ffmpeg_cmd(input_file, output_file, cpu_enc, audio_opts, vf_filter,
                                                 self.quality_mode.get(), self.bitrate_var.get(), self.hwaccels)
            self.t_start = time.time()
            rc = self.processor.run_ffmpeg_sync(cmd, lambda msg: self.after(0, self._log, msg), self._update_progress)

        self.after(0, self._single_conversion_report, rc)

    def _update_progress(self, data: Dict[str, str]) -> None:
        try:
            out_time_us = int(data.get("out_time_us", 0) or 0)
        except ValueError:
            out_time_us = 0
        elapsed_s = out_time_us / 1_000_000
        pct = min(100.0, (elapsed_s / self.vdur * 100)) if self.vdur else 0.0
        self.progress_var.set(pct)

        self.stat_fps.config(text=f"fps: {data.get('fps', '-')}")
        self.stat_speed.config(text=f"speed: {data.get('speed', '-')}")
        self.stat_size.config(text=f"size: {hardware.bytes_to_mb(data.get('total_size', '-'))}")
        self.stat_eta.config(text=f"ETA: {app_utils.calculate_eta(pct, self.t_start)}")

    def _single_conversion_report(self, rc: int) -> None:
        if rc == 0:
            elapsed = int(time.time() - self.t_start)
            report = app_utils.generate_report_text(self._input_file, self._output_file, elapsed)
            self._log(report)
            self.progress_var.set(100.0)
        else:
            self._log("Cancelled" if self.processor.cancel_requested else f"Failed | Code: {rc}")
            self.progress_var.set(0.0)

    def _batch_done(self) -> None:
        self.btn_convert.config(state="normal")
        self.btn_cancel.config(state="disabled")
        self.btn_cancel.pack_forget()
        self.btn_select_file.config(state="normal")
        self.btn_select_dir.config(state="normal")
        self.lbl_batch_progress.config(
            text="Task cancelled." if self.processor.cancel_requested else "All files processed.")

    def _cancel_conversion(self) -> None:
        self.processor.terminate()

    def _ensure_tools_detected(self) -> bool:
        if self._tools_detected: return True
        self.encoders = hardware.get_ffmpeg_encoders()
        self.hwaccels = hardware.get_ffmpeg_hwaccels()
        self._tools_detected = True
        self._update_cq_hint()
        if not self.encoders:
            self._log("KRITINĖ KLAIDA: Nerastas 'ffmpeg.exe'")
            return False
        self._log(f"Detected video encoders: {', '.join(sorted(self.encoders))}")
        return True

    def _show_about_info(self) -> None:
        AboutWindow(self)

    def _log(self, text: str) -> None:
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
        self._log_widget = scrolledtext.ScrolledText(self._log_window, font=("Consolas", 8), relief="flat",
                                                     borderwidth=0)
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


if __name__ == "__main__":
    VideoConverterApp().mainloop()