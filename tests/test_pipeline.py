import json
from contextlib import nullcontext

import pytest

import gtaviral.pipeline as pl
from gtaviral.audio_events import AudioEvents
from gtaviral.media import MediaInfo
from gtaviral.transcribe import Segment, Transcript
from tests.fakes import FakeLLM
from tests.test_doctor import make_cfg

INFO = MediaInfo(30.0, 1920, 1080, 60.0, True, "h264")
TRANSCRIPT = Transcript("en", (
    Segment(0, 0.0, 4.0, "Look at this car.", ()),
    Segment(1, 4.0, 12.0, "It flew over the bridge.", ()),
    Segment(2, 12.0, 20.0, "This is insane bro.", ()),
))
CLIPS_REPLY = {"clipes": [
    {"inicio": 0.0, "fim": 12.0, "motivo": "carro voa", "gancho": "Olha isso"},
    {"inicio": 12.0, "fim": 20.0, "motivo": "reação", "gancho": "Insano"},
]}
COPY = {"ganchos": list("abcde"), "titulos": ["t1", "t2", "t3"], "legenda_instagram": "li",
        "descricao_tiktok": "dt", "hashtags": ["#a", "#b", "#c", "#d"], "pergunta": "p",
        "texto_capa": "c", "justificativa": "j"}
QUIET = lambda msg: None  # noqa: E731


def translation_reply(user: str) -> dict:
    items = json.loads(user.split("Traduza:\n", 1)[1])
    return {"itens": [{"id": i["id"], "texto": f"pt {i['id']}", "destaques": []} for i in items]}


def llm_factory(*replies):
    fake = FakeLLM(list(replies))
    return fake, (lambda cfg: nullcontext(fake))


@pytest.fixture
def env(tmp_path, monkeypatch):
    calls = {"probe": 0, "extract": 0, "transcribe": 0, "detect": 0}

    def fake_probe(cfg, path):
        calls["probe"] += 1
        return INFO

    def fake_extract(cfg, src, dst):
        calls["extract"] += 1
        dst.write_bytes(b"wav")

    def fake_transcribe(cfg, wav, prefix):
        calls["transcribe"] += 1
        return TRANSCRIPT

    def fake_detect(cfg, wav, duration):
        calls["detect"] += 1
        return AudioEvents((), ((5.0, -10.0),))

    monkeypatch.setattr(pl, "probe", fake_probe)
    monkeypatch.setattr(pl, "extract_audio", fake_extract)
    monkeypatch.setattr(pl, "transcribe", fake_transcribe)
    monkeypatch.setattr(pl, "detect", fake_detect)
    video = tmp_path / "video.mp4"
    video.write_bytes(b"fake video bytes")
    return make_cfg(tmp_path), video, calls


@pytest.fixture
def analyzed(env, monkeypatch):
    cfg, video, _ = env
    _, factory = llm_factory(translation_reply, CLIPS_REPLY)
    job = pl.analyze(cfg, video, "https://youtu.be/x", "próprio", llm_factory=factory, log=QUIET)
    rendered = []

    def fake_render(cfg_, src, info, start, end, profile, framing, crop_x, subs_file, out_path):
        assert (out_path.parent / subs_file).is_file()
        rendered.append((start, end, framing))
        out_path.write_bytes(b"mp4")

    monkeypatch.setattr(pl, "render_clip", fake_render)
    monkeypatch.setattr(pl, "verify_output", lambda cfg_, out, profile, expected_fps: INFO)
    return cfg, job, rendered


def test_analyze_requires_source_and_license(env):
    cfg, video, _ = env
    with pytest.raises(pl.PipelineError, match="--fonte"):
        pl.analyze(cfg, video, fonte="", licenca="próprio", log=QUIET)


