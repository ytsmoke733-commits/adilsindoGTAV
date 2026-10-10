# PROMPT MASTER — GTA 6 VIRAL CLIPS AI

Quero que você atue como um **engenheiro de software sênior, especialista em inteligência artificial, automação de vídeos curtos, edição audiovisual, análise de tendências e crescimento orgânico no TikTok e Instagram**.

Sua missão é desenvolver uma aplicação funcional chamada provisoriamente **GTA VIRAL AI**, especializada em encontrar tendências internacionais relacionadas a GTA 6, transformar vídeos autorizados em conteúdo vertical legendado em português brasileiro e preparar publicações para TikTok e Instagram Reels.

Não quero apenas uma landing page bonita, um protótipo visual ou uma lista de ideias. Quero um sistema funcional, modular, com interface profissional, processamento real de vídeos e integrações configuráveis.

## 1. OBJETIVO PRINCIPAL

Criar um sistema que automatize o máximo possível do seguinte processo:

1. Descobrir vídeos e clipes internacionais sobre GTA 6 que estejam ganhando popularidade.
2. Identificar tendências, assuntos virais, memes, novidades, cenas engraçadas, teorias e momentos surpreendentes.
3. Analisar os vídeos encontrados e identificar quais têm maior potencial de engajamento no Brasil.
4. Trabalhar com arquivos enviados pelo usuário ou vídeos cujo uso tenha sido autorizado, incluindo materiais licenciados e conteúdos próprios.
5. Transcrever as falas originais, traduzir para português brasileiro e gerar legendas sincronizadas.
6. Editar os vídeos automaticamente, mantendo o contexto original e destacando os momentos mais interessantes.
7. Gerar diferentes versões para Instagram Reels e TikTok.
8. Criar títulos, descrições, hashtags e sugestões de chamadas para comentários.
9. Organizar os conteúdos em uma fila de revisão e publicação.
10. Aprender com os resultados das publicações para melhorar as próximas recomendações.

O sistema deve priorizar a automação, mas nunca fingir que executou uma ação que não foi realmente concluída.

## 2. PAINEL PRINCIPAL

Crie um dashboard moderno, responsivo, com estética inspirada no universo GTA: preto, grafite, branco e detalhes em verde-limão ou amarelo. Utilize uma interface limpa, sem excesso de elementos visuais.

O painel deve apresentar:

- Quantidade de tendências encontradas.
- Vídeos analisados.
- Clipes editados.
- Vídeos aguardando revisão.
- Publicações programadas.
- Publicações concluídas.
- Histórico de processamento.
- Taxa de aprovação dos vídeos.
- Desempenho dos conteúdos publicados, quando houver dados disponíveis.

Inclua botões funcionais para:

- **Buscar tendências**
- **Analisar vídeos**
- **Gerar novos clipes**
- **Editar em lote**
- **Abrir editor**
- **Revisar conteúdos**
- **Exportar vídeos**
- **Conectar redes sociais**
- **Configurar automações**

Cada botão deve executar uma ação real ou informar claramente qual integração ainda precisa ser configurada.

## 3. RADAR DE TENDÊNCIAS INTERNACIONAIS

Desenvolva um módulo chamado TREND RADAR.

Ele deverá pesquisar e organizar conteúdos relacionados a GTA 6 usando fontes e integrações legítimas disponíveis, como:

- YouTube Data API.
- Fontes públicas e autorizadas de tendências.
- Canais especializados em GTA.
- Criadores internacionais.
- Notícias recentes sobre GTA 6.
- Listas de vídeos populares e resultados de pesquisa.
- Fontes adicionais que possam ser conectadas legalmente.

Pesquise termos em inglês, incluindo:

- GTA 6 funny moments
- GTA 6 gameplay
- GTA 6 hidden details
- GTA 6 leaks and rumors
- GTA 6 insane moments
- GTA 6 NPC reactions
- GTA 6 secrets
- GTA 6 news
- GTA 6 theories
- GTA 6 viral clips
- GTA 6 comparison
- GTA 6 memes

Diferencie claramente notícias confirmadas, teorias, rumores e conteúdo humorístico. Não apresente especulações como fatos oficiais.

Para cada resultado, armazene, quando disponível:

- Título.
- Criador ou canal.
- Plataforma de origem.
- Link original.
- Data de publicação.
- Visualizações.
- Curtidas e comentários, se acessíveis.
- Duração.
- Idioma.
- Tema identificado.
- Fonte dos dados.
- Situação de autorização de uso.
- Potencial estimado de interesse para o público brasileiro.

Não invente métricas. Se determinada plataforma não fornecer um dado, apresente-o como indisponível.

### Pontuação de viralização

Crie um algoritmo de pontuação de 0 a 100 que considere:

- Velocidade de crescimento das visualizações, quando houver dados históricos.
- Engajamento proporcional às visualizações.
- Recência.
- Interesse do público brasileiro pelo assunto.
- Potencial de retenção nos primeiros segundos.
- Originalidade e relevância do momento.
- Saturação do tema.
- Possibilidade de produzir uma adaptação autorizada.

Não confunda visualizações totais com crescimento viral. Quando não houver dados suficientes, apresente uma pontuação provisória e explique a limitação.

Permita filtrar por período, idioma, duração, assunto, plataforma e pontuação.

## 4. ANÁLISE INTELIGENTE DOS CLIPES

Crie um módulo chamado CLIP ANALYZER.

Quando um vídeo autorizado for disponibilizado, o sistema deverá:

1. Analisar sua duração e características técnicas.
2. Identificar cenas visualmente interessantes.
3. Transcrever as falas utilizando reconhecimento de voz.
4. Identificar mudanças de assunto, pausas, reações e momentos de surpresa.
5. Encontrar possíveis pontos de início e término para clipes curtos.
6. Identificar trechos com potencial de gerar curiosidade.
7. Sugerir ganchos para os primeiros 1 a 3 segundos, sem distorcer o conteúdo.
8. Recomendar a duração ideal conforme o material disponível.
9. Detectar informações possivelmente falsas, alegações não verificadas e trechos que necessitem de contexto.
10. Apresentar uma prévia dos cortes antes de renderizar.

Utilize processamento de vídeo real, com ferramentas como FFmpeg, e modelos de IA apropriados para transcrição e análise visual.

Não implemente apenas botões fictícios. Se uma dependência estiver ausente, informe o que precisa ser instalado.

## 5. TRADUÇÃO E LEGENDAS AUTOMÁTICAS

Crie um módulo chamado AUTO SUBTITLE.

Fluxo obrigatório:

1. Detectar o idioma original.
2. Transcrever as falas.
3. Traduzir o texto para português brasileiro natural.
4. Preservar o significado, o humor e as gírias relevantes.
5. Ajustar a tradução para leitura rápida em vídeos curtos.
6. Sincronizar cada frase com o áudio.
7. Gerar legendas embutidas no vídeo.
8. Permitir correções manuais.
9. Exportar também arquivos SRT e VTT.
10. Gerar uma transcrição revisável antes da renderização final.

As legendas devem ter estética profissional de vídeos curtos:

- Fonte sem serifa, forte e legível.
- Texto branco com contorno escuro.
- Palavras importantes destacadas em amarelo ou verde.
- Quebra automática de linhas.
- Sincronização precisa.
- Posicionamento dentro da área segura da tela.
- Animações discretas quando apropriadas.
- Sem cobrir elementos essenciais do jogo.

Permita escolher entre legendas simples, legendas dinâmicas e legendas com destaque de palavras.

Não traduza nomes próprios, termos do jogo ou gírias automaticamente quando isso prejudicar o contexto.

## 6. EDITOR AUTOMÁTICO DE VÍDEOS

Crie o módulo AUTO EDITOR.

O editor deve permitir:

- Cortar trechos.
- Unir segmentos.
- Ajustar proporção.
- Redimensionar vídeos.
- Reposicionar a imagem.
- Aplicar legendas.
- Ajustar volume.
- Normalizar áudio quando necessário.
- Aplicar correção de imagem moderada.
- Adicionar zooms discretos em momentos relevantes.
- Inserir transições somente quando fizerem sentido.
- Adicionar uma introdução curta, se solicitada.
- Gerar encerramentos opcionais.
- Exportar diferentes versões do mesmo clipe.

Configuração padrão:

- Proporção: 9:16.
- Resolução: 1080 × 1920.
- Formato: MP4.
- Codec de vídeo: H.264.
- Áudio: AAC.
- Taxa de quadros: preservar a original quando viável, ou usar uma taxa compatível com o material.
- Duração: definida de acordo com o melhor trecho, sem forçar cortes artificiais.

