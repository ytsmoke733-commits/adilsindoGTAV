from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from gtaviral.config import Config, resolve_tool
from gtaviral.proc import ToolError, run

FIX_FFMPEG = "winget install Gyan.FFmpeg (depois abra um terminal novo)"
FIX_WHISPER = r"rode scripts\build_whisper_vulkan.bat (ou o plano B do README)"
FIX_TOOLS = r"rode: powershell -ExecutionPolicy Bypass -File scripts\get_tools.ps1"


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str
    fix: str = ""


def _tool_check(name: str, value: str, fix: str) -> tuple[Check, Path | None]:
    path = resolve_tool(value)
    if path is None:
        return Check(name, False, f"não encontrado: {value}", fix), None
    return Check(name, True, str(path)), path


def _file_check(name: str, path: Path, fix: str) -> Check:
    if path.is_file():
        return Check(name, True, f"{path} ({path.stat().st_size / 1024**2:.0f} MB)")
    return Check(name, False, f"não encontrado: {path}", fix)


def check_environment(cfg: Config) -> list[Check]:
    checks: list[Check] = []
    ffmpeg_check, ffmpeg = _tool_check("ffmpeg", cfg.ffmpeg, FIX_FFMPEG)
    checks.append(ffmpeg_check)
    if ffmpeg is not None:
        try:
            filters = run([ffmpeg, "-hide_banner", "-filters"]).stdout
            has_ass = any(line.split()[1:2] == ["subtitles"] for line in filters.splitlines())
        except (ToolError, OSError):
            has_ass = False
        checks.append(Check(
            "ffmpeg com libass",
            has_ass,
            "filtro 'subtitles' presente" if has_ass else "filtro 'subtitles' ausente (legenda embutida não funciona)",
            "" if has_ass else FIX_FFMPEG,
        ))
    checks.append(_tool_check("ffprobe", cfg.ffprobe, FIX_FFMPEG)[0])
    checks.append(_tool_check("whisper-cli", cfg.whisper_cli, FIX_WHISPER)[0])
    checks.append(_file_check("modelo do Whisper", cfg.whisper_model, FIX_TOOLS))
    if cfg.whisper_vad_model is not None:
        checks.append(_file_check("modelo VAD do Whisper", cfg.whisper_vad_model, FIX_TOOLS))
    checks.append(_tool_check("llama-server", cfg.llama_server, FIX_TOOLS)[0])
    checks.append(_file_check("modelo do LLM", cfg.llm_model, FIX_TOOLS))
    return checks
