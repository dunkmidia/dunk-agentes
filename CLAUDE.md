# CLAUDE.md — dunk-agentes

Repositório dos agentes de marketing da **Dunk** (agência de marketing, Bragança Paulista/SP). Este arquivo é lido pelo Claude Code em toda sessão. Fonte da verdade dos documentos: Google Drive `PROJ_04_DUNK/Operação/Claude` (D61). Em conflito entre este arquivo e um doc numerado, vale o doc e este arquivo deve ser atualizado.

_v1 · 17/11/2026 · Base: docs 01, 03 (D34, D51, D53, D54, D62, D69, D70, D71, D92, D99), 07, 08 §13 e §16, 09 (regras 3–6), 21 v2.1, 23c §7–8._

---

## 1. O que este repositório faz

| Módulo | Pasta | Função | Status |
|---|---|---|---|
| Coletor | `coletor/` | Lê os Insights do Instagram @dunkmidia todos os dias e grava na planilha `Dunk_Metricas` | Etapa 2 |
| Fábrica de Posts v0 | `fabrica/` | Pauta → roteiro → carrossel em PNG → checagem → pasta para revisão humana | Etapa 3 |

**Princípio de arquitetura:** o agente **lê** dados na planilha/banco, nunca analisa direto da API. As APIs da Meta são usadas para coletar (leitura). **Nada é publicado, pausado, impulsionado ou alterado automaticamente.** Quem publica é um humano (Lucas, D62).

## 2. Regras de segurança (inegociáveis)

1. Nenhum token, chave, senha ou JSON de conta de serviço em arquivo versionado. Só em `.env` (local, ignorado pelo git) e nos Secrets do GitHub.
2. Nunca imprimir token em log, saída de terminal ou commit. Ao depurar, mascarar (`EAAB…xyz`).
3. Permissões da Meta: somente leitura (`instagram_basic`, `instagram_manage_insights`, `pages_show_list`, `pages_read_engagement`). Se uma tarefa exigir permissão de escrita, **parar e perguntar ao Pedro**.
4. Nunca coletar dado de terceiros (seguidores, comentaristas, DMs) além de contagens agregadas. LGPD.
5. Antes de usar qualquer endpoint ou métrica da Meta, **ler a documentação atual** da Instagram Graph API: nomes de métrica mudam (ex.: `impressions` foi descontinuada e substituída por `views`). Não confiar em memória.
6. Ação fora do plano aprovado ou irreversível (apagar arquivo, sobrescrever planilha, mudar permissão): parar e perguntar. "Foi" do Pedro executa só o plano apresentado (D91).

## 3. A marca (resumo para gerar conteúdo)

- **Dunk** = agência de marketing generalista: "transformar atenção em cliente" para negócios locais (D70, D92). O perfil @dunkmidia é **100% agência generalista**, com a agência na frente (doc 21, D92).
- Sobretítulo e região: **"Agência de marketing · interior de São Paulo"** (D99).
- Produto para clínicas de estética ("Operação de Agenda", "Do clique à cadeira") **não** entra no @dunkmidia salvo decisão em contrário.
- Até 20/01/2027: **sem preço, proposta ou venda** em conteúdo (D34, D103). O fundo de funil é **conversa de diagnóstico por DM** ("Envie CLIENTE por DM").
- Personalidade: Sábio + Cuidador; direta, numérica, elegante, próxima (08 §10).

### 3.1 Identidade visual (Manual da Marca Dunk v1, D69)

| Elemento | Regra |
|---|---|
| Cores | Preto Dunk `#111111` · Laranja Dunk `#FF6A00` · Areia `#F4F1EC` · Branco `#FFFFFF` |
| Proporção | ~60% preto · 25% areia/branco · 15% laranja (provisória até o teste A/B, D47) |
| Fonte | **Inter Tight** (Google Fonts): 800 em títulos e números; 600 em rótulos (rótulo em MAIÚSCULAS); 400 em texto corrido. Nunca outra fonte |
| Contraste | Texto sobre laranja **sempre preto**. Laranja **nunca** é cor de texto sobre areia ou branco (só botão, destaque ou marca-texto com texto preto). Branco sobre laranja proibido em texto |
| Logo | "dunk." minúsculo com ponto; ponto sempre de cor diferente das letras. Arquivos em `Marketing/Dunk_logo_vetor/` (A_principal, B_destaque, simbolo_d). **Versão C não usar** |
| Proibido | Esticar logo, tirar o ponto, "DUNK." em maiúsculas, contorno, letra e fundo da mesma cor |

### 3.2 Voz e texto

