"""Analista semanal (opção A: regras fixas, sem IA) — lê a aba `posts` e imprime o resumo da semana.

Uso (na raiz do repo):
    python analista/semanal.py                    # última semana completa (seg–dom), só imprime
    python analista/semanal.py --ate 2026-11-17   # 7 dias que terminam em 17/11 (inclusive)
    python analista/semanal.py --todos            # alertas sobre todos os posts, não só os da semana
    python analista/semanal.py --gravar           # grava nas abas semanal e alertas (+ resumo do Actions)

Itens 1 a 7 da seção 3 do PRD_ANALISTA_SEMANAL.md. Grupos com menos de 5 posts saem marcados
"amostra pequena". Sem --gravar, nada é escrito na planilha. Com --gravar: a aba semanal tem 1 linha
por semana (atualizada no lugar se rodar de novo); a aba alertas só recebe alertas novos e nunca
reescreve linha existente (a coluna status preenchida à mão é preservada). Nunca apaga nada.
"""

import argparse
import os
import re
import statistics
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from coletor.instagram import BRASILIA, abrir_aba, abrir_planilha, agora_brasilia, com_retentativa  # noqa: E402
from config import ErroConfig  # noqa: E402

AMOSTRA_MINIMA = 5        # PRD §4: comparação só com ≥ 5 posts em cada grupo
META_POSTS_SEMANA = 6     # doc 21
META_TAXA = 0.02          # envios ÷ alcance e salvamentos ÷ alcance (doc 21)
INTERVALO_MINIMO = timedelta(hours=2)
POSTS_DIA_ALERTA = 3      # alerta diário a partir de 3 posts no dia (ou intervalo < 2 h)
AMOSTRA = "amostra pequena"

FORMATOS = {"REELS": "Reels", "CAROUSEL_ALBUM": "Carrossel", "IMAGE": "Imagem"}
NUMERICAS = [
    "alcance", "visualizacoes", "compartilhamentos", "salvamentos", "curtidas", "comentarios",
    "interacoes_totais", "visitas_perfil", "seguidores_ganhos", "tempo_medio_assistido_s",
]
SEM_SERIE = "(sem série)"
EPOCA_SHEETS = datetime(1899, 12, 30)


# ---------------------------------------------------------------- leitura

def ler_linhas(planilha=None) -> list[list]:
    """Valores crus da aba posts (números como número). Só leitura."""
    from gspread.utils import ValueRenderOption

    planilha = planilha or abrir_planilha()
    aba = com_retentativa(planilha.worksheet, "posts")
    return com_retentativa(aba.get_all_values, value_render_option=ValueRenderOption.unformatted)


def para_numero(valor) -> float | None:
    if valor is None or valor == "":
        return None
    if isinstance(valor, (int, float)):
        return float(valor)
    texto = str(valor).strip().replace(" ", "")
    if "," in texto:  # formato brasileiro digitado à mão: 1.234,5
        texto = texto.replace(".", "").replace(",", ".")
    try:
        return float(texto)
    except ValueError:
        return None


def para_data(valor) -> datetime | None:
    if isinstance(valor, (int, float)):  # célula convertida em data pelo Sheets
        return EPOCA_SHEETS + timedelta(days=float(valor))
    texto = str(valor or "").strip()
    for formato in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(texto, formato)
        except ValueError:
            continue
    return None


def montar_posts(linhas: list[list]) -> tuple[list[dict], int]:
    """Lista de posts (dict) e quantidade de linhas descartadas por data inválida."""
    if not linhas:
        return [], 0
    cabecalho = [str(c).strip() for c in linhas[0]]
    posts, descartadas = [], 0
    for bruta in linhas[1:]:
        celula = dict(zip(cabecalho, bruta))
        if not str(celula.get("post_id", "")).strip():
            continue
        quando = para_data(celula.get("data"))
        if quando is None:
            descartadas += 1
            continue
        post = {
            "post_id": str(celula["post_id"]).strip(),
            "data": quando,
            "tipo": str(celula.get("tipo", "")).strip(),
            "permalink": str(celula.get("permalink", "")).strip(),
            "serie": str(celula.get("serie", "")).strip().lower() or SEM_SERIE,
            "legenda": str(celula.get("legenda", "")),
        }
        for coluna in NUMERICAS:
            post[coluna] = para_numero(celula.get(coluna))
        posts.append(post)
    return posts, descartadas


# ---------------------------------------------------------------- contas

