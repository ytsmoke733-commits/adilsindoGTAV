import json

import pytest

from gtaviral.transcribe import Segment, Transcript
from gtaviral.translate import (
    TranslatedSegment,
    TranslationError,
    max_chars_for,
    translate,
    translated_from_dicts,
    translated_to_dicts,
)
from tests.fakes import FakeLLM


def tr(lang: str = "en") -> Transcript:
    return Transcript(lang, (
        Segment(0, 0.0, 2.5, "Bro, look at this car.", ()),
        Segment(1, 2.5, 6.0, "It just flew over the bridge.", ()),
    ))


def reply(*items) -> dict:
    return {"itens": [{"id": i, "texto": t, "destaques": d} for i, t, d in items]}


def sent_items(user_prompt: str) -> list[dict]:
    return json.loads(user_prompt.split("Traduza:\n", 1)[1])


def test_translate_keeps_order_times_and_source():
    llm = FakeLLM([reply((1, "Ele voou por cima da ponte.", ["voou"]), (0, "Mano, olha esse carro.", ["carro"]))])
    out = translate(tr(), llm)
    assert [s.text for s in out] == ["Mano, olha esse carro.", "Ele voou por cima da ponte."]
    assert out[0] == TranslatedSegment(0, 0.0, 2.5, "Bro, look at this car.", "Mano, olha esse carro.", ("carro",))


def test_glossary_and_char_limits_go_in_prompt():
    llm = FakeLLM([reply((0, "a", []), (1, "b", []))])
    translate(tr(), llm)
    system, user, _ = llm.calls[0]
    assert "Vice City" in system and "Leonida" in system
    assert sent_items(user)[0] == {"id": 0, "max_caracteres": 42, "texto": "Bro, look at this car."}


def test_missing_ids_are_retried_once_with_only_the_missing():
    llm = FakeLLM([reply((0, "Mano, olha esse carro.", [])), reply((1, "Voou por cima da ponte.", []))])
    out = translate(tr(), llm)
    assert len(out) == 2
    assert [i["id"] for i in sent_items(llm.calls[1][1])] == [1]


def test_still_missing_after_retry_raises():
    llm = FakeLLM([reply((0, "x", [])), reply((0, "x", []))])
    with pytest.raises(TranslationError, match=r"\[1\]"):
        translate(tr(), llm)


def test_highlights_not_in_text_are_dropped():
    llm = FakeLLM([reply((0, "Mano, olha esse carro.", ["carro", "avião"]), (1, "Voou.", []))])
    assert translate(tr(), llm)[0].highlights == ("carro",)


def test_portuguese_is_passthrough_without_llm():
    out = translate(tr("pt"), None)
    assert [s.text for s in out] == [s.source for s in out]


def test_foreign_language_without_llm_raises():
    with pytest.raises(TranslationError, match="LLM"):
        translate(tr("en"), None)


def test_max_chars_bounds():
    assert max_chars_for(0, 0.2) == 12
    assert max_chars_for(0, 20) == 80


def test_dicts_roundtrip():
    seg = TranslatedSegment(0, 0.0, 1.0, "a", "b", ("b",))
    assert translated_from_dicts(json.loads(json.dumps(translated_to_dicts([seg])))) == [seg]
