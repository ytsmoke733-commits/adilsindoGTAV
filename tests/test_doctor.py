from pathlib import Path

from gtaviral.config import Config
from gtaviral.doctor import check_environment


def make_cfg(tmp_path: Path, **over) -> Config:
    base = dict(
        ffmpeg="nao-existe-ffmpeg-123",
        ffprobe="nao-existe-ffprobe-123",
        whisper_cli=str(tmp_path / "whisper-cli.exe"),
        whisper_model=tmp_path / "w.bin",
        llama_server=str(tmp_path / "llama-server.exe"),
        llm_model=tmp_path / "m.gguf",
        llm_port=8089,
        work_dir=tmp_path / "work",
        output_dir=tmp_path / "saida",
        max_file_gb=4.0,
        max_duration_min=20,
        subtitle_font="Arial Black",
        whisper_threads=8,
    )
    base.update(over)
    return Config(**base)


def test_everything_missing_gives_a_fix_for_each(tmp_path: Path):
    checks = check_environment(make_cfg(tmp_path))
    failing = [c for c in checks if not c.ok]
    names = {c.name for c in failing}
    assert {"ffmpeg", "ffprobe", "whisper-cli", "modelo do Whisper", "llama-server", "modelo do LLM"} <= names
    assert all(c.fix for c in failing)
    assert any("winget install Gyan.FFmpeg" in c.fix for c in failing)


def test_present_model_files_pass(tmp_path: Path):
    (tmp_path / "w.bin").write_bytes(b"x")
    (tmp_path / "m.gguf").write_bytes(b"x")
    checks = {c.name: c for c in check_environment(make_cfg(tmp_path))}
    assert checks["modelo do Whisper"].ok
    assert checks["modelo do LLM"].ok
