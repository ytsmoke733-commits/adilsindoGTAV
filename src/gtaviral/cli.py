from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from gtaviral.config import Config, ConfigError, load_config
from gtaviral.doctor import check_environment
from gtaviral.llm import LLMError
from gtaviral.media import MediaError
from gtaviral.pipeline import PipelineError, analyze, load_clips, render_clips
from gtaviral.proc import ToolError
from gtaviral.render import FRAMINGS, PROFILES, RenderError
from gtaviral.subtitles import STYLES
from gtaviral.translate import TranslationError

KNOWN_ERRORS = (ConfigError, PipelineError, MediaError, ToolError, LLMError, TranslationError, RenderError)


def _int_list(value: str) -> list[int]:
    try:
        return [int(x) for x in value.split(",") if x.strip()]
    except ValueError:
        raise argparse.ArgumentTypeError("use números separados por vírgula, ex.: 1,3") from None


def _position(value: str) -> float:
    try:
        v = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError("use um número entre 0 e 1") from None
    if not 0.0 <= v <= 1.0:
        raise argparse.ArgumentTypeError("use um número entre 0 (esquerda) e 1 (direita)")
    return v


def _ts(t: float) -> str:
    m, s = divmod(t, 60)
    return f"{int(m):02d}:{s:04.1f}"


def _verificar(cfg: Config) -> int:
    checks = check_environment(cfg)
    for c in checks:
        print(f"[{'OK' if c.ok else 'FALTA'}] {c.name}: {c.detail}")
        if not c.ok:
            print(f"        como resolver: {c.fix}")
    return 0 if all(c.ok for c in checks) else 2


def _analisar(cfg: Config, args: argparse.Namespace) -> int:
    job = analyze(cfg, args.video, args.fonte, args.licenca, max_clips=args.max_clipes,
                  use_llm=not args.sem_llm, redo_clips=args.refazer_cortes)
    clips = load_clips(cfg, job)
    origem = "LLM" if clips and clips[0].source == "llm" else "regras de áudio"
    print(f"\nJob {job}: {len(clips)} clipe(s) sugerido(s) por {origem}\n")
    print(" #  início   fim      duração  motivo")
    for c in clips:
        print(f"{c.index:>2}  {_ts(c.start)}  {_ts(c.end)}  {c.end - c.start:>6.1f}s  {c.reason}")
        if c.hook:
            print(f"    gancho: {c.hook}")
    print(f"\nPróximo passo: gtaviral renderizar {job} [--clipes 1,3] [--enquadramento corte|desfoque] [--posicao 0.5]")
    return 0


def _renderizar(cfg: Config, args: argparse.Namespace) -> int:
    if not re.fullmatch(r"[0-9a-f]{12}", args.job):
        raise PipelineError(f"número de job inválido: {args.job!r} (são 12 caracteres hexadecimais; veja o analisar)")
    results = render_clips(cfg, args.job, indexes=args.clipes, framing=args.enquadramento, crop_x=args.posicao,
                           style=args.estilo, profile_name=args.perfil, use_llm=not args.sem_textos)
    print()
    for r in results:
        if r.output:
            extra = f"  ({len(r.warnings)} avisos em avisos.txt)" if r.warnings else ""
            print(f"[OK] clipe {r.index}: {r.output}{extra}")
        else:
            print(f"[FALHOU] clipe {r.index}: {r.error}")
    ok = sum(1 for r in results if r.output)
    print(f"\n{ok} de {len(results)} clipe(s) prontos. Para corrigir a legenda, edite legenda_editavel.srt "
          "na pasta do clipe e rode este comando de novo.")
    return 0 if ok == len(results) else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gtaviral",
        description="Clipes verticais legendados em PT-BR a partir de vídeos autorizados.",
    )
    parser.add_argument("--config", type=Path, default=Path("config.toml"))
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("verificar", help="confere se ffmpeg, whisper e o LLM estão instalados")

    a = sub.add_parser("analisar", help="transcreve, traduz e sugere cortes (não renderiza)")
    a.add_argument("video", type=Path)
    a.add_argument("--fonte", required=True, help="link ou origem do vídeo")
    a.add_argument("--licenca", required=True,
                   help='fundamento de uso, ex.: "próprio" ou "autorizado por @canal em 09/10/2026, print salvo"')
    a.add_argument("--max-clipes", type=int, default=3)
    a.add_argument("--sem-llm", action="store_true", help="cortes por regras de áudio; só serve para vídeo em português")
    a.add_argument("--refazer-cortes", action="store_true", help="escolhe os cortes de novo (a tradução é reaproveitada)")

    r = sub.add_parser("renderizar", help="gera os MP4 verticais com legenda")
    r.add_argument("job")
    r.add_argument("--clipes", type=_int_list, default=None, help="ex.: 1,3 (padrão: todos)")
    r.add_argument("--enquadramento", choices=FRAMINGS, default="corte")
    r.add_argument("--posicao", type=_position, default=0.5, help="só no corte: 0 = esquerda, 0.5 = centro, 1 = direita")
    r.add_argument("--estilo", choices=STYLES, default="destaque")
    r.add_argument("--perfil", choices=sorted(PROFILES), default="1080", help="1080 = 1080x1920; 1440 = 1440x2560")
    r.add_argument("--sem-textos", action="store_true", help="não gera títulos, descrições e hashtags")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        cfg = load_config(args.config)
        if args.cmd == "verificar":
            return _verificar(cfg)
        if args.cmd == "analisar":
            return _analisar(cfg, args)
        return _renderizar(cfg, args)
    except KeyboardInterrupt:
        print("Interrompido.", file=sys.stderr)
        return 130
    except KNOWN_ERRORS as e:
        print(f"ERRO: {e}", file=sys.stderr)
        return 1
    except (OSError, ValueError, KeyError) as e:
        print(f"ERRO: {e}", file=sys.stderr)
        print("Se o erro for num arquivo de work\\<job>, apague a pasta do job e rode analisar de novo.",
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
