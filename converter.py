import glob
import os
import subprocess
import threading
import time
import tkinter as tk
from tkinter import filedialog, scrolledtext, ttk
from typing import Any, Dict, List, Optional, Tuple

import ffmpeg_engine
import hardware

# ── CONSTANTS ────────────────────────────────────────────────────────────────
VIDEO_EXTENSIONS: Tuple[str, ...] = ("*.mp4", "*.avi", "*.mkv", "*.m2ts", "*.ts")

AUDIO_MAP: Dict[str, List[str]] = {
    "0": ["-c:a", "aac", "-b:a", "96k", "-ac", "2", "-ar", "48000"],
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
FPS_MAP: Dict[str, str] = {"2": "fps=30", "3": "fps=24"}

STREAM_LABELS: Dict[str, str] = {
    "codec_name": "Codec",
    "width": "Width",
    "height": "Height",
    "r_frame_rate": "Frame rate",
    "bit_rate": "Bit rate",
    "duration": "Duration",
    "size": "File size",
}

# Compact light theme.
BG_MAIN = "#f6f7f9"
BG_PANEL = "#ffffff"
BG_FIELD = "#f9fafb"
COLOR_TEXT = "#172033"
COLOR_MUTED = "#7B7D87"
COLOR_BORDER = "#d9dee8"
COLOR_ACCENT = "#3b6ea8"
COLOR_SUCCESS = "#535456"
COLOR_DANGER = "#c71616"
COLOR_BUTTON = "#e7ebf0"
COLOR_BUTTON_ACTIVE = "#d8dee6"

FONT_UI = ("Segoe UI", 8)
FONT_UI_BOLD = ("Segoe UI", 8, "bold")
FONT_SMALL = ("Segoe UI", 7)
FONT_MONO = ("Consolas", 8)


class VideoConverterApp(tk.Tk):

    def __init__(self) -> None:
        super().__init__()
        self.title("Video Converter")
        self.resizable(False, False)
        self.configure(bg=BG_MAIN)

        self._set_icon()

        self.converting = False
        self.proc: Optional[subprocess.Popen[str]] = None
        self.t_start = 0.0
        self.vdur = 0

        self.queue_files: List[str] = []
        self.current_index = 0
        self.cancel_requested = False

        self._input_file = ""
        self._output_file = ""
        self._vcodec = ""
        self._encoder_kind = ""
        self._decode_tech = ""
        self._encode_tech = ""
        self._progress_prefix = ""
        self._quality_value = 0
        self._log_lines: List[str] = []
        self._log_window: Optional[tk.Toplevel] = None
        self._log_widget: Optional[scrolledtext.ScrolledText] = None
        self._tools_detected = False

        self.encoders: set = set()
        self.hwaccels: set = set()

        self._build_ui()

    def _set_icon(self) -> None:
        icon_path = hardware.find_resource("converter.ico")
        if not icon_path:
            return
        try:
            self.iconbitmap(icon_path)
        except tk.TclError:
            pass

    def _build_ui(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(".", font=FONT_UI)
        style.configure("TCombobox", padding=2)
        style.configure("TScale", background=BG_PANEL, troughcolor=COLOR_BORDER)
        style.configure("App.Horizontal.TProgressbar", troughcolor=COLOR_BORDER, background=COLOR_SUCCESS, thickness=7)

        self.columnconfigure(0, weight=1)
        pad = {"padx": 8, "pady": 4, "fill": "x"}

        sec1 = self._section("Source")
        sec1.pack(**pad)
        source_row = self._row(sec1)
        self.btn_select_file = self._button(source_row, "File", self._select_file)
        self.btn_select_file.pack(side="left", padx=(0, 5))
        self.btn_select_dir = self._button(source_row, "Folder", self._select_directory)
        self.btn_select_dir.pack(side="left", padx=(0, 8))
        self.lbl_source_status = self._label(source_row, "No source selected", COLOR_MUTED)
        self.lbl_source_status.pack(side="left", fill="x", expand=True)

        sec2 = self._section("Codec and quality")
        sec2.pack(**pad)

        codec_row = self._row(sec2)
        self.codec_var = tk.IntVar(value=1)
        self._radio(codec_row, "H.264 / AVC", 1).pack(side="left", padx=(0, 14))
        self._radio(codec_row, "H.265 / HEVC", 2).pack(side="left", padx=(0, 14))
        self.encoder_status = self._label(codec_row, "", COLOR_MUTED)
        self.encoder_status.pack(side="left", fill="x", expand=True)

        qmode_row = self._qmode_row = self._row(sec2)
        self.quality_mode = tk.StringVar(value="cq")
        tk.Radiobutton(
            qmode_row, text="CQ (quality)", variable=self.quality_mode, value="cq",
            bg=BG_PANEL, fg=COLOR_TEXT, selectcolor=BG_PANEL, activebackground=BG_PANEL,
            activeforeground=COLOR_TEXT, font=FONT_UI, command=self._on_quality_mode_change,
        ).pack(side="left", padx=(0, 14))
        tk.Radiobutton(
            qmode_row, text="Avg bitrate", variable=self.quality_mode, value="bitrate",
            bg=BG_PANEL, fg=COLOR_TEXT, selectcolor=BG_PANEL, activebackground=BG_PANEL,
            activeforeground=COLOR_TEXT, font=FONT_UI, command=self._on_quality_mode_change,
        ).pack(side="left")

        self.cq_row_frame = self._row(sec2)
        self.cq_hint = self._label(self.cq_row_frame, "", COLOR_MUTED, FONT_SMALL)
        self.cq_hint.pack(side="left", padx=(0, 8))
        self.cq_var = tk.IntVar(value=30)
        self.cq_scale = ttk.Scale(
            self.cq_row_frame, from_=18, to=40, variable=self.cq_var, orient="horizontal", length=210,
            command=lambda _e: self._update_cq_label(),
        )
        self.cq_scale.pack(side="left")
        self.cq_label = self._label(self.cq_row_frame, "30", COLOR_ACCENT, FONT_UI_BOLD)
        self.cq_label.pack(side="left", padx=(8, 0))
        self._update_cq_hint()

        self.br_row_frame = self._row(sec2)
        self._label(self.br_row_frame, "Video bitrate:", COLOR_MUTED, FONT_SMALL).pack(side="left", padx=(0, 6))
        self.bitrate_var = tk.IntVar(value=2000)
        self.bitrate_scale = ttk.Scale(
            self.br_row_frame, from_=500, to=8000, variable=self.bitrate_var, orient="horizontal", length=210,
            command=lambda _e: self._update_bitrate_label(),
        )
        self.bitrate_scale.pack(side="left")
        self.bitrate_label = self._label(self.br_row_frame, "2000 kbps", COLOR_ACCENT, FONT_UI_BOLD)
        self.bitrate_label.pack(side="left", padx=(8, 0))
        self.br_row_frame.pack_forget()

        sec3 = self._section("Output options")
        sec3.pack(**pad)
        combo_row = self._row(sec3)
        self.audio_var = tk.StringVar(value="1")
        self.res_var = tk.StringVar(value="1")
        self.fps_var = tk.StringVar(value="1")

        self._combo(combo_row, "Audio", ["AAC 96k", "AAC 128k", "AAC 192k", "Copy"], ["0", "1", "2", "3"],
                    self.audio_var, 1)
        self._combo(combo_row, "Resolution", ["Original", "1920x1080", "1280x720", "960x540", "720x480"],
                    ["1", "2", "3", "4", "5"], self.res_var, 0)
        self._combo(combo_row, "FPS", ["Original", "30 fps", "24 fps"], ["1", "2", "3"], self.fps_var, 0)

        sec4 = self._section("Progress")
        sec4.pack(**pad)
        self.lbl_batch_progress = self._label(sec4, "Ready", COLOR_TEXT, FONT_UI_BOLD)
        self.lbl_batch_progress.pack(anchor="w", pady=(0, 3))
        self.progress_var = tk.DoubleVar(value=0.0)
        self.progress_bar = ttk.Progressbar(sec4, variable=self.progress_var, maximum=100, length=420,
                                            style="App.Horizontal.TProgressbar")
        self.progress_bar.pack(fill="x", pady=(0, 3))

        stat_row = self._row(sec4)
        self.stat_fps = self._label(stat_row, "fps: -", COLOR_MUTED, FONT_SMALL)
        self.stat_speed = self._label(stat_row, "speed: -", COLOR_MUTED, FONT_SMALL)
        self.stat_size = self._label(stat_row, "size: -", COLOR_MUTED, FONT_SMALL)
        self.stat_eta = self._label(stat_row, "ETA: -", COLOR_MUTED, FONT_SMALL)
        for widget in (self.stat_fps, self.stat_speed, self.stat_size, self.stat_eta):
            widget.pack(side="left", padx=(0, 16))

        self.stat_tech = self._label(sec4, "decode: -, encode: -", COLOR_MUTED, FONT_SMALL)
        self.stat_tech.pack(anchor="w", pady=(0, 2))

        btn_row = tk.Frame(self, bg=BG_MAIN)
        btn_row.pack(padx=8, pady=(5, 8), fill="x")
        self.btn_convert = self._button(btn_row, "Start", self._start_batch_conversion, COLOR_SUCCESS, "#ffffff")
        self.btn_convert.pack(side="left")
        self.btn_cancel = self._button(btn_row, "Cancel", self._cancel_conversion, COLOR_DANGER, "#ffffff")
        self.btn_cancel.config(state="disabled")
        self.btn_log = self._button(btn_row, "Log", self._open_log_window)
        self.btn_log.pack(side="right")

    def _section(self, title: str) -> tk.Frame:
        frame = tk.Frame(self, bg=BG_PANEL, padx=8, pady=6, highlightbackground=COLOR_BORDER, highlightthickness=1)
        self._label(frame, title, COLOR_MUTED, FONT_UI_BOLD).pack(anchor="w", pady=(0, 4))
        return frame

    def _row(self, parent: tk.Widget) -> tk.Frame:
        row = tk.Frame(parent, bg=BG_PANEL)
        row.pack(fill="x", pady=2)
        return row

    def _label(self, parent: tk.Widget, text: str, color: str = COLOR_TEXT,
               font: Tuple[str, int] = FONT_UI) -> tk.Label:
        return tk.Label(parent, text=text, bg=parent["bg"], fg=color, font=font)

    def _button(self, parent: tk.Widget, text: str, command: Any, bg: str = COLOR_BUTTON,
                fg: str = COLOR_TEXT) -> tk.Button:
        return tk.Button(
            parent, text=text, bg=bg, fg=fg, relief="flat", font=FONT_UI_BOLD, padx=10, pady=3, cursor="hand2",
            activebackground=COLOR_BUTTON_ACTIVE, activeforeground=fg, command=command,
        )

    def _radio(self, parent: tk.Widget, text: str, value: int) -> tk.Radiobutton:
        return tk.Radiobutton(
            parent, text=text, variable=self.codec_var, value=value, bg=BG_PANEL, fg=COLOR_TEXT, selectcolor=BG_PANEL,
            activebackground=BG_PANEL, activeforeground=COLOR_TEXT, font=FONT_UI, command=self._update_cq_hint,
        )

    def _combo(self, parent: tk.Widget, label: str, labels: List[str], values: List[str], target: tk.StringVar,
               current: int) -> None:
        self._label(parent, f"{label}:", COLOR_MUTED, FONT_SMALL).pack(side="left", padx=(0, 3))
        combo = ttk.Combobox(parent, values=labels, state="readonly", width=11, font=FONT_UI)
        combo.current(current)
        combo.pack(side="left", padx=(0, 10))
        combo.bind("<<ComboboxSelected>>", lambda _e: target.set(values[combo.current()]))

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
        if self.codec_var.get() == 1:
            self.cq_hint.config(text="Quality: 28-32 for 1080p, 24-28 for 720p")
        else:
            self.cq_hint.config(text="Quality: 26-30 for 1080p, 22-26 for 720p")
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
        raw = self.bitrate_var.get()
        snapped = round(raw / 100) * 100
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
        if not dir_path:
            return
        norm_dir = os.path.normpath(dir_path)
        found_files: List[str] = []
        for ext in VIDEO_EXTENSIONS:
            found_files.extend(glob.glob(os.path.join(norm_dir, ext)))
        self.queue_files = sorted(found_files)
        if self.queue_files:
            self.lbl_source_status.config(text=f"Folder: {os.path.basename(norm_dir)} ({len(self.queue_files)} files)")
        else:
            self.lbl_source_status.config(text=f"Folder: {os.path.basename(norm_dir)} (no supported videos)")

    def _set_active_encoder(self, encoder: ffmpeg_engine.VideoEncoder) -> None:
        self._vcodec = encoder.name
        self._encoder_kind = encoder.kind
        # SUTVARKYTA: Kreipiamės tiesiai į teisingas ffmpeg_engine funkcijas
        self._decode_tech = ffmpeg_engine._decode_label_for(encoder, self.hwaccels)
        self._encode_tech = ffmpeg_engine._encode_label_for(encoder)

    def _refresh_progress_label(self) -> None:
        tech_text = f"decode: {self._decode_tech}, encode: {self._encode_tech}" if self._decode_tech else ""
        self.lbl_batch_progress.config(text=self._progress_prefix or "Ready")
        self.stat_tech.config(text=tech_text or "decode: -, encode: -")

    def _start_batch_conversion(self) -> None:
        if not self.queue_files:
            self._log("Warning: no file or folder selected.")
            self._open_log_window()
            return

        self.converting = True
        self.cancel_requested = False
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
        while self.current_index < total and not self.cancel_requested:
            self._prepare_and_run_single(self.queue_files[self.current_index], self.current_index + 1, total)
            self.current_index += 1
        self.after(0, self._batch_done)

    def _prepare_and_run_single(self, input_file: str, current: int, total: int) -> None:
        codec_id = self.codec_var.get()
        quality = self._get_quality_opts()
        encoder = ffmpeg_engine.select_encoder(codec_id, quality, self.encoders, self.hwaccels)
        audio_opts = AUDIO_MAP[self.audio_var.get()]

        filters: List[str] = []
        if self.res_var.get() in SCALE_MAP:
            filters.append(SCALE_MAP[self.res_var.get()])
        if self.fps_var.get() in FPS_MAP:
            filters.append(FPS_MAP[self.fps_var.get()])
        vf_filter = ",".join(filters)

        base = os.path.splitext(input_file)[0]
        output_file = f"{base}_OPT_{encoder.codec_label}.mp4"

        self.vdur = hardware.get_duration(input_file)
        cmd = ffmpeg_engine.build_ffmpeg_cmd(
            input_file, output_file, encoder, audio_opts, vf_filter,
            self.quality_mode.get(), self.bitrate_var.get(), self.hwaccels
        )

        filename = os.path.basename(input_file)
        self._progress_prefix = f"File {current}/{total}: {filename}"
        self._set_active_encoder(encoder)
        self.after(0, self._refresh_progress_label)
        self.after(0, lambda: self.progress_var.set(0.0))
        self.t_start = time.time()

        self._output_file = output_file
        self._input_file = input_file
        self._quality_value = quality

        self._log(f"Starting: {filename}")
        self._log(f"Decode selected: {self._decode_tech}")
        self._log(f"Encoder selected: {encoder.name} ({encoder.kind})")
        self._run_ffmpeg_with_fallback(cmd, codec_id, audio_opts, vf_filter, output_file)

    def _run_ffmpeg_with_fallback(self, cmd: List[str], codec_id: int, audio_opts: List[str], vf_filter: str,
                                  output_file: str) -> None:
        rc = self._run_ffmpeg_sync(cmd)
        if rc == 0 or self.cancel_requested or self._encoder_kind not in {"nvenc", "amf"}:
            self._report_on_ui(rc)
            return

        failed_kind = self._encoder_kind.upper()
        self._log(f"{failed_kind} failed on this machine. Retrying with CPU encoder.")
        self.encoders.discard(self._vcodec)
        cpu_encoder = ffmpeg_engine.select_encoder(codec_id, self._quality_value, self.encoders, self.hwaccels)
        self._set_active_encoder(cpu_encoder)
        self.after(0, self._refresh_progress_label)
        retry_cmd = ffmpeg_engine.build_ffmpeg_cmd(
            self._input_file, output_file, cpu_encoder, audio_opts, vf_filter,
            self.quality_mode.get(), self.bitrate_var.get(), self.hwaccels
        )
        self.t_start = time.time()
        rc = self._run_ffmpeg_sync(retry_cmd)
        self._report_on_ui(rc)

    def _run_ffmpeg_sync(self, cmd: List[str]) -> int:
        try:
            self.proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                encoding="utf-8", errors="ignore", bufsize=1, **hardware.hidden_subprocess_kwargs(),
            )
            current: Dict[str, str] = {}
            if self.proc.stdout:
                for line in self.proc.stdout:
                    line = line.strip()
                    if "=" in line:
                        key, value = line.split("=", 1)
                        current[key] = value
                        if key == "progress":
                            self.after(0, self._update_progress, dict(current))
                            current = {}
                    elif line:
                        self.after(0, self._log, line)
            self.proc.wait()
            return int(self.proc.returncode or 0)
        except Exception as exc:
            self.after(0, self._log, f"Error running FFmpeg: {exc}")
            return 1

    def _report_on_ui(self, rc: int) -> None:
        event = threading.Event()
        self.after(0, lambda: [self._single_conversion_report(rc), event.set()])
        event.wait()

    def _update_progress(self, data: Dict[str, str]) -> None:
        try:
            out_time_us = int(data.get("out_time_us", 0) or 0)
        except ValueError:
            out_time_us = 0

        elapsed_s = out_time_us / 1_000_000
        pct = min(100.0, (elapsed_s / self.vdur * 100)) if self.vdur else 0.0
        self.progress_var.set(pct)

        fps = data.get("fps", "-")
        speed = data.get("speed", "-")
        size = data.get("total_size", "-")

        wall_elapsed = time.time() - self.t_start
        if pct > 0:
            eta_s = max(0, int(wall_elapsed / (pct / 100) - wall_elapsed))
            eta = f"{eta_s // 60}m {eta_s % 60}s"
        else:
            eta = "-"

        self.stat_fps.config(text=f"fps: {fps}")
        self.stat_speed.config(text=f"speed: {speed}")
        self.stat_size.config(text=f"size: {hardware.bytes_to_mb(size)}")
        self.stat_eta.config(text=f"ETA: {eta}")

    def _single_conversion_report(self, rc: int) -> None:
        elapsed = int(time.time() - self.t_start)
        minutes, seconds = elapsed // 60, elapsed % 60
        speed_x = round(self.vdur / elapsed, 1) if elapsed > 0 else 0.0

        if rc == 0:
            self._log("")
            self._log("=" * 56)
            self._log("CONVERSION REPORT")
            self._log("=" * 56)
            self._log(f"Source  : {self._input_file}")
            self._log(f"Output  : {self._output_file}")

            mode_str = f"Bitrate: {self.bitrate_var.get()} kbps" if self.quality_mode.get() == "bitrate" else f"Quality: {self._quality_value}"
            self._log(f"Encoder : {self._vcodec} ({self._encoder_kind}) {mode_str}")

            src_size = os.path.getsize(self._input_file) if os.path.isfile(self._input_file) else 0
            out_size = os.path.getsize(self._output_file) if os.path.isfile(self._output_file) else 0
            self._log(f"Source size : {hardware.bytes_to_mb(src_size)} ({src_size:,} bytes)")
            self._log(f"Output size : {hardware.bytes_to_mb(out_size)} ({out_size:,} bytes)")
            if src_size:
                self._log(f"Reduction   : {(1 - out_size / src_size) * 100:.1f}%")
            self._log(f"Time        : {minutes} min {seconds} sec")
            self._log(f"Avg speed   : x{speed_x}")

            info = hardware.get_ffprobe_info(self._output_file)
            self._log("")
            self._log("--- Stream info ---")
            seen: set = set()
            for key, label in STREAM_LABELS.items():
                if key in info and key not in seen:
                    value = info[key]
                    if key == "bit_rate":
                        value = hardware.format_bitrate(value)
                    elif key == "size":
                        value = hardware.bytes_to_mb(value)
                    elif key == "duration":
                        try:
                            d = int(float(value))
                            value = f"{d // 3600}h {(d % 3600) // 60}m {d % 60}s"
                        except ValueError:
                            pass
                    self._log(f"{label:<12}: {value}")
                    seen.add(key)
            self._log("=" * 56)
            self.progress_var.set(100.0)
        else:
            if self.cancel_requested:
                self._log(f"Conversion cancelled: {os.path.basename(self._input_file)}")
            else:
                self._log(f"Conversion failed: {os.path.basename(self._input_file)} | Exit code: {rc}")
            self.progress_var.set(0.0)

    def _batch_done(self) -> None:
        self.converting = False
        self.btn_convert.config(state="normal")
        self.btn_cancel.config(state="disabled")
        self.btn_cancel.pack_forget()
        self.btn_select_file.config(state="normal")
        self.btn_select_dir.config(state="normal")
        if self.cancel_requested:
            self.lbl_batch_progress.config(text="Task cancelled.")
        else:
            self.lbl_batch_progress.config(text="All files processed.")

    def _cancel_conversion(self) -> None:
        self.cancel_requested = True
        if self.proc and self.converting:
            self.proc.terminate()

    def _ensure_tools_detected(self) -> bool:
        if self._tools_detected:
            return True
        self.after(0, self.lbl_batch_progress.config, {"text": "Checking FFmpeg..."})
        self.encoders = hardware.get_ffmpeg_encoders()
        self.hwaccels = hardware.get_ffmpeg_hwaccels()
        self._tools_detected = True
        self.after(0, self._update_cq_hint)

        if not self.encoders:
            self._log("=" * 60)
            self._log("KRITINĖ KLAIDA: Nerastas 'ffmpeg.exe' arba nepavyko nuskaityti FFmpeg enkoderių.")
            self._log("-" * 60)
            self._log("KAIP SUTVARKYTI:")
            self._log("1. Atsisiųskite FFmpeg iš oficialios svetainės: https://www.gyan.dev/ffmpeg/builds/")
            self._log("   (Rekomenduojama rinktis: ffmpeg-release-full-shared.7z)")
            self._log("2. Išpakuokite atsisiųstą archyvą.")
            self._log("3. Nukopijuokite failus iš 'bin' aplanko ir įkelkite juos:")
            self._log(f"   TIESIAI ŠALIA ŠIOS PROGRAMOS ({hardware.app_dir()})")
            self._log("   Reikalingi failai: ffmpeg.exe, ffprobe.exe ir visi šalia esantys .dll failai.")
            self._log("4. Iš nujojo paleiskite šią programą.")
            self._log("=" * 60)
            self.after(0, self._open_log_window)
            return False

        self._log_available_hardware()
        return True

    def _log_available_hardware(self) -> None:
        if not self.encoders:
            self._log("Warning: ffmpeg encoders could not be detected.")
            return
        self._log(f"Detected video encoders: {', '.join(sorted(self.encoders))}")
        if self.hwaccels:
            self._log(f"Detected hardware accelerators: {', '.join(sorted(self.hwaccels))}")

    def _log(self, text: str, color: Optional[str] = None) -> None:
        del color
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
        self._log_window.configure(bg=BG_MAIN)
        self._log_window.geometry("720x360")
        self._log_widget = scrolledtext.ScrolledText(
            self._log_window, bg=BG_FIELD, fg=COLOR_TEXT, font=FONT_MONO, relief="flat", borderwidth=0, state="normal",
            wrap="word",
        )
        self._log_widget.pack(fill="both", expand=True, padx=8, pady=8)
        self._log_widget.insert("end", "\n".join(self._log_lines))
        if self._log_lines:
            self._log_widget.insert("end", "\n")
        self._log_widget.see("end")
        self._log_widget.config(state="disabled")
        self._log_window.protocol("WM_DELETE_WINDOW", self._close_log_window)

    def _close_log_window(self) -> None:
        if self._log_window:
            self._log_window.destroy()
        self._log_window = None
        self._log_widget = None


if __name__ == "__main__":
    app = VideoConverterApp()
    app.mainloop()