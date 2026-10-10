from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Sequence

from gtaviral.translate import TranslatedSegment

STYLES = ("simples", "dinamica", "destaque")
MAX_LINE = 20
CHUNK_MAX = {"simples": 2 * MAX_LINE, "destaque": 2 * MAX_LINE, "dinamica": 18}
HIGHLIGHT_ASS = "&H00E5FF&"  # amarelo #FFE500 (ASS usa BGR)
WHITE_ASS = "&HFFFFFF&"
POP_IN = r"{\fscx85\fscy85\t(0,120,\fscx100\fscy100)}"

_TIME = re.compile(r"(\d+):(\d{2}):(\d{2})[,.](\d{3})")


@dataclass(frozen=True)
class Cue:
    start: float
    end: float
    text: str
    highlights: tuple[str, ...] = ()


def wrap_lines(text: str, max_line: int = MAX_LINE) -> list[str]:
    lines: list[str] = []
    cur = ""
    for word in text.split():
        if cur and len(cur) + 1 + len(word) > max_line:
            lines.append(cur)
            cur = word
        else:
            cur = f"{cur} {word}" if cur else word
    if cur:
        lines.append(cur)
    return lines


def split_text(text: str, max_chars: int) -> list[str]:
    chunks: list[str] = []
    cur = ""
    for word in text.split():
        candidate = f"{cur} {word}" if cur else word
        if cur and len(candidate) > max_chars:
            chunks.append(cur)
            cur = word
        else:
            cur = candidate
        if cur.endswith((".", "!", "?")) and len(cur) >= max_chars * 0.25:
            chunks.append(cur)
            cur = ""
    if cur:
        chunks.append(cur)
    return chunks


def build_cues(
    segments: Sequence[TranslatedSegment], clip_start: float, clip_end: float, style: str
) -> list[Cue]:
    if style not in STYLES:
        raise ValueError(f"estilo desconhecido: {style} (use {', '.join(STYLES)})")
    cues: list[Cue] = []
    for seg in segments:
        s, e = max(seg.start, clip_start), min(seg.end, clip_end)
        if e - s < 0.2:
            continue
        chunks = split_text(seg.text, CHUNK_MAX[style])
        total = sum(len(c) for c in chunks) or 1
        t = s
        for chunk in chunks:
            dur = (e - s) * len(chunk) / total
            highs = () if style == "simples" else tuple(h for h in seg.highlights if h.lower() in chunk.lower())
            cues.append(Cue(round(t - clip_start, 3), round(t + dur - clip_start, 3), chunk, highs))
            t += dur
    return cues


def _hmsms(t: float) -> tuple[int, int, int, int]:
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return h, m, s, ms


def fmt_srt_time(t: float) -> str:
    h, m, s, ms = _hmsms(t)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def fmt_vtt_time(t: float) -> str:
    return fmt_srt_time(t).replace(",", ".")


def fmt_ass_time(t: float) -> str:
    cs = int(round(t * 100))
    h, cs = divmod(cs, 360_000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def cps_warnings(cues: Sequence[Cue], limit: float = 20.0) -> list[str]:
    out = []
    for i, c in enumerate(cues, 1):
        cps = len(c.text) / max(c.end - c.start, 0.001)
        if cps > limit:
            out.append(f"legenda {i} ({fmt_srt_time(c.start)}): {cps:.0f} caracteres/s — rápida demais, encurte o texto")
    return out


def _mark(text: str, highlights: Sequence[str], before: str, after: str) -> str:
    for h in sorted(set(highlights), key=len, reverse=True):
        text = re.sub(
            rf"(?<!\w)({re.escape(h)})(?!\w)",
            lambda m: before + m.group(1) + after,
            text,
            count=1,
            flags=re.IGNORECASE,
        )
    return text


def to_srt(cues: Sequence[Cue], mark: bool = False) -> str:
    blocks = []
    for i, c in enumerate(cues, 1):
        lines = wrap_lines(c.text)
        if mark:
            lines = [_mark(line, c.highlights, "*", "*") for line in lines]
        blocks.append(f"{i}\n{fmt_srt_time(c.start)} --> {fmt_srt_time(c.end)}\n" + "\n".join(lines))
    return "\n\n".join(blocks) + "\n"


def _parse_time(value: str) -> float:
    m = _TIME.search(value)
    if not m:
        raise ValueError(f"tempo inválido na legenda: {value.strip()!r}")
    h, mi, s, ms = map(int, m.groups())
    return h * 3600 + mi * 60 + s + ms / 1000


def parse_srt(text: str) -> list[Cue]:
    cues: list[Cue] = []
    normalized = text.lstrip("﻿").replace("\r\n", "\n").strip()
    for block in re.split(r"\n\s*\n", normalized):
        lines = [line for line in block.split("\n") if line.strip()]
        idx = next((i for i, line in enumerate(lines) if "-->" in line), None)
        if idx is None:
            continue
        a, b = lines[idx].split("-->")
        body = " ".join(line.strip() for line in lines[idx + 1:])
        highlights = tuple(re.findall(r"\*([^*]+)\*", body))
        clean = body.replace("*", "")
        if clean:
            cues.append(Cue(_parse_time(a), _parse_time(b), clean, highlights))
    return cues


def to_vtt(cues: Sequence[Cue]) -> str:
    blocks = [f"{fmt_vtt_time(c.start)} --> {fmt_vtt_time(c.end)}\n" + "\n".join(wrap_lines(c.text)) for c in cues]
    return "WEBVTT\n\n" + "\n\n".join(blocks) + "\n"


def _ass_escape(text: str) -> str:
    return text.replace("\\", "/").replace("{", "(").replace("}", ")")


def to_ass(cues: Sequence[Cue], width: int, height: int, font: str, style: str) -> str:
    size = round(height * 0.034)
    outline = max(2, round(height * 0.0042))
    margin_l, margin_r, margin_v = round(width * 0.08), round(width * 0.15), round(height * 0.28)
    header = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        f"PlayResX: {width}\n"
        f"PlayResY: {height}\n"
        "WrapStyle: 0\n"
        "ScaledBorderAndShadow: yes\n"
        "\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Main,{font},{size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,"
        f"{outline},0,2,{margin_l},{margin_r},{margin_v},1\n"
        "\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )
    events = []
    for c in cues:
        lines = [_ass_escape(line) for line in wrap_lines(c.text)]
        if style != "simples":
            lines = [_mark(line, c.highlights, "{\\c" + HIGHLIGHT_ASS + "}", "{\\c" + WHITE_ASS + "}") for line in lines]
        text = r"\N".join(lines)
        if style == "dinamica":
            text = POP_IN + text
        events.append(f"Dialogue: 0,{fmt_ass_time(c.start)},{fmt_ass_time(c.end)},Main,,0,0,0,,{text}")
    return header + "\n".join(events) + "\n"