- Número ou cena na 1ª linha (08 §16; 23c §8).
- Uma ideia por peça. Um CTA por peça.
- Linguagem do cliente, não da agência.
- CTA de topo "mandável" ("manda pra quem cuida do seu WhatsApp"); CTA de fundo "Envie CLIENTE por DM".
- Legenda com palavras-chave (busca do Instagram); no máximo 5 hashtags.

### 3.3 Palavras e expressões banidas (08 §13; D71)

`garantido`, `resultado garantido`, `faturamento garantido`, `lotar agenda`, `bombar`, `viralizar`, `explodir`, `alavancar`, `hack`, `robô` (usar "atendente de IA"), `Ponto garantido.` (lema só interno).

## 4. Regras de conteúdo que a checagem aplica (09 regras 3–6; 07; D51)

1. **Prova só das camadas 1 e 2** (D51): consultoria comercial dos sócios (empresas de serviço de R$100 mil a R$6 mi/mês) e operação de Instagram (saúde, viagens, escolas de dança). Nunca afirmar resultado de cliente sem número e autorização. Nunca misturar camadas.
2. **Todo número tem fonte** (nome + data) **ou o rótulo `EXEMPLO`** na própria peça.
3. **Nada da Clínica-Laboratório** em público.
4. **Sem antes/depois e sem dado de cliente/paciente.**
5. Sem promessa de resultado que a Dunk não controla (CDC, art. 37).
6. **Imagem:** a IA não gera rosto, pessoa, pele ou corpo. Peças usam tipografia, número, tela/print real anonimizado ou foto real fornecida pelos sócios.
7. **Reels e vídeo:** rosto e voz humanos (08 §16; 23c §7). A fábrica escreve o roteiro; quem grava é um sócio. Avatar só com decisão nova dos sócios.

## 5. Linha editorial (doc 21 v2.1, pendente de decisão na T-05)

| Dia | Série | Funil | Formato | Território |
|---|---|---|---|---|
| Seg | Conversa que vende | Topo | Reels | Agenda |
| Ter | A conta (derivada do artigo do blog) | Meio | Carrossel | Margem |
| Qua | Pronto para repassar | Topo | Carrossel | Agenda |
| Qui | Diagnóstico | Fundo | — | Experiência |
| Sex | Dunk por dentro | Meio | Reels | Experiência |
| Dom 20h | Do comercial para o marketing | Meio | — | Margem |

Toda peça sai em **collab** com o perfil do sócio do território (D53). Se a T-05 mudar a grade, atualizar esta tabela.

**Métrica:** envios ÷ alcance ≥ 2%, lida **por série a cada 4 semanas**, mais % de interações vindas do ICP (≥ 30%). Uma peça isolada é ruído (doc 21).

## 6. Estrutura do repositório

```
dunk-agentes/
├── CLAUDE.md
├── README.md
├── .env.example        # nomes das variáveis, sem valores
├── .gitignore          # bloqueia .env, *.json, credenciais/, saida/, .venv/
├── config.py           # lê .env; resolve GOOGLE_SA_JSON (caminho ou conteúdo)
├── credenciais/        # JSON da conta de serviço local (ignorado pelo git)
├── coletor/
│   ├── instagram.py
│   └── requirements.txt
├── fabrica/
│   ├── templates/      # HTML 1080×1350 com Inter Tight e cores D69
│   ├── gerar.py
│   ├── checar.py
│   └── referencias/    # banco de referências (agente 4)
├── saida/              # PNGs gerados (ignorado pelo git; vai para o Drive)
└── .github/workflows/coletor.yml
```

## 7. Variáveis de ambiente

| Variável | O que é |
|---|---|
| `META_TOKEN` | Token do usuário de sistema "coletor" (BM da Dunk, app Dunk Coletor) |
| `IG_USER_ID` | ID da conta business do @dunkmidia (descobrir com `python coletor/teste_token.py`) |
| `GOOGLE_SA_JSON` | Caminho do arquivo **ou** conteúdo do JSON da conta de serviço Google (projeto `dunk-agentes`). Local: caminho em `credenciais/`; GitHub Secrets: conteúdo. Ler via `config.carregar_credencial_google()` |
| `SHEET_ID` | ID da planilha `Dunk_Metricas` |

## 8. Como trabalhar neste repositório

- Antes de escrever código: mostrar o plano curto e esperar ok.
- Código em Python 3.11+, dependências em `requirements.txt`, funções pequenas, sem dependência paga.
- Testar contra dados reais com 3 posts e comparar com o app do Instagram antes de agendar.
- Commits pequenos, mensagem em português.
- Ao terminar uma etapa, atualizar o `README.md` com como rodar e o que falta.
