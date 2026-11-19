# dunk-agentes

Agentes de marketing da **Dunk**. Regras, marca e arquitetura: ver [`CLAUDE.md`](CLAUDE.md).

| Módulo | Pasta | Status |
|---|---|---|
| Coletor (Insights do @dunkmidia → planilha `Dunk_Metricas`) | `coletor/` | Etapa 2 — concluída; roda todo dia às 06:00 |
| Analista semanal (opção A: regras fixas, sem IA) | `analista/` | Concluído; roda toda segunda às 07:00 |
| Fábrica de Posts v0 (pauta → carrossel PNG → checagem) | `fabrica/` | Etapa 3 — não iniciado |

Nada é publicado, pausado ou alterado automaticamente. Quem publica é um humano.

## Instalação (Windows / PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r coletor/requirements.txt
```

Requer Python 3.11+.

## Configuração

1. Copie `.env.example` para `.env` e preencha (o `.env` é ignorado pelo git).
2. `GOOGLE_SA_JSON` aceita **caminho** ou **conteúdo** do JSON da conta de serviço:
   - local: salve o arquivo em `credenciais/` (pasta ignorada) e use
     `GOOGLE_SA_JSON=credenciais/dunk-agentes-sa.json`;
   - GitHub Actions: cole o conteúdo do JSON no Secret `GOOGLE_SA_JSON`.
3. No código, use `config.obter("NOME")` e `config.carregar_credencial_google()`.

Nunca coloque token, chave ou JSON de credencial em arquivo versionado. O `.gitignore` bloqueia `.env`, `credenciais/` e qualquer `*.json`.

## Coletor (Etapa 2)

```powershell
.\.venv\Scripts\python coletor\teste_token.py            # confere token, página e IG_USER_ID
.\.venv\Scripts\python coletor\instagram.py --seco --limite 3   # só imprime, não grava
.\.venv\Scripts\python coletor\instagram.py               # coleta tudo e grava na planilha
```

- Grava na aba `posts` de `Dunk_Metricas` (chave `post_id`: atualiza se existe, acrescenta se é novo; nunca apaga) e registra cada execução na aba `log`.
- Métricas (Graph API v27.0): imagem e carrossel = alcance, visualizações, compartilhamentos, salvamentos, curtidas, comentários, interações totais, visitas ao perfil, seguidores ganhos; Reels = as mesmas sem visitas/seguidores (a API não oferece) + tempo médio assistido (s).
- `envios_por_alcance` = compartilhamentos ÷ alcance (vazio se alcance = 0).
- `serie` vem da tag `#serie_<nome>` na legenda (gravada em minúsculas). Sem tag, a célula **nunca** é alterada: série preenchida à mão é preservada. Com tag, a tag prevalece.
  - Como funciona: `montar_linha` só inclui `serie` no dict quando há tag, e `gravar_posts` atualiza linhas existentes célula a célula, apenas com as chaves presentes (o mesmo vale para métricas que a API não devolveu). Conferido em 18/11/2026 com planilha simulada: duas execuções seguidas mantiveram a série manual e atualizaram as métricas.

### Agendamento (GitHub Actions)

- `.github/workflows/coletor.yml` roda todo dia às 06:00 de Brasília (`cron: 0 9 * * *`) e também à mão em **Actions > coletor > Run workflow**.
- Secrets do repositório (Settings > Secrets and variables > Actions > **Repository secrets**): `META_TOKEN` (só o valor, sem `META_TOKEN=` nem aspas), `IG_USER_ID`, `SHEET_ID`, `GOOGLE_SA_JSON` (**conteúdo** do JSON, não o caminho).
- Falha: execução vermelha + e-mail do GitHub; o motivo fica na aba `log`. Erro 190 "Malformed access token" = segredo colado errado; 190 sem "Malformed" = token expirado/revogado.
- Token do usuário de sistema "coletor" gerado com validade **Nunca**.
- A planilha precisa estar compartilhada como Editor com a conta de serviço `coletor@dunk-agentes.iam.gserviceaccount.com`.

## Analista semanal

Lê a aba `posts` (nunca a API) e faz a leitura da semana com regras fixas, sem IA. Base: PRD do Analista Semanal (no Drive).

**O que faz**

