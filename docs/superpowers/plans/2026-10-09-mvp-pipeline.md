# GTA Viral AI — Plano 1: MVP do pipeline (vídeo autorizado → clipe vertical legendado) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Uma linha de comando que recebe um vídeo autorizado e entrega, por clipe, um MP4 vertical 9:16 com legenda PT-BR embutida, os arquivos SRT/VTT, uma legenda editável e os textos para postar. Tudo grátis e rodando local.

**Architecture:** Pacote Python só com a biblioteca padrão, que orquestra três executáveis externos: **FFmpeg** (vídeo e áudio), **whisper.cpp compilado com Vulkan** (transcrição na RX 6600) e **llama.cpp com Vulkan** rodando um LLM local (Qwen2.5-7B-Instruct), usado para traduzir, escolher os cortes e escrever títulos. Cada vídeo vira um "job" identificado pelo hash do arquivo. Cada etapa grava o próprio resultado em JSON. Quando uma etapa já foi feita, ela é pulada, o que dá retomada e prevenção de duplicata. O fluxo tem dois comandos: `analisar` (para antes de renderizar e mostra os cortes sugeridos) e `renderizar` (gera os clipes escolhidos).

**Tech Stack:** Python 3.14 (stdlib: argparse, tomllib, json, subprocess, urllib, dataclasses), pytest, FFmpeg 9 (Gyan full, com libass), whisper.cpp v1.9.5 + Vulkan SDK, llama.cpp (release Vulkan x64), modelos `ggml-large-v3-turbo-q8_0.bin` e `Qwen2.5-7B-Instruct-Q4_K_M.gguf`.

**Spec:** `docs/spec/prompt-original.md` (prompt "GTA VIRAL AI" do usuário). Este plano cobre a "Prioridade máxima" da seção 18 e partes das seções 4, 5, 6, 8, 14 e 15. O resto fica no roteiro do fim do arquivo.

## Decisões já tomadas (com o usuário, 09/10/2026)

| Tema | Decisão | Motivo |
|---|---|---|
| Transcrição | whisper.cpp compilado com Vulkan | Grátis e acelera na RX 6600. A release oficial não traz binário Vulkan para Windows (só CPU/CUDA), então compilamos. O binário CPU da release é o plano B, com a mesma linha de comando. |
| Tradução, cortes e textos | LLM local via llama.cpp (Vulkan) | O usuário pediu opção grátis. Um LLM local (~4,5 GB) traduz gíria e humor bem melhor que tradutor automático (Argos) e também escolhe cortes e escreve títulos. Fica plugável: um provedor Claude API pode entrar depois com a mesma interface `chat_json`. |
| Horizontal → vertical | Os dois modos, escolhidos por clipe | `corte` (faixa vertical cheia, posição ajustável de 0 a 1) e `desfoque` (vídeo inteiro no meio, fundo borrado). |
| Interface | Só linha de comando neste plano | A central de revisão web é o Plano 2. Aqui a revisão é: ver o MP4, editar `legenda_editavel.srt`, rodar `renderizar` de novo. |

## Global Constraints

- Windows 10, Python 3.14 (`requires-python = ">=3.12"`). **Nenhuma dependência de runtime fora da stdlib**; `pytest` só para desenvolvimento.
- Nada pago no MVP: sem API externa e sem chave.
- O LLM escuta em `127.0.0.1:8089`. **Nunca usar a 8080**: nesta máquina ela é da Steam (`steamwebhelper`), que nunca deve ser encerrada.
- VRAM de 8 GB: Whisper e LLM **nunca** rodam juntos. O LLM só sobe depois da transcrição e é encerrado antes do render (se foi o sistema que o subiu).
- Saída padrão: 1080×1920, H.264 High, `yuv420p`, CRF 18, AAC 192k 48 kHz, MP4 com `+faststart`, **fps da origem preservado** (sem filtro de fps). Perfil opcional `1440` (1440×2560): o Instagram entrega até esse nível, conforme medido pelo usuário.
- **Nunca esticar a imagem.** Enquadramento `corte` ou `desfoque`, sem tarja preta.
- Todo job exige `--fonte` e `--licenca`, gravados no `manifest.json`. Sem isso o sistema recusa o vídeo (spec, seção 14).
- Nenhuma mensagem diz que algo deu certo sem o arquivo existir e ser conferido com `ffprobe` (`verify_output`).
- Mensagens ao usuário em PT-BR; identificadores de código em inglês.
- Duração máxima padrão do vídeo de entrada: 20 min (cabe no contexto de 16k tokens do LLM). Vídeo mais longo fica para um plano futuro.
- Todo commit termina com a linha `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Rodar `.bat` em terminal `cmd`/PowerShell, não no Git Bash: nesta máquina, o Git Bash resolve o ambiente do Visual Studio de outro jeito.

## Estrutura de arquivos

```
D:\OutrosProjetos\gta-viral-ai\
  pyproject.toml              pacote, script `gtaviral`, config do pytest
  config.example.toml         modelo de config (copiar para config.toml, que é ignorado no git)
  .gitignore
  README.md                   instalação e uso
  scripts\
    build_whisper_vulkan.bat  compila whisper.cpp com Vulkan -> tools\whisper\
    get_tools.ps1             baixa llama.cpp Vulkan e os dois modelos -> tools\
  tools\                      (git-ignored) binários e modelos
  src\gtaviral\
    __init__.py
    proc.py            run(): executa ferramenta externa e levanta ToolError com o fim do stderr
    config.py          Config, load_config(), resolve_tool()
    doctor.py          check_environment(): o que está instalado e como instalar o que falta
    media.py           MediaInfo, probe(), validate(), extract_audio(), file_sha256()
    transcribe.py      Word/Segment/Transcript, parse_whisper_json(), transcribe()
    audio_events.py    AudioEvents, detecção de silêncios e picos de volume
    llm.py             LLM (Protocol), LlamaClient, LlamaServer (sobe e desce o llama-server)
    translate.py       TranslatedSegment, translate()
    select_clips.py    ClipCandidate, rule_candidates(), llm_candidates(), select_clips()
    subtitles.py       Cue, build_cues(), SRT/VTT/ASS, parse_srt(), cps_warnings()
    render.py          Profile, filtergraph de corte/desfoque, render_clip(), verify_output()
    copywriter.py      generate_copy(), format_copy()
    pipeline.py        analyze(), render_clips(): jobs, cache por etapa, isolamento de falha
    cli.py             gtaviral verificar | analisar | renderizar
  tests\
    conftest.py        fixtures de integração (vídeo sintético com fala gerada pela voz Zira do Windows)
    fakes.py           FakeLLM
    fixtures\whisper_sample.json
    fixtures\tts.ps1
    test_*.py          um arquivo por módulo
  work\<job>\          (git-ignored) manifest.json, probe.json, audio.wav, transcript.json, events.json,
                       translation.json, clips.json
  saida\<job>\clipe_NN\ (git-ignored) clipe.mp4, legenda_editavel.srt, legenda.srt, legenda.vtt,
                       legenda.ass, avisos.txt, render.json, copy.json, copy.txt
```

Testes: os unitários rodam sem nenhuma ferramenta instalada (`pytest`). Os de integração levam `@pytest.mark.integration` e rodam com `pytest -m integration`. Precisam da Task 0 concluída e de um `config.toml` na raiz.

---

### Task 0: Ferramentas externas (FFmpeg, whisper.cpp Vulkan, llama.cpp Vulkan, modelos)

Sem TDD: é instalação. Cada passo tem um comando de conferência com a saída esperada.

**Files:**
- Create: `scripts/build_whisper_vulkan.bat`
- Create: `scripts/get_tools.ps1`

- [ ] **Step 1: Instalar FFmpeg (build completo, com libass) e Vulkan SDK**

```powershell
winget install --id Gyan.FFmpeg -e --accept-package-agreements --accept-source-agreements
winget install --id KhronosGroup.VulkanSDK -e --accept-package-agreements --accept-source-agreements
```

Feche e abra o terminal (o PATH e o `VULKAN_SDK` só valem em terminal novo). Confira:

```powershell
ffmpeg -hide_banner -filters | Select-String " subtitles "
$env:VULKAN_SDK
```
Esperado: uma linha com `subtitles  V->V` e um caminho tipo `C:\VulkanSDK\1.4.363.0`.

- [ ] **Step 2: Criar `scripts/build_whisper_vulkan.bat`**

```bat
@echo off
setlocal
set "ROOT=%~dp0.."
set "VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
if not exist "%VSWHERE%" (echo [ERRO] vswhere nao encontrado & exit /b 1)

rem Capturar com for /f falha em silencio nesta maquina: redirecionar para arquivo.
"%VSWHERE%" -latest -products * -property installationPath > "%TEMP%\gtaviral_vsp.txt"
set /p VS=<"%TEMP%\gtaviral_vsp.txt"
if not exist "%VS%\VC\Auxiliary\Build\vcvars64.bat" (echo [ERRO] vcvars64.bat nao encontrado em "%VS%" & exit /b 1)
call "%VS%\VC\Auxiliary\Build\vcvars64.bat" || exit /b 1

if "%VULKAN_SDK%"=="" (echo [ERRO] VULKAN_SDK vazio: instale o Vulkan SDK e abra um terminal novo & exit /b 1)

set "SRC=%ROOT%\tools\src\whisper.cpp"
if not exist "%SRC%" (
  git clone --depth 1 --branch v1.9.5 https://github.com/ggml-org/whisper.cpp "%SRC%" || exit /b 1
)

rem Usa o CMake do VS: existe um cmake do MinGW (WinLibs) no PATH que escolheria o compilador errado.
set "CMAKE=%VS%\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe"
"%CMAKE%" -S "%SRC%" -B "%SRC%\build" -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_COMPILER=cl -DCMAKE_CXX_COMPILER=cl -DGGML_VULKAN=1 -DWHISPER_BUILD_TESTS=OFF || exit /b 1
"%CMAKE%" --build "%SRC%\build" -j || exit /b 1

if not exist "%ROOT%\tools\whisper" mkdir "%ROOT%\tools\whisper"
copy /y "%SRC%\build\bin\*.exe" "%ROOT%\tools\whisper\" >nul || exit /b 1
copy /y "%SRC%\build\bin\*.dll" "%ROOT%\tools\whisper\" >nul 2>nul
echo [OK] whisper-cli em %ROOT%\tools\whisper
```

- [ ] **Step 3: Compilar**

Num terminal `cmd` (não Git Bash), na raiz do projeto:
```
scripts\build_whisper_vulkan.bat
```
Esperado: termina com `[OK] whisper-cli em ...\tools\whisper`.

Se a compilação Vulkan falhar e não houver correção rápida, use o **plano B**: baixe `whisper-bin-x64.zip` da release `b5454` em https://github.com/ggml-org/whisper.cpp/releases e extraia os `.exe`/`.dll` em `tools\whisper\`. A interface é a mesma; só fica mais lento, na CPU. Anote no README qual dos dois foi usado.

- [ ] **Step 4: Criar `scripts/get_tools.ps1`**

```powershell
$ErrorActionPreference = 'Stop'
$root  = Split-Path $PSScriptRoot -Parent
$tools = Join-Path $root 'tools'
New-Item -ItemType Directory -Force (Join-Path $tools 'llama'), (Join-Path $tools 'models') | Out-Null

function Get-File([string]$url, [string]$dest) {
    if (Test-Path $dest) { Write-Host "ja existe: $dest"; return }
    curl.exe -L --fail -o "$dest.part" $url
    if ($LASTEXITCODE -ne 0) { throw "download falhou ($LASTEXITCODE): $url" }
    Move-Item "$dest.part" $dest
}

# llama.cpp com Vulkan (ultima release)
if (-not (Test-Path (Join-Path $tools 'llama\llama-server.exe'))) {
    $rel   = Invoke-RestMethod 'https://api.github.com/repos/ggml-org/llama.cpp/releases/latest'
    $asset = $rel.assets | Where-Object { $_.name -like 'llama-*-bin-win-vulkan-x64.zip' } | Select-Object -First 1
    if (-not $asset) { throw 'a release mais recente do llama.cpp nao tem binario Vulkan x64' }
    $zip = Join-Path $env:TEMP $asset.name
    Get-File $asset.browser_download_url $zip
    Expand-Archive -Force $zip (Join-Path $tools 'llama')
    $nested = Get-ChildItem (Join-Path $tools 'llama') -Recurse -Filter 'llama-server.exe' | Select-Object -First 1
    if (-not $nested) { throw 'llama-server.exe nao veio no zip' }
    if ($nested.DirectoryName -ne (Join-Path $tools 'llama')) {
        Get-ChildItem $nested.DirectoryName | Move-Item -Destination (Join-Path $tools 'llama') -Force
    }
}

# Modelos
Get-File 'https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo-q8_0.bin' (Join-Path $tools 'models\ggml-large-v3-turbo-q8_0.bin')
Get-File 'https://huggingface.co/bartowski/Qwen2.5-7B-Instruct-GGUF/resolve/main/Qwen2.5-7B-Instruct-Q4_K_M.gguf' (Join-Path $tools 'models\Qwen2.5-7B-Instruct-Q4_K_M.gguf')
Write-Host '[OK] ferramentas em' $tools
```

- [ ] **Step 5: Rodar e conferir**

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\get_tools.ps1
tools\whisper\whisper-cli.exe -m tools\models\ggml-large-v3-turbo-q8_0.bin -f tools\src\whisper.cpp\samples\jfk.wav -l auto
```
Esperado: o log mostra `ggml_vulkan: Found 1 Vulkan devices` com `AMD Radeon RX 6600` (não aparece no plano B) e a transcrição contém `And so my fellow Americans`.

```powershell
$p = Start-Process tools\llama\llama-server.exe -ArgumentList '-m','tools\models\Qwen2.5-7B-Instruct-Q4_K_M.gguf','--host','127.0.0.1','--port','8089','-ngl','99','-c','16384' -PassThru
# espere ~30 s
curl.exe -s http://127.0.0.1:8089/health
Stop-Process -Id $p.Id
```
Esperado: `{"status":"ok"}`.

Os commits desta task entram na Task 1, junto com o `git init`.

---

### Task 1: Esqueleto do projeto, config e `gtaviral verificar`

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `config.example.toml`, `README.md`
- Create: `src/gtaviral/__init__.py`, `src/gtaviral/proc.py`, `src/gtaviral/config.py`, `src/gtaviral/doctor.py`
- Create: `src/gtaviral/cli.py` (só o subcomando `verificar` nesta task)
- Test: `tests/test_config.py`, `tests/test_doctor.py`

**Interfaces:**
- Produces:
  - `proc.ToolError(RuntimeError)`
  - `proc.run(cmd: list, cwd: Path | None = None, timeout: float | None = None) -> subprocess.CompletedProcess[str]`
  - `config.ConfigError(RuntimeError)`
  - `config.Config` (dataclass frozen): `ffmpeg: str, ffprobe: str, whisper_cli: str, whisper_model: Path, llama_server: str, llm_model: Path, llm_port: int, work_dir: Path, output_dir: Path, max_file_gb: float, max_duration_min: float, subtitle_font: str, whisper_threads: int`
  - `config.load_config(path: Path) -> Config`
  - `config.resolve_tool(value: str) -> Path | None`
  - `doctor.Check` (dataclass frozen): `name: str, ok: bool, detail: str, fix: str = ""`
  - `doctor.check_environment(cfg: Config) -> list[Check]`
  - `cli.main(argv: list[str] | None = None) -> int`

- [ ] **Step 1: Criar repositório, venv e arquivos de projeto**

```powershell
cd D:\OutrosProjetos\gta-viral-ai
git init
py -3.14 -m venv .venv
```

