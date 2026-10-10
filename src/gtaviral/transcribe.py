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


EPS = 0.02  # s; os tempos do mapa vem do log com 2 casas decimais


def parse_vad_map(log: str) -> VadMap:
    """Trechos de fala que o VAD do whisper.cpp manteve, lidos do log (sem -np)."""
    return [tuple(float(x) for x in m.groups()) for m in _VAD_INFO.finditer(log)]  # type: ignore[misc]


def unmap_vad(t: float, vad_map: VadMap, kind: str) -> float:
    """Com VAD, o whisper.cpp devolve o tempo das palavras no audio compactado (so a fala);
    isto volta para o tempo do audio original. No vao entre trechos (o Whisper estica o fim da
    ultima palavra ate la), inicio vai para o proximo trecho e fim para o anterior."""
    for i, (o0, o1, v0, v1) in enumerate(vad_map):
        # fim colado no inicio do trecho seguinte pertence ao anterior (EPS: o log arredonda a 0,01 s)
        glued_end = kind == "end" and i > 0 and abs(t - v0) <= EPS
        if t < v0 - EPS or glued_end:
            if i == 0 or kind == "start":
                return o0
            return vad_map[i - 1][1]
        if t <= v1 + EPS:
            return round(min(max(o0 + (t - v0), o0), o1), 3)
    return vad_map[-1][1]


def _unmap_word(w: Word, vad_map: VadMap) -> Word:
    start = unmap_vad(w.start, vad_map, "start")
    end = unmap_vad(w.end, vad_map, "end")
    chunk_end = next((o1 for o0, o1, _, _ in vad_map if start <= o1 + EPS), end)
    end = min(end, chunk_end)
    return Word(w.text, min(start, end), end, w.prob)


MAX_WORD_GAP = 2.0  # pausa entre palavras (s) a partir da qual o segmento e dividido


def _split_on_pauses(words: tuple[Word, ...]) -> list[list[Word]]:
    pieces: list[list[Word]] = [[]]
    for w in words:
        if pieces[-1] and w.start - pieces[-1][-1].end > MAX_WORD_GAP:
            pieces.append([])
        pieces[-1].append(w)
    return pieces


def parse_whisper_json(data: dict, vad_map: VadMap | None = None) -> Transcript:
    language = data.get("result", {}).get("language") or "?"
    segments: list[Segment] = []
    for item in data.get("transcription", []):
        text = item.get("text", "").strip()
        if not text:
            continue
        words = tuple(_words_from_tokens(item.get("tokens", [])))
        if vad_map:
            # Com VAD o tempo das palavras vem do audio compactado: volta ao original. Uma palavra nao
            # atravessa dois trechos de fala (o fim e limitado ao fim do trecho do inicio), e uma palavra
            # solta no vao fica colada no fim da fala anterior.
            words = tuple(_unmap_word(w, vad_map) for w in words)
        start, end = item["offsets"]["from"] / 1000, item["offsets"]["to"] / 1000
        pieces = _split_on_pauses(words)
        if len(pieces) > 1:
            for piece in pieces:
                p_start, p_end = piece[0].start, piece[-1].end
                if p_end <= p_start:  # trecho degenerado: duracao minima de 0,2 s
                    p_end = p_start + 0.2
                segments.append(Segment(len(segments), p_start, p_end,
                                        " ".join(w.text for w in piece), tuple(piece)))
            continue
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
    vad_map = parse_vad_map(proc.stderr) if cfg.whisper_vad_model is not None else []
    transcript = parse_whisper_json(json.loads(raw, strict=False), vad_map)
    if cfg.whisper_vad_model is not None and not vad_map and transcript.segments:
        raise ToolError(
            "mapa do VAD não encontrado no log do whisper-cli (versão incompatível?); "
            f"veja {log_path} ou desligue o VAD na config")
    return transcript
