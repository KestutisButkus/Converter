import os
import shutil
import subprocess
from typing import Any, Dict, Optional, Sequence


def app_dir() -> str:
    import sys
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def find_resource(*parts: str) -> Optional[str]:
    import sys
    base_dirs = [
        app_dir(),
        getattr(sys, "_MEIPASS", ""),
        os.path.dirname(os.path.abspath(__file__)),
        os.getcwd(),
    ]
    seen: set = set()
    for base_dir in base_dirs:
        if not base_dir:
            continue
        path = os.path.join(base_dir, *parts)
        if path in seen:
            continue
        seen.add(path)
        if os.path.isfile(path):
            return path
    return None


def find_tool(name: str) -> Optional[str]:
    # 1. Pirmiausia tikriname, ar failas yra tiesiai šalia programos (nešiojama versija)
    local_path = find_resource(f"{name}.exe")
    if local_path and os.path.isfile(local_path):
        return local_path

    # 2. SUTVARKYTA: Jei vietinio failo nėra, saugiai tikriname sisteminį PATH aplinką per shutil.which
    # Tai nesukelia Smart App Control įtarimų, nes neleidžia jokio fono proceso.
    system_path = shutil.which(name)
    if system_path:
        return system_path

    return None


# Konstantos dabar tvarkingai nustatomos pagal rastus kelius (vietinius arba sisteminius)
FFMPEG: Optional[str] = find_tool("ffmpeg")
FFPROBE: Optional[str] = find_tool("ffprobe")


def hidden_subprocess_kwargs() -> Dict[str, Any]:
    if os.name != "nt":
        return {}
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE
    kwargs: Dict[str, Any] = {"startupinfo": startupinfo}
    if hasattr(subprocess, "CREATE_NO_WINDOW"):
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    return kwargs


def run_tool(args: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        errors="ignore",
        check=False,
        **hidden_subprocess_kwargs(),
    )


def get_ffmpeg_encoders() -> set:
    if not FFMPEG:
        return set()
    result = run_tool([FFMPEG, "-hide_banner", "-encoders"])
    if result.returncode != 0:
        return set()
    encoders = set()
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0].startswith("V"):
            encoders.add(parts[1])
    return encoders


def get_ffmpeg_hwaccels() -> set:
    if not FFMPEG:
        return set()
    result = run_tool([FFMPEG, "-hide_banner", "-hwaccels"])
    if result.returncode != 0:
        return set()
    return {
        line.strip().lower()
        for line in result.stdout.splitlines()
        if line.strip()
    }


def get_duration(filepath: str) -> int:
    if not FFPROBE:
        return 0
    try:
        result = subprocess.run(
            [
                FFPROBE, "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                filepath,
            ],
            capture_output=True,
            text=True,
            errors="ignore",
            check=True,
            **hidden_subprocess_kwargs(),
        )
        stdout_clean = result.stdout.strip()
        return int(float(stdout_clean.split(".")[0])) if stdout_clean else 0
    except (subprocess.SubprocessError, ValueError, IndexError):
        return 0


def get_ffprobe_info(filepath: str) -> Dict[str, str]:
    if not FFPROBE:
        return {}
    try:
        result = subprocess.run(
            [
                FFPROBE, "-v", "error",
                "-show_entries", "format=duration,bit_rate,size",
                "-show_entries", "stream=codec_name,codec_type,width,height,r_frame_rate,bit_rate",
                "-of", "default=noprint_wrappers=1",
                filepath,
            ],
            capture_output=True,
            text=True,
            errors="ignore",
            check=True,
            **hidden_subprocess_kwargs(),
        )
        info: Dict[str, str] = {}
        for line in result.stdout.strip().splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                info[key] = value
        return info
    except subprocess.SubprocessError:
        return {}


def bytes_to_mb(value: Any) -> str:
    try:
        return f"{int(value) / 1_048_576:.1f} MB"
    except (ValueError, TypeError):
        return str(value)


def format_bitrate(value: Any) -> str:
    try:
        return f"{int(value) // 1000} kb/s"
    except (ValueError, TypeError):
        return str(value)