def no_periodo(posts: list[dict], primeiro_dia: date, ultimo_dia: date) -> list[dict]:
    inicio = datetime.combine(primeiro_dia, datetime.min.time())
    fim = datetime.combine(ultimo_dia + timedelta(days=1), datetime.min.time())
    return sorted((p for p in posts if inicio <= p["data"] < fim), key=lambda p: p["data"])


def valores(posts: list[dict], coluna: str) -> list[float]:
    return [p[coluna] for p in posts if p[coluna] is not None]


def soma(posts: list[dict], coluna: str) -> float | None:
    lista = valores(posts, coluna)
    return sum(lista) if lista else None


def mediana(posts: list[dict], coluna: str) -> float | None:
    lista = valores(posts, coluna)
    return statistics.median(lista) if lista else None


def media(posts: list[dict], coluna: str) -> float | None:
    lista = valores(posts, coluna)
    return statistics.fmean(lista) if lista else None


def taxa(posts: list[dict], numerador: str) -> tuple[float | None, int]:
    """Soma do numerador ÷ soma do alcance, só nos posts que têm os dois. Retorna (taxa, n)."""
    validos = [p for p in posts if p[numerador] is not None and p["alcance"] is not None]
    alcance = sum(p["alcance"] for p in validos)
    if not alcance:
        return None, len(validos)
    return sum(p[numerador] for p in validos) / alcance, len(validos)


def variacao(atual: float | None, anterior: float | None) -> str:
    if atual is None or anterior is None or anterior == 0:
        return "—"
    return f"{(atual - anterior) / anterior * 100:+.1f}%".replace(".", ",")


# ---------------------------------------------------------------- formatação

def num(valor: float | None, casas: int = 0) -> str:
    if valor is None:
        return "—"
    texto = f"{valor:,.{casas}f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def pct(valor: float | None) -> str:
    return "—" if valor is None else f"{valor * 100:.2f}%".replace(".", ",")


def dia(d: date | datetime) -> str:
    return d.strftime("%d/%m")


def marca_amostra(n: int) -> str:
    return f"  [{AMOSTRA}]" if n < AMOSTRA_MINIMA else ""


def nome_formato(tipo: str) -> str:
    return FORMATOS.get(tipo, tipo or "?")


def titulo(texto: str) -> list[str]:
    return ["", texto, "-" * len(texto)]


# ---------------------------------------------------------------- seções

def secao_resumo(semana: list[dict], anterior: list[dict], rotulo_sem: str, rotulo_ant: str) -> list[str]:
    linhas = titulo(f"1. RESUMO DA SEMANA  {rotulo_sem}  ×  anterior {rotulo_ant}")
    linhas.append(f"{'':28}{'semana':>12}{'anterior':>12}{'variação':>11}")

    def linha(rotulo, atual, ant, casas=0):
        linhas.append(f"{rotulo:28}{num(atual, casas):>12}{num(ant, casas):>12}{variacao(atual, ant):>11}")

    linha("posts", len(semana), len(anterior))
    linha("alcance total", soma(semana, "alcance"), soma(anterior, "alcance"))
    linha("alcance mediano por post", mediana(semana, "alcance"), mediana(anterior, "alcance"), 1)
    linha("alcance médio por post", media(semana, "alcance"), media(anterior, "alcance"), 1)
    for rotulo, coluna in [("visualizações", "visualizacoes"), ("envios", "compartilhamentos"),
                           ("salvamentos", "salvamentos"), ("comentários", "comentarios"),
                           ("visitas ao perfil *", "visitas_perfil"), ("seguidores ganhos *", "seguidores_ganhos")]:
        linha(rotulo, soma(semana, coluna), soma(anterior, coluna))
    linhas.append("* só imagem e carrossel (a API não dá essas métricas para Reels)")
    if len(semana) < AMOSTRA_MINIMA or len(anterior) < AMOSTRA_MINIMA:
        linhas.append(f"[{AMOSTRA}] uma das semanas tem menos de {AMOSTRA_MINIMA} posts: variação não é conclusiva")
    return linhas