`pyproject.toml`:
```toml
[build-system]
requires = ["setuptools>=69"]
build-backend = "setuptools.build_meta"

[project]
name = "gtaviral"
version = "0.1.0"
description = "Clipes verticais legendados em PT-BR a partir de videos autorizados"
requires-python = ">=3.12"
dependencies = []

[project.optional-dependencies]
dev = ["pytest>=8"]

[project.scripts]
gtaviral = "gtaviral.cli:main"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
markers = ["integration: precisa de ffmpeg, whisper e llama instalados (Task 0) e de config.toml"]
addopts = "-m 'not integration'"
```

`.gitignore`:
```
.venv/
__pycache__/
*.egg-info/
tools/
work/
saida/
config.toml
.pytest_cache/
```

`config.example.toml`:
```toml
# Copie para config.toml. Caminhos relativos sao relativos a este arquivo.
[tools]
ffmpeg = "ffmpeg"                  # nome no PATH ou caminho
ffprobe = "ffprobe"
whisper_cli = "tools/whisper/whisper-cli.exe"
whisper_model = "tools/models/ggml-large-v3-turbo-q8_0.bin"
whisper_threads = 8
llama_server = "tools/llama/llama-server.exe"
llm_model = "tools/models/Qwen2.5-7B-Instruct-Q4_K_M.gguf"

[llm]
port = 8089                        # NAO usar 8080: e da Steam nesta maquina

[paths]
work_dir = "work"
output_dir = "saida"

[limits]
max_file_gb = 4.0
max_duration_min = 20

[subtitles]
font = "Arial Black"
```

`src/gtaviral/__init__.py`:
```python
"""GTA Viral AI: clipes verticais legendados em PT-BR a partir de vídeos autorizados."""
```

```powershell
.venv\Scripts\python -m pip install -e .[dev]
Copy-Item config.example.toml config.toml
```

- [ ] **Step 2: Escrever os testes que falham**

`tests/test_config.py`:
```python
from pathlib import Path

import pytest

from gtaviral.config import ConfigError, load_config, resolve_tool

MINIMAL = """
[tools]
whisper_cli = "tools/whisper/whisper-cli.exe"
whisper_model = "tools/models/w.bin"
llama_server = "tools/llama/llama-server.exe"
llm_model = "tools/models/m.gguf"
"""


def test_load_config_resolves_relative_paths_against_config_dir(tmp_path: Path):
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text(MINIMAL, encoding="utf-8")
    cfg = load_config(cfg_file)
    assert cfg.whisper_model == (tmp_path / "tools/models/w.bin").resolve()
    assert cfg.whisper_cli == str((tmp_path / "tools/whisper/whisper-cli.exe").resolve())
    assert cfg.ffmpeg == "ffmpeg"  # nome solto continua nome, para ser achado no PATH
    assert cfg.llm_port == 8089
    assert cfg.work_dir == (tmp_path / "work").resolve()
    assert cfg.max_duration_min == 20


def test_load_config_missing_file_explains_what_to_do(tmp_path: Path):
    with pytest.raises(ConfigError, match="config.example.toml"):
        load_config(tmp_path / "config.toml")


def test_load_config_missing_required_field(tmp_path: Path):
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text("[tools]\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="whisper_cli"):
        load_config(cfg_file)


def test_resolve_tool_finds_file_and_rejects_unknown(tmp_path: Path):
    exe = tmp_path / "x.exe"
    exe.write_bytes(b"")
    assert resolve_tool(str(exe)) == exe
    assert resolve_tool("nao-existe-gtaviral-123") is None
```

`tests/test_doctor.py`:
```python
from pathlib import Path

from gtaviral.config import Config
from gtaviral.doctor import check_environment


def make_cfg(tmp_path: Path, **over) -> Config:
    base = dict(
        ffmpeg="nao-existe-ffmpeg-123",
        ffprobe="nao-existe-ffprobe-123",
        whisper_cli=str(tmp_path / "whisper-cli.exe"),
        whisper_model=tmp_path / "w.bin",
        llama_server=str(tmp_path / "llama-server.exe"),
        llm_model=tmp_path / "m.gguf",
        llm_port=8089,
        work_dir=tmp_path / "work",
        output_dir=tmp_path / "saida",
        max_file_gb=4.0,
        max_duration_min=20,
        subtitle_font="Arial Black",
        whisper_threads=8,
    )
    base.update(over)
    return Config(**base)


def test_everything_missing_gives_a_fix_for_each(tmp_path: Path):
    checks = check_environment(make_cfg(tmp_path))
    failing = [c for c in checks if not c.ok]
    names = {c.name for c in failing}
    assert {"ffmpeg", "ffprobe", "whisper-cli", "modelo do Whisper", "llama-server", "modelo do LLM"} <= names
    assert all(c.fix for c in failing)
    assert any("winget install Gyan.FFmpeg" in c.fix for c in failing)


def test_present_model_files_pass(tmp_path: Path):
    (tmp_path / "w.bin").write_bytes(b"x")
    (tmp_path / "m.gguf").write_bytes(b"x")
    checks = {c.name: c for c in check_environment(make_cfg(tmp_path))}
    assert checks["modelo do Whisper"].ok
    assert checks["modelo do LLM"].ok
```

- [ ] **Step 3: Rodar e ver falhar**

Run: `.venv\Scripts\python -m pytest tests/test_config.py tests/test_doctor.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'gtaviral.config'`

- [ ] **Step 4: Implementar**

`src/gtaviral/proc.py`:
```python
from __future__ import annotations

import subprocess
from pathlib import Path


class ToolError(RuntimeError):
    """Uma ferramenta externa (ffmpeg, whisper-cli...) terminou com erro."""


def run(cmd: list, cwd: Path | None = None, timeout: float | None = None) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        [str(c) for c in cmd],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    if proc.returncode != 0:
        tail = "\n".join(proc.stderr.strip().splitlines()[-15:])
        raise ToolError(f"{Path(str(cmd[0])).name} saiu com código {proc.returncode}:\n{tail}")
    return proc
```

`src/gtaviral/config.py`:
```python
from __future__ import annotations

import shutil
import tomllib
from dataclasses import dataclass
from pathlib import Path


class ConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class Config:
    ffmpeg: str
    ffprobe: str
    whisper_cli: str
    whisper_model: Path
    llama_server: str
    llm_model: Path
    llm_port: int
    work_dir: Path
    output_dir: Path
    max_file_gb: float
    max_duration_min: float
    subtitle_font: str
    whisper_threads: int


def _abs(base: Path, value: str) -> Path:
    p = Path(value)
    return p if p.is_absolute() else (base / p).resolve()


def _tool(base: Path, value: str) -> str:
    """Nome solto (ex. 'ffmpeg') fica como está para ser achado no PATH; caminho vira absoluto."""
    if "/" in value or "\\" in value:
        return str(_abs(base, value))
    return value


def load_config(path: Path) -> Config:
    if not path.is_file():
        raise ConfigError(f"config não encontrada: {path} (copie config.example.toml para config.toml)")
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    base = path.resolve().parent
    tools = data.get("tools", {})
    paths = data.get("paths", {})
    limits = data.get("limits", {})
    try:
        return Config(
            ffmpeg=_tool(base, tools.get("ffmpeg", "ffmpeg")),
            ffprobe=_tool(base, tools.get("ffprobe", "ffprobe")),
            whisper_cli=_tool(base, tools["whisper_cli"]),
            whisper_model=_abs(base, tools["whisper_model"]),
            llama_server=_tool(base, tools["llama_server"]),
            llm_model=_abs(base, tools["llm_model"]),
            llm_port=int(data.get("llm", {}).get("port", 8089)),
            work_dir=_abs(base, paths.get("work_dir", "work")),
            output_dir=_abs(base, paths.get("output_dir", "saida")),
            max_file_gb=float(limits.get("max_file_gb", 4.0)),
            max_duration_min=float(limits.get("max_duration_min", 20)),
            subtitle_font=str(data.get("subtitles", {}).get("font", "Arial Black")),
            whisper_threads=int(tools.get("whisper_threads", 8)),
        )
    except KeyError as e:
        raise ConfigError(f"campo obrigatório ausente em [tools]: {e.args[0]}") from e


def resolve_tool(value: str) -> Path | None:
    p = Path(value)
    if p.is_file():
        return p
    found = shutil.which(value)
    return Path(found) if found else None
```

`src/gtaviral/doctor.py`:
```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from gtaviral.config import Config, resolve_tool
from gtaviral.proc import ToolError, run

FIX_FFMPEG = "winget install Gyan.FFmpeg (depois abra um terminal novo)"
FIX_WHISPER = r"rode scripts\build_whisper_vulkan.bat (ou o plano B do README)"
FIX_TOOLS = r"rode: powershell -ExecutionPolicy Bypass -File scripts\get_tools.ps1"


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str
    fix: str = ""


def _tool_check(name: str, value: str, fix: str) -> tuple[Check, Path | None]:
    path = resolve_tool(value)
    if path is None:
        return Check(name, False, f"não encontrado: {value}", fix), None
    return Check(name, True, str(path)), path


def _file_check(name: str, path: Path, fix: str) -> Check:
    if path.is_file():
        return Check(name, True, f"{path} ({path.stat().st_size / 1024**2:.0f} MB)")
    return Check(name, False, f"não encontrado: {path}", fix)


def check_environment(cfg: Config) -> list[Check]:
    checks: list[Check] = []
    ffmpeg_check, ffmpeg = _tool_check("ffmpeg", cfg.ffmpeg, FIX_FFMPEG)
    checks.append(ffmpeg_check)
    if ffmpeg is not None:
        try:
            filters = run([ffmpeg, "-hide_banner", "-filters"]).stdout
            has_ass = any(line.split()[1:2] == ["subtitles"] for line in filters.splitlines())
        except ToolError:
            has_ass = False
        checks.append(Check(
            "ffmpeg com libass",
            has_ass,
            "filtro 'subtitles' presente" if has_ass else "filtro 'subtitles' ausente (legenda embutida não funciona)",
            "" if has_ass else FIX_FFMPEG,
        ))
    checks.append(_tool_check("ffprobe", cfg.ffprobe, FIX_FFMPEG)[0])
    checks.append(_tool_check("whisper-cli", cfg.whisper_cli, FIX_WHISPER)[0])
    checks.append(_file_check("modelo do Whisper", cfg.whisper_model, FIX_TOOLS))
    checks.append(_tool_check("llama-server", cfg.llama_server, FIX_TOOLS)[0])
    checks.append(_file_check("modelo do LLM", cfg.llm_model, FIX_TOOLS))
    return checks
```

`src/gtaviral/cli.py` (versão inicial; a Task 11 acrescenta `analisar` e `renderizar`):
```python
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
```

`README.md` (a Task 12 completa):
```markdown
# GTA Viral AI

Transforma um vídeo **autorizado** em clipes verticais 9:16 com legenda em PT-BR.
Tudo roda local e grátis (FFmpeg + whisper.cpp + llama.cpp).

## Instalação

1. Siga a Task 0 do plano `docs/superpowers/plans/2026-10-09-mvp-pipeline.md`.
2. `py -3.14 -m venv .venv` e `.venv\Scripts\python -m pip install -e .[dev]`
3. `Copy-Item config.example.toml config.toml`
4. `.venv\Scripts\gtaviral verificar` (tudo tem que dar `[OK]`)
```

- [ ] **Step 5: Rodar os testes**

Run: `.venv\Scripts\python -m pytest tests/test_config.py tests/test_doctor.py -v`
Expected: 6 passed

Run: `.venv\Scripts\gtaviral verificar`
Expected (com a Task 0 feita): todas as linhas `[OK]`, saída com código 0.

- [ ] **Step 6: Commit**

```powershell
git add .
git commit -m "feat: esqueleto do projeto, config e comando verificar" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Mídia (probe, validação, hash, extração de áudio)

**Files:**
- Create: `src/gtaviral/media.py`
- Create: `tests/conftest.py`, `tests/fixtures/tts.ps1`
- Test: `tests/test_media.py`

**Interfaces:**
- Consumes: `Config`, `resolve_tool`, `run`, `ToolError`
- Produces:
  - `media.MediaError(RuntimeError)`
  - `media.MediaInfo` (dataclass frozen): `duration: float, width: int, height: int, fps: float, has_audio: bool, video_codec: str` (largura e altura já com a rotação aplicada)
  - `media.parse_probe(data: dict) -> MediaInfo`
  - `media.validate(info: MediaInfo, size_bytes: int, max_file_gb: float, max_duration_min: float) -> None`
  - `media.probe(cfg: Config, path: Path) -> MediaInfo`
  - `media.file_sha256(path: Path) -> str`
  - `media.extract_audio(cfg: Config, src: Path, dst_wav: Path) -> None` (WAV mono 16 kHz PCM 16 bits)
  - fixtures do pytest: `real_cfg` (Config do `config.toml` da raiz; pula o teste se não existir) e `speech_video` (MP4 1920×1080 60 fps com fala em inglês)

- [ ] **Step 1: Escrever os testes unitários que falham**

`tests/test_media.py`:
```python
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
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv\Scripts\python -m pytest tests/test_media.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'gtaviral.media'`

- [ ] **Step 3: Implementar `src/gtaviral/media.py`**

```python
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from gtaviral.config import Config, resolve_tool
from gtaviral.proc import ToolError, run


class MediaError(RuntimeError):
    pass


@dataclass(frozen=True)
class MediaInfo:
    duration: float
    width: int
    height: int
    fps: float
    has_audio: bool
    video_codec: str


def _ratio(value: str) -> float:
    num, _, den = str(value).partition("/")
    try:
        n, d = float(num), float(den or 1)
    except ValueError:
        return 0.0
    return n / d if d else 0.0


def parse_probe(data: dict) -> MediaInfo:
    streams = data.get("streams", [])
    video = next(
        (s for s in streams
         if s.get("codec_type") == "video" and not s.get("disposition", {}).get("attached_pic")),
        None,
    )
    if video is None:
        raise MediaError("o arquivo não tem faixa de vídeo")
    width, height = int(video["width"]), int(video["height"])
    rotation = 0
    for side in video.get("side_data_list", []):
        if "rotation" in side:
            rotation = int(side["rotation"])
    if abs(rotation) % 180 == 90:
        width, height = height, width
    fps = _ratio(video.get("avg_frame_rate", "0/0")) or _ratio(video.get("r_frame_rate", "0/0"))
    duration = float(data.get("format", {}).get("duration") or video.get("duration") or 0)
    return MediaInfo(
        duration=duration,
        width=width,
        height=height,
        fps=fps,
        has_audio=any(s.get("codec_type") == "audio" for s in streams),
        video_codec=str(video.get("codec_name", "?")),
    )


def validate(info: MediaInfo, size_bytes: int, max_file_gb: float, max_duration_min: float) -> None:
    size_gb = size_bytes / 1024**3
    if size_gb > max_file_gb:
        raise MediaError(f"arquivo tem {size_gb:.1f} GB; o limite é {max_file_gb} GB (ajuste [limits] na config)")
    if info.duration <= 0:
        raise MediaError("a duração do vídeo não pôde ser lida")
    if info.duration > max_duration_min * 60:
        raise MediaError(
            f"vídeo tem {info.duration / 60:.1f} min; o limite é {max_duration_min:g} min (ajuste [limits] na config)"
        )
    if info.width < 320 or info.height < 240:
        raise MediaError(f"resolução {info.width}x{info.height} é baixa demais")


def _require(cfg_value: str, label: str) -> Path:
    path = resolve_tool(cfg_value)
    if path is None:
        raise ToolError(f"{label} não encontrado — rode: gtaviral verificar")
    return path


