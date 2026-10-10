from dataclasses import replace

import pytest

from gtaviral.media import probe
from gtaviral.pipeline import analyze, render_clips


@pytest.mark.integration
def test_end_to_end_on_synthetic_video(real_cfg, speech_video, tmp_path):
    cfg = replace(real_cfg, work_dir=tmp_path / "work", output_dir=tmp_path / "saida")
    job = analyze(cfg, speech_video, "teste sintético", "próprio (gerado no teste)", max_clips=1)
    results = render_clips(cfg, job, framing="desfoque")
    assert results and all(r.output for r in results), [r.error for r in results]
    out = results[0].output
    info = probe(cfg, out)
    assert (info.width, info.height) == (1080, 1920)
    srt = (out.parent / "legenda.srt").read_text(encoding="utf-8").lower()
    assert any(w in srt for w in ("carro", "ponte", "polícia", "policia", "mano"))
    assert (out.parent / "copy.txt").is_file()
