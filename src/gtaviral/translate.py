from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from gtaviral.llm import LLM
from gtaviral.transcribe import Segment, Transcript

CPS = 17.0

GLOSSARY = (
    "GTA", "GTA 6", "GTA VI", "Rockstar", "Rockstar Games", "Vice City", "Leonida",
    "Lucia", "Jason", "Los Santos", "Grove Street", "NPC",
)

SYSTEM = """Você traduz legendas de vídeos curtos de games para o público gamer brasileiro.
Regras:
1. Português do Brasil natural e informal, como um brasileiro falaria. Gíria gamer quando couber.
2. Preserve o sentido, o humor e o tom. Gíria em inglês vira a gíria brasileira equivalente, não a tradução literal.
3. NÃO traduza nomes próprios nem estes termos: {glossary}.
4. Cada item tem "max_caracteres": a tradução TEM que caber nesse limite. Condense sem perder o sentido.
5. Não acrescente nada que não foi dito. Não explique a piada.
6. Devolva exatamente um item para cada "id" recebido, com o mesmo id.
7. "destaques": de 0 a 2 palavras da SUA tradução que merecem cor na legenda, escritas exatamente como aparecem no texto. Só palavras de impacto."""

SCHEMA = {
    "type": "object",
    "properties": {
        "itens": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "texto": {"type": "string"},
                    "destaques": {"type": "array", "items": {"type": "string"}, "maxItems": 2},
                },
                "required": ["id", "texto", "destaques"],
            },
        }
    },
    "required": ["itens"],
}


class TranslationError(RuntimeError):
    pass


@dataclass(frozen=True)
class TranslatedSegment:
    id: int
    start: float
    end: float
    source: str
    text: str
    highlights: tuple[str, ...] = ()


def max_chars_for(start: float, end: float) -> int:
    return int(min(80, max(12, (end - start) * CPS)))


def _user_prompt(batch: list[Segment], context: list[Segment]) -> str:
    lines: list[str] = []
    if context:
        lines.append("Contexto (frases anteriores, NÃO traduza):")
        lines += [f"- {s.text}" for s in context]
        lines.append("")
    items = [{"id": s.id, "max_caracteres": max_chars_for(s.start, s.end), "texto": s.text} for s in batch]
    lines.append("Traduza:")
    lines.append(json.dumps(items, ensure_ascii=False))
    return "\n".join(lines)


def _clean_highlights(text: str, highlights: list) -> tuple[str, ...]:
    low = text.lower()
    out = []
    for h in highlights[:2]:
        h = str(h).strip()
        if h and h.lower() in low:
            out.append(h)
    return tuple(out)


def translate(
    transcript: Transcript, llm: LLM | None, glossary: tuple[str, ...] = GLOSSARY, batch_size: int = 12
) -> list[TranslatedSegment]:
    segs = list(transcript.segments)
    if transcript.language == "pt":
        return [TranslatedSegment(s.id, s.start, s.end, s.text, s.text) for s in segs]
    if llm is None:
        raise TranslationError(
            f"o vídeo está em '{transcript.language}' e a tradução precisa do LLM local (rode sem --sem-llm)"
        )
    system = SYSTEM.format(glossary=", ".join(glossary))
    out: list[TranslatedSegment] = []
    for i in range(0, len(segs), batch_size):
        batch = segs[i:i + batch_size]
        context = segs[max(0, i - 3):i]
        wanted = {s.id for s in batch}
        got: dict[int, dict] = {}
        for _attempt in range(2):
            pending = [s for s in batch if s.id not in got]
            reply = llm.chat_json(system, _user_prompt(pending, context), SCHEMA)
            for item in reply.get("itens", []):
                if isinstance(item, dict) and item.get("id") in wanted and str(item.get("texto", "")).strip():
                    got[item["id"]] = item
            if wanted <= got.keys():
                break
        missing = sorted(wanted - got.keys())
        if missing:
            raise TranslationError(f"o modelo não devolveu tradução para os segmentos {missing}")
        for s in batch:
            text = str(got[s.id]["texto"]).strip()
            out.append(TranslatedSegment(
                s.id, s.start, s.end, s.text, text, _clean_highlights(text, list(got[s.id].get("destaques", [])))
            ))
    return out


def translated_to_dicts(segs: list[TranslatedSegment]) -> list[dict]:
    return [asdict(s) for s in segs]


def translated_from_dicts(data: list[dict]) -> list[TranslatedSegment]:
    return [TranslatedSegment(**{**d, "highlights": tuple(d["highlights"])}) for d in data]