def probe(cfg: Config, path: Path) -> MediaInfo:
    ffprobe = _require(cfg.ffprobe, "ffprobe")
    try:
        out = run([ffprobe, "-v", "error", "-print_format", "json", "-show_format", "-show_streams", path]).stdout
    except ToolError as e:
        raise MediaError(f"não parece um vídeo válido: {path.name}\n{e}") from e
    return parse_probe(json.loads(out))


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def extract_audio(cfg: Config, src: Path, dst_wav: Path) -> None:
    ffmpeg = _require(cfg.ffmpeg, "ffmpeg")
    tmp = dst_wav.with_suffix(".tmp.wav")
    run([ffmpeg, "-hide_banner", "-nostats", "-y", "-i", src, "-vn", "-ac", "1", "-ar", "16000",
         "-c:a", "pcm_s16le", tmp])
    tmp.replace(dst_wav)
```

- [ ] **Step 4: Rodar os unitários**

Run: `.venv\Scripts\python -m pytest tests/test_media.py -v`
Expected: 8 passed, 1 deselected

- [ ] **Step 5: Fixtures de integração**

`tests/fixtures/tts.ps1`:
```powershell
param([string]$Out, [string]$Text)
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$s.SelectVoice('Microsoft Zira Desktop')
$s.Rate = 0
$s.SetOutputToWaveFile($Out)
$s.Speak($Text)
$s.Dispose()
```

`tests/conftest.py`:
```python
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from gtaviral.config import Config, load_config, resolve_tool

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures"

SPEECH_TEXT = (
    "Bro, look at this car. It just flew over the bridge and landed on the police station. "
    "This is the craziest thing I have seen in GTA Six. "
    "The cops did not even react. They just kept walking like nothing happened. "
    "I swear this game is going to be insane when it comes out."
)


@pytest.fixture(scope="session")
def real_cfg() -> Config:
    cfg_path = ROOT / "config.toml"
    if not cfg_path.is_file():
        pytest.skip("config.toml ausente na raiz (necessário para testes de integração)")
    cfg = load_config(cfg_path)
    if resolve_tool(cfg.ffmpeg) is None:
        pytest.skip("ffmpeg não instalado")
    return cfg


@pytest.fixture(scope="session")
def speech_wav(tmp_path_factory) -> Path:
    out = tmp_path_factory.mktemp("tts") / "speech.wav"
    subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(FIXTURES / "tts.ps1"),
         "-Out", str(out), "-Text", SPEECH_TEXT],
        check=True,
    )
    return out


@pytest.fixture(scope="session")
def speech_video(real_cfg: Config, speech_wav: Path, tmp_path_factory) -> Path:
    out = tmp_path_factory.mktemp("video") / "speech.mp4"
    subprocess.run(
        [str(resolve_tool(real_cfg.ffmpeg)), "-hide_banner", "-y",
         "-f", "lavfi", "-i", "testsrc2=size=1920x1080:rate=60",
         "-i", str(speech_wav), "-shortest",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(out)],
        check=True, capture_output=True,
    )
    return out
```

Acrescente ao fim de `tests/test_media.py`:
```python
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
```

- [ ] **Step 6: Rodar a integração**

Run: `.venv\Scripts\python -m pytest tests/test_media.py -m integration -v`
Expected: 1 passed (ou "skipped" se a Task 0 não foi feita; nesse caso, fazer a Task 0 antes de seguir).

- [ ] **Step 7: Commit**

```powershell
git add src/gtaviral/media.py tests/
git commit -m "feat: probe, validacao, hash e extracao de audio" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Transcrição (whisper.cpp → Transcript com tempo por palavra)

**Files:**
- Create: `src/gtaviral/transcribe.py`
- Create: `tests/__init__.py` (vazio), `tests/fixtures/whisper_sample.json`
- Test: `tests/test_transcribe.py`

**Interfaces:**
- Consumes: `Config`, `resolve_tool`, `run`, `ToolError`
- Produces:
  - `transcribe.Word` (frozen): `text: str, start: float, end: float, prob: float`
  - `transcribe.Segment` (frozen): `id: int, start: float, end: float, text: str, words: tuple[Word, ...]`
  - `transcribe.Transcript` (frozen): `language: str, segments: tuple[Segment, ...]`
  - `transcribe.parse_whisper_json(data: dict) -> Transcript`
  - `transcribe.transcript_to_dict(t: Transcript) -> dict` / `transcribe.transcript_from_dict(d: dict) -> Transcript`
  - `transcribe.transcribe(cfg: Config, wav: Path, out_prefix: Path, language: str = "auto") -> Transcript`

Formato conferido no código-fonte do `whisper-cli` (`examples/cli/cli.cpp`, v1.9.5): `-ojf` liga o tempo por token. Cada segmento tem `offsets.from/to` em **milissegundos**, `text` e `tokens[]` (`text`, `offsets`, `id`, `p`). Tokens especiais (`[_BEG_]`, `[_TT_123]`) também aparecem e precisam ser descartados. Um token que começa com espaço inicia uma palavra nova; sem espaço, continua a anterior (ex.: `" fl"` + `"ew"`).

- [ ] **Step 1: Criar `tests/__init__.py` vazio e a fixture `tests/fixtures/whisper_sample.json`**

`tests/__init__.py` vazio deixa os testes importarem uns dos outros (`from tests.test_doctor import make_cfg`).

`tests/fixtures/whisper_sample.json`:
```json
{
  "systeminfo": "AVX = 1",
  "model": {"type": "large v3 turbo", "multilingual": true},
  "params": {"model": "ggml-large-v3-turbo-q8_0.bin", "language": "auto", "translate": false},
  "result": {"language": "en"},
  "transcription": [
    {
      "timestamps": {"from": "00:00:00,000", "to": "00:00:02,500"},
      "offsets": {"from": 0, "to": 2500},
      "text": " Bro, look at this car.",
      "tokens": [
        {"text": "[_BEG_]", "offsets": {"from": 0, "to": 0}, "id": 50365, "p": 0.98, "t_dtw": -1},
        {"text": " Bro", "offsets": {"from": 0, "to": 400}, "id": 1, "p": 0.9, "t_dtw": -1},
        {"text": ",", "offsets": {"from": 400, "to": 450}, "id": 2, "p": 0.95, "t_dtw": -1},
        {"text": " look", "offsets": {"from": 600, "to": 900}, "id": 3, "p": 0.99, "t_dtw": -1},
        {"text": " at", "offsets": {"from": 900, "to": 1000}, "id": 4, "p": 0.99, "t_dtw": -1},
        {"text": " this", "offsets": {"from": 1000, "to": 1300}, "id": 5, "p": 0.99, "t_dtw": -1},
        {"text": " car", "offsets": {"from": 1300, "to": 1800}, "id": 6, "p": 0.97, "t_dtw": -1},
        {"text": ".", "offsets": {"from": 1800, "to": 1850}, "id": 7, "p": 0.99, "t_dtw": -1},
        {"text": "[_TT_125]", "offsets": {"from": 2500, "to": 2500}, "id": 50490, "p": 0.5, "t_dtw": -1}
      ]
    },
    {
      "timestamps": {"from": "00:00:02,500", "to": "00:00:06,000"},
      "offsets": {"from": 2500, "to": 6000},
      "text": " It just flew over the bridge.",
      "tokens": [
        {"text": " It", "offsets": {"from": 2500, "to": 2700}, "id": 8, "p": 0.99, "t_dtw": -1},
        {"text": " just", "offsets": {"from": 2700, "to": 3000}, "id": 9, "p": 0.99, "t_dtw": -1},
        {"text": " fl", "offsets": {"from": 3000, "to": 3200}, "id": 10, "p": 0.8, "t_dtw": -1},
        {"text": "ew", "offsets": {"from": 3200, "to": 3500}, "id": 11, "p": 0.6, "t_dtw": -1},
        {"text": " over", "offsets": {"from": 3500, "to": 3900}, "id": 12, "p": 0.99, "t_dtw": -1},
        {"text": " the", "offsets": {"from": 3900, "to": 4000}, "id": 13, "p": 0.99, "t_dtw": -1},
        {"text": " bridge", "offsets": {"from": 4000, "to": 4600}, "id": 14, "p": 0.99, "t_dtw": -1},
        {"text": ".", "offsets": {"from": 4600, "to": 4650}, "id": 15, "p": 0.99, "t_dtw": -1}
      ]
    },
    {
      "timestamps": {"from": "00:00:06,000", "to": "00:00:06,500"},
      "offsets": {"from": 6000, "to": 6500},
      "text": " ",
      "tokens": []
    }
  ]
}
```

- [ ] **Step 2: Escrever os testes que falham**

`tests/test_transcribe.py`:
```python
import json
from pathlib import Path

import pytest

from gtaviral.proc import ToolError
from gtaviral.transcribe import (
    Word,
    parse_whisper_json,
    transcribe,
    transcript_from_dict,
    transcript_to_dict,
)
from tests.test_doctor import make_cfg

FIXTURE = Path(__file__).parent / "fixtures" / "whisper_sample.json"


def load():
    return parse_whisper_json(json.loads(FIXTURE.read_text(encoding="utf-8")))


def test_language_and_non_empty_segments():
    t = load()
    assert t.language == "en"
    assert [s.text for s in t.segments] == ["Bro, look at this car.", "It just flew over the bridge."]
    assert [s.id for s in t.segments] == [0, 1]
    assert t.segments[1].start == 2.5 and t.segments[1].end == 6.0


def test_words_skip_special_tokens_and_glue_punctuation():
    words = load().segments[0].words
    assert [w.text for w in words] == ["Bro,", "look", "at", "this", "car."]
    assert words[0] == Word("Bro,", 0.0, 0.45, 0.9)


def test_subword_tokens_merge_with_min_probability():
    flew = [w for w in load().segments[1].words if w.text == "flew"][0]
    assert (flew.start, flew.end, flew.prob) == (3.0, 3.5, 0.6)


def test_dict_roundtrip():
    t = load()
    assert transcript_from_dict(json.loads(json.dumps(transcript_to_dict(t)))) == t


def test_transcribe_without_cli_explains(tmp_path):
    with pytest.raises(ToolError, match="gtaviral verificar"):
        transcribe(make_cfg(tmp_path), tmp_path / "a.wav", tmp_path / "out")


@pytest.mark.integration
def test_transcribe_real_speech(real_cfg, speech_wav, tmp_path):
    from gtaviral.media import extract_audio

    wav = tmp_path / "a.wav"
    extract_audio(real_cfg, speech_wav, wav)
    t = transcribe(real_cfg, wav, tmp_path / "whisper")
    text = " ".join(s.text for s in t.segments).lower()
    assert t.language == "en"
    assert "car" in text and "bridge" in text
    starts = [w.start for s in t.segments for w in s.words]
    assert starts == sorted(starts) and len(starts) > 20
```

- [ ] **Step 3: Rodar e ver falhar**

Run: `.venv\Scripts\python -m pytest tests/test_transcribe.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'gtaviral.transcribe'`

- [ ] **Step 4: Implementar `src/gtaviral/transcribe.py`**

```python
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from gtaviral.config import Config, resolve_tool
from gtaviral.proc import ToolError, run

_SPECIAL = re.compile(r"^\s*(\[_[A-Z_0-9]+\]|<\|.*\|>)\s*$")


@dataclass(frozen=True)
class Word:
    text: str
    start: float
    end: float
    prob: float


@dataclass(frozen=True)
class Segment:
    id: int
    start: float
    end: float
    text: str
    words: tuple[Word, ...]


@dataclass(frozen=True)
class Transcript:
    language: str
    segments: tuple[Segment, ...]


def _words_from_tokens(tokens: list[dict]) -> list[Word]:
    words: list[Word] = []
    text, start, end, prob = "", 0.0, 0.0, 1.0
    for tok in tokens:
        piece = tok.get("text", "")
        if not piece or _SPECIAL.match(piece) or "offsets" not in tok:
            continue
        t0, t1 = tok["offsets"]["from"] / 1000, tok["offsets"]["to"] / 1000
        p = float(tok.get("p", 1.0))
        if piece.startswith(" ") or not text:
            if text.strip():
                words.append(Word(text.strip(), start, end, prob))
            text, start, end, prob = piece, t0, t1, p
        else:
            text += piece
            end = t1
            prob = min(prob, p)
    if text.strip():
        words.append(Word(text.strip(), start, end, prob))
    return words


def parse_whisper_json(data: dict) -> Transcript:
    language = data.get("result", {}).get("language") or "?"
    segments: list[Segment] = []
    for item in data.get("transcription", []):
        text = item.get("text", "").strip()
        if not text:
            continue
        segments.append(Segment(
            id=len(segments),
            start=item["offsets"]["from"] / 1000,
            end=item["offsets"]["to"] / 1000,
            text=text,
            words=tuple(_words_from_tokens(item.get("tokens", []))),
        ))
    return Transcript(language=language, segments=tuple(segments))


def transcript_to_dict(t: Transcript) -> dict:
    return asdict(t)


def transcript_from_dict(d: dict) -> Transcript:
    return Transcript(
        language=d["language"],
        segments=tuple(
            Segment(s["id"], s["start"], s["end"], s["text"], tuple(Word(**w) for w in s["words"]))
            for s in d["segments"]
        ),
    )


def transcribe(cfg: Config, wav: Path, out_prefix: Path, language: str = "auto") -> Transcript:
    cli = resolve_tool(cfg.whisper_cli)
    if cli is None:
        raise ToolError("whisper-cli não encontrado — rode: gtaviral verificar")
    if not cfg.whisper_model.is_file():
        raise ToolError(f"modelo do Whisper não encontrado: {cfg.whisper_model} — rode: gtaviral verificar")
    run([cli, "-m", cfg.whisper_model, "-f", wav, "-l", language, "-ojf", "-of", out_prefix,
         "-np", "-t", str(cfg.whisper_threads)])
    json_path = out_prefix.parent / (out_prefix.name + ".json")
    raw = json_path.read_text(encoding="utf-8", errors="replace")
    return parse_whisper_json(json.loads(raw, strict=False))
```

- [ ] **Step 5: Rodar unitários e integração**

Run: `.venv\Scripts\python -m pytest tests/test_transcribe.py -v`
Expected: 5 passed, 1 deselected

Run: `.venv\Scripts\python -m pytest tests/test_transcribe.py -m integration -v`
Expected: 1 passed. Se falhar no parse, abra o `.json` real gerado em `tmp_path` e compare com a fixture. Se o formato divergir, corrija a fixture **e** o parser juntos, e rode os dois de novo.

- [ ] **Step 6: Commit**

```powershell
git add src/gtaviral/transcribe.py tests/
git commit -m "feat: transcricao com whisper.cpp e tempo por palavra" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Eventos de áudio (silêncios e picos de volume)

**Files:**
- Create: `src/gtaviral/audio_events.py`
- Test: `tests/test_audio_events.py`

**Interfaces:**
- Consumes: `Config`, `resolve_tool`, `run`, `ToolError`
- Produces:
  - `audio_events.AudioEvents` (frozen): `silences: tuple[tuple[float, float], ...]`, `loud_moments: tuple[tuple[float, float], ...]` (pares `(segundo, dB RMS)`, do mais alto para o mais baixo)
  - `audio_events.parse_silencedetect(log: str, duration: float) -> list[tuple[float, float]]`
  - `audio_events.parse_rms(log: str) -> list[tuple[float, float]]`
  - `audio_events.find_loud_moments(rms, delta_db=9.0, min_gap=3.0, limit=20) -> list[tuple[float, float]]`
  - `audio_events.events_to_dict(e) -> dict` / `audio_events.events_from_dict(d) -> AudioEvents`
  - `audio_events.detect(cfg: Config, wav: Path, duration: float) -> AudioEvents`

Como funciona: o filtro `silencedetect` do FFmpeg registra no log o início e o fim de cada silêncio. O `astats` com janelas de 0,5 s (8000 amostras a 16 kHz), seguido de `ametadata=print`, registra o volume RMS de cada janela. "Pico" é a janela 9 dB ou mais acima da mediana do vídeo: grito, explosão, risada. Os dois logs saem no stderr.

- [ ] **Step 1: Escrever os testes que falham**

`tests/test_audio_events.py`:
```python
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
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv\Scripts\python -m pytest tests/test_audio_events.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'gtaviral.audio_events'`

- [ ] **Step 3: Implementar `src/gtaviral/audio_events.py`**

```python
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from gtaviral.config import Config, resolve_tool
from gtaviral.proc import ToolError, run

