from gtaviral.audio_events import AudioEvents
from gtaviral.select_clips import (
    ClipCandidate,
    clips_from_dicts,
    clips_to_dicts,
    fit_span,
    llm_candidates,
    rule_candidates,
    select_clips,
)
from gtaviral.translate import TranslatedSegment
from tests.fakes import FakeLLM


def segs(*bounds):
    return [TranslatedSegment(i, float(a), float(b), f"src {i}", f"texto {i}") for i, (a, b) in enumerate(bounds)]


SEGS = segs((0, 4), (4, 10), (10, 15), (15, 22), (22, 30), (30, 41), (41, 50), (50, 60))
NO_EVENTS = AudioEvents((), ())


def test_fit_span_snaps_to_segment_boundaries():
    assert fit_span(SEGS, 5.0, 21.0, 60.0) == (4.0, 22.0)


def test_fit_span_caps_long_spans_at_a_segment_end():
    long = segs(*[(i * 10, i * 10 + 10) for i in range(20)])
    assert fit_span(long, 0, 150, 200.0) == (0.0, 90.0)


def test_fit_span_extends_short_spans_and_rejects_tiny_videos():
    assert fit_span(SEGS, 0.5, 2.0, 60.0) == (0.0, 10.0)
    assert fit_span(segs((0, 3)), 0, 3, 3.0) is None


def test_rule_candidates_from_peaks_without_overlap():
    ev = AudioEvents((), ((12.0, -10.0), (13.0, -11.0), (45.0, -12.0)))
    out = rule_candidates(SEGS, ev, 60.0, max_clips=3)
    assert [(c.index, c.start, c.end) for c in out] == [(1, 4.0, 30.0), (2, 30.0, 60.0)]
    assert all(c.source == "regras" for c in out)
    assert "12.0s" in out[0].reason


def test_rule_candidates_fallback_windows_when_no_peaks():
    out = rule_candidates(SEGS, NO_EVENTS, 60.0, max_clips=3)
    assert [(c.start, c.end) for c in out] == [(0.0, 30.0), (30.0, 60.0)]
    assert "nenhum pico" in out[0].reason


def test_llm_candidates_validate_snap_and_drop_bad_items():
    llm = FakeLLM([{"clipes": [
        {"inicio": 5.0, "fim": 21.0, "motivo": "carro voa", "gancho": "Olha isso"},
        {"inicio": 30.0, "fim": 20.0, "motivo": "invertido", "gancho": ""},
        {"inicio": 6.0, "fim": 20.0, "motivo": "sobreposto", "gancho": ""},
        {"inicio": 41.0, "fim": 59.0, "motivo": "policia", "gancho": "Ninguém reagiu"},
    ]}])
    out = llm_candidates(SEGS, NO_EVENTS, 60.0, llm, max_clips=3)
    assert [(c.index, c.start, c.end, c.reason) for c in out] == [(1, 4.0, 22.0, "carro voa"), (2, 41.0, 60.0, "policia")]
    assert out[0].hook == "Olha isso" and out[0].source == "llm"


def test_prompt_contains_timed_transcript_and_peaks():
    llm = FakeLLM([{"clipes": []}])
    llm_candidates(SEGS, AudioEvents((), ((12.0, -10.0),)), 60.0, llm, max_clips=3)
    system, user, _ = llm.calls[0]
    assert "[4.0-10.0] texto 1" in user
    assert "12.0" in user
    assert "No máximo 3 clipes" in system


def test_select_falls_back_to_rules_when_llm_gives_nothing():
    out = select_clips(SEGS, NO_EVENTS, 60.0, FakeLLM([{"clipes": []}]), max_clips=2)
    assert out and all(c.source == "regras" for c in out)


def test_select_without_llm_uses_rules():
    assert all(c.source == "regras" for c in select_clips(SEGS, NO_EVENTS, 60.0, None, max_clips=2))


def test_clips_dict_roundtrip():
    c = ClipCandidate(1, 0.0, 10.0, "r", "h", "llm")
    assert clips_from_dicts(clips_to_dicts([c])) == [c]
