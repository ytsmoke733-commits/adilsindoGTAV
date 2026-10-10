import json
import subprocess
from pathlib import Path

import pytest

from gtaviral.proc import ToolError
from gtaviral.transcribe import (
    Transcript,
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
    assert t.segments[1].start == 2.5 and t.segments[1].end == 4.65


def test_segment_bounds_follow_word_timestamps():
    t = load()
    assert (t.segments[0].start, t.segments[0].end) == (0.0, 1.85)
    assert (t.segments[1].start, t.segments[1].end) == (2.5, 4.65)


def test_segment_without_words_keeps_offsets():
    data = {"result": {"language": "pt"}, "transcription": [
        {"offsets": {"from": 1000, "to": 3000}, "text": " oi", "tokens": []}]}
    seg = parse_whisper_json(data).segments[0]
    assert (seg.start, seg.end) == (1.0, 3.0)


def test_degenerate_word_span_keeps_offsets():
    data = {"result": {"language": "pt"}, "transcription": [
        {"offsets": {"from": 1000, "to": 3000}, "text": " oi",
         "tokens": [{"text": " oi", "offsets": {"from": 2000, "to": 2000}, "p": 0.9}]}]}
    seg = parse_whisper_json(data).segments[0]
    assert (seg.start, seg.end) == (1.0, 3.0)


VAD_LOG = """whisper_vad: vad_segment_info: orig_start: 10.00, orig_end: 12.00, vad_start: 0.00, vad_end: 2.00
whisper_vad: vad_segment_info: orig_start: 30.00, orig_end: 33.00, vad_start: 2.20, vad_end: 5.20
"""


def test_parse_vad_map():
    from gtaviral.transcribe import parse_vad_map
    assert parse_vad_map("ggml_vulkan: x\n" + VAD_LOG) == [(10.0, 12.0, 0.0, 2.0), (30.0, 33.0, 2.2, 5.2)]
    assert parse_vad_map("sem vad") == []


def test_vad_map_moves_word_times_back_to_original_audio():
    # fixture: palavras em tempo "compactado" 0.0-1.85 e 2.5-4.65
    t = parse_whisper_json(json.loads(FIXTURE.read_text(encoding="utf-8")),
                           vad_map=[(10.0, 12.0, 0.0, 2.0), (30.0, 33.0, 2.2, 5.2)])
    s0, s1 = t.segments
    assert (s0.start, s0.end) == (10.0, 11.85)
    assert s1.start == 30.3 and s1.end == 32.45
    assert s1.words[0].start == 30.3


def test_vad_gap_start_snaps_forward_and_gap_end_snaps_back():
    from gtaviral.transcribe import unmap_vad
    m = [(10.0, 12.0, 0.0, 2.0), (30.0, 33.0, 2.2, 5.2)]
    assert unmap_vad(2.1, m, "start") == 30.0
    assert unmap_vad(2.1, m, "end") == 12.0
    assert unmap_vad(9.0, m, "end") == 33.0
    assert unmap_vad(-0.1, m, "start") == 10.0


def test_segment_splits_at_long_pause_between_words():
    data = {"result": {"language": "pt"}, "transcription": [
        {"offsets": {"from": 0, "to": 12000}, "text": " oi tudo bem tchau", "tokens": [
            {"text": " oi", "offsets": {"from": 0, "to": 500}, "p": 0.9},
            {"text": " tudo", "offsets": {"from": 500, "to": 1000}, "p": 0.9},
            {"text": " bem", "offsets": {"from": 1000, "to": 1500}, "p": 0.9},
            {"text": " tchau", "offsets": {"from": 6500, "to": 7000}, "p": 0.9}]},
        {"offsets": {"from": 12000, "to": 13000}, "text": " fim", "tokens": [
            {"text": " fim", "offsets": {"from": 12000, "to": 12500}, "p": 0.9}]}]}
    segs = parse_whisper_json(data).segments
    assert [(s.id, s.text, s.start, s.end) for s in segs] == [
        (0, "oi tudo bem", 0.0, 1.5), (1, "tchau", 6.5, 7.0), (2, "fim", 12.0, 12.5)]
    assert [w.text for w in segs[0].words] == ["oi", "tudo", "bem"]


def test_word_ending_exactly_at_next_chunk_start_belongs_to_previous_chunk():
    from gtaviral.transcribe import unmap_vad
    m = [(10.0, 12.0, 0.0, 2.0), (30.0, 33.0, 2.2, 5.2)]
    assert unmap_vad(2.2, m, "end") == 12.0
    assert unmap_vad(2.2, m, "start") == 30.0


def test_word_edge_slightly_past_chunk_boundary_stays_in_its_chunk():
    from gtaviral.transcribe import unmap_vad
    m = [(10.0, 12.0, 0.0, 2.0), (30.0, 33.0, 2.2, 5.2)]
    assert unmap_vad(2.01, m, "start") == 12.0   # 0,01 s alem do fim do trecho (log arredonda)
    assert unmap_vad(2.19, m, "end") == 12.0     # fim 0,01 s antes do trecho seguinte: e do anterior
    assert unmap_vad(2.21, m, "end") == 12.0     # fim 0,01 s depois do inicio do seguinte: ainda e o anterior


def test_degenerate_piece_after_split_gets_minimum_span():
    data = {"result": {"language": "pt"}, "transcription": [
        {"offsets": {"from": 0, "to": 9000}, "text": " oi tchau", "tokens": [
            {"text": " oi", "offsets": {"from": 0, "to": 500}, "p": 0.9},
            {"text": " tchau", "offsets": {"from": 6000, "to": 6000}, "p": 0.9}]}]}
    segs = parse_whisper_json(data).segments
    assert [(s.text, s.start, s.end) for s in segs] == [("oi", 0.0, 0.5), ("tchau", 6.0, 6.2)]


def _vad_cfg(tmp_path):
    (tmp_path / "w.bin").write_bytes(b"x")
    vad = tmp_path / "vad.bin"
    vad.write_bytes(b"x")
    return make_cfg(tmp_path, whisper_vad_model=vad)


def test_vad_without_map_in_log_fails_loudly(tmp_path, monkeypatch):
    _fake_run(monkeypatch, tmp_path, [], stderr="ggml_vulkan: RX 6600")
    with pytest.raises(ToolError, match="VAD"):
        transcribe(_vad_cfg(tmp_path), tmp_path / "a.wav", tmp_path / "whisper")


def test_vad_without_map_and_without_segments_is_just_no_speech(tmp_path, monkeypatch):
    _fake_run(monkeypatch, tmp_path, [], stderr="ggml_vulkan: RX 6600")
    monkeypatch.setattr("gtaviral.transcribe.parse_whisper_json",
                        lambda data, vad_map=None: Transcript("en", ()))
    assert transcribe(_vad_cfg(tmp_path), tmp_path / "a.wav", tmp_path / "whisper").segments == ()


def test_word_stretched_into_next_chunk_is_clamped_and_segment_splits():
    data = {"result": {"language": "pt"}, "transcription": [
        {"offsets": {"from": 0, "to": 9000}, "text": " oi tchau", "tokens": [
            {"text": " oi", "offsets": {"from": 100, "to": 2300}, "p": 0.9},
            {"text": " tchau", "offsets": {"from": 2300, "to": 3000}, "p": 0.9}]}]}
    segs = parse_whisper_json(data, vad_map=[(10.0, 12.0, 0.0, 2.0), (30.0, 33.0, 2.2, 5.2)]).segments
    assert [(s.text, s.start, s.end) for s in segs] == [("oi", 10.1, 12.0), ("tchau", 30.1, 30.8)]


def test_word_stranded_in_vad_gap_stays_with_previous_speech():
    data = {"result": {"language": "pt"}, "transcription": [
        {"offsets": {"from": 0, "to": 9000}, "text": " oi tchau", "tokens": [
            {"text": " oi", "offsets": {"from": 100, "to": 900}, "p": 0.9},
            {"text": " tchau", "offsets": {"from": 2100, "to": 2100}, "p": 0.9}]}]}
    seg = parse_whisper_json(data, vad_map=[(10.0, 12.0, 0.0, 2.0), (30.0, 33.0, 2.2, 5.2)]).segments[0]
    assert seg.words[1].start == seg.words[1].end == 12.0
    assert (seg.start, seg.end) == (10.1, 12.0)


def _fake_run(monkeypatch, tmp_path, captured, fail=False, stderr="ggml_vulkan: RX 6600"):
    cli = tmp_path / "whisper-cli.exe"
    cli.write_bytes(b"")
    monkeypatch.setattr("gtaviral.transcribe.resolve_tool", lambda v: cli)

    def fake(cmd, **kw):
        captured.append([str(c) for c in cmd])
        if fail:
            raise ToolError("whisper-cli saiu com código 1:\nerro de teste")
        prefix = Path(str(cmd[cmd.index("-of") + 1]))
        (prefix.parent / (prefix.name + ".json")).write_text(
            FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, stdout="saida-out", stderr=stderr)

    monkeypatch.setattr("gtaviral.transcribe.run", fake)


def test_vad_flags_added_when_configured_and_log_written(tmp_path, monkeypatch):
    (tmp_path / "w.bin").write_bytes(b"x")
    vad = tmp_path / "vad.bin"
    vad.write_bytes(b"x")
    captured: list = []
    _fake_run(monkeypatch, tmp_path, captured, stderr="ggml_vulkan: RX 6600\n" + VAD_LOG)
    cfg = make_cfg(tmp_path, whisper_vad_model=vad)
    transcribe(cfg, tmp_path / "a.wav", tmp_path / "whisper")
    cmd = captured[0]
    assert "--vad" in cmd and cmd[cmd.index("-vm") + 1] == str(vad)
    log = (tmp_path / "whisper.log").read_text(encoding="utf-8")
    assert "RX 6600" in log and "saida-out" in log


def test_transcribe_remaps_times_from_vad_log_and_keeps_log_verbose(tmp_path, monkeypatch):
    (tmp_path / "w.bin").write_bytes(b"x")
    vad = tmp_path / "vad.bin"
    vad.write_bytes(b"x")
    captured: list = []
    _fake_run(monkeypatch, tmp_path, captured, stderr=VAD_LOG)
    t = transcribe(make_cfg(tmp_path, whisper_vad_model=vad), tmp_path / "a.wav", tmp_path / "whisper")
    assert (t.segments[0].start, t.segments[0].end) == (10.0, 11.85)
    assert "-np" not in captured[0]  # sem -np o whisper-cli registra GPU/Vulkan e o mapa do VAD no log


def test_no_vad_flags_without_config(tmp_path, monkeypatch):
    (tmp_path / "w.bin").write_bytes(b"x")
    captured: list = []
    _fake_run(monkeypatch, tmp_path, captured)
    transcribe(make_cfg(tmp_path), tmp_path / "a.wav", tmp_path / "whisper")
    assert "--vad" not in captured[0] and "-vm" not in captured[0]


def test_missing_vad_model_explains(tmp_path, monkeypatch):
    (tmp_path / "w.bin").write_bytes(b"x")
    _fake_run(monkeypatch, tmp_path, [])
    cfg = make_cfg(tmp_path, whisper_vad_model=tmp_path / "nao-existe.bin")
    with pytest.raises(ToolError, match="VAD"):
        transcribe(cfg, tmp_path / "a.wav", tmp_path / "whisper")


def test_log_written_on_failure_too(tmp_path, monkeypatch):
    (tmp_path / "w.bin").write_bytes(b"x")
    _fake_run(monkeypatch, tmp_path, [], fail=True)
    with pytest.raises(ToolError):
        transcribe(make_cfg(tmp_path), tmp_path / "a.wav", tmp_path / "whisper")
    assert "erro de teste" in (tmp_path / "whisper.log").read_text(encoding="utf-8")


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