_START = re.compile(r"silence_start:\s*(-?[\d.]+)")
_END = re.compile(r"silence_end:\s*([\d.]+)")
_SILENT_DB = -120.0


@dataclass(frozen=True)
class AudioEvents:
    silences: tuple[tuple[float, float], ...]
    loud_moments: tuple[tuple[float, float], ...]


def parse_silencedetect(log: str, duration: float) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = []
    start: float | None = None
    for line in log.splitlines():
        if m := _START.search(line):
            start = max(0.0, float(m.group(1)))
        elif (m := _END.search(line)) and start is not None:
            out.append((start, float(m.group(1))))
            start = None
    if start is not None:
        out.append((start, duration))
    return out


def parse_rms(log: str) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = []
    t: float | None = None
    for line in log.splitlines():
        if "pts_time:" in line:
            t = float(line.split("pts_time:")[1].split()[0])
        elif "RMS_level=" in line and t is not None:
            raw = line.split("RMS_level=", 1)[1].strip()
            db = _SILENT_DB if raw in ("-inf", "inf", "nan") else float(raw)
            out.append((t, db))
            t = None
    return out


def find_loud_moments(
    rms: list[tuple[float, float]], delta_db: float = 9.0, min_gap: float = 3.0, limit: int = 20
) -> list[tuple[float, float]]:
    finite = sorted(db for _, db in rms if db > -100)
    if not finite:
        return []
    median = finite[len(finite) // 2]
    candidates = sorted(((t, db) for t, db in rms if db >= median + delta_db), key=lambda x: -x[1])
    chosen: list[tuple[float, float]] = []
    for t, db in candidates:
        if all(abs(t - c) >= min_gap for c, _ in chosen):
            chosen.append((t, db))
        if len(chosen) >= limit:
            break
    return chosen


def events_to_dict(e: AudioEvents) -> dict:
    return {"silences": [list(s) for s in e.silences], "loud_moments": [list(m) for m in e.loud_moments]}


def events_from_dict(d: dict) -> AudioEvents:
    return AudioEvents(
        silences=tuple((float(a), float(b)) for a, b in d["silences"]),
        loud_moments=tuple((float(a), float(b)) for a, b in d["loud_moments"]),
    )


def detect(cfg: Config, wav: Path, duration: float) -> AudioEvents:
    ffmpeg = resolve_tool(cfg.ffmpeg)
    if ffmpeg is None:
        raise ToolError("ffmpeg não encontrado — rode: gtaviral verificar")
    silence_log = run([ffmpeg, "-hide_banner", "-nostats", "-i", wav,
                       "-af", "silencedetect=noise=-35dB:d=0.4", "-f", "null", "-"]).stderr
    rms_log = run([ffmpeg, "-hide_banner", "-nostats", "-i", wav,
                   "-af", "asetnsamples=n=8000,astats=metadata=1:reset=1,"
                          "ametadata=print:key=lavfi.astats.Overall.RMS_level",
                   "-f", "null", "-"]).stderr
    return AudioEvents(
        silences=tuple(parse_silencedetect(silence_log, duration)),
        loud_moments=tuple(find_loud_moments(parse_rms(rms_log))),
    )
```

- [ ] **Step 4: Rodar unitários e integração**

Run: `.venv\Scripts\python -m pytest tests/test_audio_events.py -v`
Expected: 5 passed, 1 deselected

Run: `.venv\Scripts\python -m pytest tests/test_audio_events.py -m integration -v`
Expected: 1 passed

- [ ] **Step 5: Commit**

```powershell
git add src/gtaviral/audio_events.py tests/test_audio_events.py
git commit -m "feat: deteccao de silencios e picos de audio" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Cliente do LLM local (llama-server) com saída JSON garantida

**Files:**
- Create: `src/gtaviral/llm.py`
- Create: `tests/fakes.py`
- Test: `tests/test_llm.py`

**Interfaces:**
- Consumes: `Config`, `resolve_tool`
- Produces:
  - `llm.LLMError(RuntimeError)`
  - `llm.LLM` (Protocol): `chat_json(self, system: str, user: str, schema: dict) -> dict`
  - `llm.LlamaClient(base_url: str, timeout: float = 600.0)`: `.health() -> bool`, `.chat_json(system, user, schema, temperature=0.3) -> dict`
  - `llm.LlamaServer(cfg: Config, startup_timeout: float = 240.0)`: context manager. Ao entrar devolve um `LlamaClient` e sobe o `llama-server` se ainda não estiver no ar; ao sair, encerra o processo **só se foi ele que o subiu**.
  - `tests.fakes.FakeLLM(replies: list)`: `.chat_json(...)` devolve a próxima resposta da lista (um dict, ou uma função `user -> dict`) e guarda as chamadas em `.calls`.

O `llama-server` expõe uma API no formato OpenAI (`POST /v1/chat/completions`) e aceita `response_format` com `json_schema`: o modelo é forçado a responder JSON nesse formato. `GET /health` responde 200 quando o modelo terminou de carregar e 503 enquanto carrega.

- [ ] **Step 1: Escrever os testes que falham**

`tests/fakes.py`:
```python
from __future__ import annotations


class FakeLLM:
    def __init__(self, replies: list) -> None:
        self.replies = list(replies)
        self.calls: list[tuple[str, str, dict]] = []

    def chat_json(self, system: str, user: str, schema: dict) -> dict:
        self.calls.append((system, user, schema))
        reply = self.replies.pop(0)
        return reply(user) if callable(reply) else reply
```

`tests/test_llm.py`:
```python
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from gtaviral.llm import LlamaClient, LlamaServer, LLMError
from tests.test_doctor import make_cfg


class _Handler(BaseHTTPRequestHandler):
    responses: list = []
    requests: list = []

    def do_GET(self):
        self._send(200 if self.path == "/health" else 404, {"status": "ok"})

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        type(self).requests.append(body)
        code, payload = type(self).responses.pop(0)
        self._send(code, payload)

    def _send(self, code, payload):
        data = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


def completion(content: str) -> dict:
    return {"choices": [{"message": {"role": "assistant", "content": content}}]}


@pytest.fixture
def server():
    _Handler.responses = []
    _Handler.requests = []
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}", _Handler
    httpd.shutdown()


def test_health(server):
    url, _ = server
    assert LlamaClient(url).health() is True
    assert LlamaClient("http://127.0.0.1:1").health() is False


def test_chat_json_sends_schema_and_parses(server):
    url, h = server
    h.responses = [(200, completion('{"ok": true}'))]
    schema = {"type": "object", "properties": {"ok": {"type": "boolean"}}}
    assert LlamaClient(url).chat_json("sys", "user", schema) == {"ok": True}
    sent = h.requests[0]
    assert sent["response_format"]["type"] == "json_schema"
    assert sent["response_format"]["json_schema"]["schema"] == schema
    assert [m["role"] for m in sent["messages"]] == ["system", "user"]


def test_chat_json_retries_once_on_bad_json(server):
    url, h = server
    h.responses = [(200, completion("não é json")), (200, completion('{"ok": 1}'))]
    assert LlamaClient(url).chat_json("s", "u", {}) == {"ok": 1}
    assert len(h.requests) == 2


def test_chat_json_gives_up_after_two_failures(server):
    url, h = server
    h.responses = [(200, completion("x")), (200, completion("[1, 2]"))]
    with pytest.raises(LLMError, match="formato"):
        LlamaClient(url).chat_json("s", "u", {})


def test_llama_server_without_binary_explains(tmp_path):
    cfg = make_cfg(tmp_path, llm_port=1)
    with pytest.raises(LLMError, match="gtaviral verificar"):
        with LlamaServer(cfg):
            pass


@pytest.mark.integration
def test_real_llama_server_returns_schema_json(real_cfg):
    schema = {"type": "object", "properties": {"traducao": {"type": "string"}}, "required": ["traducao"]}
    with LlamaServer(real_cfg) as llm:
        out = llm.chat_json("Traduza para português do Brasil.", "Bro, look at this car.", schema)
    assert isinstance(out["traducao"], str) and out["traducao"]
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv\Scripts\python -m pytest tests/test_llm.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'gtaviral.llm'`

- [ ] **Step 3: Implementar `src/gtaviral/llm.py`**

```python
from __future__ import annotations

import json
import subprocess
import time
import urllib.error
import urllib.request
from typing import IO, Protocol

from gtaviral.config import Config, resolve_tool


class LLMError(RuntimeError):
    pass


class LLM(Protocol):
    def chat_json(self, system: str, user: str, schema: dict) -> dict: ...


class LlamaClient:
    def __init__(self, base_url: str, timeout: float = 600.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def health(self) -> bool:
        try:
            with urllib.request.urlopen(f"{self.base_url}/health", timeout=2) as r:
                return r.status == 200
        except (urllib.error.URLError, OSError):
            return False

    def chat_json(self, system: str, user: str, schema: dict, temperature: float = 0.3) -> dict:
        body = {
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": temperature,
            "response_format": {"type": "json_schema", "json_schema": {"name": "saida", "schema": schema}},
        }
        last_error = ""
        for _ in range(2):
            req = urllib.request.Request(
                f"{self.base_url}/v1/chat/completions",
                data=json.dumps(body).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    payload = json.loads(r.read().decode("utf-8"))
                result = json.loads(payload["choices"][0]["message"]["content"])
                if isinstance(result, dict):
                    return result
                last_error = "resposta fora do formato: não é um objeto JSON"
            except (json.JSONDecodeError, KeyError, IndexError, TypeError) as e:
                last_error = f"resposta fora do formato: {e}"
            except (urllib.error.URLError, OSError) as e:
                last_error = f"falha de conexão com o LLM: {e}"
        raise LLMError(last_error)


class LlamaServer:
    """Sobe o llama-server se ele não estiver no ar e o encerra na saída (só se foi ele que subiu)."""

    def __init__(self, cfg: Config, startup_timeout: float = 240.0) -> None:
        self.cfg = cfg
        self.client = LlamaClient(f"http://127.0.0.1:{cfg.llm_port}")
        self.startup_timeout = startup_timeout
        self.log_path = cfg.work_dir / "llama-server.log"
        self.proc: subprocess.Popen | None = None
        self._log: IO[str] | None = None

    def __enter__(self) -> LlamaClient:
        if self.client.health():
            return self.client
        exe = resolve_tool(self.cfg.llama_server)
        if exe is None:
            raise LLMError("llama-server não encontrado — rode: gtaviral verificar")
        if not self.cfg.llm_model.is_file():
            raise LLMError(f"modelo do LLM não encontrado: {self.cfg.llm_model} — rode: gtaviral verificar")
        self.cfg.work_dir.mkdir(parents=True, exist_ok=True)
        self._log = self.log_path.open("w", encoding="utf-8", errors="replace")
        self.proc = subprocess.Popen(
            [str(exe), "-m", str(self.cfg.llm_model), "--host", "127.0.0.1", "--port", str(self.cfg.llm_port),
             "-ngl", "99", "-c", "16384"],
            stdout=self._log,
            stderr=subprocess.STDOUT,
        )
        deadline = time.monotonic() + self.startup_timeout
        while time.monotonic() < deadline:
            if self.proc.poll() is not None:
                code = self.proc.returncode
                self._stop()
                raise LLMError(f"llama-server fechou ao iniciar (código {code}):\n{self._tail()}")
            if self.client.health():
                return self.client
            time.sleep(1)
        self._stop()
        raise LLMError(f"llama-server não respondeu em {self.startup_timeout:.0f}s (log: {self.log_path})")

    def __exit__(self, *exc) -> bool:
        self._stop()
        return False

    def _stop(self) -> None:
        if self.proc is not None and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait()
        self.proc = None
        if self._log is not None:
            self._log.close()
            self._log = None

    def _tail(self) -> str:
        try:
            return "\n".join(self.log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-15:])
        except OSError:
            return "(sem log)"
```

- [ ] **Step 4: Rodar unitários e integração**

Run: `.venv\Scripts\python -m pytest tests/test_llm.py -v`
Expected: 5 passed, 1 deselected

Run: `.venv\Scripts\python -m pytest tests/test_llm.py -m integration -v`
Expected: 1 passed (a primeira carga do modelo leva de 10 a 60 s). Se o `llama-server` recusar o formato de `response_format`, veja no `work\llama-server.log` qual campo ele espera, ajuste `body` e rode os testes unitários de novo.

- [ ] **Step 5: Commit**

```powershell
git add src/gtaviral/llm.py tests/fakes.py tests/test_llm.py
git commit -m "feat: cliente do LLM local com JSON por schema" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Tradução para PT-BR (LLM local, com glossário e limite de caracteres)

**Files:**
- Create: `src/gtaviral/translate.py`
- Test: `tests/test_translate.py`

**Interfaces:**
- Consumes: `Transcript`, `Segment` (Task 3), `LLM` (Task 5)
- Produces:
  - `translate.TranslatedSegment` (frozen): `id: int, start: float, end: float, source: str, text: str, highlights: tuple[str, ...] = ()`
  - `translate.TranslationError(RuntimeError)`
  - `translate.GLOSSARY: tuple[str, ...]`
  - `translate.max_chars_for(start: float, end: float) -> int`
  - `translate.translate(transcript: Transcript, llm: LLM | None, glossary=GLOSSARY, batch_size=12) -> list[TranslatedSegment]`
  - `translate.translated_to_dicts(segs) -> list[dict]` / `translate.translated_from_dicts(data) -> list[TranslatedSegment]`

Regras de projeto:
- O limite de caracteres vem da velocidade de leitura: 17 caracteres/s × duração do trecho, entre 12 e 80. É por isso que a tradução sai **resumida**, não literal.
- Os segmentos vão em lotes de 12, com as 3 frases anteriores como contexto (para a gíria e o humor fazerem sentido).
- Se faltar algum id na resposta, o lote é repetido **uma vez**, só com os ids que faltaram. Se ainda faltar, dá erro dizendo quais. Nunca preenche com texto inventado.
- Vídeo já em português passa direto, sem LLM.

- [ ] **Step 1: Escrever os testes que falham**

`tests/test_translate.py`:
```python
import json

import pytest

from gtaviral.transcribe import Segment, Transcript
from gtaviral.translate import (
    TranslatedSegment,
    TranslationError,
    max_chars_for,
    translate,
    translated_from_dicts,
    translated_to_dicts,
)
from tests.fakes import FakeLLM


def tr(lang: str = "en") -> Transcript:
    return Transcript(lang, (
        Segment(0, 0.0, 2.5, "Bro, look at this car.", ()),
        Segment(1, 2.5, 6.0, "It just flew over the bridge.", ()),
    ))


def reply(*items) -> dict:
    return {"itens": [{"id": i, "texto": t, "destaques": d} for i, t, d in items]}


def sent_items(user_prompt: str) -> list[dict]:
    return json.loads(user_prompt.split("Traduza:\n", 1)[1])


def test_translate_keeps_order_times_and_source():
    llm = FakeLLM([reply((1, "Ele voou por cima da ponte.", ["voou"]), (0, "Mano, olha esse carro.", ["carro"]))])
    out = translate(tr(), llm)
    assert [s.text for s in out] == ["Mano, olha esse carro.", "Ele voou por cima da ponte."]
    assert out[0] == TranslatedSegment(0, 0.0, 2.5, "Bro, look at this car.", "Mano, olha esse carro.", ("carro",))


def test_glossary_and_char_limits_go_in_prompt():
    llm = FakeLLM([reply((0, "a", []), (1, "b", []))])
    translate(tr(), llm)
    system, user, _ = llm.calls[0]
    assert "Vice City" in system and "Leonida" in system
    assert sent_items(user)[0] == {"id": 0, "max_caracteres": 42, "texto": "Bro, look at this car."}


def test_missing_ids_are_retried_once_with_only_the_missing():
    llm = FakeLLM([reply((0, "Mano, olha esse carro.", [])), reply((1, "Voou por cima da ponte.", []))])
    out = translate(tr(), llm)
    assert len(out) == 2
    assert [i["id"] for i in sent_items(llm.calls[1][1])] == [1]


def test_still_missing_after_retry_raises():
    llm = FakeLLM([reply((0, "x", [])), reply((0, "x", []))])
    with pytest.raises(TranslationError, match=r"\[1\]"):
        translate(tr(), llm)


def test_highlights_not_in_text_are_dropped():
    llm = FakeLLM([reply((0, "Mano, olha esse carro.", ["carro", "avião"]), (1, "Voou.", []))])
    assert translate(tr(), llm)[0].highlights == ("carro",)


def test_portuguese_is_passthrough_without_llm():
    out = translate(tr("pt"), None)
    assert [s.text for s in out] == [s.source for s in out]


def test_foreign_language_without_llm_raises():
    with pytest.raises(TranslationError, match="LLM"):
        translate(tr("en"), None)


def test_max_chars_bounds():
    assert max_chars_for(0, 0.2) == 12
    assert max_chars_for(0, 20) == 80


def test_dicts_roundtrip():
    seg = TranslatedSegment(0, 0.0, 1.0, "a", "b", ("b",))
    assert translated_from_dicts(json.loads(json.dumps(translated_to_dicts([seg])))) == [seg]
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv\Scripts\python -m pytest tests/test_translate.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'gtaviral.translate'`

- [ ] **Step 3: Implementar `src/gtaviral/translate.py`**

```python
from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from gtaviral.llm import LLM
from gtaviral.transcribe import Segment, Transcript

CPS = 17.0

GLOSSARY = (
    "GTA", "GTA 6", "GTA VI", "Rockstar", "Rockstar Games", "Vice City", "Leonida",
    "Lucia", "Jason", "Los Santos", "Grove Street", "NPC",
)

SYSTEM = """Você traduz legendas de vídeos curtos de games para o público gamer brasileiro.
Regras:
1. Português do Brasil natural e informal, como um brasileiro falaria. Gíria gamer quando couber.
2. Preserve o sentido, o humor e o tom. Gíria em inglês vira a gíria brasileira equivalente, não a tradução literal.
3. NÃO traduza nomes próprios nem estes termos: {glossary}.
4. Cada item tem "max_caracteres": a tradução TEM que caber nesse limite. Condense sem perder o sentido.
5. Não acrescente nada que não foi dito. Não explique a piada.
6. Devolva exatamente um item para cada "id" recebido, com o mesmo id.
7. "destaques": de 0 a 2 palavras da SUA tradução que merecem cor na legenda, escritas exatamente como aparecem no texto. Só palavras de impacto."""

SCHEMA = {
    "type": "object",
    "properties": {
        "itens": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "texto": {"type": "string"},
                    "destaques": {"type": "array", "items": {"type": "string"}, "maxItems": 2},
                },
                "required": ["id", "texto", "destaques"],
            },
        }
    },
    "required": ["itens"],
}


