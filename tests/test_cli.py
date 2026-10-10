import pytest

from gtaviral import cli
from gtaviral.select_clips import ClipCandidate
from tests.test_doctor import make_cfg


def test_analisar_requires_source_and_license():
    with pytest.raises(SystemExit) as e:
        cli.main(["analisar", "video.mp4"])
    assert e.value.code == 2


def test_errors_are_reported_in_portuguese(tmp_path, capsys):
    assert cli.main(["--config", str(tmp_path / "nao.toml"), "verificar"]) == 1
    assert "config.example.toml" in capsys.readouterr().err


def test_int_list_and_position_parsers():
    assert cli._int_list("1, 3") == [1, 3]
    assert cli._position("0.25") == 0.25
    with pytest.raises(Exception):
        cli._position("2")


def test_analisar_prints_table_and_next_step(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(cli, "load_config", lambda path: make_cfg(tmp_path))
    monkeypatch.setattr(cli, "analyze", lambda cfg, video, fonte, licenca, **kw: "abc123")
    monkeypatch.setattr(cli, "load_clips", lambda cfg, job: [ClipCandidate(1, 4.0, 22.0, "carro voa", "Olha isso", "llm")])
    assert cli.main(["analisar", "v.mp4", "--fonte", "f", "--licenca", "l"]) == 0
    out = capsys.readouterr().out
    assert "abc123" in out and "00:04.0" in out and "carro voa" in out and "Olha isso" in out
    assert "gtaviral renderizar abc123" in out