Se o vídeo original for horizontal, utilize enquadramento inteligente para manter a ação principal visível. Evite ampliar excessivamente ou cortar elementos importantes.

Nunca estique a imagem para preencher a tela.

Não aplique músicas, efeitos sonoros ou trilhas comerciais sem autorização apropriada. Quando necessário, utilize áudio original autorizado ou bibliotecas licenciadas.

### Perfis de edição

Implemente quatro presets:

**PRESET 1 — GAMEPLAY VIRAL**
- Cortes rápidos quando apropriados.
- Legendas dinâmicas.
- Zooms sutis em acontecimentos importantes.
- Gancho inicial baseado no conteúdo real.

**PRESET 2 — CURIOSIDADES GTA 6**
- Edição mais informativa.
- Legendas claras.
- Espaço para contexto e explicações.
- Indicação da fonte das informações.

**PRESET 3 — HUMOR E MEMES**
- Ritmo adequado à piada.
- Destaque das falas relevantes.
- Efeitos discretos e opcionais.
- Preservação do contexto original.

**PRESET 4 — NOTÍCIAS E TEORIAS**
- Título contextual.
- Legendas limpas.
- Identificação de rumores e informações confirmadas.
- Fonte verificável quando disponível.

Todos os presets devem ser editáveis.

## 7. GERAÇÃO DE CONTEÚDO EM LOTE

Crie um sistema de processamento em lote.

O usuário poderá selecionar diversos vídeos autorizados e escolher:

- Idioma de origem.
- Idioma das legendas.
- Estilo de edição.
- Duração desejada.
- Resolução.
- Número máximo de cortes por vídeo.
- Modelo de legenda.
- Nome do arquivo.
- Perfil de exportação.
- Prioridade de processamento.

O sistema deverá criar uma fila de tarefas, exibir o progresso real de cada uma e permitir pausar, cancelar, retomar ou repetir tarefas que falharam.

Implemente controle de erros, registro de logs e prevenção de arquivos duplicados.

Se um vídeo falhar, os outros devem continuar sendo processados.

Não mantenha todos os vídeos simultaneamente na memória. Utilize processamento eficiente, arquivos temporários e limpeza segura dos arquivos intermediários.

## 8. IA PARA CRIAR TÍTULOS, LEGENDAS E DESCRIÇÕES

Crie um módulo chamado VIRAL COPYWRITER.

Para cada clipe, gere:

- Cinco opções de gancho inicial.
- Três títulos.
- Uma legenda curta para Instagram.
- Uma descrição adaptada para TikTok.
- Um conjunto de hashtags relevantes.
- Uma pergunta para estimular comentários.
- Uma sugestão de texto para a capa.
- Uma breve justificativa da estratégia escolhida.

O tom deve ser brasileiro, natural, direto e familiar ao público gamer.

Evite títulos enganosos, falsas promessas, hashtags irrelevantes e frases genéricas repetidas em todos os vídeos.

Não invente acontecimentos que não aparecem no clipe.

Permita gerar textos em estilos diferentes: humorístico, curioso, informativo e provocativo, sem recorrer a desinformação.

## 9. CENTRAL DE REVISÃO

Crie uma biblioteca de vídeos com os seguintes estados:

- Encontrado.
- Aguardando autorização.
- Pronto para análise.
- Em processamento.
- Aguardando revisão.
- Aprovado.
- Exportado.
- Programado.
- Publicado.
- Falhou.

Cada vídeo deverá possuir:

- Miniatura.
- Título.
- Fonte.
- Duração.
- Pontuação de tendência.
- Prévia do vídeo.
- Transcrição.
- Legenda traduzida.
- Configurações de edição.
- Histórico de versões.
- Botões de aprovar, rejeitar, editar, reprocessar e exportar.

Nenhum vídeo deve ser publicado automaticamente antes de ser aprovado pelo usuário, salvo se ele ativar explicitamente essa opção nas configurações.

## 10. PUBLICAÇÃO NO INSTAGRAM E TIKTOK

Implemente uma camada de integração com as APIs oficiais e os recursos de publicação disponibilizados por cada plataforma.

Para o Instagram, avalie a Instagram Graph API e os requisitos de conta profissional, permissões e publicação de Reels.