class TranslationError(RuntimeError):
    pass


@dataclass(frozen=True)
class TranslatedSegment:
    id: int
    start: float
    end: float
    source: str
    text: str
    highlights: tuple[str, ...] = ()


def max_chars_for(start: float, end: float) -> int:
    return int(min(80, max(12, (end - start) * CPS)))


def _user_prompt(batch: list[Segment], context: list[Segment]) -> str:
    lines: list[str] = []
    if context:
        lines.append("Contexto (frases anteriores, NÃO traduza):")
        lines += [f"- {s.text}" for s in context]
        lines.append("")
    items = [{"id": s.id, "max_caracteres": max_chars_for(s.start, s.end), "texto": s.text} for s in batch]
    lines.append("Traduza:")
    lines.append(json.dumps(items, ensure_ascii=False))
    return "\n".join(lines)


def _clean_highlights(text: str, highlights: list) -> tuple[str, ...]:
    low = text.lower()
    out = []
    for h in highlights[:2]:
        h = str(h).strip()
        if h and h.lower() in low:
            out.append(h)
    return tuple(out)


def translate(
    transcript: Transcript, llm: LLM | None, glossary: tuple[str, ...] = GLOSSARY, batch_size: int = 12
) -> list[TranslatedSegment]:
    segs = list(transcript.segments)
    if transcript.language == "pt":
        return [TranslatedSegment(s.id, s.start, s.end, s.text, s.text) for s in segs]
    if llm is None:
        raise TranslationError(
            f"o vídeo está em '{transcript.language}' e a tradução precisa do LLM local (rode sem --sem-llm)"
        )
    system = SYSTEM.format(glossary=", ".join(glossary))
    out: list[TranslatedSegment] = []
    for i in range(0, len(segs), batch_size):
        batch = segs[i:i + batch_size]
        context = segs[max(0, i - 3):i]
        wanted = {s.id for s in batch}
        got: dict[int, dict] = {}
        for _attempt in range(2):
            pending = [s for s in batch if s.id not in got]
            reply = llm.chat_json(system, _user_prompt(pending, context), SCHEMA)
            for item in reply.get("itens", []):
                if isinstance(item, dict) and item.get("id") in wanted and str(item.get("texto", "")).strip():
                    got[item["id"]] = item
            if wanted <= got.keys():
                break
        missing = sorted(wanted - got.keys())
        if missing:
            raise TranslationError(f"o modelo não devolveu tradução para os segmentos {missing}")
        for s in batch:
            text = str(got[s.id]["texto"]).strip()
            out.append(TranslatedSegment(
                s.id, s.start, s.end, s.text, text, _clean_highlights(text, list(got[s.id].get("destaques", [])))
            ))
    return out


def translated_to_dicts(segs: list[TranslatedSegment]) -> list[dict]:
    return [asdict(s) for s in segs]


def translated_from_dicts(data: list[dict]) -> list[TranslatedSegment]:
    return [TranslatedSegment(**{**d, "highlights": tuple(d["highlights"])}) for d in data]
```

- [ ] **Step 4: Rodar os testes**

Run: `.venv\Scripts\python -m pytest tests/test_translate.py -v`
Expected: 9 passed

- [ ] **Step 5: Commit**

```powershell
git add src/gtaviral/translate.py tests/test_translate.py
git commit -m "feat: traducao PT-BR com glossario e limite de leitura" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Seleção de cortes (LLM + regras de áudio, sempre validada)

**Files:**
- Create: `src/gtaviral/select_clips.py`
- Test: `tests/test_select_clips.py`

**Interfaces:**
- Consumes: `TranslatedSegment` (Task 6), `AudioEvents` (Task 4), `LLM` (Task 5)
- Produces:
  - `select_clips.MIN_LEN = 8.0`, `select_clips.MAX_LEN = 90.0`
  - `select_clips.ClipCandidate` (frozen): `index: int, start: float, end: float, reason: str, hook: str, source: str` (`"llm"` ou `"regras"`)
  - `select_clips.fit_span(segs, start, end, duration) -> tuple[float, float] | None`
  - `select_clips.rule_candidates(segs, events, duration, max_clips) -> list[ClipCandidate]`
  - `select_clips.llm_candidates(segs, events, duration, llm, max_clips) -> list[ClipCandidate]`
  - `select_clips.select_clips(segs, events, duration, llm: LLM | None, max_clips: int) -> list[ClipCandidate]`
  - `select_clips.clips_to_dicts(clips) -> list[dict]` / `select_clips.clips_from_dicts(data) -> list[ClipCandidate]`

Regras de projeto:
- **O LLM sugere, o código valida.** Todo intervalo é encaixado nas fronteiras de fala (início de um segmento, fim de outro), para nunca cortar no meio de uma frase. Duração entre 8 e 90 s. Clipe invertido é descartado, e clipe que sobrepõe mais de 50% de outro também.
- **Regras sem LLM:** cada pico de áudio vira uma janela de ~8 s antes a ~12 s depois. Sem pico, janelas de ~30 s em sequência, com o motivo dizendo isso abertamente.
- Se o LLM não devolver nenhum clipe válido, cai nas regras, e o `source` mostra isso.

- [ ] **Step 1: Escrever os testes que falham**

`tests/test_select_clips.py`:
```python
from gtaviral.audio_events import AudioEvents
from gtaviral.select_clips import (
    ClipCandidate,
    clips_from_dicts,
    clips_to_dicts,
    fit_span,
    llm_candidates,
    rule_candidates,
    select_clips,
)
from gtaviral.translate import TranslatedSegment
from tests.fakes import FakeLLM


def segs(*bounds):
    return [TranslatedSegment(i, float(a), float(b), f"src {i}", f"texto {i}") for i, (a, b) in enumerate(bounds)]


SEGS = segs((0, 4), (4, 10), (10, 15), (15, 22), (22, 30), (30, 41), (41, 50), (50, 60))
NO_EVENTS = AudioEvents((), ())


def test_fit_span_snaps_to_segment_boundaries():
    assert fit_span(SEGS, 5.0, 21.0, 60.0) == (4.0, 22.0)


def test_fit_span_caps_long_spans_at_a_segment_end():
    long = segs(*[(i * 10, i * 10 + 10) for i in range(20)])
    assert fit_span(long, 0, 150, 200.0) == (0.0, 90.0)


def test_fit_span_extends_short_spans_and_rejects_tiny_videos():
    assert fit_span(SEGS, 0.5, 2.0, 60.0) == (0.0, 10.0)
    assert fit_span(segs((0, 3)), 0, 3, 3.0) is None


def test_rule_candidates_from_peaks_without_overlap():
    ev = AudioEvents((), ((12.0, -10.0), (13.0, -11.0), (45.0, -12.0)))
    out = rule_candidates(SEGS, ev, 60.0, max_clips=3)
    assert [(c.index, c.start, c.end) for c in out] == [(1, 4.0, 30.0), (2, 30.0, 60.0)]
    assert all(c.source == "regras" for c in out)
    assert "12.0s" in out[0].reason


def test_rule_candidates_fallback_windows_when_no_peaks():
    out = rule_candidates(SEGS, NO_EVENTS, 60.0, max_clips=3)
    assert [(c.start, c.end) for c in out] == [(0.0, 30.0), (30.0, 60.0)]
    assert "nenhum pico" in out[0].reason


def test_llm_candidates_validate_snap_and_drop_bad_items():
    llm = FakeLLM([{"clipes": [
        {"inicio": 5.0, "fim": 21.0, "motivo": "carro voa", "gancho": "Olha isso"},
        {"inicio": 30.0, "fim": 20.0, "motivo": "invertido", "gancho": ""},
        {"inicio": 6.0, "fim": 20.0, "motivo": "sobreposto", "gancho": ""},
        {"inicio": 41.0, "fim": 59.0, "motivo": "policia", "gancho": "Ninguém reagiu"},
    ]}])
    out = llm_candidates(SEGS, NO_EVENTS, 60.0, llm, max_clips=3)
    assert [(c.index, c.start, c.end, c.reason) for c in out] == [(1, 4.0, 22.0, "carro voa"), (2, 41.0, 60.0, "policia")]
    assert out[0].hook == "Olha isso" and out[0].source == "llm"


def test_prompt_contains_timed_transcript_and_peaks():
    llm = FakeLLM([{"clipes": []}])
    llm_candidates(SEGS, AudioEvents((), ((12.0, -10.0),)), 60.0, llm, max_clips=3)
    system, user, _ = llm.calls[0]
    assert "[4.0-10.0] texto 1" in user
    assert "12.0" in user
    assert "No máximo 3 clipes" in system


def test_select_falls_back_to_rules_when_llm_gives_nothing():
    out = select_clips(SEGS, NO_EVENTS, 60.0, FakeLLM([{"clipes": []}]), max_clips=2)
    assert out and all(c.source == "regras" for c in out)


def test_select_without_llm_uses_rules():
    assert all(c.source == "regras" for c in select_clips(SEGS, NO_EVENTS, 60.0, None, max_clips=2))


def test_clips_dict_roundtrip():
    c = ClipCandidate(1, 0.0, 10.0, "r", "h", "llm")
    assert clips_from_dicts(clips_to_dicts([c])) == [c]
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv\Scripts\python -m pytest tests/test_select_clips.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'gtaviral.select_clips'`

- [ ] **Step 3: Implementar `src/gtaviral/select_clips.py`**

