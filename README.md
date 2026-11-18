# dunk-agentes

Agentes de marketing da **Dunk**. Regras, marca e arquitetura: ver [`CLAUDE.md`](CLAUDE.md).

| Módulo | Pasta | Status |
|---|---|---|
| Coletor (Insights do @dunkmidia → planilha `Dunk_Metricas`) | `coletor/` | Etapa 2 — não iniciado |
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

## O que falta

- [ ] Etapa 2: `coletor/instagram.py` (após ler a doc atual da Instagram Graph API), gravação na planilha, `.github/workflows/coletor.yml`, teste com 3 posts reais comparando com o app.
- [ ] Etapa 3: templates HTML 1080×1350 em `fabrica/templates/`, `gerar.py`, `checar.py`.
