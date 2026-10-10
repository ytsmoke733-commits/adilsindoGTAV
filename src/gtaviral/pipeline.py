from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, ContextManager

from gtaviral.audio_events import AudioEvents, detect, events_from_dict, events_to_dict
from gtaviral.config import Config
from gtaviral.copywriter import format_copy, generate_copy
from gtaviral.llm import LLM, LlamaServer
from gtaviral.media import MediaError, MediaInfo, extract_audio, file_sha256, probe, validate, validate_size
from gtaviral.proc import ToolError
from gtaviral.render import PROFILES, Profile, RenderError, render_clip, verify_output
from gtaviral.select_clips import ClipCandidate, clips_from_dicts, clips_to_dicts, select_clips
from gtaviral.subtitles import build_cues, cps_warnings, parse_srt, to_ass, to_srt, to_vtt
from gtaviral.transcribe import Transcript, transcribe, transcript_from_dict, transcript_to_dict
from gtaviral.translate import (
    TranslatedSegment,
    TranslationError,
    translate,
    translated_from_dicts,
    translated_to_dicts,
)

Log = Callable[[str], None]
LLMFactory = Callable[[Config], ContextManager[LLM]]

__all__ = ["PipelineError", "ClipResult", "analyze", "load_clips", "render_clips", "ToolError", "TranslationError"]


CUT_MARKER = "corte.json"


class PipelineError(RuntimeError):
    pass


@dataclass(frozen=True)
class ClipResult:
    index: int
    output: Path | None
    error: str = ""
    warnings: tuple[str, ...] = ()


def _write_json(path: Path, data: Any) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _cached(path: Path, compute: Callable[[], Any]) -> Any:
    if path.is_file():
        return _read_json(path)
    data = compute()
    _write_json(path, data)
    return data


def _job_dir(cfg: Config, job: str) -> Path:
    return cfg.work_dir / job


def _clip_dir(cfg: Config, job: str, index: int) -> Path:
    return cfg.output_dir / job / f"clipe_{index:02d}"


def load_clips(cfg: Config, job: str) -> list[ClipCandidate]:
    path = _job_dir(cfg, job) / "clips.json"
    if not path.is_file():
        raise PipelineError(f"job {job} não encontrado ou não analisado — rode: gtaviral analisar <video>")
    return clips_from_dicts(_read_json(path))


def analyze(
    cfg: Config, video: Path, fonte: str, licenca: str, max_clips: int = 3, use_llm: bool = True,
    redo_clips: bool = False, llm_factory: LLMFactory = LlamaServer, log: Log = print,
) -> str:
    if not fonte.strip() or not licenca.strip():
        raise PipelineError("informe --fonte e --licenca: nenhum vídeo é processado sem registro de origem e autorização")
    video = video.resolve()
    if not video.is_file():
        raise PipelineError(f"arquivo não encontrado: {video}")

    validate_size(video.stat().st_size, cfg.max_file_gb)  # antes de gastar tempo no SHA-256
    log("Calculando a identidade do arquivo (SHA-256)...")
    sha = file_sha256(video)
    job = sha[:12]
    jd = _job_dir(cfg, job)
    jd.mkdir(parents=True, exist_ok=True)
    manifest = jd / "manifest.json"
    if manifest.is_file():
        log(f"Este vídeo já foi analisado (job {job}): reaproveitando as etapas prontas.")
        old = _read_json(manifest)
        if old.get("fonte") != fonte.strip() or old.get("licenca") != licenca.strip():
            log(f"Aviso: --fonte/--licenca diferentes do registro deste vídeo; mantido o registro original "
                f"(fonte={old.get('fonte')}, licenca={old.get('licenca')})")
    else:
        _write_json(manifest, {
            "id": job, "video": str(video), "sha256": sha, "fonte": fonte.strip(), "licenca": licenca.strip(),
            "criado_em": datetime.now().isoformat(timespec="seconds"),
        })

    info = MediaInfo(**_cached(jd / "probe.json", lambda: asdict(probe(cfg, video))))
    validate(info, video.stat().st_size, cfg.max_file_gb, cfg.max_duration_min)
    if not info.has_audio:
        raise PipelineError("o vídeo não tem áudio: não há fala para transcrever")
    log(f"Vídeo: {info.width}x{info.height}, {info.fps:.2f} fps, {info.duration:.1f}s")

    wav = jd / "audio.wav"
    if not wav.is_file():
        log("Extraindo o áudio...")
        extract_audio(cfg, video, wav)
    if not (jd / "transcript.json").is_file():
        log("Transcrevendo com whisper.cpp...")
    transcript = transcript_from_dict(
        _cached(jd / "transcript.json", lambda: transcript_to_dict(transcribe(cfg, wav, jd / "whisper")))
    )
    if not transcript.segments:
        raise PipelineError("nenhuma fala detectada no vídeo")
    log(f"Idioma detectado: {transcript.language} — {len(transcript.segments)} trechos de fala")
    events = events_from_dict(_cached(jd / "events.json", lambda: events_to_dict(detect(cfg, wav, info.duration))))
    log(f"Áudio: {len(events.loud_moments)} picos, {len(events.silences)} silêncios")

    if redo_clips:
        (jd / "clips.json").unlink(missing_ok=True)
    needs_llm = use_llm and not ((jd / "translation.json").is_file() and (jd / "clips.json").is_file())
    if needs_llm:
        log("Subindo o LLM local (llama.cpp)...")
        with llm_factory(cfg) as llm:
            _analyze_text(jd, transcript, events, info, llm, max_clips, log)
    else:
        _analyze_text(jd, transcript, events, info, None, max_clips, log)
    return job


