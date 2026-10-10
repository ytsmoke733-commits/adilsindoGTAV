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


_VAD_INFO = re.compile(
    r"vad_segment_info: orig_start: ([\d.]+), orig_end: ([\d.]+), vad_start: ([\d.]+), vad_end: ([\d.]+)")

VadMap = list[tuple[float, float, float, float]]  # (orig_start, orig_end, vad_start, vad_end)


def parse_vad_map(log: str) -> VadMap:
    """Trechos de fala que o VAD do whisper.cpp manteve, lidos do log (sem -np)."""
    return [tuple(float(x) for x in m.groups()) for m in _VAD_INFO.finditer(log)]  # type: ignore[misc]


def unmap_vad(t: float, vad_map: VadMap, kind: str) -> float:
    """Com VAD, o whisper.cpp devolve o tempo das palavras no audio compactado (so a fala);
    isto volta para o tempo do audio original. No vao entre trechos (o Whisper estica o fim da
    ultima palavra ate la), inicio vai para o proximo trecho e fim para o anterior."""
    for i, (o0, o1, v0, v1) in enumerate(vad_map):
        if t < v0:
            if i == 0 or kind == "start":
                return o0
            return vad_map[i - 1][1]
        if t <= v1:
            return round(o0 + (t - v0), 3)
    return vad_map[-1][1]


def parse_whisper_json(data: dict, vad_map: VadMap | None = None) -> Transcript:
    language = data.get("result", {}).get("language") or "?"
    segments: list[Segment] = []
    for item in data.get("transcription", []):
        text = item.get("text", "").strip()
        if not text:
            continue
        words = tuple(_words_from_tokens(item.get("tokens", [])))
        if vad_map:
            # palavra "solta" no vao (inicio e fim no mesmo vao) fica colada no fim da fala anterior
            words = tuple(
                Word(w.text, min(unmap_vad(w.start, vad_map, "start"), unmap_vad(w.end, vad_map, "end")),
                     unmap_vad(w.end, vad_map, "end"), w.prob)
                for w in words)
        start, end = item["offsets"]["from"] / 1000, item["offsets"]["to"] / 1000
        # Os limites do segmento no Whisper sao folgados; o tempo por palavra e mais justo.
        if words and words[-1].end > words[0].start:
            start, end = words[0].start, words[-1].end
        segments.append(Segment(id=len(segments), start=start, end=end, text=text, words=words))
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
    cmd = [cli, "-m", cfg.whisper_model, "-f", wav, "-l", language, "-ojf", "-of", out_prefix,
           "-t", str(cfg.whisper_threads)]  # sem -np: o log registra GPU/Vulkan e o mapa do VAD
    if cfg.whisper_vad_model is not None:
        if not cfg.whisper_vad_model.is_file():
            raise ToolError(
                f"modelo VAD do Whisper não encontrado: {cfg.whisper_vad_model} — rode: gtaviral verificar")
        cmd += ["--vad", "-vm", cfg.whisper_vad_model]
    log_path = out_prefix.parent / "whisper.log"
    try:
        proc = run(cmd)
    except ToolError as e:
        log_path.write_text(str(e), encoding="utf-8")
        raise
    log_path.write_text(f"{proc.stderr}\n--- stdout ---\n{proc.stdout}", encoding="utf-8")
    json_path = out_prefix.parent / (out_prefix.name + ".json")
    raw = json_path.read_text(encoding="utf-8", errors="replace")
    return parse_whisper_json(json.loads(raw, strict=False), parse_vad_map(proc.stderr))
