import pytest

from gtaviral.audio_events import (
    AudioEvents,
    events_from_dict,
    events_to_dict,
    find_loud_moments,
    parse_rms,
    parse_silencedetect,
)

SILENCE_LOG = """\
[silencedetect @ 000001] silence_start: 1.5
[silencedetect @ 000001] silence_end: 2.75 | silence_duration: 1.25
size=N/A time=00:00:05.00 bitrate=N/A speed=1x
[silencedetect @ 000001] silence_start: 9.1
"""


def rms_log(values: list[tuple[float, str]]) -> str:
    lines = []
    for i, (t, db) in enumerate(values):
        lines.append(f"[Parsed_ametadata_2 @ 0000] frame:{i}    pts:{int(t * 16000)}       pts_time:{t}")
        lines.append(f"[Parsed_ametadata_2 @ 0000] lavfi.astats.Overall.RMS_level={db}")
    return "\n".join(lines)


def test_parse_silencedetect_closes_open_silence_at_duration():
    assert parse_silencedetect(SILENCE_LOG, duration=10.0) == [(1.5, 2.75), (9.1, 10.0)]


def test_parse_rms_handles_inf():
    rms = parse_rms(rms_log([(0, "-30.5"), (0.5, "-inf")]))
    assert rms == [(0.0, -30.5), (0.5, -120.0)]


def test_find_loud_moments_threshold_gap_and_order():
    rms = [(i * 0.5, -40.0) for i in range(40)]
    rms[10] = (5.0, -20.0)
    rms[11] = (5.5, -22.0)   # a menos de 3 s do pico de 5.0: descartado
    rms[30] = (15.0, -25.0)
    rms[31] = (15.5, -120.0)  # silêncio não entra na mediana
    assert find_loud_moments(rms) == [(5.0, -20.0), (15.0, -25.0)]


def test_find_loud_moments_empty_when_all_silent():
    assert find_loud_moments([(0.0, -120.0), (0.5, -120.0)]) == []


def test_events_dict_roundtrip():
    e = AudioEvents(silences=((1.0, 2.0),), loud_moments=((5.0, -20.0),))
    assert events_from_dict(events_to_dict(e)) == e


@pytest.mark.integration
def test_detect_on_synthetic_audio(real_cfg, tmp_path):
    import subprocess

    from gtaviral.audio_events import detect
    from gtaviral.config import resolve_tool

    wav = tmp_path / "ev.wav"
    graph = (
        "aevalsrc=exprs='0.05*sin(2*PI*440*t)':s=16000:d=5[a];"
        "aevalsrc=exprs='0.8*sin(2*PI*440*t)':s=16000:d=1[b];"
        "anullsrc=r=16000:cl=mono,atrim=0:2[c];"
        "[a][b][c]concat=n=3:v=0:a=1"
    )
    subprocess.run([str(resolve_tool(real_cfg.ffmpeg)), "-hide_banner", "-y", "-filter_complex", graph,
                    "-ac", "1", "-c:a", "pcm_s16le", str(wav)], check=True, capture_output=True)
    ev = detect(real_cfg, wav, duration=8.0)
    assert ev.loud_moments and 5.0 <= ev.loud_moments[0][0] < 6.0
    assert any(abs(start - 6.0) < 0.3 for start, _ in ev.silences)
