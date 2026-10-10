import hashlib
from pathlib import Path

import pytest

from gtaviral.media import MediaError, MediaInfo, file_sha256, parse_probe, validate

PROBE = {
    "streams": [
        {"codec_type": "video", "codec_name": "h264", "width": 1920, "height": 1080,
         "avg_frame_rate": "60/1", "r_frame_rate": "60/1", "disposition": {"attached_pic": 0}},
        {"codec_type": "audio", "codec_name": "aac"},
    ],
    "format": {"duration": "42.5"},
}


def test_parse_probe_reads_basic_fields():
    info = parse_probe(PROBE)
    assert info == MediaInfo(duration=42.5, width=1920, height=1080, fps=60.0, has_audio=True, video_codec="h264")


def test_parse_probe_swaps_dimensions_for_rotated_phone_video():
    data = {"streams": [{"codec_type": "video", "codec_name": "h264", "width": 1920, "height": 1080,
                         "avg_frame_rate": "30000/1001", "side_data_list": [{"rotation": -90}]}],
            "format": {"duration": "10"}}
    info = parse_probe(data)
    assert (info.width, info.height) == (1080, 1920)
    assert info.fps == pytest.approx(29.97, abs=0.01)
    assert info.has_audio is False


def test_parse_probe_ignores_cover_art_and_requires_video():
    data = {"streams": [{"codec_type": "video", "codec_name": "mjpeg", "width": 500, "height": 500,
                         "disposition": {"attached_pic": 1}},
                        {"codec_type": "audio", "codec_name": "mp3"}],
            "format": {"duration": "200"}}
    with pytest.raises(MediaError, match="faixa de vídeo"):
        parse_probe(data)


@pytest.mark.parametrize("size_gb,duration,msg", [
    (5.0, 60.0, "limite"),
    (1.0, 30 * 60.0, "min"),
    (1.0, 0.0, "duração"),
])
def test_validate_rejects(size_gb, duration, msg):
    info = MediaInfo(duration=duration, width=1920, height=1080, fps=60.0, has_audio=True, video_codec="h264")
    with pytest.raises(MediaError, match=msg):
        validate(info, int(size_gb * 1024**3), max_file_gb=4.0, max_duration_min=20)


def test_validate_rejects_tiny_resolution():
    info = MediaInfo(duration=10, width=160, height=120, fps=30.0, has_audio=True, video_codec="h264")
    with pytest.raises(MediaError, match="resolução"):
        validate(info, 1000, max_file_gb=4.0, max_duration_min=20)


def test_file_sha256_matches_hashlib(tmp_path: Path):
    f = tmp_path / "a.bin"
    f.write_bytes(b"gta" * 1_000_000)
    assert file_sha256(f) == hashlib.sha256(b"gta" * 1_000_000).hexdigest()


@pytest.mark.integration
def test_probe_and_extract_audio_on_real_video(real_cfg, speech_video, tmp_path):
    from gtaviral.media import extract_audio, probe

    info = probe(real_cfg, speech_video)
    assert (info.width, info.height) == (1920, 1080)
    assert info.fps == pytest.approx(60.0)
    assert info.has_audio and info.duration > 5

    wav = tmp_path / "a.wav"
    extract_audio(real_cfg, speech_video, wav)
    # O WAV não tem vídeo (probe recusaria); confere pelo tamanho: 16 kHz * 2 bytes * duração.
    assert wav.stat().st_size == pytest.approx(16000 * 2 * info.duration, rel=0.05)