def test_analyze_writes_manifest_and_clips(env):
    cfg, video, _ = env
    _, factory = llm_factory(translation_reply, CLIPS_REPLY)
    job = pl.analyze(cfg, video, "https://youtu.be/x", "próprio", llm_factory=factory, log=QUIET)
    manifest = json.loads((cfg.work_dir / job / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["fonte"] == "https://youtu.be/x" and manifest["licenca"] == "próprio"
    assert [(c.start, c.end, c.reason) for c in pl.load_clips(cfg, job)] == [
        (0.0, 12.0, "carro voa"), (12.0, 20.0, "reação")]


def test_analyze_twice_reuses_every_stage(env):
    cfg, video, calls = env
    _, first = llm_factory(translation_reply, CLIPS_REPLY)
    job1 = pl.analyze(cfg, video, "f", "l", llm_factory=first, log=QUIET)
    fake2, second = llm_factory()
    job2 = pl.analyze(cfg, video, "f", "l", llm_factory=second, log=QUIET)
    assert job1 == job2
    assert calls == {"probe": 1, "extract": 1, "transcribe": 1, "detect": 1}
    assert fake2.calls == []


def test_redo_clips_only_reruns_clip_selection(env):
    cfg, video, _ = env
    _, first = llm_factory(translation_reply, CLIPS_REPLY)
    job = pl.analyze(cfg, video, "f", "l", llm_factory=first, log=QUIET)
    fake2, second = llm_factory({"clipes": [{"inicio": 4.0, "fim": 20.0, "motivo": "novo", "gancho": ""}]})
    pl.analyze(cfg, video, "f", "l", redo_clips=True, llm_factory=second, log=QUIET)
    assert len(fake2.calls) == 1
    assert [c.reason for c in pl.load_clips(cfg, job)] == ["novo"]


def test_analyze_without_llm_rejects_foreign_language(env):
    cfg, video, _ = env
    with pytest.raises(pl.TranslationError, match="LLM"):
        pl.analyze(cfg, video, "f", "l", use_llm=False, log=QUIET)


def test_render_writes_all_files_per_clip(analyzed):
    cfg, job, rendered = analyzed
    results = pl.render_clips(cfg, job, use_llm=False, log=QUIET)
    assert [r.index for r in results if r.output] == [1, 2]
    cdir = cfg.output_dir / job / "clipe_01"
    for name in ["clipe.mp4", "legenda_editavel.srt", "legenda.srt", "legenda.vtt", "legenda.ass",
                 "avisos.txt", "render.json"]:
        assert (cdir / name).is_file(), name
    assert "pt 0" in (cdir / "legenda.srt").read_text(encoding="utf-8")


def test_render_failure_of_one_clip_does_not_stop_the_other(analyzed, monkeypatch):
    cfg, job, _ = analyzed
    working = pl.render_clip

    def flaky(cfg_, src, info, start, end, *rest):
        if start == 0.0:
            raise pl.ToolError("ffmpeg explodiu")
        return working(cfg_, src, info, start, end, *rest)

    monkeypatch.setattr(pl, "render_clip", flaky)
    results = pl.render_clips(cfg, job, use_llm=False, log=QUIET)
    assert results[0].output is None and "explodiu" in results[0].error
    assert results[1].output is not None


def test_render_uses_user_edited_srt(analyzed):
    cfg, job, _ = analyzed
    pl.render_clips(cfg, job, indexes=[1], use_llm=False, log=QUIET)
    editable = cfg.output_dir / job / "clipe_01" / "legenda_editavel.srt"
    editable.write_text("1\n00:00:00,000 --> 00:00:02,000\nTexto *corrigido*\n", encoding="utf-8")
    pl.render_clips(cfg, job, indexes=[1], use_llm=False, log=QUIET)
    ass = (editable.parent / "legenda.ass").read_text(encoding="utf-8")
    assert "corrigido" in ass and "pt 0" not in ass


def test_render_generates_copy_with_source_and_license(analyzed):
    cfg, job, _ = analyzed
    _, factory = llm_factory(dict(COPY), dict(COPY))
    pl.render_clips(cfg, job, use_llm=True, llm_factory=factory, log=QUIET)
    txt = (cfg.output_dir / job / "clipe_02" / "copy.txt").read_text(encoding="utf-8")
    assert "https://youtu.be/x" in txt and "próprio" in txt and "1. t1" in txt


def test_render_unknown_job_explains(env):
    cfg, _, _ = env
    with pytest.raises(pl.PipelineError, match="analisar"):
        pl.render_clips(cfg, "naoexiste", log=QUIET)


def test_recut_clip_discards_old_subtitle_and_copy(analyzed, env):
    cfg, job, _ = analyzed
    _, video, _ = env
    pl.render_clips(cfg, job, indexes=[1], use_llm=False, log=QUIET)
    cdir = cfg.output_dir / job / "clipe_01"
    (cdir / "legenda_editavel.srt").write_text("1\n00:00:00,000 --> 00:00:02,000\nEDICAO ANTIGA\n", encoding="utf-8")
    (cdir / "copy.json").write_text("{}", encoding="utf-8")
    (cdir / "copy.txt").write_text("velho", encoding="utf-8")
    fake, factory = llm_factory({"clipes": [{"inicio": 4.0, "fim": 20.0, "motivo": "novo", "gancho": ""}]})
    pl.analyze(cfg, video, "https://youtu.be/x", "próprio", redo_clips=True, llm_factory=factory, log=QUIET)
    pl.render_clips(cfg, job, indexes=[1], use_llm=False, log=QUIET)
    assert "EDICAO ANTIGA" not in (cdir / "legenda_editavel.srt").read_text(encoding="utf-8")
    assert not (cdir / "copy.json").exists() and not (cdir / "copy.txt").exists()


def test_failed_render_then_recut_rebuilds_subtitle_for_new_span(analyzed, env, monkeypatch):
    cfg, job, _ = analyzed
    _, video, _ = env
    working = pl.render_clip
    monkeypatch.setattr(pl, "render_clip", lambda *a, **k: (_ for _ in ()).throw(pl.ToolError("falhou")))
    assert pl.render_clips(cfg, job, indexes=[1], use_llm=False, log=QUIET)[0].output is None
    cdir = cfg.output_dir / job / "clipe_01"
    (cdir / "legenda_editavel.srt").write_text("1\n00:00:00,000 --> 00:00:02,000\nEDICAO ANTIGA\n", encoding="utf-8")
    (cdir / "clipe.mp4").write_bytes(b"velho")
    _, factory = llm_factory({"clipes": [{"inicio": 4.0, "fim": 20.0, "motivo": "novo", "gancho": ""}]})
    pl.analyze(cfg, video, "f", "l", redo_clips=True, llm_factory=factory, log=QUIET)
    monkeypatch.setattr(pl, "render_clip", working)
    monkeypatch.setattr(pl, "render_clip", lambda *a, **k: a[-1].write_bytes(b"mp4"))
    assert pl.render_clips(cfg, job, indexes=[1], use_llm=False, log=QUIET)[0].output is not None
    assert "EDICAO ANTIGA" not in (cdir / "legenda_editavel.srt").read_text(encoding="utf-8")


def test_recut_removes_old_mp4_and_failed_verify_leaves_no_mp4(analyzed, monkeypatch):
    cfg, job, _ = analyzed
    pl.render_clips(cfg, job, indexes=[1], use_llm=False, log=QUIET)
    mp4 = cfg.output_dir / job / "clipe_01" / "clipe.mp4"
    assert mp4.is_file()

    def bad_verify(*a, **k):
        raise pl.RenderError("saida invalida")

    monkeypatch.setattr(pl, "verify_output", bad_verify)
    res = pl.render_clips(cfg, job, indexes=[1], use_llm=False, log=QUIET)[0]
    assert res.output is None and not mp4.exists()


def test_unknown_requested_indexes_are_logged(analyzed):
    cfg, job, _ = analyzed
    msgs = []
    pl.render_clips(cfg, job, indexes=[1, 9], use_llm=False, log=msgs.append)
    assert any("9" in m and "não existe" in m for m in msgs)


def test_oversized_file_is_rejected_before_hashing(env, monkeypatch):
    cfg, video, _ = env
    monkeypatch.setattr(pl, "file_sha256", lambda p: (_ for _ in ()).throw(AssertionError("hash antes do limite")))
    small = make_cfg(cfg.work_dir.parent, max_file_gb=1e-9)
    with pytest.raises(pl.MediaError, match="limite"):
        pl.analyze(small, video, "f", "l", log=QUIET)


def test_copy_stage_os_error_keeps_videos(analyzed, monkeypatch):
    cfg, job, _ = analyzed

    def boom(*a, **k):
        raise OSError("disco cheio")

    monkeypatch.setattr(pl, "generate_copy", boom)
    _, factory = llm_factory()
    results = pl.render_clips(cfg, job, use_llm=True, llm_factory=factory, log=QUIET)
    assert all(r.output for r in results) and len(results) == 2


def test_mkdir_failure_isolated_per_clip(analyzed):
    cfg, job, _ = analyzed
    (cfg.output_dir / job).mkdir(parents=True, exist_ok=True)
    (cfg.output_dir / job / "clipe_01").write_text("arquivo", encoding="utf-8")
    results = pl.render_clips(cfg, job, use_llm=False, log=QUIET)
    assert results[0].output is None and results[1].output is not None


def test_rerun_with_different_license_warns(env):
    cfg, video, _ = env
    _, first = llm_factory(translation_reply, CLIPS_REPLY)
    pl.analyze(cfg, video, "f", "l", llm_factory=first, log=QUIET)
    msgs = []
    _, second = llm_factory()
    pl.analyze(cfg, video, "f", "outra", llm_factory=second, log=msgs.append)
    assert any("Aviso" in m for m in msgs)
