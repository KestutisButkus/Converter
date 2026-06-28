import subprocess
from typing import List, Optional, Any

import hardware


class BatchProcessor:

    def __init__(self) -> None:
        self.proc: Optional[subprocess.Popen[str]] = None
        self.cancel_requested: bool = False

    def run_ffmpeg_sync(self, cmd: List[str], log_callback: Any, progress_callback: Any) -> int:
        try:
            self.proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                encoding="utf-8", errors="ignore", bufsize=1, **hardware.hidden_subprocess_kwargs(),
            )
            current_data = {}
            if self.proc.stdout:
                for line in self.proc.stdout:
                    line = line.strip()
                    if "=" in line:
                        key, value = line.split("=", 1)
                        current_data[key] = value
                        if key == "progress":
                            progress_callback(current_data)
                            current_data = {}
                    elif line:
                        log_callback(line)
            self.proc.wait()
            return int(self.proc.returncode or 0)
        except Exception as exc:
            log_callback(f"Error running FFmpeg: {exc}")
            return 1

    def terminate(self) -> None:
        self.cancel_requested = True
        if self.proc:
            self.proc.terminate()
