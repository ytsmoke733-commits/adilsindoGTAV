from gtaviral.subtitles import (
    Cue,
    build_cues,
    cps_warnings,
    fmt_ass_time,
    fmt_srt_time,
    parse_srt,
    split_text,
    to_ass,
    to_srt,
    to_vtt,
    wrap_lines,
)
from gtaviral.translate import TranslatedSegment


def seg(i, a, b, text, highs=()):
    return TranslatedSegment(i, float(a), float(b), "src", text, tuple(highs))


def test_time_formats():
    assert fmt_srt_time(3661.5) == "01:01:01,500"
    assert fmt_ass_time(3661.5) == "1:01:01.50"


def test_wrap_lines_respects_width():
    assert wrap_lines("mano olha esse carro voando por cima da ponte", 20) == [
        "mano olha esse carro", "voando por cima da", "ponte"]


def test_split_text_breaks_after_sentence_end_and_at_limit():
    assert split_text("Olha isso. O carro voou longe demais mano", 40) == [
        "Olha isso.", "O carro voou longe demais mano"]
    assert all(len(c) <= 18 for c in split_text("um dois tres quatro cinco seis sete oito", 18))


def test_build_cues_shifts_to_clip_time_and_clips_edges():
    segs = [seg(0, 0, 4, "fora do clipe"),
            seg(1, 9, 12, "Mano, olha esse carro.", ["carro"]),
            seg(2, 12, 20, "Voou por cima da ponte.")]
    assert build_cues(segs, clip_start=10.0, clip_end=16.0, style="destaque") == [
        Cue(0.0, 2.0, "Mano, olha esse carro.", ("carro",)),
        Cue(2.0, 6.0, "Voou por cima da ponte.", ()),
    ]


def test_dinamica_makes_short_chunks_with_proportional_contiguous_timing():
    cues = build_cues([seg(0, 0, 4, "um dois tres quatro cinco seis sete oito")], 0, 4, "dinamica")
    assert len(cues) >= 2 and all(len(c.text) <= 18 for c in cues)
    assert cues[0].start == 0.0 and cues[-1].end == 4.0
    assert all(a.end == b.start for a, b in zip(cues, cues[1:]))


def test_simples_drops_highlights():
    assert build_cues([seg(0, 0, 3, "olha o carro", ["carro"])], 0, 3, "simples")[0].highlights == ()


def test_srt_roundtrip_with_marked_highlights():
    cues = [Cue(0.0, 2.0, "Mano, olha esse carro.", ("carro",)), Cue(2.0, 6.5, "Voou por cima da ponte.", ())]
    marked = to_srt(cues, mark=True)
    assert "*carro*" in marked
    assert parse_srt(marked) == cues
    assert "*" not in to_srt(cues)


def test_parse_srt_accepts_user_edits_with_crlf_and_bom():
    text = ("﻿1\r\n00:00:00,000 --> 00:00:01,500\r\nTexto *corrigido*\r\n\r\n"
            "2\r\n00:00:01,500 --> 00:00:03,000\r\nOutra linha\r\n")
    assert parse_srt(text) == [Cue(0.0, 1.5, "Texto corrigido", ("corrigido",)), Cue(1.5, 3.0, "Outra linha", ())]


def test_vtt_header_and_dot_times():
    vtt = to_vtt([Cue(0.0, 1.25, "oi", ())])
    assert vtt.startswith("WEBVTT\n\n")
    assert "00:00:00.000 --> 00:00:01.250" in vtt


def test_ass_has_canvas_style_and_highlight_markup():
    ass = to_ass([Cue(0.0, 2.0, "Mano, olha esse carro.", ("carro",))], 1080, 1920, "Arial Black", "destaque")
    assert "PlayResX: 1080" in ass and "PlayResY: 1920" in ass
    assert "Style: Main,Arial Black,65," in ass
    assert r"Mano, olha esse\N{\c&H00E5FF&}carro{\c&HFFFFFF&}." in ass
    assert "Dialogue: 0,0:00:00.00,0:00:02.00,Main" in ass


def test_ass_escapes_braces_and_backslashes():
    ass = to_ass([Cue(0.0, 1.0, r"a {b} c\d", ())], 1080, 1920, "Arial Black", "simples")
    assert "a (b) c/d" in ass


def test_ass_dinamica_adds_pop_in():
    ass = to_ass([Cue(0.0, 1.0, "oi", ())], 1080, 1920, "Arial Black", "dinamica")
    assert r"{\fscx85\fscy85\t(0,120,\fscx100\fscy100)}oi" in ass


def test_cps_warning_only_for_fast_cue():
    warns = cps_warnings([Cue(0.0, 1.0, "x" * 30, ()), Cue(1.0, 4.0, "curto", ())])
    assert len(warns) == 1 and "legenda 1" in warns[0]