def secao_indicadores(janela: list[dict], rotulo: str) -> list[str]:
    linhas = titulo(f"2. INDICADORES DO DOC 21  (4 semanas: {rotulo}; meta ≥ {pct(META_TAXA)})")
    linhas.append(f"{'grupo':24}{'posts':>6}{'alcance':>10}{'envios÷alc':>12}{'salv÷alc':>12}")

    def status(valor):
        if valor is None:
            return "   "
        return " ok" if valor >= META_TAXA else " ↓ "

    def linha(rotulo, grupo):
        envios, _ = taxa(grupo, "compartilhamentos")
        salvos, _ = taxa(grupo, "salvamentos")
        linhas.append(f"{rotulo[:24]:24}{len(grupo):>6}{num(soma(grupo, 'alcance')):>10}"
                      f"{pct(envios):>9}{status(envios)}{pct(salvos):>9}{status(salvos)}{marca_amostra(len(grupo))}")

    linha("TODOS", janela)
    por_serie = defaultdict(list)
    for p in janela:
        por_serie[p["serie"]].append(p)
    for serie in sorted(por_serie, key=lambda s: (s == SEM_SERIE, s)):
        linha(serie, por_serie[serie])
    linhas.append("conta = soma do numerador ÷ soma do alcance · ok = atinge a meta · ↓ = abaixo")
    return linhas


def linha_post(p: dict, coluna: str) -> str:
    return (f"  {dia(p['data'])} {p['data']:%H:%M}  {nome_formato(p['tipo']):9} "
            f"{num(p[coluna]):>6}  {p['permalink']}")


def secao_ranking(semana: list[dict]) -> list[str]:
    linhas = titulo("3. RANKING DA SEMANA")
    for rotulo, coluna in [("alcance", "alcance"), ("envios", "compartilhamentos")]:
        com_dado = [p for p in semana if p[coluna] is not None]
        if coluna == "compartilhamentos" and not any(p[coluna] for p in com_dado):
            linhas.append("por envios: nenhum post da semana teve envio")
            continue
        if not com_dado:
            linhas.append(f"por {rotulo}: sem dados")
            continue
        ordenados = sorted(com_dado, key=lambda p: (-p[coluna], p["data"]))
        if len(ordenados) <= 3:
            linhas.append(f"por {rotulo} (só {len(ordenados)} posts):")
            linhas += [linha_post(p, coluna) for p in ordenados]
            continue
        linhas.append(f"por {rotulo} — 3 melhores:")
        linhas += [linha_post(p, coluna) for p in ordenados[:3]]
        linhas.append(f"por {rotulo} — 3 piores:")
        linhas += [linha_post(p, coluna) for p in sorted(ordenados[-3:], key=lambda p: (p[coluna], p["data"]))]
    return linhas


def secao_formato(janela: list[dict], rotulo: str) -> list[str]:
    linhas = titulo(f"4. POR FORMATO  (4 semanas: {rotulo})")
    linhas.append(f"{'formato':12}{'posts':>6}{'alcance médio':>15}{'mediano':>10}")
    por_tipo = defaultdict(list)
    for p in janela:
        por_tipo[p["tipo"]].append(p)
    ordem = list(FORMATOS) + sorted(t for t in por_tipo if t not in FORMATOS)
    for tipo in ordem:
        grupo = por_tipo.get(tipo, [])
        if not grupo and tipo not in FORMATOS:
            continue
        linhas.append(f"{nome_formato(tipo):12}{len(grupo):>6}{num(media(grupo, 'alcance'), 1):>15}"
                      f"{num(mediana(grupo, 'alcance'), 1):>10}{marca_amostra(len(grupo))}")
    return linhas


