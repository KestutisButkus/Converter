import glob
import os
import time
from typing import Dict, List, Tuple
import hardware

VIDEO_EXTENSIONS: Tuple[str, ...] = ("*.mp4", "*.avi", "*.mkv", "*.m2ts", "*.ts")
STREAM_LABELS: Dict[str, str] = {
    "codec_name": "Codec", "width": "Width", "height": "Height",
    "r_frame_rate": "Frame rate", "bit_rate": "Bit rate", "duration": "Duration",
    "size": "File size"
}


def scan_directory(dir_path: str) -> List[str]:
    norm_dir = os.path.normpath(dir_path)
    found = []
    for ext in VIDEO_EXTENSIONS:
        found.extend(glob.glob(os.path.join(norm_dir, ext)))
    return sorted(found)


def calculate_eta(pct: float, t_start: float) -> str:
    if pct <= 0:
        return "-"
    wall = time.time() - t_start
    eta_s = int(wall / (pct / 100) - wall)
    return f"{eta_s // 60}m {eta_s % 60}s"


def generate_report_text(input_file: str, output_file: str, elapsed_s: int) -> str:
    text = f"\nCONVERSION REPORT\nTime: {elapsed_s // 60} min {elapsed_s % 60} sec\n"
    src_size = os.path.getsize(input_file) if os.path.isfile(input_file) else 0
    out_size = os.path.getsize(output_file) if os.path.isfile(output_file) else 0
    text += f"Reduction: {(1 - out_size / src_size) * 100:.1f}%\n" if src_size else "Reduction: -\n"

    info = hardware.get_ffprobe_info(output_file)
    for k, label in STREAM_LABELS.items():
        if k in info:
            val = hardware.format_bitrate(info[k]) if k == "bit_rate" else info[k]
            text += f"{label}: {val}\n"
    return text.strip()