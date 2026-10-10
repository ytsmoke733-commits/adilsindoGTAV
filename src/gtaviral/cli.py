from __future__ import annotations

import argparse
import sys
from pathlib import Path

from gtaviral.config import Config, ConfigError, load_config
from gtaviral.doctor import check_environment


def _verificar(cfg: Config) -> int:
    checks = check_environment(cfg)
    for c in checks:
        print(f"[{'OK' if c.ok else 'FALTA'}] {c.name}: {c.detail}")
        if not c.ok:
            print(f"        como resolver: {c.fix}")
    return 0 if all(c.ok for c in checks) else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gtaviral",
        description="Clipes verticais legendados em PT-BR a partir de vídeos autorizados.",
    )
    parser.add_argument("--config", type=Path, default=Path("config.toml"))
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("verificar", help="confere se ffmpeg, whisper e o LLM estão instalados")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        cfg = load_config(args.config)
        return _verificar(cfg)
    except ConfigError as e:
        print(f"ERRO: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