def _analyze_text(
    jd: Path, transcript: Transcript, events: AudioEvents, info: MediaInfo, llm: LLM | None, max_clips: int, log: Log
) -> None:
    if not (jd / "translation.json").is_file():
        log("Traduzindo para PT-BR...")
    translated = translated_from_dicts(
        _cached(jd / "translation.json", lambda: translated_to_dicts(translate(transcript, llm)))
    )
    if not (jd / "clips.json").is_file():
        log("Escolhendo os cortes...")
    _cached(jd / "clips.json", lambda: clips_to_dicts(select_clips(translated, events, info.duration, llm, max_clips)))


def render_clips(
    cfg: Config, job: str, indexes: list[int] | None = None, framing: str = "corte", crop_x: float = 0.5,
    style: str = "destaque", profile_name: str = "1080", use_llm: bool = True,
    llm_factory: LLMFactory = LlamaServer, log: Log = print,
) -> list[ClipResult]:
    clips = load_clips(cfg, job)
    jd = _job_dir(cfg, job)
    manifest = _read_json(jd / "manifest.json")
    info = MediaInfo(**_read_json(jd / "probe.json"))
    translated = translated_from_dicts(_read_json(jd / "translation.json"))
    if profile_name not in PROFILES:
        raise PipelineError(f"perfil desconhecido: {profile_name} (use {', '.join(PROFILES)})")
    profile = PROFILES[profile_name]
    missing = sorted(set(indexes or []) - {c.index for c in clips})
    if missing:
        log(f"Aviso: clipe(s) {', '.join(map(str, missing))} não existe(m) neste job (tem {len(clips)}); ignorado(s)")
    chosen = [c for c in clips if indexes is None or c.index in indexes]
    if not chosen:
        raise PipelineError(f"nenhum clipe com esses números; o job tem {len(clips)}")
    src = Path(manifest["video"])
    if not src.is_file():
        raise PipelineError(f"o vídeo original não está mais em {src}")

    results = [
        _render_one(cfg, job, clip, src, info, translated, profile, framing, crop_x, style, log) for clip in chosen
    ]
    done = [clip for clip, res in zip(chosen, results) if res.output]
    if use_llm and done:
        _write_copies(cfg, job, done, translated, manifest, llm_factory, log)
    return results