```python
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Sequence

from gtaviral.audio_events import AudioEvents
from gtaviral.llm import LLM
from gtaviral.translate import TranslatedSegment

MIN_LEN = 8.0
MAX_LEN = 90.0

SYSTEM = """Você é editor de vídeos curtos de games para TikTok e Reels no Brasil.
Você recebe a transcrição traduzida de um vídeo, com tempos em segundos, e os momentos de pico de áudio.
Escolha os melhores trechos para virar clipes curtos.
Regras:
1. Cada clipe faz sentido sozinho: começa antes do acontecimento e termina depois da reação ou da conclusão.
2. Duração entre {min_len:.0f} e {max_len:.0f} segundos. Não force duração: use o tamanho natural do momento.
3. "motivo": uma frase dizendo o que acontece no trecho, baseada SÓ no que está na transcrição.
4. "gancho": uma frase curta para os primeiros segundos, fiel ao conteúdo, sem prometer o que não acontece.
5. No máximo {max_clips} clipes, do melhor para o pior, sem sobreposição."""

SCHEMA = {
    "type": "object",
    "properties": {
        "clipes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "inicio": {"type": "number"},
                    "fim": {"type": "number"},
                    "motivo": {"type": "string"},
                    "gancho": {"type": "string"},
                },
                "required": ["inicio", "fim", "motivo", "gancho"],
            },
        }
    },
    "required": ["clipes"],
}


@dataclass(frozen=True)
class ClipCandidate:
    index: int
    start: float
    end: float
    reason: str
    hook: str
    source: str


def _snap_start(segs: Sequence[TranslatedSegment], t: float) -> float:
    starts = [s.start for s in segs if s.start <= t + 1e-6]
    return max(starts) if starts else 0.0


def _snap_end(segs: Sequence[TranslatedSegment], t: float, duration: float) -> float:
    ends = [s.end for s in segs if s.end >= t - 1e-6]
    return min(ends) if ends else duration


def fit_span(
    segs: Sequence[TranslatedSegment], start: float, end: float, duration: float
) -> tuple[float, float] | None:
    s = max(0.0, _snap_start(segs, start))
    e = min(duration, _snap_end(segs, end, duration))
    if e - s > MAX_LEN:
        ends = [x.end for x in segs if s < x.end <= s + MAX_LEN]
        e = max(ends) if ends and max(ends) - s >= MIN_LEN else s + MAX_LEN
    if e - s < MIN_LEN:
        e = min(duration, _snap_end(segs, s + MIN_LEN, duration))
    if e - s < MIN_LEN:
        return None
    return round(s, 2), round(e, 2)


def _overlaps(a: tuple[float, float], b: tuple[float, float]) -> bool:
    inter = min(a[1], b[1]) - max(a[0], b[0])
    return inter > 0.5 * min(a[1] - a[0], b[1] - b[0])


def rule_candidates(
    segs: Sequence[TranslatedSegment], events: AudioEvents, duration: float, max_clips: int
) -> list[ClipCandidate]:
    picked: list[tuple[tuple[float, float], str]] = []
    for t, db in events.loud_moments:
        if len(picked) >= max_clips:
            break
        span = fit_span(segs, t - 8.0, t + 12.0, duration)
        if span and not any(_overlaps(span, p) for p, _ in picked):
            picked.append((span, f"pico de áudio em {t:.1f}s ({db:.0f} dB)"))
    if not picked:
        cursor = 0.0
        while len(picked) < max_clips:
            span = fit_span(segs, cursor, cursor + 30.0, duration)
            if span is None or span[1] <= cursor:
                break
            if not any(_overlaps(span, p) for p, _ in picked):
                picked.append((span, "trecho com fala contínua (nenhum pico de áudio detectado)"))
            cursor = span[1]
    return [ClipCandidate(i + 1, s, e, reason, "", "regras") for i, ((s, e), reason) in enumerate(picked)]


def llm_candidates(
    segs: Sequence[TranslatedSegment], events: AudioEvents, duration: float, llm: LLM, max_clips: int
) -> list[ClipCandidate]:
    lines = [f"Duração total: {duration:.1f}s", "", "Transcrição:"]
    lines += [f"[{s.start:.1f}-{s.end:.1f}] {s.text}" for s in segs]
    if events.loud_moments:
        lines += ["", "Picos de áudio (segundo):", ", ".join(f"{t:.1f}" for t, _ in sorted(events.loud_moments))]
    system = SYSTEM.format(min_len=MIN_LEN, max_len=MAX_LEN, max_clips=max_clips)
    reply = llm.chat_json(system, "\n".join(lines), SCHEMA)
    picked: list[tuple[tuple[float, float], str, str]] = []
    for item in reply.get("clipes", []):
        if len(picked) >= max_clips:
            break
        try:
            start, end = float(item["inicio"]), float(item["fim"])
        except (KeyError, TypeError, ValueError):
            continue
        if end <= start:
            continue
        span = fit_span(segs, start, end, duration)
        if span and not any(_overlaps(span, p) for p, _, _ in picked):
            picked.append((span, str(item.get("motivo", "")).strip(), str(item.get("gancho", "")).strip()))
    return [ClipCandidate(i + 1, s, e, reason, hook, "llm") for i, ((s, e), reason, hook) in enumerate(picked)]


def select_clips(
    segs: Sequence[TranslatedSegment], events: AudioEvents, duration: float, llm: LLM | None, max_clips: int
) -> list[ClipCandidate]:
    if llm is not None:
        found = llm_candidates(segs, events, duration, llm, max_clips)
        if found:
            return found
    return rule_candidates(segs, events, duration, max_clips)


def clips_to_dicts(clips: list[ClipCandidate]) -> list[dict]:
    return [asdict(c) for c in clips]


def clips_from_dicts(data: list[dict]) -> list[ClipCandidate]:
    return [ClipCandidate(**d) for d in data]
```

- [ ] **Step 4: Rodar os testes**

Run: `.venv\Scripts\python -m pytest tests/test_select_clips.py -v`
Expected: 10 passed

- [ ] **Step 5: Commit**

```powershell
git add src/gtaviral/select_clips.py tests/test_select_clips.py
git commit -m "feat: selecao de cortes por LLM com validacao e fallback por regras" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Legendas (cues, SRT/VTT/ASS, legenda editável, aviso de leitura)

**Files:**
- Create: `src/gtaviral/subtitles.py`
- Test: `tests/test_subtitles.py`

**Interfaces:**
- Consumes: `TranslatedSegment` (Task 6)
- Produces:
  - `subtitles.STYLES = ("simples", "dinamica", "destaque")`
  - `subtitles.Cue` (frozen): `start: float, end: float, text: str, highlights: tuple[str, ...] = ()` (tempos relativos ao início do clipe)
  - `subtitles.wrap_lines(text: str, max_line: int = 20) -> list[str]`
  - `subtitles.split_text(text: str, max_chars: int) -> list[str]`
  - `subtitles.build_cues(segments, clip_start: float, clip_end: float, style: str) -> list[Cue]`
  - `subtitles.cps_warnings(cues, limit: float = 20.0) -> list[str]`
  - `subtitles.fmt_srt_time(t) -> str`, `subtitles.fmt_vtt_time(t) -> str`, `subtitles.fmt_ass_time(t) -> str`
  - `subtitles.to_srt(cues, mark: bool = False) -> str` (com `mark=True`, as palavras destacadas saem entre `*asteriscos*`)
  - `subtitles.parse_srt(text: str) -> list[Cue]` (lê `*asteriscos*` de volta como destaque)
  - `subtitles.to_vtt(cues) -> str`
  - `subtitles.to_ass(cues, width: int, height: int, font: str, style: str) -> str`

Regras de projeto:
- **Sincronização é por frase.** O tempo por palavra do Whisper é do áudio em **inglês**; a frase traduzida tem outras palavras, em outra ordem. Quando uma frase é quebrada em várias legendas (estilo `dinamica`, ou frase longa), o tempo é dividido **proporcionalmente ao número de caracteres**. É uma aproximação, e o README precisa dizer isso.
- Tamanho: fonte com 3,4% da altura (65 px em 1920), no máximo 20 caracteres por linha e 2 linhas por legenda (40 caracteres). No estilo `dinamica`, pedaços de até 18 caracteres.
- **Área segura:** a legenda fica 28% acima da borda de baixo (onde ficam descrição e nome no TikTok/Reels), com margem direita de 15% (coluna de botões) e esquerda de 8%. O `WrapStyle: 0` do ASS quebra sozinho se uma linha ainda passar da largura.
- Visual: branco, contorno preto de 8 px, destaque em amarelo `#FFE500`. No ASS a cor é BGR: `&H00E5FF&`.
- `legenda_editavel.srt` é o arquivo que o usuário corrige. `*palavra*` marca o destaque. O SRT final (`legenda.srt`) sai limpo, sem asteriscos.

- [ ] **Step 1: Escrever os testes que falham**

`tests/test_subtitles.py`:
```python
from gtaviral.subtitles import (
    Cue,
    build_cues,
    cps_warnings,
    fmt_ass_time,
    fmt_srt_time,
    parse_srt,
    split_text,
    to_ass,
    to_srt,
    to_vtt,
    wrap_lines,
)
from gtaviral.translate import TranslatedSegment


def seg(i, a, b, text, highs=()):
    return TranslatedSegment(i, float(a), float(b), "src", text, tuple(highs))


def test_time_formats():
    assert fmt_srt_time(3661.5) == "01:01:01,500"
    assert fmt_ass_time(3661.5) == "1:01:01.50"


def test_wrap_lines_respects_width():
    assert wrap_lines("mano olha esse carro voando por cima da ponte", 20) == [
        "mano olha esse carro", "voando por cima da", "ponte"]


def test_split_text_breaks_after_sentence_end_and_at_limit():
    assert split_text("Olha isso. O carro voou longe demais mano", 40) == [
        "Olha isso.", "O carro voou longe demais mano"]
    assert all(len(c) <= 18 for c in split_text("um dois tres quatro cinco seis sete oito", 18))


def test_build_cues_shifts_to_clip_time_and_clips_edges():
    segs = [seg(0, 0, 4, "fora do clipe"),
            seg(1, 9, 12, "Mano, olha esse carro.", ["carro"]),
            seg(2, 12, 20, "Voou por cima da ponte.")]
    assert build_cues(segs, clip_start=10.0, clip_end=16.0, style="destaque") == [
        Cue(0.0, 2.0, "Mano, olha esse carro.", ("carro",)),
        Cue(2.0, 6.0, "Voou por cima da ponte.", ()),
    ]


def test_dinamica_makes_short_chunks_with_proportional_contiguous_timing():
    cues = build_cues([seg(0, 0, 4, "um dois tres quatro cinco seis sete oito")], 0, 4, "dinamica")
    assert len(cues) >= 2 and all(len(c.text) <= 18 for c in cues)
    assert cues[0].start == 0.0 and cues[-1].end == 4.0
    assert all(a.end == b.start for a, b in zip(cues, cues[1:]))


def test_simples_drops_highlights():
    assert build_cues([seg(0, 0, 3, "olha o carro", ["carro"])], 0, 3, "simples")[0].highlights == ()


def test_srt_roundtrip_with_marked_highlights():
    cues = [Cue(0.0, 2.0, "Mano, olha esse carro.", ("carro",)), Cue(2.0, 6.5, "Voou por cima da ponte.", ())]
    marked = to_srt(cues, mark=True)
    assert "*carro*" in marked
    assert parse_srt(marked) == cues
    assert "*" not in to_srt(cues)


def test_parse_srt_accepts_user_edits_with_crlf_and_bom():
    text = ("﻿1\r\n00:00:00,000 --> 00:00:01,500\r\nTexto *corrigido*\r\n\r\n"
            "2\r\n00:00:01,500 --> 00:00:03,000\r\nOutra linha\r\n")
    assert parse_srt(text) == [Cue(0.0, 1.5, "Texto corrigido", ("corrigido",)), Cue(1.5, 3.0, "Outra linha", ())]


def test_vtt_header_and_dot_times():
    vtt = to_vtt([Cue(0.0, 1.25, "oi", ())])
    assert vtt.startswith("WEBVTT\n\n")
    assert "00:00:00.000 --> 00:00:01.250" in vtt


def test_ass_has_canvas_style_and_highlight_markup():
    ass = to_ass([Cue(0.0, 2.0, "Mano, olha esse carro.", ("carro",))], 1080, 1920, "Arial Black", "destaque")
    assert "PlayResX: 1080" in ass and "PlayResY: 1920" in ass
    assert "Style: Main,Arial Black,65," in ass
    assert r"Mano, olha esse\N{\c&H00E5FF&}carro{\c&HFFFFFF&}." in ass
    assert "Dialogue: 0,0:00:00.00,0:00:02.00,Main" in ass


def test_ass_escapes_braces_and_backslashes():
    ass = to_ass([Cue(0.0, 1.0, r"a {b} c\d", ())], 1080, 1920, "Arial Black", "simples")
    assert "a (b) c/d" in ass


def test_ass_dinamica_adds_pop_in():
    ass = to_ass([Cue(0.0, 1.0, "oi", ())], 1080, 1920, "Arial Black", "dinamica")
    assert r"{\fscx85\fscy85\t(0,120,\fscx100\fscy100)}oi" in ass


def test_cps_warning_only_for_fast_cue():
    warns = cps_warnings([Cue(0.0, 1.0, "x" * 30, ()), Cue(1.0, 4.0, "curto", ())])
    assert len(warns) == 1 and "legenda 1" in warns[0]
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv\Scripts\python -m pytest tests/test_subtitles.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'gtaviral.subtitles'`

- [ ] **Step 3: Implementar `src/gtaviral/subtitles.py`**

```python
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Sequence

from gtaviral.translate import TranslatedSegment

STYLES = ("simples", "dinamica", "destaque")
MAX_LINE = 20
CHUNK_MAX = {"simples": 2 * MAX_LINE, "destaque": 2 * MAX_LINE, "dinamica": 18}
HIGHLIGHT_ASS = "&H00E5FF&"  # amarelo #FFE500 (ASS usa BGR)
WHITE_ASS = "&HFFFFFF&"
POP_IN = r"{\fscx85\fscy85\t(0,120,\fscx100\fscy100)}"

_TIME = re.compile(r"(\d+):(\d{2}):(\d{2})[,.](\d{3})")


@dataclass(frozen=True)
class Cue:
    start: float
    end: float
    text: str
    highlights: tuple[str, ...] = ()


def wrap_lines(text: str, max_line: int = MAX_LINE) -> list[str]:
    lines: list[str] = []
    cur = ""
    for word in text.split():
        if cur and len(cur) + 1 + len(word) > max_line:
            lines.append(cur)
            cur = word
        else:
            cur = f"{cur} {word}" if cur else word
    if cur:
        lines.append(cur)
    return lines


def split_text(text: str, max_chars: int) -> list[str]:
    chunks: list[str] = []
    cur = ""
    for word in text.split():
        candidate = f"{cur} {word}" if cur else word
        if cur and len(candidate) > max_chars:
            chunks.append(cur)
            cur = word
        else:
            cur = candidate
        if cur.endswith((".", "!", "?")) and len(cur) >= max_chars * 0.25:
            chunks.append(cur)
            cur = ""
    if cur:
        chunks.append(cur)
    return chunks


def build_cues(
    segments: Sequence[TranslatedSegment], clip_start: float, clip_end: float, style: str
) -> list[Cue]:
    if style not in STYLES:
        raise ValueError(f"estilo desconhecido: {style} (use {', '.join(STYLES)})")
    cues: list[Cue] = []
    for seg in segments:
        s, e = max(seg.start, clip_start), min(seg.end, clip_end)
        if e - s < 0.2:
            continue
        chunks = split_text(seg.text, CHUNK_MAX[style])
        total = sum(len(c) for c in chunks) or 1
        t = s
        for chunk in chunks:
            dur = (e - s) * len(chunk) / total
            highs = () if style == "simples" else tuple(h for h in seg.highlights if h.lower() in chunk.lower())
            cues.append(Cue(round(t - clip_start, 3), round(t + dur - clip_start, 3), chunk, highs))
            t += dur
    return cues


def _hmsms(t: float) -> tuple[int, int, int, int]:
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return h, m, s, ms


def fmt_srt_time(t: float) -> str:
    h, m, s, ms = _hmsms(t)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def fmt_vtt_time(t: float) -> str:
    return fmt_srt_time(t).replace(",", ".")


def fmt_ass_time(t: float) -> str:
    cs = int(round(t * 100))
    h, cs = divmod(cs, 360_000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def cps_warnings(cues: Sequence[Cue], limit: float = 20.0) -> list[str]:
    out = []
    for i, c in enumerate(cues, 1):
        cps = len(c.text) / max(c.end - c.start, 0.001)
        if cps > limit:
            out.append(f"legenda {i} ({fmt_srt_time(c.start)}): {cps:.0f} caracteres/s — rápida demais, encurte o texto")
    return out


def _mark(text: str, highlights: Sequence[str], before: str, after: str) -> str:
    for h in sorted(set(highlights), key=len, reverse=True):
        text = re.sub(
            rf"(?<!\w)({re.escape(h)})(?!\w)",
            lambda m: before + m.group(1) + after,
            text,
            count=1,
            flags=re.IGNORECASE,
        )
    return text


def to_srt(cues: Sequence[Cue], mark: bool = False) -> str:
    blocks = []
    for i, c in enumerate(cues, 1):
        lines = wrap_lines(c.text)
        if mark:
            lines = [_mark(line, c.highlights, "*", "*") for line in lines]
        blocks.append(f"{i}\n{fmt_srt_time(c.start)} --> {fmt_srt_time(c.end)}\n" + "\n".join(lines))
    return "\n\n".join(blocks) + "\n"


def _parse_time(value: str) -> float:
    m = _TIME.search(value)
    if not m:
        raise ValueError(f"tempo inválido na legenda: {value.strip()!r}")
    h, mi, s, ms = map(int, m.groups())
    return h * 3600 + mi * 60 + s + ms / 1000


def parse_srt(text: str) -> list[Cue]:
    cues: list[Cue] = []
    normalized = text.lstrip("﻿").replace("\r\n", "\n").strip()
    for block in re.split(r"\n\s*\n", normalized):
        lines = [line for line in block.split("\n") if line.strip()]
        idx = next((i for i, line in enumerate(lines) if "-->" in line), None)
        if idx is None:
            continue
        a, b = lines[idx].split("-->")
        body = " ".join(line.strip() for line in lines[idx + 1:])
        highlights = tuple(re.findall(r"\*([^*]+)\*", body))
        clean = body.replace("*", "")
        if clean:
            cues.append(Cue(_parse_time(a), _parse_time(b), clean, highlights))
    return cues


def to_vtt(cues: Sequence[Cue]) -> str:
    blocks = [f"{fmt_vtt_time(c.start)} --> {fmt_vtt_time(c.end)}\n" + "\n".join(wrap_lines(c.text)) for c in cues]
    return "WEBVTT\n\n" + "\n\n".join(blocks) + "\n"


def _ass_escape(text: str) -> str:
    return text.replace("\\", "/").replace("{", "(").replace("}", ")")


def to_ass(cues: Sequence[Cue], width: int, height: int, font: str, style: str) -> str:
    size = round(height * 0.034)
    outline = max(2, round(height * 0.0042))
    margin_l, margin_r, margin_v = round(width * 0.08), round(width * 0.15), round(height * 0.28)
    header = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        f"PlayResX: {width}\n"
        f"PlayResY: {height}\n"
        "WrapStyle: 0\n"
        "ScaledBorderAndShadow: yes\n"
        "\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Main,{font},{size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,"
        f"{outline},0,2,{margin_l},{margin_r},{margin_v},1\n"
        "\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )
    events = []
    for c in cues:
        lines = [_ass_escape(line) for line in wrap_lines(c.text)]
        if style != "simples":
            lines = [_mark(line, c.highlights, "{\\c" + HIGHLIGHT_ASS + "}", "{\\c" + WHITE_ASS + "}") for line in lines]
        text = r"\N".join(lines)
        if style == "dinamica":
            text = POP_IN + text
        events.append(f"Dialogue: 0,{fmt_ass_time(c.start)},{fmt_ass_time(c.end)},Main,,0,0,0,,{text}")
    return header + "\n".join(events) + "\n"
```

