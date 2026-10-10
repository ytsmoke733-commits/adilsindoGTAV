from pathlib import Path

import pytest

from gtaviral.config import ConfigError, load_config, resolve_tool

MINIMAL = """
[tools]
whisper_cli = "tools/whisper/whisper-cli.exe"
whisper_model = "tools/models/w.bin"
llama_server = "tools/llama/llama-server.exe"
llm_model = "tools/models/m.gguf"
"""


def test_load_config_resolves_relative_paths_against_config_dir(tmp_path: Path):
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text(MINIMAL, encoding="utf-8")
    cfg = load_config(cfg_file)
    assert cfg.whisper_model == (tmp_path / "tools/models/w.bin").resolve()
    assert cfg.whisper_cli == str((tmp_path / "tools/whisper/whisper-cli.exe").resolve())
    assert cfg.ffmpeg == "ffmpeg"  # nome solto continua nome, para ser achado no PATH
    assert cfg.llm_port == 8089
    assert cfg.work_dir == (tmp_path / "work").resolve()
    assert cfg.max_duration_min == 20


def test_load_config_missing_file_explains_what_to_do(tmp_path: Path):
    with pytest.raises(ConfigError, match="config.example.toml"):
        load_config(tmp_path / "config.toml")


def test_load_config_missing_required_field(tmp_path: Path):
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text("[tools]\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="whisper_cli"):
        load_config(cfg_file)


def test_resolve_tool_finds_file_and_rejects_unknown(tmp_path: Path):
    exe = tmp_path / "x.exe"
    exe.write_bytes(b"")
    assert resolve_tool(str(exe)) == exe
    assert resolve_tool("nao-existe-gtaviral-123") is None