1. Resumo da semana × semana anterior: posts, alcance (total, mediano e médio por post), visualizações, envios, salvamentos, comentários, visitas ao perfil, seguidores ganhos, com variação em %.
2. Indicadores do doc 21 em 4 semanas: envios ÷ alcance e salvamentos ÷ alcance (meta ≥ 2%), no total e por série.
3. Ranking: 3 melhores e 3 piores posts da semana por alcance (e por envios, se houver), com link.
4. Alcance médio por formato (Reels, carrossel, imagem) em 4 semanas.
5. Frequência: posts × meta de 6, dias com mais de 1 post, posts a menos de 2 h um do outro.
6. Alertas:
   - legenda: número sem `Fonte:` nem `EXEMPLO`, taxa anual a conferir ("80%, ano após ano"), palavra banida, mais de 5 hashtags, provável anotação interna, CTA "Siga para" (só conta), número sem substantivo e frase sem pontuação (indícios de texto truncado);
   - frequência: dia com 3+ posts ou intervalo < 2 h; semana com mais de 6 posts.

Grupo com menos de 5 posts sai marcado **amostra pequena**: não tire conclusão dele. Os alertas são heurísticos (há falso positivo); a conferência é humana.

**Quando roda:** `.github/workflows/analista.yml`, toda segunda às 07:00 de Brasília (`cron: 0 10 * * 1`, 1 h depois da coleta), sobre a **última semana completa (segunda a domingo)**. Também roda à mão em **Actions > analista > Run workflow**. Usa só 2 dos secrets do coletor: `SHEET_ID` e `GOOGLE_SA_JSON` (não acessa a Meta). Falha = execução vermelha + e-mail do GitHub.

**O que grava** (na planilha `Dunk_Metricas`; nunca apaga nada):

- Aba `semanal`: 1 linha por semana (chave `semana_inicio`), com os números do resumo, indicadores de 4 semanas, frequência e `alertas_da_semana`. Rodar de novo na mesma semana atualiza a linha em vez de duplicar.
- Aba `alertas`: 1 linha por alerta (`data`, `post_id`, `link`, `tipo`, `nivel`, `regra`, `trecho`, `status`, `criado_em`). Níveis: `alerta` (provável erro), `conferir` (indício fraco), `contar` (só contagem).
  - **Coluna `status`:** quem tratar o alerta escreve `ok` (falso positivo ou já resolvido) ou `corrigir`. O analista só acrescenta alertas novos (chave = post + regra + trecho) e nunca reescreve linha existente: o `status` preenchido à mão é preservado.
  - Na 1ª execução (aba vazia) olha todos os posts; depois, só os da semana. Alerta de frequência só é gravado para dia/semana já encerrados.
- Resumo da execução: o relatório inteiro aparece na página da execução no GitHub Actions (job summary).

**Como rodar à mão**

```powershell
.\.venv\Scripts\python analista\semanal.py                     # última semana completa, só imprime
.\.venv\Scripts\python analista\semanal.py --ate 2026-11-17    # 7 dias que terminam nessa data, só imprime
.\.venv\Scripts\python analista\semanal.py --todos             # alertas sobre todos os posts
.\.venv\Scripts\python analista\semanal.py --gravar            # grava nas abas semanal e alertas
```

Sem `--gravar`, nada é escrito. Com `--gravar`, `--ate` precisa ser um domingo.

## O que falta

- [x] Etapa 2: `coletor/instagram.py`, gravação na planilha, conferência de 3 posts com o app (18/11/2026), agendamento diário no GitHub Actions (1ª execução verde em 18/11/2026).
- [x] Analista semanal (pedidos A1–A4 do PRD): resumo, alertas, gravação nas abas `semanal` e `alertas` (1ª gravação local em 18/11/2026), agendamento às segundas.
- [ ] Analista: teste final pelo Actions (Run workflow) e conferência dos critérios A1–A5 do PRD; o alerta de 5 posts em 17/11 entra na aba `alertas` na execução de 23/11/2026.
- [ ] Definir quem trata os alertas toda segunda (PRD Q1).
- [ ] Preencher à mão a coluna `serie` dos posts antigos (sem tag `#serie_`).
- [ ] Etapa 3: templates HTML 1080×1350 em `fabrica/templates/`, `gerar.py`, `checar.py`.
