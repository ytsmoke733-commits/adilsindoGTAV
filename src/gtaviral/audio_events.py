from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from gtaviral.config import Config, resolve_tool
from gtaviral.proc import ToolError, run

_START = re.compile(r"silence_start:\s*(-?[\d.]+)")
_END = re.compile(r"silence_end:\s*([\d.]+)")
_SILENT_DB = -120.0


@dataclass(frozen=True)
class AudioEvents:
    silences: tuple[tuple[float, float], ...]
    loud_moments: tuple[tuple[float, float], ...]


def parse_silencedetect(log: str, duration: float) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = []
    start: float | None = None
    for line in log.splitlines():
        if m := _START.search(line):
            start = max(0.0, float(m.group(1)))
        elif (m := _END.search(line)) and start is not None:
            out.append((start, float(m.group(1))))
            start = None
    if start is not None:
        out.append((start, duration))
    return out


def parse_rms(log: str) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = []
    t: float | None = None
    for line in log.splitlines():
        if "pts_time:" in line:
            t = float(line.split("pts_time:")[1].split()[0])
        elif "RMS_level=" in line and t is not None:
            raw = line.split("RMS_level=", 1)[1].strip()
            db = _SILENT_DB if raw in ("-inf", "inf", "nan") else float(raw)
            out.append((t, db))
            t = None
    return out


def find_loud_moments(
    rms: list[tuple[float, float]], delta_db: float = 9.0, min_gap: float = 3.0, limit: int = 20
) -> list[tuple[float, float]]:
    finite = sorted(db for _, db in rms if db > -100)
    if not finite:
        return []
    median = finite[len(finite) // 2]
    candidates = sorted(((t, db) for t, db in rms if db >= median + delta_db), key=lambda x: -x[1])
    chosen: list[tuple[float, float]] = []
    for t, db in candidates:
        if all(abs(t - c) >= min_gap for c, _ in chosen):
            chosen.append((t, db))
        if len(chosen) >= limit:
            break
    return chosen


def events_to_dict(e: AudioEvents) -> dict:
    return {"silences": [list(s) for s in e.silences], "loud_moments": [list(m) for m in e.loud_moments]}


def events_from_dict(d: dict) -> AudioEvents:
    return AudioEvents(
        silences=tuple((float(a), float(b)) for a, b in d["silences"]),
        loud_moments=tuple((float(a), float(b)) for a, b in d["loud_moments"]),
    )


def detect(cfg: Config, wav: Path, duration: float) -> AudioEvents:
    ffmpeg = resolve_tool(cfg.ffmpeg)
    if ffmpeg is None:
        raise ToolError("ffmpeg não encontrado — rode: gtaviral verificar")
    silence_log = run([ffmpeg, "-hide_banner", "-nostats", "-i", wav,
                       "-af", "silencedetect=noise=-35dB:d=0.4", "-f", "null", "-"]).stderr
    rms_log = run([ffmpeg, "-hide_banner", "-nostats", "-i", wav,
                   "-af", "asetnsamples=n=8000,astats=metadata=1:reset=1,"
                          "ametadata=print:key=lavfi.astats.Overall.RMS_level",
                   "-f", "null", "-"]).stderr
    return AudioEvents(
        silences=tuple(parse_silencedetect(silence_log, duration)),
        loud_moments=tuple(find_loud_moments(parse_rms(rms_log))),
    )
