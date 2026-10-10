from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Sequence

from gtaviral.audio_events import AudioEvents
from gtaviral.llm import LLM
from gtaviral.translate import TranslatedSegment

MIN_LEN = 8.0
MAX_LEN = 90.0

SYSTEM = """Você é editor de vídeos curtos de games para TikTok e Reels no Brasil.
Você recebe a transcrição traduzida de um vídeo, com tempos em segundos, e os momentos de pico de áudio.
Escolha os melhores trechos para virar clipes curtos.
Regras:
1. Cada clipe faz sentido sozinho: começa antes do acontecimento e termina depois da reação ou da conclusão.
2. Duração entre {min_len:.0f} e {max_len:.0f} segundos. Não force duração: use o tamanho natural do momento.
3. "motivo": uma frase dizendo o que acontece no trecho, baseada SÓ no que está na transcrição.
4. "gancho": uma frase curta para os primeiros segundos, fiel ao conteúdo, sem prometer o que não acontece.
5. No máximo {max_clips} clipes, do melhor para o pior, sem sobreposição."""

SCHEMA = {
    "type": "object",
    "properties": {
        "clipes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "inicio": {"type": "number"},
                    "fim": {"type": "number"},
                    "motivo": {"type": "string"},
                    "gancho": {"type": "string"},
                },
                "required": ["inicio", "fim", "motivo", "gancho"],
            },
        }
    },
    "required": ["clipes"],
}


@dataclass(frozen=True)
class ClipCandidate:
    index: int
    start: float
    end: float
    reason: str
    hook: str
    source: str


def _snap_start(segs: Sequence[TranslatedSegment], t: float) -> float:
    starts = [s.start for s in segs if s.start <= t + 1e-6]
    return max(starts) if starts else 0.0


def _snap_end(segs: Sequence[TranslatedSegment], t: float, duration: float) -> float:
    ends = [s.end for s in segs if s.end >= t - 1e-6]
    return min(ends) if ends else duration


def fit_span(
    segs: Sequence[TranslatedSegment], start: float, end: float, duration: float
) -> tuple[float, float] | None:
    s = max(0.0, _snap_start(segs, start))
    e = min(duration, _snap_end(segs, end, duration))
    if e - s > MAX_LEN:
        ends = [x.end for x in segs if s < x.end <= s + MAX_LEN]
        e = max(ends) if ends and max(ends) - s >= MIN_LEN else s + MAX_LEN
    if e - s < MIN_LEN:
        e = min(duration, _snap_end(segs, s + MIN_LEN, duration))
    if e - s < MIN_LEN:
        return None
    return round(s, 2), round(e, 2)


def _overlaps(a: tuple[float, float], b: tuple[float, float]) -> bool:
    inter = min(a[1], b[1]) - max(a[0], b[0])
    return inter > 0.5 * min(a[1] - a[0], b[1] - b[0])


def rule_candidates(
    segs: Sequence[TranslatedSegment], events: AudioEvents, duration: float, max_clips: int
) -> list[ClipCandidate]:
    picked: list[tuple[tuple[float, float], str]] = []
    for t, db in events.loud_moments:
        if len(picked) >= max_clips:
            break
        span = fit_span(segs, t - 8.0, t + 12.0, duration)
        if span and not any(_overlaps(span, p) for p, _ in picked):
            picked.append((span, f"pico de áudio em {t:.1f}s ({db:.0f} dB)"))
    if not picked:
        cursor = 0.0
        while len(picked) < max_clips:
            span = fit_span(segs, cursor, cursor + 30.0, duration)
            if span is None or span[1] <= cursor:
                break
            if not any(_overlaps(span, p) for p, _ in picked):
                picked.append((span, "trecho com fala contínua (nenhum pico de áudio detectado)"))
            cursor = span[1]
    return [ClipCandidate(i + 1, s, e, reason, "", "regras") for i, ((s, e), reason) in enumerate(picked)]


def llm_candidates(
    segs: Sequence[TranslatedSegment], events: AudioEvents, duration: float, llm: LLM, max_clips: int
) -> list[ClipCandidate]:
    lines = [f"Duração total: {duration:.1f}s", "", "Transcrição:"]
    lines += [f"[{s.start:.1f}-{s.end:.1f}] {s.text}" for s in segs]
    if events.loud_moments:
        lines += ["", "Picos de áudio (segundo):", ", ".join(f"{t:.1f}" for t, _ in sorted(events.loud_moments))]
    system = SYSTEM.format(min_len=MIN_LEN, max_len=MAX_LEN, max_clips=max_clips)
    reply = llm.chat_json(system, "\n".join(lines), SCHEMA)
    picked: list[tuple[tuple[float, float], str, str]] = []
    for item in reply.get("clipes", []):
        if len(picked) >= max_clips:
            break
        try:
            start, end = float(item["inicio"]), float(item["fim"])
        except (KeyError, TypeError, ValueError):
            continue
        if end <= start:
            continue
        span = fit_span(segs, start, end, duration)
        if span and not any(_overlaps(span, p) for p, _, _ in picked):
            picked.append((span, str(item.get("motivo", "")).strip(), str(item.get("gancho", "")).strip()))
    return [ClipCandidate(i + 1, s, e, reason, hook, "llm") for i, ((s, e), reason, hook) in enumerate(picked)]


def select_clips(
    segs: Sequence[TranslatedSegment], events: AudioEvents, duration: float, llm: LLM | None, max_clips: int
) -> list[ClipCandidate]:
    if llm is not None:
        found = llm_candidates(segs, events, duration, llm, max_clips)
        if found:
            return found
    return rule_candidates(segs, events, duration, max_clips)


def clips_to_dicts(clips: list[ClipCandidate]) -> list[dict]:
    return [asdict(c) for c in clips]


def clips_from_dicts(data: list[dict]) -> list[ClipCandidate]:
    return [ClipCandidate(**d) for d in data]