def secao_frequencia(semana: list[dict]) -> list[str]:
    linhas = titulo("5. FREQUÊNCIA DA SEMANA")
    n = len(semana)
    situacao = "acima da meta" if n > META_POSTS_SEMANA else "abaixo da meta" if n < META_POSTS_SEMANA else "na meta"
    linhas.append(f"posts: {n} × meta {META_POSTS_SEMANA} ({situacao})")

    por_dia = Counter(p["data"].date() for p in semana)
    cheios = sorted(d for d, qtd in por_dia.items() if qtd > 1)
    if cheios:
        linhas.append("dias com mais de 1 post: " + ", ".join(f"{dia(d)} ({por_dia[d]})" for d in cheios))
    else:
        linhas.append("dias com mais de 1 post: nenhum")

    proximos = [(a, b) for a, b in zip(semana, semana[1:]) if b["data"] - a["data"] < INTERVALO_MINIMO]
    if proximos:
        linhas.append(f"posts com menos de 2 h de intervalo: {len(proximos)} par(es)")
        for a, b in proximos:
            minutos = int((b["data"] - a["data"]).total_seconds() // 60)
            linhas.append(f"  {dia(a['data'])} {a['data']:%H:%M} → {b['data']:%H:%M} ({minutos // 60}h{minutos % 60:02d})"
                          f"  {nome_formato(a['tipo'])} → {nome_formato(b['tipo'])}")
    else:
        linhas.append("posts com menos de 2 h de intervalo: nenhum")
    return linhas


# ---------------------------------------------------------------- alertas (item 6 + frequência)

# Níveis: "alerta" = provável erro; "conferir" = indício fraco, humano decide; "contar" = só contagem.
FONTE_OU_EXEMPLO = re.compile(r"fonte\s*:|exemplo", re.IGNORECASE)
NUMERO = re.compile(
    r"\d+(?:[.,]\d+)?\s*%"                    # 86%, 24,4 %
    r"|R\$\s*\d"                              # R$ 16,6
    r"|\b(?:bilh|milh)(?:ões|ão)\b"           # bilhões, milhões
    r"|(?<![/\d])\b(?:19|20)\d{2}\b(?!/)",    # ano isolado (não pega dd/mm/aaaa)
    re.IGNORECASE,
)
BANIDAS = re.compile(  # 08 §13; D71 — as mais longas primeiro para o trecho sair inteiro
    r"\b(?:resultado garantido|faturamento garantido|ponto garantido|garantid[oa]s?|lotar (?:a )?agenda"
    r"|bombar|viralizar|explodir|alavancar|hacks?|rob[ôo]s?)\b",
    re.IGNORECASE,
)
HASHTAG = re.compile(r"#\w+")
MAX_HASHTAGS = 5
# TODO só em maiúsculas: "todo" minúsculo é palavra comum em português
ANOTACAO = re.compile(r"^\s*[—–]|(?i:na hora de publicar)|\bTODO\b|(?i:\bobs\s*:)|[\[\]]", re.MULTILINE)
SIGA = re.compile(r"\bsiga para\b", re.IGNORECASE)
# Ajuste A2: taxa anual ("80%, ano após ano") é erro comum de leitura da fonte (acumulado × por ano)
TAXA_ANUAL = re.compile(
    r"\d+(?:[.,]\d+)?\s*%[^.\n]{0,25}?\b(?:ano após ano|ao ano|por ano|a cada ano|todo ano|anualmente)\b",
    re.IGNORECASE,
)
# Ajuste A2: artigo + número + "de/da/do" sem substantivo ("as 6 das duas semanas") = palavra faltando.
# Não acusa "os 2 dos 3" (número dos dois lados).
NUMERO_SEM_SUBSTANTIVO = re.compile(r"\b(?:os|as)\s+\d+\s+d[aeo]s?\b(?!\s*\d)", re.IGNORECASE)
ITEM_DE_LISTA = re.compile(r"^\d+[.)]\s")
PONTUACAO_FINAL = set(".!?:;…)\"”»'")


def trecho(texto: str, inicio: int, fim: int, margem: int = 35) -> str:
    a, b = max(0, inicio - margem), min(len(texto), fim + margem)
    corte = " ".join(texto[a:b].split())
    return ("…" if a > 0 else "") + corte + ("…" if b < len(texto) else "")


def sem_simbolos_finais(linha: str) -> str:
    """Tira espaços e emojis do fim da linha."""
    while linha and (linha[-1].isspace() or unicodedata.category(linha[-1]) in ("So", "Sk", "Cf", "Mn")):
        linha = linha[:-1]
    return linha


def frases_sem_pontuacao(legenda: str) -> list[str]:
    """Última linha de cada parágrafo (seguido de linha em branco) que termina sem pontuação.
    Ignora hashtags, itens de lista, linhas que começam com emoji/símbolo (ex.: "📡 Radar Dunk", "☐ …")."""
    paragrafos = re.split(r"\n\s*\n", legenda.strip())
    achados = []
    for paragrafo in paragrafos[:-1]:
        ultima = paragrafo.strip().splitlines()[-1].strip()
        if not ultima or not ultima[0].isalnum() or ITEM_DE_LISTA.match(ultima):
            continue
        limpa = sem_simbolos_finais(ultima)
        if limpa and limpa[-1] not in PONTUACAO_FINAL:
            achados.append(limpa)
    return achados


def alertas_da_legenda(legenda: str) -> list[tuple[str, str, str]]:
    """Lista de (nível, regra, trecho) para uma legenda."""
    achados = []
    numero = NUMERO.search(legenda)
    if numero and not FONTE_OU_EXEMPLO.search(legenda):
        achados.append(("alerta", "número sem Fonte nem EXEMPLO", trecho(legenda, *numero.span())))
    for m in TAXA_ANUAL.finditer(legenda):
        achados.append(("conferir", "taxa anual: confira com a fonte (acumulado × por ano)", trecho(legenda, *m.span())))
    for m in BANIDAS.finditer(legenda):
        achados.append(("alerta", f"palavra banida: {m.group(0).lower()}", trecho(legenda, *m.span())))
    hashtags = HASHTAG.findall(legenda)
    if len(hashtags) > MAX_HASHTAGS:
        achados.append(("alerta", f"{len(hashtags)} hashtags (máx. {MAX_HASHTAGS})", " ".join(hashtags)))
    for m in ANOTACAO.finditer(legenda):
        inicio = legenda.rfind("\n", 0, m.start()) + 1
        fim = legenda.find("\n", m.end())
        linha = legenda[inicio:fim if fim != -1 else len(legenda)].strip()
        if not any(r == "provável anotação interna" and t == linha for _, r, t in achados):
            achados.append(("alerta", "provável anotação interna", linha))
    for m in SIGA.finditer(legenda):
        achados.append(("contar", 'CTA "Siga para" (doc 21 prefere "manda para…"/"Envie CLIENTE por DM")',
                        trecho(legenda, *m.span())))
    for m in NUMERO_SEM_SUBSTANTIVO.finditer(legenda):
        achados.append(("conferir", "número sem substantivo: palavra faltando?", trecho(legenda, *m.span())))
    for frase in frases_sem_pontuacao(legenda):
        achados.append(("conferir", "frase sem pontuação antes de linha em branco: truncada?", frase[-80:]))
    return achados


def segunda_feira(d: date) -> date:
    return d - timedelta(days=d.weekday())


def alerta_sem_post(quando: date, regra: str, texto: str) -> dict:
    return {"data": datetime.combine(quando, datetime.min.time()), "post_id": "", "tipo": "",
            "permalink": "", "nivel": "alerta", "regra": regra, "trecho": texto}


def alertas_de_frequencia(posts: list[dict], todos: list[dict], hoje: date, ate: date | None = None) -> list[dict]:
    """Diário: dia com ≥ 3 posts ou com posts a menos de 2 h. Semanal: semana seg–dom com mais de 6 posts.
    `posts` define quais dias/semanas olhar; `todos` dá a contagem completa da semana.
    `ate`: se informado, só dias e semanas encerrados até essa data (para gravar sem contagem parcial)."""
    alertas = []
    por_dia = defaultdict(list)
    for p in sorted(posts, key=lambda p: p["data"]):
        por_dia[p["data"].date()].append(p)
    for d in sorted(por_dia):
        if ate and d > ate:
            continue
        grupo = por_dia[d]
        perto = sum(1 for a, b in zip(grupo, grupo[1:]) if b["data"] - a["data"] < INTERVALO_MINIMO)
        if len(grupo) < POSTS_DIA_ALERTA and not perto:
            continue
        horarios = ", ".join(f"{p['data']:%H:%M}" for p in grupo)
        texto = f"{dia(d)}: {len(grupo)} posts ({horarios})" + (f"; {perto} com menos de 2 h do anterior" if perto else "")
        alertas.append(alerta_sem_post(d, "frequência: dia com 3+ posts ou intervalo < 2 h", texto))

    por_semana = Counter(segunda_feira(p["data"].date()) for p in todos)
    for inicio in sorted({segunda_feira(p["data"].date()) for p in posts}):
        n = por_semana[inicio]
        fim = inicio + timedelta(days=6)
        if n <= META_POSTS_SEMANA or (ate and fim > ate):
            continue
        andamento = " (semana em andamento)" if fim >= hoje else ""
        texto = f"semana {dia(inicio)}–{dia(fim)}: {n} posts × meta {META_POSTS_SEMANA}{andamento}"
        alertas.append(alerta_sem_post(inicio, "frequência: semana acima da meta", texto))
    return sorted(alertas, key=lambda a: a["data"])


def gerar_alertas(posts: list[dict], todos: list[dict] | None = None, hoje: date | None = None,
                  ate: date | None = None) -> list[dict]:
    """Alertas de legenda (1 por achado) + alertas de frequência (diário e semanal)."""
    todos = posts if todos is None else todos
    hoje = hoje or datetime.now(BRASILIA).date()
    alertas = []
    for p in sorted(posts, key=lambda p: p["data"]):
        for nivel, regra, texto in alertas_da_legenda(p["legenda"]):
            alertas.append({"data": p["data"], "post_id": p["post_id"], "tipo": p["tipo"],
                            "permalink": p["permalink"], "nivel": nivel, "regra": regra, "trecho": texto})
    return alertas + alertas_de_frequencia(posts, todos, hoje, ate)


def secao_alertas(alertas: list[dict], n_posts: int, rotulo: str) -> list[str]:
    niveis = Counter(a["nivel"] for a in alertas)
    linhas = titulo(f"6. ALERTAS  ({rotulo}: {n_posts} posts · {len(alertas)} achados: "
                    f"{niveis['alerta']} alerta, {niveis['conferir']} conferir, {niveis['contar']} contar)")
    legenda = [a for a in alertas if a["post_id"]]
    frequencia = [a for a in alertas if not a["post_id"]]
    atual = None
    for a in legenda:
        if a["post_id"] != atual:
            atual = a["post_id"]
            linhas.append(f"{a['data']:%d/%m %H:%M}  {nome_formato(a['tipo']):9} {a['permalink']}")
        linhas.append(f"  [{a['nivel']}] {a['regra']}: {a['trecho']}")
    if not legenda:
        linhas.append("legendas: nenhum alerta")
    linhas.append("frequência:" if frequencia else "frequência: nenhum alerta")
    linhas += [f"  [{a['nivel']}] {a['trecho']}" for a in frequencia]
    return linhas


def rodape(janela: list[dict], total: int, descartadas: int, gravar: bool) -> list[str]:
    linhas = ["", "Observações"]
    linhas.append("- O alcance dos posts dos últimos 2–3 dias ainda está crescendo: a semana atual tende a sair subestimada.")
    sem_serie = sum(1 for p in janela if p["serie"] == SEM_SERIE)
    if sem_serie:
        linhas.append(f"- {sem_serie} de {len(janela)} posts das 4 semanas estão sem série (coluna `serie` vazia).")
    linhas.append(f"- Posts lidos na aba posts: {total}." + (f" Linhas ignoradas por data inválida: {descartadas}." if descartadas else ""))
    if not gravar:
        linhas.append("- Nada foi gravado (modo leitura; use --gravar).")
    return linhas


# ---------------------------------------------------------------- cálculo e relatório

def periodo(ultimo_dia: date, dias: int) -> tuple[date, date, str]:
    primeiro = ultimo_dia - timedelta(days=dias - 1)
    return primeiro, ultimo_dia, f"{dia(primeiro)}–{dia(ultimo_dia)}"


def calcular(posts: list[dict], ultimo_dia: date) -> dict:
    ini_s, fim_s, rot_s = periodo(ultimo_dia, 7)
    ini_a, fim_a, rot_a = periodo(ultimo_dia - timedelta(days=7), 7)
    ini_j, fim_j, rot_j = periodo(ultimo_dia, 28)
    return {
        "inicio": ini_s, "fim": fim_s, "rot_semana": rot_s, "rot_anterior": rot_a, "rot_janela": rot_j,
        "semana": no_periodo(posts, ini_s, fim_s),
        "anterior": no_periodo(posts, ini_a, fim_a),
        "janela": no_periodo(posts, ini_j, fim_j),
    }


def relatorio(c: dict, alertas: list[dict], n_alvo: int, rotulo_alertas: str,
              total: int, descartadas: int, gravar: bool) -> list[str]:
    linhas = [f"ANALISTA SEMANAL @dunkmidia · semana {c['rot_semana']}/{c['fim'].year} · "
              f"gerado {datetime.now(BRASILIA):%d/%m/%Y %H:%M}"]
    linhas += secao_resumo(c["semana"], c["anterior"], c["rot_semana"], c["rot_anterior"])
    linhas += secao_indicadores(c["janela"], c["rot_janela"])
    linhas += secao_ranking(c["semana"])
    linhas += secao_formato(c["janela"], c["rot_janela"])
    linhas += secao_frequencia(c["semana"])
    linhas += secao_alertas(alertas, n_alvo, rotulo_alertas)
    linhas += rodape(c["janela"], total, descartadas, gravar)
    return linhas


# ---------------------------------------------------------------- gravação (só com --gravar)

COLUNAS_SEMANAL = [
    "semana_inicio", "semana_fim", "posts", "alcance_total", "alcance_mediano", "alcance_medio",
    "visualizacoes", "envios", "salvamentos", "comentarios", "visitas_perfil", "seguidores_ganhos",
    "posts_4s", "envios_por_alcance_4s", "salvamentos_por_alcance_4s",
    "alcance_medio_reels_4s", "alcance_medio_carrossel_4s", "alcance_medio_imagem_4s",
    "meta_posts", "dias_3_ou_mais_posts", "pares_menos_2h", "alertas_da_semana", "gerado_em",
]
COLUNAS_ALERTAS = ["chave", "data", "post_id", "link", "tipo", "nivel", "regra", "trecho", "status", "criado_em"]


def arredondar(valor: float | None, casas: int):
    if valor is None:
        return ""
    return int(round(valor)) if casas == 0 else round(valor, casas)


def linha_semanal(c: dict, alertas: list[dict]) -> dict:
    """Uma linha da aba semanal. Estável: rodar de novo na mesma semana dá os mesmos valores."""
    semana, janela = c["semana"], c["janela"]
    da_semana = sum(1 for a in alertas if c["inicio"] <= a["data"].date() <= c["fim"])
    por_dia = Counter(p["data"].date() for p in semana)
    pares = sum(1 for a, b in zip(semana, semana[1:]) if b["data"] - a["data"] < INTERVALO_MINIMO)
    envios, _ = taxa(janela, "compartilhamentos")
    salvos, _ = taxa(janela, "salvamentos")
    linha = {
        "semana_inicio": c["inicio"].isoformat(),
        "semana_fim": c["fim"].isoformat(),
        "posts": len(semana),
        "alcance_mediano": arredondar(mediana(semana, "alcance"), 1),
        "alcance_medio": arredondar(media(semana, "alcance"), 1),
        "posts_4s": len(janela),
        "envios_por_alcance_4s": arredondar(envios, 4),
        "salvamentos_por_alcance_4s": arredondar(salvos, 4),
        "meta_posts": META_POSTS_SEMANA,
        "dias_3_ou_mais_posts": sum(1 for n in por_dia.values() if n >= POSTS_DIA_ALERTA),
        "pares_menos_2h": pares,
        "alertas_da_semana": da_semana,
        "gerado_em": agora_brasilia(),
    }
    for coluna_planilha, coluna_post in [
        ("alcance_total", "alcance"), ("visualizacoes", "visualizacoes"), ("envios", "compartilhamentos"),
        ("salvamentos", "salvamentos"), ("comentarios", "comentarios"),
        ("visitas_perfil", "visitas_perfil"), ("seguidores_ganhos", "seguidores_ganhos"),
    ]:
        linha[coluna_planilha] = arredondar(soma(semana, coluna_post), 0)
    for tipo, sufixo in [("REELS", "reels"), ("CAROUSEL_ALBUM", "carrossel"), ("IMAGE", "imagem")]:
        grupo = [p for p in janela if p["tipo"] == tipo]
        linha[f"alcance_medio_{sufixo}_4s"] = arredondar(media(grupo, "alcance"), 1)
    return linha


def chave_alerta(a: dict) -> str:
    if a["post_id"]:
        return f"{a['post_id']}|{a['regra']}|{a['trecho']}"
    return f"{a['data']:%Y-%m-%d}|{a['regra']}"


def anexar_linhas(aba, total_linhas: int, novas: list[list]) -> None:
    inicio = total_linhas + 1
    fim = inicio + len(novas) - 1
    if fim > aba.row_count:
        com_retentativa(aba.add_rows, fim - aba.row_count)
    com_retentativa(aba.update, novas, f"A{inicio}", value_input_option="RAW")


def gravar_alertas(aba, cabecalho: list[str], valores: list[list], alertas: list[dict]) -> tuple[int, int]:
    """Acrescenta só alertas com chave nova. Nunca reescreve linha existente (preserva `status`).
    Retorna (novos, já existentes)."""
    i_chave = cabecalho.index("chave")
    existentes = {linha[i_chave] for linha in valores[1:] if i_chave < len(linha) and linha[i_chave]}
    agora = agora_brasilia()
    novas, vistas = [], set()
    for a in alertas:
        chave = chave_alerta(a)
        if chave in existentes or chave in vistas:
            continue
        vistas.add(chave)
        registro = {
            "chave": chave,
            "data": a["data"].strftime("%Y-%m-%d %H:%M") if a["post_id"] else a["data"].strftime("%Y-%m-%d"),
            "post_id": a["post_id"], "link": a["permalink"], "tipo": a["tipo"], "nivel": a["nivel"],
            "regra": a["regra"], "trecho": a["trecho"], "status": "", "criado_em": agora,
        }
        novas.append([registro.get(c, "") for c in cabecalho])
    if novas:
        anexar_linhas(aba, len(valores), novas)
    return len(novas), len(alertas) - len(novas)


def gravar_semanal(planilha, linha: dict) -> str:
    """Atualiza a linha da semana (chave semana_inicio) ou acrescenta. Retorna 'nova' ou 'atualizada'."""
    aba, cabecalho, valores = abrir_aba(planilha, "semanal", COLUNAS_SEMANAL)
    i_chave = cabecalho.index("semana_inicio")
    nova = [linha.get(c, "") for c in cabecalho]
    for numero, existente in enumerate(valores[1:], start=2):
        if i_chave < len(existente) and existente[i_chave] == linha["semana_inicio"]:
            com_retentativa(aba.update, [nova], f"A{numero}", value_input_option="RAW")
            return "atualizada"
    anexar_linhas(aba, len(valores), [nova])
    return "nova"


def gravar_resumo_actions(linhas: list[str]) -> None:
    """Resumo da execução no GitHub Actions (job summary), se estiver rodando lá."""
    destino = os.getenv("GITHUB_STEP_SUMMARY")
    if not destino:
        return
    corpo = "\n".join(linhas[1:]).strip()
    with open(destino, "a", encoding="utf-8") as arquivo:
        arquivo.write(f"## {linhas[0]}\n\n```text\n{corpo}\n```\n")


# ---------------------------------------------------------------- execução

def ultimo_domingo(hoje: date) -> date:
    """Fim da última semana completa (seg–dom). Na segunda, é ontem."""
    return hoje - timedelta(days=hoje.weekday() + 1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Resumo semanal da aba posts.")
    parser.add_argument("--ate", help="último dia da semana, AAAA-MM-DD (padrão: último domingo, horário de Brasília)")
    parser.add_argument("--todos", action="store_true",
                        help="alertas sobre todos os posts da aba (padrão: só os da semana)")
    parser.add_argument("--gravar", action="store_true",
                        help="grava nas abas semanal e alertas (sem isso, só imprime)")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")  # Windows usa cp1252 quando a saída é redirecionada

    if args.ate:
        try:
            ultimo_dia = datetime.strptime(args.ate, "%Y-%m-%d").date()
        except ValueError:
            print("--ate precisa estar no formato AAAA-MM-DD")
            sys.exit(2)
        if args.gravar and ultimo_dia.weekday() != 6:
            print("Com --gravar, --ate precisa ser um domingo (a aba semanal guarda semanas de segunda a domingo).")
            sys.exit(2)
    else:
        ultimo_dia = ultimo_domingo(datetime.now(BRASILIA).date())

    try:
        planilha = abrir_planilha()
        posts, descartadas = montar_posts(ler_linhas(planilha))
    except ErroConfig as e:
        print(e)
        sys.exit(1)

    c = calcular(posts, ultimo_dia)

    todos_alertas = args.todos
    if args.gravar:
        aba_alertas, cab_alertas, val_alertas = abrir_aba(planilha, "alertas", COLUNAS_ALERTAS)
        if len(val_alertas) <= 1:  # 1ª execução: aba vazia -> todos os posts (PRD §3 item 6)
            todos_alertas = True
    alvo = sorted(posts, key=lambda p: p["data"]) if todos_alertas else c["semana"]
    rotulo = "todos os posts" if todos_alertas else f"semana {c['rot_semana']}"
    alertas = gerar_alertas(alvo, posts, ate=ultimo_dia if args.gravar else None)

    linhas = relatorio(c, alertas, len(alvo), rotulo, len(posts), descartadas, args.gravar)

    if args.gravar:
        novos, repetidos = gravar_alertas(aba_alertas, cab_alertas, val_alertas, alertas)
        situacao = gravar_semanal(planilha, linha_semanal(c, alertas))
        linhas.append(f"- Gravado: aba semanal (semana {c['rot_semana']}, linha {situacao}); "
                      f"aba alertas ({novos} novos, {repetidos} já existiam).")

    print("\n".join(linhas))
    gravar_resumo_actions(linhas)


if __name__ == "__main__":
    main()
