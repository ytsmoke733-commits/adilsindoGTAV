from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from gtaviral.config import Config, load_config, resolve_tool

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures"

SPEECH_TEXT = (
    "Bro, look at this car. It just flew over the bridge and landed on the police station. "
    "This is the craziest thing I have seen in GTA Six. "
    "The cops did not even react. They just kept walking like nothing happened. "
    "I swear this game is going to be insane when it comes out."
)


@pytest.fixture(scope="session")
def real_cfg() -> Config:
    cfg_path = ROOT / "config.toml"
    if not cfg_path.is_file():
        pytest.skip("config.toml ausente na raiz (necessário para testes de integração)")
    cfg = load_config(cfg_path)
    if resolve_tool(cfg.ffmpeg) is None:
        pytest.skip("ffmpeg não instalado")
    return cfg


@pytest.fixture(scope="session")
def speech_wav(tmp_path_factory) -> Path:
    out = tmp_path_factory.mktemp("tts") / "speech.wav"
    subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(FIXTURES / "tts.ps1"),
         "-Out", str(out), "-Text", SPEECH_TEXT],
        check=True,
    )
    return out


@pytest.fixture(scope="session")
def speech_video(real_cfg: Config, speech_wav: Path, tmp_path_factory) -> Path:
    out = tmp_path_factory.mktemp("video") / "speech.mp4"
    subprocess.run(
        [str(resolve_tool(real_cfg.ffmpeg)), "-hide_banner", "-y",
         "-f", "lavfi", "-i", "testsrc2=size=1920x1080:rate=60",
         "-i", str(speech_wav), "-shortest",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(out)],
        check=True, capture_output=True,
    )
    return out