Para o TikTok, avalie a Content Posting API, suas permissões, requisitos de auditoria e limitações de publicação.

O sistema deve:

- Permitir conectar contas de maneira segura.
- Mostrar quais permissões estão faltando.
- Preparar vídeos, descrições e hashtags.
- Permitir exportação manual quando a publicação direta não estiver disponível.
- Programar publicações apenas quando a integração permitir.
- Registrar IDs e links de publicações quando retornados pela plataforma.
- Consultar métricas disponíveis e autorizadas.
- Identificar falhas e permitir novas tentativas seguras.

Não prometa publicação automática em contas sem as permissões necessárias. Se uma API não permitir determinada ação, apresente uma alternativa funcional.

Nunca armazene senhas de redes sociais em texto puro.

## 11. PAINEL DE DESEMPENHO

Desenvolva um módulo de análise que acompanhe, quando houver dados acessíveis:

- Visualizações.
- Curtidas.
- Comentários.
- Compartilhamentos.
- Tempo médio assistido.
- Retenção.
- Percentual de conclusão.
- Seguidores conquistados.
- Desempenho por tema.
- Desempenho por estilo de edição.
- Horários de publicação.

Compare os vídeos publicados e identifique padrões.

Exemplo: se clipes de NPCs tiverem desempenho superior ao de teorias, o sistema poderá recomendar mais conteúdo desse tema, desde que os dados sustentem essa conclusão.

Não invente dados de retenção ou estatísticas que as APIs não forneçam.

## 12. ARQUITETURA TÉCNICA

Antes de implementar, avalie uma arquitetura adequada para processamento de vídeo e integrações reais.

Considere a seguinte stack como ponto de partida:

- Front-end: Next.js com TypeScript.
- Interface: Tailwind CSS e componentes acessíveis.
- Back-end: Python com FastAPI.
- Banco de dados: PostgreSQL.
- Fila de tarefas: Redis com Celery ou solução equivalente.
- Processamento audiovisual: FFmpeg.
- Transcrição: Whisper ou serviço equivalente.
- IA de texto: Claude API ou outro modelo configurável.
- Armazenamento: sistema de arquivos local em desenvolvimento e armazenamento de objetos em produção.
- Autenticação: sistema seguro com controle de acesso.
- Monitoramento: logs, estados das tarefas e tratamento de exceções.

Você pode propor alternativas melhores, mas explique as decisões e mantenha o projeto simples de instalar e manter.

Nunca exponha chaves de API no front-end.

Crie um arquivo `.env.example` com os nomes das variáveis necessárias, sem segredos reais.

Inclua migrações de banco de dados, documentação de instalação e testes para as principais funcionalidades.

## 13. INTEGRAÇÕES E CUSTOS

O sistema deve permitir configurar separadamente:

- Chave da Anthropic API.
- Credenciais da YouTube Data API.
- Serviço de transcrição.
- Armazenamento.
- Credenciais e tokens das redes sociais.
- Serviço de análise visual, caso necessário.

Não presuma que minha conta Claude inclui acesso à API da Anthropic. Explique a diferença entre assinatura do Claude e uso da API, além dos custos externos de processamento, armazenamento e transcrição.

Crie uma tela de configurações para informar quais serviços estão conectados e testar suas conexões.

Quando não houver credenciais, ofereça um modo de demonstração claramente identificado, sem apresentar dados fictícios como resultados reais.

## 14. DIREITOS AUTORAIS E USO RESPONSÁVEL

Este requisito é obrigatório.

O sistema não deve baixar indiscriminadamente vídeos de terceiros nem contornar proteções técnicas ou restrições das plataformas.

Utilize materiais próprios, licenciados, autorizados pelo criador ou obtidos por meios oficialmente permitidos.

A disponibilidade pública de um vídeo não significa que ele esteja liberado para republicação.

Inclua um campo para registrar a licença, autorização ou fundamento de uso de cada arquivo.

Não considere que traduzir, cortar, legendar ou adicionar efeitos concede automaticamente o direito de republicar o conteúdo.

Permita armazenar o link da fonte, os dados do criador e as informações de atribuição solicitadas pela licença.

Diferencie autorização de uso, direitos autorais e eventuais permissões específicas das plataformas.

