from pathlib import Path

import pytest

import gtaviral.render as r
from gtaviral.media import MediaInfo
from gtaviral.render import PROFILES, blur_chain, build_command, build_filtergraph, crop_chain

H = MediaInfo(60.0, 1920, 1080, 60.0, True, "h264")
P = PROFILES["1080"]


def test_crop_center_of_landscape():
    assert crop_chain(1920, 1080, P, 0.5) == "crop=608:1080:656:0,scale=1080:1920:flags=lanczos,setsar=1"


def test_crop_left_and_right_edges():
    assert crop_chain(1920, 1080, P, 0.0).startswith("crop=608:1080:0:0,")
    assert crop_chain(1920, 1080, P, 1.0).startswith("crop=608:1080:1312:0,")


def test_crop_tall_source_cuts_top_and_bottom_centered():
    assert crop_chain(1080, 2400, P, 0.5).startswith("crop=1080:1920:0:240,")


def test_crop_rejects_out_of_range_position():
    with pytest.raises(ValueError):
        crop_chain(1920, 1080, P, 1.5)


def test_blur_chain_never_stretches():
    chain = blur_chain(P)
    assert "force_original_aspect_ratio=increase" in chain
    assert "force_original_aspect_ratio=decrease" in chain
    assert "overlay=(W-w)/2:(H-h)/2" in chain


def test_filtergraph_labels_and_subtitles():
    g = build_filtergraph(H, P, "desfoque", 0.5, "legenda.ass")
    assert g.startswith("[0:v]split=2[bg][fg];")
    assert g.endswith(",subtitles=legenda.ass[v]")
    with pytest.raises(ValueError):
        build_filtergraph(H, P, "esticar", 0.5, None)


def test_build_command_trims_maps_and_encodes():
    cmd = build_command("ffmpeg", Path("in.mp4"), H, 10.0, 25.5, P, "corte", 0.5, "legenda.ass", Path("out.mp4"))
    assert cmd[cmd.index("-ss") + 1] == "10.000"
    assert cmd[cmd.index("-t") + 1] == "15.500"
    assert cmd.index("-ss") < cmd.index("-i")
    for flag, value in [("-c:v", "libx264"), ("-crf", "18"), ("-profile:v", "high"), ("-pix_fmt", "yuv420p"),
                        ("-c:a", "aac"), ("-movflags", "+faststart")]:
        assert cmd[cmd.index(flag) + 1] == value
    assert "-r" not in cmd
    assert cmd[-1] == "out.mp4"


def test_build_command_without_audio_skips_audio_options():
    silent = MediaInfo(60.0, 1920, 1080, 60.0, False, "h264")
    cmd = build_command("ffmpeg", Path("in.mp4"), silent, 0, 10, P, "corte", 0.5, None, Path("o.mp4"))
    assert "-c:a" not in cmd and "0:a:0" not in cmd


def test_profile_1440():
    assert (PROFILES["1440"].width, PROFILES["1440"].height) == (1440, 2560)


def test_verify_output_missing_file(tmp_path):
    with pytest.raises(r.RenderError, match="não gerou"):
        r.verify_output(None, tmp_path / "nao.mp4", P, expected_fps=60.0)


@pytest.mark.parametrize("got,msg", [
    (MediaInfo(5, 720, 1280, 60.0, True, "h264"), "720x1280"),
    (MediaInfo(5, 1080, 1920, 30.0, True, "h264"), "fps"),
    (MediaInfo(5, 1080, 1920, 60.0, True, "hevc"), "hevc"),
])
def test_verify_output_rejects_mismatch(monkeypatch, tmp_path, got, msg):
    out = tmp_path / "o.mp4"
    out.write_bytes(b"x")
    monkeypatch.setattr(r, "probe", lambda cfg, p: got)
    with pytest.raises(r.RenderError, match=msg):
        r.verify_output(None, out, P, expected_fps=60.0)


@pytest.mark.integration
@pytest.mark.parametrize("framing", ["corte", "desfoque"])
def test_render_real_clip(real_cfg, speech_video, tmp_path, framing):
    from gtaviral.media import probe
    from gtaviral.subtitles import Cue, to_ass

    info = probe(real_cfg, speech_video)
    ass = to_ass([Cue(0.0, 3.0, "Mano, olha esse carro.", ("carro",))], 1080, 1920, real_cfg.subtitle_font, "destaque")
    (tmp_path / "legenda.ass").write_text(ass, encoding="utf-8")
    out = tmp_path / "clipe.mp4"
    r.render_clip(real_cfg, speech_video, info, 1.0, 5.0, P, framing, 0.5, "legenda.ass", out)
    got = r.verify_output(real_cfg, out, P, expected_fps=info.fps)
    assert got.duration == pytest.approx(4.0, abs=0.2)
    assert got.has_audio


def test_render_clip_uses_absolute_paths_and_cleans_tmp_on_failure(monkeypatch, tmp_path):
    from types import SimpleNamespace

    from gtaviral.proc import ToolError

    monkeypatch.chdir(tmp_path)
    (tmp_path / "job").mkdir()
    calls = {}

    def fake_run(cmd, cwd=None, timeout=None):
        calls["cmd"], calls["cwd"] = cmd, cwd
        Path(cmd[-1]).write_bytes(b"parcial")
        raise ToolError("ffmpeg falhou")

    monkeypatch.setattr(r, "resolve_tool", lambda name: Path("ffmpeg.exe"))
    monkeypatch.setattr(r, "run", fake_run)
    with pytest.raises(ToolError):
        r.render_clip(SimpleNamespace(ffmpeg="ffmpeg"), Path("in.mp4"), H, 0, 5, P, "corte", 0.5, None,
                      Path("job/clipe.mp4"))
    cmd = calls["cmd"]
    for arg in (cmd[0], cmd[cmd.index("-i") + 1], cmd[-1]):
        assert Path(arg).is_absolute(), arg
    assert Path(cmd[-1]).parent == (tmp_path / "job").resolve()
    assert not Path(cmd[-1]).exists()