def _render_one(
    cfg: Config, job: str, clip: ClipCandidate, src: Path, info: MediaInfo, translated: list[TranslatedSegment],
    profile: Profile, framing: str, crop_x: float, style: str, log: Log,
) -> ClipResult:
    cdir = _clip_dir(cfg, job, clip.index)
    try:
        cdir.mkdir(parents=True, exist_ok=True)
        _discard_if_recut(cdir, clip, log)
        editable = cdir / "legenda_editavel.srt"
        if editable.is_file():
            cues = parse_srt(editable.read_text(encoding="utf-8"))
            log(f"Clipe {clip.index}: usando as suas correções de {editable.name}")
        else:
            cues = build_cues(translated, clip.start, clip.end, style)
            editable.write_text(to_srt(cues, mark=True), encoding="utf-8")
            _write_json(cdir / CUT_MARKER, {"inicio": clip.start, "fim": clip.end})
        (cdir / "legenda.srt").write_text(to_srt(cues), encoding="utf-8")
        (cdir / "legenda.vtt").write_text(to_vtt(cues), encoding="utf-8")
        (cdir / "legenda.ass").write_text(
            to_ass(cues, profile.width, profile.height, cfg.subtitle_font, style), encoding="utf-8"
        )
        out = cdir / "clipe.mp4"
        log(f"Clipe {clip.index}: renderizando {clip.end - clip.start:.1f}s "
            f"({framing}, {profile.width}x{profile.height})...")
        try:
            render_clip(cfg, src, info, clip.start, clip.end, profile, framing, crop_x, "legenda.ass", out)
            verify_output(cfg, out, profile, info.fps)
        except BaseException:
            out.unlink(missing_ok=True)  # nunca deixar um clipe.mp4 sem verificacao
            raise
        warnings = tuple(cps_warnings(cues))
        (cdir / "avisos.txt").write_text("".join(w + "\n" for w in warnings), encoding="utf-8")
        _write_json(cdir / "render.json", {
            "enquadramento": framing, "posicao": crop_x, "estilo": style, "perfil": profile.name,
            "inicio": clip.start, "fim": clip.end,
        })
        log(f"Clipe {clip.index}: pronto em {out}" + (f" ({len(warnings)} avisos de leitura)" if warnings else ""))
        return ClipResult(clip.index, out, "", warnings)
    except (ToolError, RenderError, MediaError, ValueError, OSError) as e:
        log(f"Clipe {clip.index} FALHOU: {e}")
        return ClipResult(clip.index, None, str(e))


def _discard_if_recut(cdir: Path, clip: ClipCandidate, log: Log) -> None:
    # corte.json nasce junto com a legenda editavel; render.json so serve a saidas de versoes antigas
    marker = next((m for m in (cdir / CUT_MARKER, cdir / "render.json") if m.is_file()), None)
    if marker is None:
        return
    try:
        prev = _read_json(marker)
        same = prev.get("inicio") == clip.start and prev.get("fim") == clip.end
    except (OSError, json.JSONDecodeError):
        same = False
    if not same:
        for name in ("legenda_editavel.srt", "copy.json", "copy.txt", "clipe.mp4", CUT_MARKER, "render.json"):
            (cdir / name).unlink(missing_ok=True)
        log(f"Clipe {clip.index}: o corte mudou; legenda e textos antigos descartados")


def _recent_titles(cfg: Config) -> list[str]:
    titles: list[str] = []
    for path in sorted(cfg.output_dir.glob("*/clipe_*/copy.json"), key=lambda p: p.stat().st_mtime):
        try:
            titles += list(_read_json(path).get("titulos", []))
        except (OSError, json.JSONDecodeError):
            continue
    return titles[-20:]


def _write_copies(
    cfg: Config, job: str, done: list[ClipCandidate], translated: list[TranslatedSegment], manifest: dict,
    llm_factory: LLMFactory, log: Log,
) -> None:
    pending = [c for c in done if not (_clip_dir(cfg, job, c.index) / "copy.json").is_file()]
    if not pending:
        return
    log("Gerando títulos, descrições e hashtags (LLM local)...")
    try:
        with llm_factory(cfg) as llm:
            for clip in pending:
                cdir = _clip_dir(cfg, job, clip.index)
                text = " ".join(s.text for s in translated if s.end > clip.start and s.start < clip.end)
                try:
                    data = generate_copy(llm, text, clip.reason, _recent_titles(cfg))
                    (cdir / "copy.txt").write_text(format_copy(data, manifest["fonte"], manifest["licenca"]),
                                                   encoding="utf-8")
                    _write_json(cdir / "copy.json", data)  # marcador de conclusão: por último
                except Exception as e:  # noqa: BLE001 - textos nunca derrubam vídeo pronto
                    log(f"Clipe {clip.index}: textos não gerados ({e}); o vídeo está pronto mesmo assim")
    except Exception as e:  # noqa: BLE001
        log(f"Textos não gerados: {e}. Os vídeos estão prontos; rode o renderizar de novo para tentar outra vez.")