- [ ] **Step 4: Rodar os testes**

Run: `.venv\Scripts\python -m pytest tests/test_subtitles.py -v`
Expected: 13 passed

- [ ] **Step 5: Commit**

```powershell
git add src/gtaviral/subtitles.py tests/test_subtitles.py
git commit -m "feat: legendas SRT/VTT/ASS com destaque e legenda editavel" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Render vertical (corte ou desfoque, legenda embutida, conferência da saída)

**Files:**
- Create: `src/gtaviral/render.py`
- Test: `tests/test_render.py`

**Interfaces:**
- Consumes: `Config`, `resolve_tool`, `run`, `ToolError`, `MediaInfo`, `probe` (Task 2)
- Produces:
  - `render.RenderError(RuntimeError)`
  - `render.Profile` (frozen): `name: str, width: int, height: int, crf: int = 18`
  - `render.PROFILES: dict[str, Profile]` com `"1080"` (1080×1920) e `"1440"` (1440×2560)
  - `render.FRAMINGS = ("corte", "desfoque")`
  - `render.crop_chain(src_w, src_h, profile, crop_x) -> str`
  - `render.blur_chain(profile) -> str`
  - `render.build_filtergraph(info, profile, framing, crop_x, subs_file: str | None) -> str`
  - `render.build_command(ffmpeg: str, src: Path, info, start, end, profile, framing, crop_x, subs_file, out_path, normalize_audio=True) -> list[str]`
  - `render.render_clip(cfg, src, info, start, end, profile, framing, crop_x, subs_file, out_path) -> None`
  - `render.verify_output(cfg, out_path, profile, expected_fps: float) -> MediaInfo`

Regras de projeto:
- **corte:** recorta a maior faixa 9:16 possível. Em vídeo horizontal, `crop_x` escolhe a posição (0 = esquerda, 0,5 = centro, 1 = direita). Em vídeo mais alto que 9:16, corta em cima e embaixo, centralizado. Depois amplia para o perfil com `lanczos`.
- **desfoque:** o fundo é o próprio vídeo ampliado para cobrir a tela, borrado (`gblur`) e escurecido 8%; a frente é o vídeo inteiro, reduzido para caber. As duas escalas preservam a proporção (`force_original_aspect_ratio`), então **nada estica**.
- O trecho é cortado com `-ss`/`-t` **antes** do `-i`. Assim o tempo do clipe começa em 0, como os tempos da legenda.
- O FFmpeg roda com `cwd` na pasta do clipe, e a legenda é passada como nome relativo (`subtitles=legenda.ass`). Isso evita o problema conhecido de escapar `C:\` dentro de filtro no Windows.
- Sem `-r`: o fps da origem é mantido. `verify_output` confere tamanho, codec e fps; se algo não bate, é erro, não sucesso.
- Áudio: `loudnorm` em -14 LUFS (volume padronizado entre clipes), AAC 192k 48 kHz.

- [ ] **Step 1: Escrever os testes que falham**

`tests/test_render.py`:
```python
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
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv\Scripts\python -m pytest tests/test_render.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'gtaviral.render'`

- [ ] **Step 3: Implementar `src/gtaviral/render.py`**

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from gtaviral.config import Config, resolve_tool
from gtaviral.media import MediaInfo, probe
from gtaviral.proc import ToolError, run

FRAMINGS = ("corte", "desfoque")


class RenderError(RuntimeError):
    pass


@dataclass(frozen=True)
class Profile:
    name: str
    width: int
    height: int
    crf: int = 18


PROFILES = {
    "1080": Profile("1080", 1080, 1920),
    "1440": Profile("1440", 1440, 2560),
}


def _even(x: float) -> int:
    v = int(round(x))
    return v - (v % 2)


def crop_chain(src_w: int, src_h: int, profile: Profile, crop_x: float) -> str:
    if not 0.0 <= crop_x <= 1.0:
        raise ValueError("a posição do corte deve estar entre 0 e 1")
    target = profile.width / profile.height
    if src_w / src_h > target:
        cw, ch = _even(src_h * target), _even(src_h)
        x, y = _even((src_w - cw) * crop_x), 0
    else:
        cw, ch = _even(src_w), _even(src_w / target)
        x, y = 0, _even((src_h - ch) / 2)
    return f"crop={cw}:{ch}:{x}:{y},scale={profile.width}:{profile.height}:flags=lanczos,setsar=1"


def blur_chain(profile: Profile) -> str:
    w, h = profile.width, profile.height
    return (
        "split=2[bg][fg];"
        f"[bg]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},"
        "gblur=sigma=40,eq=brightness=-0.08[bgb];"
        f"[fg]scale={w}:{h}:force_original_aspect_ratio=decrease:force_divisible_by=2:flags=lanczos[fgs];"
        "[bgb][fgs]overlay=(W-w)/2:(H-h)/2,setsar=1"
    )


def build_filtergraph(info: MediaInfo, profile: Profile, framing: str, crop_x: float, subs_file: str | None) -> str:
    if framing == "corte":
        chain = crop_chain(info.width, info.height, profile, crop_x)
    elif framing == "desfoque":
        chain = blur_chain(profile)
    else:
        raise ValueError(f"enquadramento desconhecido: {framing} (use {', '.join(FRAMINGS)})")
    if subs_file:
        chain += f",subtitles={subs_file}"
    return f"[0:v]{chain}[v]"


def build_command(
    ffmpeg: str, src: Path, info: MediaInfo, start: float, end: float, profile: Profile, framing: str,
    crop_x: float, subs_file: str | None, out_path: Path, normalize_audio: bool = True,
) -> list[str]:
    cmd = [
        ffmpeg, "-hide_banner", "-nostats", "-y",
        "-ss", f"{start:.3f}", "-t", f"{end - start:.3f}", "-i", str(src),
        "-filter_complex", build_filtergraph(info, profile, framing, crop_x, subs_file),
        "-map", "[v]",
        "-c:v", "libx264", "-preset", "slow", "-crf", str(profile.crf), "-profile:v", "high", "-pix_fmt", "yuv420p",
    ]
    if info.has_audio:
        cmd += ["-map", "0:a:0", "-c:a", "aac", "-b:a", "192k", "-ar", "48000"]
        if normalize_audio:
            cmd += ["-af", "loudnorm=I=-14:TP=-1.5:LRA=11"]
    cmd += ["-movflags", "+faststart", str(out_path)]
    return cmd


def render_clip(
    cfg: Config, src: Path, info: MediaInfo, start: float, end: float, profile: Profile, framing: str,
    crop_x: float, subs_file: str | None, out_path: Path,
) -> None:
    ffmpeg = resolve_tool(cfg.ffmpeg)
    if ffmpeg is None:
        raise ToolError("ffmpeg não encontrado — rode: gtaviral verificar")
    tmp = out_path.with_name(out_path.stem + ".tmp.mp4")
    run(build_command(str(ffmpeg), src, info, start, end, profile, framing, crop_x, subs_file, tmp),
        cwd=out_path.parent)
    tmp.replace(out_path)


def verify_output(cfg: Config, out_path: Path, profile: Profile, expected_fps: float) -> MediaInfo:
    if not out_path.is_file() or out_path.stat().st_size == 0:
        raise RenderError(f"o FFmpeg não gerou {out_path}")
    got = probe(cfg, out_path)
    if (got.width, got.height) != (profile.width, profile.height):
        raise RenderError(f"a saída saiu {got.width}x{got.height}; o esperado era {profile.width}x{profile.height}")
    if got.video_codec != "h264":
        raise RenderError(f"a saída saiu em {got.video_codec}; o esperado era h264")
    if expected_fps > 0 and abs(got.fps - expected_fps) > 0.5:
        raise RenderError(f"o fps mudou: origem {expected_fps:.2f}, saída {got.fps:.2f}")
    return got
```

- [ ] **Step 4: Rodar unitários e integração**

Run: `.venv\Scripts\python -m pytest tests/test_render.py -v`
Expected: 13 passed, 2 deselected

Run: `.venv\Scripts\python -m pytest tests/test_render.py -m integration -v`
Expected: 2 passed

- [ ] **Step 5: Olhar o resultado (teste verde não basta)**

```powershell
.venv\Scripts\python -m pytest tests/test_render.py -m integration --basetemp=work\render_check
ffmpeg -hide_banner -y -ss 1.5 -i (Get-ChildItem work\render_check -Recurse -Filter clipe.mp4 | Select-Object -First 1).FullName -frames:v 1 work\render_check\frame.png
```
Abra `work\render_check\frame.png` e confira:
- a imagem não está esticada;
- a legenda está em **Arial Black**, não numa fonte genérica (se a fonte errada aparecer, o libass não achou a fonte do sistema: adicione `:fontsdir=C\\:/Windows/Fonts` ao filtro `subtitles` e confira de novo);
- "carro" está em amarelo;
- o texto está acima do terço de baixo e longe da borda direita.

Se algo estiver errado, corrija antes de seguir.

- [ ] **Step 6: Commit**

```powershell
git add src/gtaviral/render.py tests/test_render.py
git commit -m "feat: render vertical com corte ou desfoque e legenda embutida" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: Textos para postar (ganchos, títulos, descrições, hashtags)

**Files:**
- Create: `src/gtaviral/copywriter.py`
- Test: `tests/test_copywriter.py`

**Interfaces:**
- Consumes: `LLM`, `LLMError` (Task 5)
- Produces:
  - `copywriter.SCHEMA: dict`
  - `copywriter.generate_copy(llm: LLM, clip_text: str, reason: str, recent_titles: list[str]) -> dict` com as chaves `ganchos` (5), `titulos` (3), `legenda_instagram`, `descricao_tiktok`, `hashtags` (4 a 8, sempre com `#`), `pergunta`, `texto_capa`, `justificativa`
  - `copywriter.format_copy(data: dict, fonte: str, licenca: str) -> str`

Os textos são gerados **só** a partir das falas do trecho e do motivo do corte, para o modelo não inventar acontecimentos. Os títulos recentes vão no prompt para evitar a mesma fórmula em todo vídeo. O `copy.txt` termina com a fonte, a licença e o aviso de que foi escrito por IA e precisa de revisão.

- [ ] **Step 1: Escrever os testes que falham**

`tests/test_copywriter.py`:
```python
import pytest

from gtaviral.copywriter import SCHEMA, format_copy, generate_copy
from gtaviral.llm import LLMError
from tests.fakes import FakeLLM

GOOD = {
    "ganchos": ["a", "b", "c", "d", "e"],
    "titulos": ["t1", "t2", "t3"],
    "legenda_instagram": "li",
    "descricao_tiktok": "dt",
    "hashtags": ["gta6", "#GTAVI", "npc engraçado", "#viral"],
    "pergunta": "p?",
    "texto_capa": "capa",
    "justificativa": "j",
}


def test_generate_copy_normalizes_hashtags_and_passes_context():
    llm = FakeLLM([dict(GOOD)])
    out = generate_copy(llm, "Mano, olha esse carro.", "carro voa", recent_titles=["Título velho"])
    assert out["hashtags"] == ["#gta6", "#GTAVI", "#npcengraçado", "#viral"]
    system, user, schema = llm.calls[0]
    assert "Título velho" in system
    assert "carro voa" in user and "Mano, olha esse carro." in user
    assert schema is SCHEMA


def test_generate_copy_rejects_incomplete_answer():
    bad = dict(GOOD)
    del bad["pergunta"]
    with pytest.raises(LLMError, match="pergunta"):
        generate_copy(FakeLLM([bad]), "x", "y", [])


def test_format_copy_has_sections_source_and_license():
    txt = format_copy(GOOD, fonte="https://youtu.be/abc", licenca="autorizado por @canal")
    assert txt.index("GANCHOS") < txt.index("TÍTULOS") < txt.index("HASHTAGS")
    assert "1. t1" in txt
    assert "https://youtu.be/abc" in txt and "autorizado por @canal" in txt
    assert "revise" in txt
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv\Scripts\python -m pytest tests/test_copywriter.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'gtaviral.copywriter'`

- [ ] **Step 3: Implementar `src/gtaviral/copywriter.py`**

