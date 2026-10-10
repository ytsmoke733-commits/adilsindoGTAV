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

Aceite de 09/10/2026, com gravação própria do Bloodstrike (OBS, 1920x1080, 60 fps, 71 s, fala em português
misturada com o áudio do jogo), na RX 6600:

- Testes: 7 de integração passam (1 min 54 s) e a suíte padrão passa (104 testes).
- `analisar`: 24 s na primeira vez (SHA-256, áudio, whisper na GPU, tradução e escolha de cortes pelo LLM);
  0,6 s na segunda, com o log "reaproveitando as etapas prontas".
- `renderizar`: clipe de 18 s em `corte` em 48 s (inclui subir o LLM para os textos); clipe de 20,8 s em
  `desfoque` + `dinamica` em 74 s; re-render só com legenda corrigida em 22 s.
- Saída conferida com `ffprobe`: 1080x1920, h264, AAC, 60 fps (igual à origem).
- Legenda dentro da área segura e sem esticar a imagem, conferido em frames dos dois clipes.
- Correção em `legenda_editavel.srt` (vírgula e `*aumentar*`) muda o `.ass` e o frame: a palavra sai em amarelo.

Resumo dos 9 critérios: passam 1, 2 (com ressalva de log), 3, 6, 7 e 8; falham em parte o 5 (tradução) e o 9
(`copy.txt`); o 4 (sincronia) precisa de uma pessoa assistindo ao clipe.

Atraso medido da legenda (clipe 1, `legenda.srt` contra o tempo por palavra de `transcript.json`; o clipe começa em
0,88 s do original). As legendas começam e terminam tarde, exceto a primeira (começa certa) e a última (termina certa):

| Legenda | Início na legenda | Primeira palavra falada | Fim na legenda | Última palavra falada |
|---|---|---|---|---|
| 1 | 0,00 s | 0,00 s | 6,16 s | 5,13 s |
| 2 ("Ted") | 6,16 s | 5,13 s | 6,69 s | 6,03 s |
| 3 | 6,69 s | 6,35 s | 11,97 s | 11,32 s |
| 4 | 11,97 s | 11,33 s | 13,38 s | 12,70 s |
| 5 | 13,38 s | 12,73 s | 17,96 s | 17,96 s |

Ou seja, os inícios atrasam de 0,34 s a 1,03 s e os finais até 1,03 s. Isso é a divisão proporcional por
caracteres descrita nas limitações. É medida em tempos, não substitui assistir ao clipe.

Falhas encontradas no aceite (ainda abertas):

- **Qualidade da transcrição em áudio de jogo.** Com música e efeitos por cima da voz, o whisper erra palavras
  ("e o destaque é bastante boa e só um Ted") e a tradução herda o erro. Revise a legenda.
- **Frase em inglês no meio da fala não é traduzida** (legenda "a gente mag stay out of sight" no clipe 2).
- **Texto vazado no `copy.txt`.** No clipe 2 o LLM escreveu o marcador literal `{ganchos[random]}` nas
  legendas do Instagram e do TikTok. Revise o `copy.txt` antes de postar.
- **Fato inventado e capa errada no clipe 1.** Os ganchos incluíram "mudando a forma do personagem", que não está
  no vídeo (veio da transcrição mal ouvida), e o "texto da capa" saiu como hashtags em vez de uma frase curta.
- **Alucinação do whisper em silêncio.** Num vídeo de gameplay sem fala
  (`D:\ReLive\BLOODSTRIKE\BLOODSTRIKE_2026.08.07-14.57.mp4`, 211 s) o whisper
  devolveu "Thank you." em trechos de 30 s e o pipeline os tratou como fala, gerando legendas e cortes sem sentido.
- O log do whisper com a RX 6600 (Vulkan) não é guardado em `work\<job>\`; o `whisper-cli` rodado à mão com o mesmo
  modelo imprime `ggml_vulkan: 0 = AMD Radeon RX 6600`.
- A sincronia fina (legenda no instante da fala) só se confirma assistindo ao clipe.