Para vídeos oficiais de GTA 6, respeite os termos aplicáveis e não presuma que qualquer material promocional possa ser reutilizado livremente.

## 15. SEGURANÇA E CONFIABILIDADE

Implemente:

- Validação dos arquivos enviados.
- Limites de tamanho e duração.
- Proteção contra arquivos maliciosos.
- Controle de acesso.
- Gerenciamento seguro de tokens.
- Limpeza de arquivos temporários.
- Tratamento de falhas de rede.
- Logs sem exposição de segredos.
- Limites de consumo por tarefa.
- Proteção contra duplicação de publicações.
- Avisos quando uma tarefa depender de serviços pagos.

O sistema deve informar claramente quando não puder concluir uma operação.

## 16. EXPERIÊNCIA DO USUÁRIO

Quero uma experiência extremamente simples.

O fluxo principal deve funcionar assim:

1. Abro o painel.
2. Clico em “Buscar tendências”.
3. Vejo os conteúdos encontrados e suas fontes.
4. Seleciono um conteúdo e verifico as condições de uso.
5. Envio o arquivo autorizado ou seleciono um material já disponível.
6. Clico em “Gerar clipes”.
7. A IA analisa, transcreve, traduz e edita.
8. Visualizo o resultado com as legendas.
9. Corrijo o que for necessário.
10. Aprovo e exporto ou publico por uma integração autorizada.
11. Acompanho os resultados quando os dados estiverem disponíveis.

Crie também um modo avançado para ajustar cortes, legendas, duração, áudio e enquadramento.

## 17. ORDEM DE EXECUÇÃO

Não tente construir tudo de uma vez sem validar a arquitetura.

Trabalhe nesta ordem:

**Fase 1 — Fundação**
- Apresentar a arquitetura.
- Criar a estrutura do projeto.
- Desenvolver o dashboard.
- Configurar banco de dados.
- Implementar autenticação e biblioteca de vídeos.

**Fase 2 — Processamento**
- Implementar upload de vídeos.
- Integrar FFmpeg.
- Implementar transcrição e tradução.
- Criar geração e sincronização de legendas.
- Implementar renderização e exportação.

**Fase 3 — Tendências**
- Conectar fontes reais.
- Implementar pesquisa.
- Criar filtros e pontuação de tendência.
- Armazenar os dados e as fontes consultadas.

**Fase 4 — Automação**
- Criar fila de tarefas.
- Implementar processamento em lote.
- Desenvolver presets de edição.
- Criar fila de revisão e histórico.

**Fase 5 — Redes sociais**
- Integrar as APIs oficiais disponíveis.
- Criar a preparação de publicações.
- Implementar publicação quando autorizada.
- Registrar resultados e erros.

**Fase 6 — Inteligência de desempenho**
- Analisar resultados reais.
- Comparar temas e formatos.
- Recomendar melhorias com base nos dados disponíveis.

## 18. INSTRUÇÕES FINAIS PARA VOCÊ, CLAUDE

Primeiro, analise todos os requisitos e apresente uma arquitetura viável, identificando limitações, dependências e custos.

Em seguida, comece a desenvolver o projeto de verdade.

Não entregue apenas um plano, wireframe, protótipo ou código ilustrativo. Implemente cada fase, teste as funcionalidades e mostre o que realmente funciona.

Se estiver trabalhando no Claude Code, utilize os recursos disponíveis para criar e modificar os arquivos do projeto, executar comandos permitidos e testar o resultado.

Se estiver trabalhando apenas no chat, gere os arquivos e o código por etapas, mantendo a estrutura consistente e explicando como executá-los.

Se uma integração não puder ser concluída sem credenciais ou aprovação externa, implemente a estrutura necessária, identifique o bloqueio e forneça instruções precisas para habilitá-la.

Não simule buscas reais, não invente vídeos encontrados e não declare uma publicação concluída sem confirmação da plataforma.

**Prioridade máxima:** construir primeiro um fluxo funcional que receba um vídeo autorizado, identifique os melhores trechos, transcreva o áudio, traduza para português, gere legendas sincronizadas, aplique edição vertical e exporte um MP4 pronto para revisão.

Depois, conecte a descoberta de tendências e a publicação nas redes sociais.

Comece pela arquitetura e pela Fase 1. Ao terminar cada fase, apresente os arquivos criados, os testes realizados, os resultados obtidos e os próximos passos.