```python
from __future__ import annotations

from gtaviral.llm import LLM, LLMError

SYSTEM = """Você escreve textos para vídeos curtos de GTA no TikTok e no Instagram Reels, para o público gamer brasileiro.
Tom: brasileiro, natural, direto, de quem joga. Nada de frase genérica de marketing.
Regras:
1. Use SÓ o que acontece no trecho descrito. Não invente acontecimento, número, data ou novidade.
2. Se o trecho for rumor ou teoria, deixe isso claro no texto.
3. Títulos sem clickbait mentiroso e sem promessa falsa.
4. Hashtags relevantes ao conteúdo, de 4 a 8, nenhuma sem relação com o vídeo.
5. Não repita a fórmula destes títulos usados recentemente: {recentes}"""

_TEXT = {"type": "string"}


def _list(n_min: int, n_max: int) -> dict:
    return {"type": "array", "items": _TEXT, "minItems": n_min, "maxItems": n_max}


SCHEMA = {
    "type": "object",
    "properties": {
        "ganchos": _list(5, 5),
        "titulos": _list(3, 3),
        "legenda_instagram": _TEXT,
        "descricao_tiktok": _TEXT,
        "hashtags": _list(4, 8),
        "pergunta": _TEXT,
        "texto_capa": _TEXT,
        "justificativa": _TEXT,
    },
    "required": ["ganchos", "titulos", "legenda_instagram", "descricao_tiktok", "hashtags", "pergunta",
                 "texto_capa", "justificativa"],
}


def generate_copy(llm: LLM, clip_text: str, reason: str, recent_titles: list[str]) -> dict:
    system = SYSTEM.format(recentes="; ".join(recent_titles[-20:]) or "nenhum")
    user = f"O que acontece no trecho: {reason}\n\nFalas do trecho (já traduzidas):\n{clip_text}"
    data = llm.chat_json(system, user, SCHEMA)
    missing = [k for k in SCHEMA["required"] if k not in data]
    if missing:
        raise LLMError(f"textos incompletos, faltou: {', '.join(missing)}")
    tags = (str(h).strip().replace(" ", "") for h in data["hashtags"])
    data["hashtags"] = [t if t.startswith("#") else f"#{t}" for t in tags if t.strip("#")]
    return data


def format_copy(data: dict, fonte: str, licenca: str) -> str:
    def numbered(items: list[str]) -> str:
        return "\n".join(f"{i}. {x}" for i, x in enumerate(items, 1))

    parts = [
        "GANCHOS (primeiros segundos)", numbered(data["ganchos"]), "",
        "TÍTULOS", numbered(data["titulos"]), "",
        "LEGENDA DO INSTAGRAM", data["legenda_instagram"], "",
        "DESCRIÇÃO DO TIKTOK", data["descricao_tiktok"], "",
        "HASHTAGS", " ".join(data["hashtags"]), "",
        "PERGUNTA PARA OS COMENTÁRIOS", data["pergunta"], "",
        "TEXTO DA CAPA", data["texto_capa"], "",
        "POR QUE ESSA ESTRATÉGIA", data["justificativa"], "",
        "FONTE E AUTORIZAÇÃO (confira antes de publicar)",
        f"Fonte: {fonte}",
        f"Licença/autorização: {licenca}",
        "",
        "Textos escritos por IA local: revise antes de postar.",
    ]
    return "\n".join(parts) + "\n"
```

- [ ] **Step 4: Rodar os testes**

Run: `.venv\Scripts\python -m pytest tests/test_copywriter.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```powershell
git add src/gtaviral/copywriter.py tests/test_copywriter.py
git commit -m "feat: textos para postar gerados pelo LLM local" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 11: Pipeline (jobs, cache por etapa, isolamento de falha) e CLI completa

**Files:**
- Create: `src/gtaviral/pipeline.py`
- Modify: `src/gtaviral/cli.py` (reescrito por inteiro abaixo)
- Test: `tests/test_pipeline.py`, `tests/test_cli.py`

**Interfaces:**
- Consumes: tudo das Tasks 1 a 10
- Produces:
  - `pipeline.PipelineError(RuntimeError)`
  - `pipeline.ClipResult` (frozen): `index: int, output: Path | None, error: str = "", warnings: tuple[str, ...] = ()`
  - `pipeline.analyze(cfg, video: Path, fonte: str, licenca: str, max_clips=3, use_llm=True, redo_clips=False, llm_factory=LlamaServer, log=print) -> str` (devolve o id do job: 12 primeiros caracteres do SHA-256)
  - `pipeline.load_clips(cfg, job: str) -> list[ClipCandidate]`
  - `pipeline.render_clips(cfg, job, indexes: list[int] | None = None, framing="corte", crop_x=0.5, style="destaque", profile_name="1080", use_llm=True, llm_factory=LlamaServer, log=print) -> list[ClipResult]`
  - CLI: `gtaviral verificar`, `gtaviral analisar <video> --fonte --licenca [--max-clipes N] [--sem-llm] [--refazer-cortes]`, `gtaviral renderizar <job> [--clipes 1,3] [--enquadramento corte|desfoque] [--posicao 0..1] [--estilo simples|dinamica|destaque] [--perfil 1080|1440] [--sem-textos]`

Regras de projeto:
- **Cache por etapa.** Cada etapa grava `work/<job>/<etapa>.json` de forma atômica (escreve `.tmp` e renomeia). Rodar de novo pula o que já existe. Isso cobre retomada após falha e duplicata: o mesmo arquivo gera o mesmo job.
- **Ordem de VRAM:** transcrição (Whisper na GPU) termina → o LLM sobe → tradução + cortes → o LLM desce. No `renderizar`, o vídeo é feito antes e o LLM só sobe depois, para os textos.
- **Falha isolada:** um clipe com erro vira `ClipResult(output=None, error=...)` e os outros continuam. Falha nos textos não invalida o vídeo pronto.
- **Correção manual:** se `legenda_editavel.srt` existir, o `renderizar` usa esse arquivo em vez de gerar de novo. Apague o arquivo para voltar à legenda automática (por exemplo, ao trocar de estilo).

- [ ] **Step 1: Escrever os testes que falham**

`tests/test_pipeline.py`:
```python
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
```

`tests/test_cli.py`:
```python
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
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv\Scripts\python -m pytest tests/test_pipeline.py tests/test_cli.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'gtaviral.pipeline'`

- [ ] **Step 3: Implementar `src/gtaviral/pipeline.py`**

```python
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, ContextManager

from gtaviral.audio_events import AudioEvents, detect, events_from_dict, events_to_dict
from gtaviral.config import Config
from gtaviral.copywriter import format_copy, generate_copy
from gtaviral.llm import LLM, LlamaServer, LLMError
from gtaviral.media import MediaError, MediaInfo, extract_audio, file_sha256, probe, validate
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

    log("Calculando a identidade do arquivo (SHA-256)...")
    sha = file_sha256(video)
    job = sha[:12]
    jd = _job_dir(cfg, job)
    jd.mkdir(parents=True, exist_ok=True)
    manifest = jd / "manifest.json"
    if manifest.is_file():
        log(f"Este vídeo já foi analisado (job {job}): reaproveitando as etapas prontas.")
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
    cdir.mkdir(parents=True, exist_ok=True)
    try:
        editable = cdir / "legenda_editavel.srt"
        if editable.is_file():
            cues = parse_srt(editable.read_text(encoding="utf-8"))
            log(f"Clipe {clip.index}: usando as suas correções de {editable.name}")
        else:
            cues = build_cues(translated, clip.start, clip.end, style)
            editable.write_text(to_srt(cues, mark=True), encoding="utf-8")
        (cdir / "legenda.srt").write_text(to_srt(cues), encoding="utf-8")
        (cdir / "legenda.vtt").write_text(to_vtt(cues), encoding="utf-8")
        (cdir / "legenda.ass").write_text(
            to_ass(cues, profile.width, profile.height, cfg.subtitle_font, style), encoding="utf-8"
        )
        out = cdir / "clipe.mp4"
        log(f"Clipe {clip.index}: renderizando {clip.end - clip.start:.1f}s "
            f"({framing}, {profile.width}x{profile.height})...")
        render_clip(cfg, src, info, clip.start, clip.end, profile, framing, crop_x, "legenda.ass", out)
        verify_output(cfg, out, profile, info.fps)
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
                except LLMError as e:
                    log(f"Clipe {clip.index}: textos não gerados ({e}); o vídeo está pronto mesmo assim")
                    continue
                _write_json(cdir / "copy.json", data)
                (cdir / "copy.txt").write_text(format_copy(data, manifest["fonte"], manifest["licenca"]),
                                               encoding="utf-8")
    except LLMError as e:
        log(f"Textos não gerados: {e}. Os vídeos estão prontos; rode o renderizar de novo para tentar outra vez.")
```

- [ ] **Step 4: Reescrever `src/gtaviral/cli.py`**

```python
from __future__ import annotations

import argparse
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
    except KNOWN_ERRORS as e:
        print(f"ERRO: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Rodar a suíte inteira**

Run: `.venv\Scripts\python -m pytest -v`
Expected: todos os unitários passam (10 de pipeline + 4 de CLI, mais os das tasks anteriores), e os de integração aparecem como deselected.

- [ ] **Step 6: Commit**

```powershell
git add src/gtaviral/pipeline.py src/gtaviral/cli.py tests/test_pipeline.py tests/test_cli.py
git commit -m "feat: pipeline com cache por etapa e comandos analisar/renderizar" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 12: Ponta a ponta, README e aceite com vídeo real

**Files:**
- Create: `tests/test_e2e.py`
- Modify: `README.md` (reescrito por inteiro abaixo)

**Interfaces:**
- Consumes: `analyze`, `render_clips`, `probe`, fixtures `real_cfg` e `speech_video`

- [ ] **Step 1: Teste ponta a ponta com as ferramentas reais**

`tests/test_e2e.py`:
```python
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
```

Run: `.venv\Scripts\python -m pytest -m integration -v`
Expected: todos os de integração passam (media, transcribe, audio_events, llm, render ×2, e2e).

- [ ] **Step 2: Reescrever `README.md`**

```markdown
# GTA Viral AI

Transforma um vídeo **autorizado** em clipes verticais 9:16 com legenda em PT-BR,
mais os textos para postar. Tudo roda local e grátis:
FFmpeg (vídeo), whisper.cpp na GPU via Vulkan (transcrição) e llama.cpp com
Qwen2.5-7B (tradução, escolha dos cortes e textos).

## O que ele NÃO faz (de propósito)

- Não baixa vídeo de ninguém. Você fornece o arquivo e informa a origem (`--fonte`) e a autorização (`--licenca`).
- Não publica nada. Os arquivos ficam em `saida\` para você revisar e postar.
- Cortar, traduzir e legendar **não** dá direito de republicar vídeo de terceiros.

## Instalação

1. Ferramentas externas: Task 0 do plano `docs/superpowers/plans/2026-10-09-mvp-pipeline.md`
   (FFmpeg e Vulkan SDK via winget, `scripts\build_whisper_vulkan.bat`, `scripts\get_tools.ps1`).
2. `py -3.14 -m venv .venv`
3. `.venv\Scripts\python -m pip install -e .[dev]`
4. `Copy-Item config.example.toml config.toml`
5. `.venv\Scripts\gtaviral verificar` (tudo tem que dar `[OK]`)

## Uso

    .venv\Scripts\gtaviral analisar "D:\videos\meu_video.mp4" --fonte "gravação própria" --licenca "próprio"
    .venv\Scripts\gtaviral renderizar <job> --clipes 1 --enquadramento corte --posicao 0.5
    .venv\Scripts\gtaviral renderizar <job> --clipes 2 --enquadramento desfoque --estilo dinamica

Saída por clipe em `saida\<job>\clipe_NN\`:

| Arquivo | Para quê |
|---|---|
| `clipe.mp4` | o vídeo pronto para revisar |
| `legenda_editavel.srt` | corrija aqui; `*palavra*` = destaque amarelo. Rode `renderizar` de novo para aplicar |
| `legenda.srt` / `legenda.vtt` | legenda separada, sem marcações |
| `copy.txt` | ganchos, títulos, descrições, hashtags, fonte e licença |
| `avisos.txt` | legendas rápidas demais para ler |

Para voltar à legenda automática (ex.: ao trocar de estilo), apague `legenda_editavel.srt`.

## Limitações conhecidas

- **Sincronização por frase.** O tempo por palavra vem do áudio original. Quando uma frase traduzida
  vira várias legendas, o tempo é dividido proporcionalmente ao número de caracteres.
- **Tradução por um modelo de 7B local.** É boa para fala comum; gíria muito específica pode sair estranha. Revise.
- **Corte por regras** (`--sem-llm` ou quando o LLM não sugere nada) só olha picos de áudio.
- **Vídeo de até 20 min** (limite de contexto do LLM local).
- **Fonte:** Arial Black do Windows; troque em `[subtitles]` na config.

## Testes

    .venv\Scripts\python -m pytest                 # unitários, sem ferramentas
    .venv\Scripts\python -m pytest -m integration  # com ffmpeg, whisper e llama instalados

## Estado verificado

(preenchido no aceite da Task 12, com data, vídeo usado e tempos medidos)
```

- [ ] **Step 3: Aceite com um vídeo real (critérios do Plano 1)**

Use um vídeo **seu** e com fala (por exemplo, um clipe do Medal em `D:\ReLive\` em que você comenta a partida). Entre 1 e 5 min.

```powershell
$t = Measure-Command { .venv\Scripts\gtaviral analisar "<video>" --fonte "gravação própria" --licenca "próprio" }
"analisar: $($t.TotalSeconds) s"
.venv\Scripts\gtaviral renderizar <job> --clipes 1 --enquadramento corte
.venv\Scripts\gtaviral renderizar <job> --clipes 2 --enquadramento desfoque --estilo dinamica
```

Critérios. **Todos** precisam ser conferidos olhando, não só pelo código de saída:

| # | Critério | Como conferir |
|---|---|---|
| 1 | `analisar` termina sem erro e sugere ≥ 1 clipe com motivo coerente com o vídeo | tabela impressa |
| 2 | o log do whisper mostra a RX 6600 (Vulkan) | `work\<job>\` + saída do comando |
| 3 | `clipe.mp4` é 1080×1920, h264, AAC, mesmo fps da origem | `ffprobe` (o `verify_output` já confere; confirme 1 vez à mão) |
| 4 | a legenda aparece enquanto a frase é falada, sem atraso perceptível | assistir o clipe inteiro |
| 5 | tradução natural, sem nome próprio traduzido | ler `legenda.srt` |
| 6 | legenda dentro da área segura, sem esticar a imagem | extrair 3 frames (`ffmpeg -ss N -i clipe.mp4 -frames:v 1 fN.png`) e olhar |
| 7 | editar `legenda_editavel.srt` e renderizar de novo muda o vídeo | assistir de novo |
| 8 | rodar `analisar` de novo no mesmo arquivo não refaz nada | log "reaproveitando as etapas prontas" e tempo de poucos segundos |
| 9 | `copy.txt` sem fato inventado e com fonte e licença no fim | ler |

Anote em "Estado verificado" do README: data, duração do vídeo, tempo do `analisar` e do `renderizar`, e qualquer critério que falhou.

- [ ] **Step 4: Commit**

```powershell
git add tests/test_e2e.py README.md
git commit -m "test: ponta a ponta com ferramentas reais e README de uso" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## Roteiro depois deste plano (um plano por subsistema)

Cada item vira um plano próprio, escrito só quando o anterior estiver aceito.

| Plano | Escopo | Depende de |
|---|---|---|
| **2. Central de revisão** | Página web local (FastAPI + HTML) sobre os mesmos jobs: biblioteca com os estados da spec (seção 9), player, editor da legenda frase a frase, controle deslizante da posição do corte, aprovar/rejeitar, histórico de versões | Plano 1 |
| **3. Fila e lote** | Vários vídeos em fila, progresso real (`-progress` do FFmpeg), pausar entre etapas, cancelar, repetir falhas, presets editáveis (os 4 da spec, seção 6) | Plano 2 |
| **4. Trend Radar (YouTube)** | Chave grátis da YouTube Data API, os 12 termos da spec, snapshots periódicos para medir crescimento real, pontuação 0–100 com fatores marcados "medido" ou "estimado", rótulo confirmado/rumor/teoria/humor | independente |
| **5. Publicação** | Primeiro exportação manual organizada; depois TikTok (upload para rascunhos) e Instagram Graph API. **Antes de integrar, medir** com `yt-dlp --list-formats` se postar pela API entrega nível de encode pior que o app | Plano 2 |
| **6. Desempenho** | Métricas que as APIs realmente entregam, comparação por tema/estilo com tamanho de amostra visível | Plano 5 |
| **Opcional** | Provedor Claude API no `llm.py` (mesma interface `chat_json`), se um dia quiser mais qualidade de tradução pagando por uso | Plano 1 |

## Fora deste plano (registrado para não se perder)

- Detecção de cena visual e análise de frames por modelo de visão (spec, seção 4, itens 2 e 9).
- Zoom automático, transições, intro e encerramento (spec, seção 6).
- Vídeo de entrada acima de 20 min (exige dividir a transcrição em janelas para o LLM).
- Autenticação (desnecessária enquanto tudo roda local, para um usuário só, sem porta aberta na rede).
