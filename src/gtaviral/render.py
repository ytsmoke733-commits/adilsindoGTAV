from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from gtaviral.config import Config, resolve_tool
from gtaviral.media import MediaInfo, probe
from gtaviral.proc import ToolError, run

FRAMINGS = ("corte", "desfoque")


class RenderError(RuntimeError):
    pass


@dataclass(frozen=True)
class Profile:
    name: str
    width: int
    height: int
    crf: int = 18


PROFILES = {
    "1080": Profile("1080", 1080, 1920),
    "1440": Profile("1440", 1440, 2560),
}


def _even(x: float) -> int:
    v = int(round(x))
    return v - (v % 2)


def crop_chain(src_w: int, src_h: int, profile: Profile, crop_x: float) -> str:
    if not 0.0 <= crop_x <= 1.0:
        raise ValueError("a posição do corte deve estar entre 0 e 1")
    target = profile.width / profile.height
    if src_w / src_h > target:
        cw, ch = _even(src_h * target), _even(src_h)
        x, y = _even((src_w - cw) * crop_x), 0
    else:
        cw, ch = _even(src_w), _even(src_w / target)
        x, y = 0, _even((src_h - ch) / 2)
    return f"crop={cw}:{ch}:{x}:{y},scale={profile.width}:{profile.height}:flags=lanczos,setsar=1"


def blur_chain(profile: Profile) -> str:
    w, h = profile.width, profile.height
    return (
        "split=2[bg][fg];"
        f"[bg]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},"
        "gblur=sigma=40,eq=brightness=-0.08[bgb];"
        f"[fg]scale={w}:{h}:force_original_aspect_ratio=decrease:force_divisible_by=2:flags=lanczos[fgs];"
        "[bgb][fgs]overlay=(W-w)/2:(H-h)/2,setsar=1"
    )


def build_filtergraph(info: MediaInfo, profile: Profile, framing: str, crop_x: float, subs_file: str | None) -> str:
    if framing == "corte":
        chain = crop_chain(info.width, info.height, profile, crop_x)
    elif framing == "desfoque":
        chain = blur_chain(profile)
    else:
        raise ValueError(f"enquadramento desconhecido: {framing} (use {', '.join(FRAMINGS)})")
    if subs_file:
        chain += f",subtitles={subs_file}"
    return f"[0:v]{chain}[v]"


def build_command(
    ffmpeg: str, src: Path, info: MediaInfo, start: float, end: float, profile: Profile, framing: str,
    crop_x: float, subs_file: str | None, out_path: Path, normalize_audio: bool = True,
) -> list[str]:
    cmd = [
        ffmpeg, "-hide_banner", "-nostats", "-y",
        "-ss", f"{start:.3f}", "-t", f"{end - start:.3f}", "-i", str(src),
        "-filter_complex", build_filtergraph(info, profile, framing, crop_x, subs_file),
        "-map", "[v]",
        "-c:v", "libx264", "-preset", "slow", "-crf", str(profile.crf), "-profile:v", "high", "-pix_fmt", "yuv420p",
    ]
    if info.has_audio:
        cmd += ["-map", "0:a:0", "-c:a", "aac", "-b:a", "192k", "-ar", "48000"]
        if normalize_audio:
            cmd += ["-af", "loudnorm=I=-14:TP=-1.5:LRA=11"]
    cmd += ["-movflags", "+faststart", str(out_path)]
    return cmd


def render_clip(
    cfg: Config, src: Path, info: MediaInfo, start: float, end: float, profile: Profile, framing: str,
    crop_x: float, subs_file: str | None, out_path: Path,
) -> None:
    ffmpeg = resolve_tool(cfg.ffmpeg)
    if ffmpeg is None:
        raise ToolError("ffmpeg não encontrado — rode: gtaviral verificar")
    src = Path(src).resolve()
    out_path = Path(out_path).resolve()
    tmp = out_path.with_name(out_path.stem + ".tmp.mp4")
    try:
        run(build_command(str(Path(ffmpeg).resolve()), src, info, start, end, profile, framing, crop_x, subs_file, tmp),
            cwd=out_path.parent)
        tmp.replace(out_path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def verify_output(cfg: Config, out_path: Path, profile: Profile, expected_fps: float) -> MediaInfo:
    if not out_path.is_file() or out_path.stat().st_size == 0:
        raise RenderError(f"o FFmpeg não gerou {out_path}")
    got = probe(cfg, out_path)
    if (got.width, got.height) != (profile.width, profile.height):
        raise RenderError(f"a saída saiu {got.width}x{got.height}; o esperado era {profile.width}x{profile.height}")
    if got.video_codec != "h264":
        raise RenderError(f"a saída saiu em {got.video_codec}; o esperado era h264")
    if expected_fps > 0 and abs(got.fps - expected_fps) > 0.5:
        raise RenderError(f"o fps mudou: origem {expected_fps:.2f}, saída {got.fps:.2f}")
    return got
