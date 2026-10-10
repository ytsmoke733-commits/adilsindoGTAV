import json
from pathlib import Path

import pytest

from gtaviral.proc import ToolError
from gtaviral.transcribe import (
    Word,
    parse_whisper_json,
    transcribe,
    transcript_from_dict,
    transcript_to_dict,
)
from tests.test_doctor import make_cfg

FIXTURE = Path(__file__).parent / "fixtures" / "whisper_sample.json"


def load():
    return parse_whisper_json(json.loads(FIXTURE.read_text(encoding="utf-8")))


def test_language_and_non_empty_segments():
    t = load()
    assert t.language == "en"
    assert [s.text for s in t.segments] == ["Bro, look at this car.", "It just flew over the bridge."]
    assert [s.id for s in t.segments] == [0, 1]
    assert t.segments[1].start == 2.5 and t.segments[1].end == 6.0


def test_words_skip_special_tokens_and_glue_punctuation():
    words = load().segments[0].words
    assert [w.text for w in words] == ["Bro,", "look", "at", "this", "car."]
    assert words[0] == Word("Bro,", 0.0, 0.45, 0.9)


def test_subword_tokens_merge_with_min_probability():
    flew = [w for w in load().segments[1].words if w.text == "flew"][0]
    assert (flew.start, flew.end, flew.prob) == (3.0, 3.5, 0.6)


def test_dict_roundtrip():
    t = load()
    assert transcript_from_dict(json.loads(json.dumps(transcript_to_dict(t)))) == t


def test_transcribe_without_cli_explains(tmp_path):
    with pytest.raises(ToolError, match="gtaviral verificar"):
        transcribe(make_cfg(tmp_path), tmp_path / "a.wav", tmp_path / "out")


@pytest.mark.integration
def test_transcribe_real_speech(real_cfg, speech_wav, tmp_path):
    from gtaviral.media import extract_audio

    wav = tmp_path / "a.wav"
    extract_audio(real_cfg, speech_wav, wav)
    t = transcribe(real_cfg, wav, tmp_path / "whisper")
    text = " ".join(s.text for s in t.segments).lower()
    assert t.language == "en"
    assert "car" in text and "bridge" in text
    starts = [w.start for s in t.segments for w in s.words]
    assert starts == sorted(starts) and len(starts) > 20
