from __future__ import annotations

import subprocess
from pathlib import Path


class ToolError(RuntimeError):
    """Uma ferramenta externa (ffmpeg, whisper-cli...) terminou com erro."""


def run(cmd: list, cwd: Path | None = None, timeout: float | None = None) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        [str(c) for c in cmd],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    if proc.returncode != 0:
        tail = "\n".join(proc.stderr.strip().splitlines()[-15:])
        raise ToolError(f"{Path(str(cmd[0])).name} saiu com código {proc.returncode}:\n{tail}")
    return proc
