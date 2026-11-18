# dunk-agentes

Agentes de marketing da **Dunk**. Regras, marca e arquitetura: ver [`CLAUDE.md`](CLAUDE.md).

| Módulo | Pasta | Status |
|---|---|---|
| Coletor (Insights do @dunkmidia → planilha `Dunk_Metricas`) | `coletor/` | Etapa 2 — coletor pronto; falta agendar |
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
- `envios_por_alcance` = compartilhamentos ÷ alcance. `serie` vem da tag `#serie_<nome>` na legenda; sem tag, a célula não é alterada (pode preencher à mão).
- A planilha precisa estar compartilhada como Editor com a conta de serviço `coletor@dunk-agentes.iam.gserviceaccount.com`.

## O que falta

- [x] Etapa 2: `coletor/instagram.py` com gravação na planilha.
- [ ] Etapa 2: comparar os 3 posts com o app do Instagram; `.github/workflows/coletor.yml` (agendamento diário).
- [ ] Etapa 3: templates HTML 1080×1350 em `fabrica/templates/`, `gerar.py`, `checar.py`.
