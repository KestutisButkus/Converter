from typing import List
from hardware import FFMPEG


class VideoEncoder:
    """Mažas adapteris enkoderio parametrams saugoti."""
    def __init__(self, name: str, codec_label: str, kind: str, options: List[str]) -> None:
        self.name = name
        self.codec_label = codec_label
        self.kind = kind
        self.options = options


def select_encoder(codec_id: int, quality: int, encoders: set, hwaccels: set) -> VideoEncoder:
    is_h264 = codec_id == 1
    nvenc = "h264_nvenc" if is_h264 else "hevc_nvenc"
    amf = "h264_amf" if is_h264 else "hevc_amf"
    cpu = "libx264" if is_h264 else "libx265"
    fallback = "mpeg4"

    if nvenc in encoders and ("cuda" in hwaccels or not hwaccels):
        preset = "p4" if is_h264 else "p1"
        return VideoEncoder(
            nvenc, "h264" if is_h264 else "hevc", "nvenc",
            ["-preset", preset, "-rc", "vbr", "-cq", str(quality)],
        )

    if amf in encoders:
        return VideoEncoder(
            amf, "h264" if is_h264 else "hevc", "amf",
            ["-quality", "balanced", "-rc", "cqp",
             "-qp_i", str(quality), "-qp_p", str(quality)],
        )

    if cpu in encoders:
        preset = "medium" if is_h264 else "fast"
        return VideoEncoder(
            cpu, "h264" if is_h264 else "hevc", "cpu",
            ["-preset", preset, "-crf", str(quality)],
        )

    return VideoEncoder(fallback, "h264", "fallback", ["-q:v", "5"])


def hwaccel_for(encoder: VideoEncoder, hwaccels: set) -> str:
    if encoder.kind == "nvenc" and "cuda" in hwaccels:
        return "cuda"
    if encoder.kind == "amf":
        if "d3d11va" in hwaccels:
            return "d3d11va"
        if "dxva2" in hwaccels:
            return "dxva2"
    return ""


def build_quality_options(encoder: VideoEncoder, quality_mode: str, bitrate_val: int) -> List[str]:
    if quality_mode == "bitrate":
        if encoder.kind == "nvenc":
            max_rate = bitrate_val * 4
            buf_size = int(max_rate * 1.5)
            return [
                "-b:v", f"{bitrate_val}k",
                "-maxrate:v", f"{max_rate}k",
                "-bufsize:v", f"{buf_size}k"
            ]

        if encoder.kind == "amf":
            max_rate = bitrate_val * 4
            return [
                "-rc", "peaking_vbr",
                "-b:v", f"{bitrate_val}k",
                "-maxrate:v", f"{max_rate}k"
            ]

        if encoder.kind == "cpu":
            max_rate = bitrate_val * 4
            buf_size = int(max_rate * 1.5)
            return [
                "-b:v", f"{bitrate_val}k",
                "-maxrate:v", f"{max_rate}k",
                "-bufsize:v", f"{buf_size}k"
            ]

        return ["-b:v", f"{bitrate_val}k"]

    return encoder.options


def build_ffmpeg_cmd(
    input_file: str,
    output_file: str,
    encoder: VideoEncoder,
    audio_opts: List[str],
    vf_filter: str,
    quality_mode: str,
    bitrate_val: int,
    hwaccels: set,
) -> List[str]:
    cmd = [FFMPEG, "-y"]

    hwaccel = hwaccel_for(encoder, hwaccels)
    is_cuda_output = False

    if hwaccel == "cuda":
        cmd += ["-hwaccel", "cuda"]
        cmd += ["-hwaccel_output_format", "cuda"]
        is_cuda_output = True
    elif hwaccel:
        cmd += ["-hwaccel", hwaccel]

    cmd += ["-i", input_file, "-map", "0:v:0", "-map", "0:a:0?", "-sn"]

    if is_cuda_output:
        if vf_filter:
            cuda_filter = vf_filter.replace("scale=", "scale_cuda=")
            cmd += ["-vf", f"{cuda_filter},scale_cuda=format=yuv420p"]
        else:
            cmd += ["-vf", "scale_cuda=format=yuv420p"]
    elif vf_filter:
        cmd += ["-vf", vf_filter]

    cmd += ["-c:v", encoder.name]

    quality_opts = build_quality_options(encoder, quality_mode, bitrate_val)
    if quality_mode == "bitrate":
        preset_opts: List[str] = []
        it = iter(encoder.options)
        for flag in it:
            if flag == "-preset":
                preset_opts += [flag, next(it, "")]
            elif flag in {"-rc", "-cq", "-crf", "-qp_i", "-qp_p", "-qp_b", "-quality"}:
                next(it, "")
        cmd += preset_opts + quality_opts
    else:
        cmd += quality_opts

    if not is_cuda_output:
        cmd += ["-pix_fmt", "yuv420p"]

    cmd += audio_opts
    cmd += ["-avoid_negative_ts", "make_zero", "-progress", "pipe:1", "-nostats", output_file]
    return cmd


def _decode_label_for(encoder: VideoEncoder, hwaccels: set) -> str:
    hwaccel = hwaccel_for(encoder, hwaccels)
    if encoder.kind == "nvenc" and hwaccel == "cuda":
        return "GPU nvdec"
    if encoder.kind == "amf" and hwaccel:
        return f"GPU {hwaccel}"
    return "CPU"


def _encode_label_for(encoder: VideoEncoder) -> str:
    if encoder.kind == "nvenc":
        return "GPU nvenc"
    if encoder.kind == "amf":
        return "GPU amf"
    if encoder.kind == "cpu":
        return f"CPU {encoder.name}"
    return encoder.name