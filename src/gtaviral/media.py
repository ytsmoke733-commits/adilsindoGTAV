from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from gtaviral.config import Config, resolve_tool
from gtaviral.proc import ToolError, run


class MediaError(RuntimeError):
    pass


@dataclass(frozen=True)
class MediaInfo:
    duration: float
    width: int
    height: int
    fps: float
    has_audio: bool
    video_codec: str


def _ratio(value: str) -> float:
    num, _, den = str(value).partition("/")
    try:
        n, d = float(num), float(den or 1)
    except ValueError:
        return 0.0
    return n / d if d else 0.0


def parse_probe(data: dict) -> MediaInfo:
    streams = data.get("streams", [])
    video = next(
        (s for s in streams
         if s.get("codec_type") == "video" and not s.get("disposition", {}).get("attached_pic")),
        None,
    )
    if video is None:
        raise MediaError("o arquivo não tem faixa de vídeo")
    width, height = int(video["width"]), int(video["height"])
    rotation = 0
    for side in video.get("side_data_list", []):
        if "rotation" in side:
            rotation = int(side["rotation"])
    if abs(rotation) % 180 == 90:
        width, height = height, width
    fps = _ratio(video.get("avg_frame_rate", "0/0")) or _ratio(video.get("r_frame_rate", "0/0"))
    duration = float(data.get("format", {}).get("duration") or video.get("duration") or 0)
    return MediaInfo(
        duration=duration,
        width=width,
        height=height,
        fps=fps,
        has_audio=any(s.get("codec_type") == "audio" for s in streams),
        video_codec=str(video.get("codec_name", "?")),
    )


def validate_size(size_bytes: int, max_file_gb: float) -> None:
    size_gb = size_bytes / 1024**3
    if size_gb > max_file_gb:
        raise MediaError(f"arquivo tem {size_gb:.1f} GB; o limite é {max_file_gb} GB (ajuste [limits] na config)")


def validate(info: MediaInfo, size_bytes: int, max_file_gb: float, max_duration_min: float) -> None:
    validate_size(size_bytes, max_file_gb)
    if info.duration <= 0:
        raise MediaError("a duração do vídeo não pôde ser lida")
    if info.duration > max_duration_min * 60:
        raise MediaError(
            f"vídeo tem {info.duration / 60:.1f} min; o limite é {max_duration_min:g} min (ajuste [limits] na config)"
        )
    if info.width < 320 or info.height < 240:
        raise MediaError(f"resolução {info.width}x{info.height} é baixa demais")


def _require(cfg_value: str, label: str) -> Path:
    path = resolve_tool(cfg_value)
    if path is None:
        raise ToolError(f"{label} não encontrado — rode: gtaviral verificar")
    return path


def probe(cfg: Config, path: Path) -> MediaInfo:
    ffprobe = _require(cfg.ffprobe, "ffprobe")
    try:
        out = run([ffprobe, "-v", "error", "-print_format", "json", "-show_format", "-show_streams", path]).stdout
    except ToolError as e:
        raise MediaError(f"não parece um vídeo válido: {path.name}\n{e}") from e
    return parse_probe(json.loads(out))


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def extract_audio(cfg: Config, src: Path, dst_wav: Path) -> None:
    ffmpeg = _require(cfg.ffmpeg, "ffmpeg")
    tmp = dst_wav.with_suffix(".tmp.wav")
    run([ffmpeg, "-hide_banner", "-nostats", "-y", "-i", src, "-vn", "-ac", "1", "-ar", "16000",
         "-c:a", "pcm_s16le", tmp])
    tmp.replace(dst_wav)
