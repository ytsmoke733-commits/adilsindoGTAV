from __future__ import annotations

from gtaviral.llm import LLM, LLMError

SYSTEM = """Você escreve textos para vídeos curtos de GTA no TikTok e no Instagram Reels, para o público gamer brasileiro.
Tom: brasileiro, natural, direto, de quem joga. Nada de frase genérica de marketing.
Regras:
1. Use SÓ o que acontece no trecho descrito. Não invente acontecimento, número, data ou novidade.
2. Se o trecho for rumor ou teoria, deixe isso claro no texto.
3. Títulos sem clickbait mentiroso e sem promessa falsa.
4. Hashtags relevantes ao conteúdo, de 4 a 8, nenhuma sem relação com o vídeo.
5. Não repita a fórmula destes títulos usados recentemente: {recentes}"""

_TEXT = {"type": "string"}


def _list(n_min: int, n_max: int) -> dict:
    return {"type": "array", "items": _TEXT, "minItems": n_min, "maxItems": n_max}


SCHEMA = {
    "type": "object",
    "properties": {
        "ganchos": _list(5, 5),
        "titulos": _list(3, 3),
        "legenda_instagram": _TEXT,
        "descricao_tiktok": _TEXT,
        "hashtags": _list(4, 8),
        "pergunta": _TEXT,
        "texto_capa": _TEXT,
        "justificativa": _TEXT,
    },
    "required": ["ganchos", "titulos", "legenda_instagram", "descricao_tiktok", "hashtags", "pergunta",
                 "texto_capa", "justificativa"],
}


def generate_copy(llm: LLM, clip_text: str, reason: str, recent_titles: list[str]) -> dict:
    system = SYSTEM.format(recentes="; ".join(recent_titles[-20:]) or "nenhum")
    user = f"O que acontece no trecho: {reason}\n\nFalas do trecho (já traduzidas):\n{clip_text}"
    data = llm.chat_json(system, user, SCHEMA)
    missing = [k for k in SCHEMA["required"] if k not in data]
    if missing:
        raise LLMError(f"textos incompletos, faltou: {', '.join(missing)}")
    _check_types(data)
    data["hashtags"] = _clean_hashtags(data["hashtags"])
    return data


_LISTAS = ("ganchos", "titulos", "hashtags")


def _check_types(data: dict) -> None:
    for campo in SCHEMA["required"]:
        valor = data[campo]
        if campo in _LISTAS:
            ok = isinstance(valor, list) and all(isinstance(x, str) for x in valor)
        else:
            ok = isinstance(valor, str)
        if not ok:
            raise LLMError(f"textos em formato inesperado: {campo}")


def _clean_hashtags(raw: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for h in raw:
        tag = h.strip().replace(" ", "")
        tag = tag if tag.startswith("#") else f"#{tag}"
        tag = tag.rstrip(".,;:!?")
        if not tag.strip("#") or tag.lower() in seen:
            continue
        seen.add(tag.lower())
        out.append(tag)
    return out[:8]


def format_copy(data: dict, fonte: str, licenca: str) -> str:
    def numbered(items: list[str]) -> str:
        return "\n".join(f"{i}. {x}" for i, x in enumerate(items, 1))

    parts = [
        "GANCHOS (primeiros segundos)", numbered(data["ganchos"]), "",
        "TÍTULOS", numbered(data["titulos"]), "",
        "LEGENDA DO INSTAGRAM", data["legenda_instagram"], "",
        "DESCRIÇÃO DO TIKTOK", data["descricao_tiktok"], "",
        "HASHTAGS", " ".join(data["hashtags"]), "",
        "PERGUNTA PARA OS COMENTÁRIOS", data["pergunta"], "",
        "TEXTO DA CAPA", data["texto_capa"], "",
        "POR QUE ESSA ESTRATÉGIA", data["justificativa"], "",
        "FONTE E AUTORIZAÇÃO (confira antes de publicar)",
        f"Fonte: {fonte}",
        f"Licença/autorização: {licenca}",
        "",
        "Textos escritos por IA local: revise antes de postar.",
    ]
    return "\n".join(parts) + "\n"
