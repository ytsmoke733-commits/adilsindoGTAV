# GTA Viral AI

Transforma um vídeo **autorizado** em clipes verticais 9:16 com legenda em PT-BR.
Tudo roda local e grátis (FFmpeg + whisper.cpp + llama.cpp).

## Instalação

1. Siga a Task 0 do plano `docs/superpowers/plans/2026-10-09-mvp-pipeline.md`.
2. `py -3.14 -m venv .venv` e `.venv\Scripts\python -m pip install -e .[dev]`
3. `Copy-Item config.example.toml config.toml`
4. `.venv\Scripts\gtaviral verificar` (tudo tem que dar `[OK]`)
