from __future__ import annotations

import shutil
import tomllib
from dataclasses import dataclass
from pathlib import Path


class ConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class Config:
    ffmpeg: str
    ffprobe: str
    whisper_cli: str
    whisper_model: Path
    llama_server: str
    llm_model: Path
    llm_port: int
    work_dir: Path
    output_dir: Path
    max_file_gb: float
    max_duration_min: float
    subtitle_font: str
    whisper_threads: int


def _abs(base: Path, value: str) -> Path:
    p = Path(value)
    return p if p.is_absolute() else (base / p).resolve()


def _tool(base: Path, value: str) -> str:
    """Nome solto (ex. 'ffmpeg') fica como está para ser achado no PATH; caminho vira absoluto."""
    if "/" in value or "\\" in value:
        return str(_abs(base, value))
    return value


def load_config(path: Path) -> Config:
    if not path.is_file():
        raise ConfigError(f"config não encontrada: {path} (copie config.example.toml para config.toml)")
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    base = path.resolve().parent
    tools = data.get("tools", {})
    paths = data.get("paths", {})
    limits = data.get("limits", {})
    try:
        return Config(
            ffmpeg=_tool(base, tools.get("ffmpeg", "ffmpeg")),
            ffprobe=_tool(base, tools.get("ffprobe", "ffprobe")),
            whisper_cli=_tool(base, tools["whisper_cli"]),
            whisper_model=_abs(base, tools["whisper_model"]),
            llama_server=_tool(base, tools["llama_server"]),
            llm_model=_abs(base, tools["llm_model"]),
            llm_port=int(data.get("llm", {}).get("port", 8089)),
            work_dir=_abs(base, paths.get("work_dir", "work")),
            output_dir=_abs(base, paths.get("output_dir", "saida")),
            max_file_gb=float(limits.get("max_file_gb", 4.0)),
            max_duration_min=float(limits.get("max_duration_min", 20)),
            subtitle_font=str(data.get("subtitles", {}).get("font", "Arial Black")),
            whisper_threads=int(tools.get("whisper_threads", 8)),
        )
    except KeyError as e:
        raise ConfigError(f"campo obrigatório ausente em [tools]: {e.args[0]}") from e


def resolve_tool(value: str) -> Path | None:
    p = Path(value)
    if p.is_file():
        return p
    found = shutil.which(value)
    return Path(found) if found else None
