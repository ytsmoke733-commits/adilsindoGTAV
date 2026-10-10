from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from gtaviral.config import Config, resolve_tool
from gtaviral.proc import ToolError, run

_SPECIAL = re.compile(r"^\s*(\[_[A-Z_0-9]+\]|<\|.*\|>)\s*$")


@dataclass(frozen=True)
class Word:
    text: str
    start: float
    end: float
    prob: float


@dataclass(frozen=True)
class Segment:
    id: int
    start: float
    end: float
    text: str
    words: tuple[Word, ...]


@dataclass(frozen=True)
class Transcript:
    language: str
    segments: tuple[Segment, ...]


def _words_from_tokens(tokens: list[dict]) -> list[Word]:
    words: list[Word] = []
    text, start, end, prob = "", 0.0, 0.0, 1.0
    for tok in tokens:
        piece = tok.get("text", "")
        if not piece or _SPECIAL.match(piece) or "offsets" not in tok:
            continue
        t0, t1 = tok["offsets"]["from"] / 1000, tok["offsets"]["to"] / 1000
        p = float(tok.get("p", 1.0))
        if piece.startswith(" ") or not text:
            if text.strip():
                words.append(Word(text.strip(), start, end, prob))
            text, start, end, prob = piece, t0, t1, p
        else:
            text += piece
            end = t1
            prob = min(prob, p)
    if text.strip():
        words.append(Word(text.strip(), start, end, prob))
    return words


def parse_whisper_json(data: dict) -> Transcript:
    language = data.get("result", {}).get("language") or "?"
    segments: list[Segment] = []
    for item in data.get("transcription", []):
        text = item.get("text", "").strip()
        if not text:
            continue
        segments.append(Segment(
            id=len(segments),
            start=item["offsets"]["from"] / 1000,
            end=item["offsets"]["to"] / 1000,
            text=text,
            words=tuple(_words_from_tokens(item.get("tokens", []))),
        ))
    return Transcript(language=language, segments=tuple(segments))


def transcript_to_dict(t: Transcript) -> dict:
    return asdict(t)


def transcript_from_dict(d: dict) -> Transcript:
    return Transcript(
        language=d["language"],
        segments=tuple(
            Segment(s["id"], s["start"], s["end"], s["text"], tuple(Word(**w) for w in s["words"]))
            for s in d["segments"]
        ),
    )


def transcribe(cfg: Config, wav: Path, out_prefix: Path, language: str = "auto") -> Transcript:
    cli = resolve_tool(cfg.whisper_cli)
    if cli is None:
        raise ToolError("whisper-cli não encontrado — rode: gtaviral verificar")
    if not cfg.whisper_model.is_file():
        raise ToolError(f"modelo do Whisper não encontrado: {cfg.whisper_model} — rode: gtaviral verificar")
    run([cli, "-m", cfg.whisper_model, "-f", wav, "-l", language, "-ojf", "-of", out_prefix,
         "-np", "-t", str(cfg.whisper_threads)])
    json_path = out_prefix.parent / (out_prefix.name + ".json")
    raw = json_path.read_text(encoding="utf-8", errors="replace")
    return parse_whisper_json(json.loads(raw, strict=False))
