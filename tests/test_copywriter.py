import pytest

from gtaviral.copywriter import SCHEMA, format_copy, generate_copy
from gtaviral.llm import LLMError
from tests.fakes import FakeLLM

GOOD = {
    "ganchos": ["a", "b", "c", "d", "e"],
    "titulos": ["t1", "t2", "t3"],
    "legenda_instagram": "li",
    "descricao_tiktok": "dt",
    "hashtags": ["gta6", "#GTAVI", "npc engraçado", "#viral"],
    "pergunta": "p?",
    "texto_capa": "capa",
    "justificativa": "j",
}


def test_generate_copy_normalizes_hashtags_and_passes_context():
    llm = FakeLLM([dict(GOOD)])
    out = generate_copy(llm, "Mano, olha esse carro.", "carro voa", recent_titles=["Título velho"])
    assert out["hashtags"] == ["#gta6", "#GTAVI", "#npcengraçado", "#viral"]
    system, user, schema = llm.calls[0]
    assert "Título velho" in system
    assert "carro voa" in user and "Mano, olha esse carro." in user
    assert schema is SCHEMA


def test_generate_copy_rejects_incomplete_answer():
    bad = dict(GOOD)
    del bad["pergunta"]
    with pytest.raises(LLMError, match="pergunta"):
        generate_copy(FakeLLM([bad]), "x", "y", [])


def test_generate_copy_rejects_wrong_types():
    bad = dict(GOOD)
    bad["titulos"] = "um titulo so"
    with pytest.raises(LLMError, match="titulos"):
        generate_copy(FakeLLM([bad]), "x", "y", [])


def test_placeholder_triggers_one_retry_and_returns_clean_answer():
    sujo = dict(GOOD, descricao_tiktok="veja {ganchos[random]}")
    llm = FakeLLM([sujo, dict(GOOD)])
    out = generate_copy(llm, "x", "y", [])
    assert out["descricao_tiktok"] == "dt"
    assert len(llm.calls) == 2


def test_placeholder_in_list_item_also_counts():
    sujo = dict(GOOD, ganchos=["a", "b", "{x}", "d", "e"])
    llm = FakeLLM([sujo, dict(GOOD)])
    generate_copy(llm, "x", "y", [])
    assert len(llm.calls) == 2


def test_placeholder_twice_raises():
    sujo = dict(GOOD, legenda_instagram="oi {ganchos[random]}")
    with pytest.raises(LLMError, match="marcador.*legenda_instagram"):
        generate_copy(FakeLLM([sujo, dict(sujo)]), "x", "y", [])


def test_clean_answer_makes_a_single_call():
    llm = FakeLLM([dict(GOOD)])
    generate_copy(llm, "x", "y", [])
    assert len(llm.calls) == 1


def test_hashtags_deduped_cleaned_and_capped():
    data = dict(GOOD)
    data["hashtags"] = ["#GTA6", "gta6", "#viral,", "#a", "#b", "#c", "#d", "#e", "#f", "#g"]
    out = generate_copy(FakeLLM([data]), "x", "y", [])
    assert out["hashtags"] == ["#GTA6", "#viral", "#a", "#b", "#c", "#d", "#e", "#f"]


def test_format_copy_has_sections_source_and_license():
    txt = format_copy(GOOD, fonte="https://youtu.be/abc", licenca="autorizado por @canal")
    assert txt.index("GANCHOS") < txt.index("TÍTULOS") < txt.index("HASHTAGS")
    assert "1. t1" in txt
    assert "https://youtu.be/abc" in txt and "autorizado por @canal" in txt
    assert "revise" in txt
