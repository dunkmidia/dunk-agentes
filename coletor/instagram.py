"""Coletor de Insights do Instagram @dunkmidia -> planilha Dunk_Metricas.

Uso (na raiz do repo):
    python coletor/instagram.py              # coleta todos os posts e grava na planilha
    python coletor/instagram.py --seco       # só imprime, não grava nada
    python coletor/instagram.py --limite 3   # só os 3 posts mais recentes

Somente leitura na Meta. Nunca imprime o token (CLAUDE.md §2). Nunca apaga linha da planilha.

Base: docs da Meta (Instagram API with Facebook Login, Graph API v27.0), lidas e conferidas
na conta real em 18/11/2026:
  - IMAGE e CAROUSEL_ALBUM (FEED) aceitam profile_visits e follows; REELS não.
  - ig_reels_avg_watch_time só em REELS, em milissegundos.
  - impressions, plays e video_views foram descontinuadas.
  - Uma métrica não suportada (#100) derruba a chamada inteira -> lista por tipo + fallback.
"""

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import ErroConfig, carregar_credencial_google, obter  # noqa: E402

VERSAO = "v27.0"
BASE = f"https://graph.facebook.com/{VERSAO}"
BRASILIA = timezone(timedelta(hours=-3))  # sem horário de verão desde 2019

# métrica da API -> coluna da planilha
METRICAS_FEED = {
    "reach": "alcance",
    "views": "visualizacoes",
    "shares": "compartilhamentos",
    "saved": "salvamentos",
    "likes": "curtidas",
    "comments": "comentarios",
    "total_interactions": "interacoes_totais",
    "profile_visits": "visitas_perfil",
    "follows": "seguidores_ganhos",
}
METRICAS_REELS = {
    "reach": "alcance",
    "views": "visualizacoes",
    "shares": "compartilhamentos",
    "saved": "salvamentos",
    "likes": "curtidas",
    "comments": "comentarios",
    "total_interactions": "interacoes_totais",
    "ig_reels_avg_watch_time": "tempo_medio_assistido_s",
}

COLUNAS_POSTS = [
    "post_id", "data", "tipo", "permalink", "legenda", "serie",
    "alcance", "visualizacoes", "compartilhamentos", "salvamentos", "curtidas", "comentarios",
    "interacoes_totais", "visitas_perfil", "seguidores_ganhos", "tempo_medio_assistido_s",
    "envios_por_alcance", "atualizado_em",
]
COLUNAS_LOG = ["data_hora", "posts_coletados", "novos", "atualizados", "erros", "detalhe_erros"]

RE_SERIE = re.compile(r"#serie_([\w-]+)", re.IGNORECASE)

# Limite de requisições: códigos da Meta que justificam esperar e tentar de novo
CODIGOS_LIMITE = {4, 17, 32, 613, 80002}
ESPERAS = [30, 60, 120, 240]  # segundos entre tentativas
USO_MAXIMO = 80  # % do limite de uso (cabeçalho x-business-use-case-usage)


# ---------------------------------------------------------------- Meta

class ErroMeta(RuntimeError):
    def __init__(self, codigo, mensagem):
        self.codigo = codigo
        super().__init__(mensagem)


class Meta:
    """Cliente mínimo de leitura da Graph API, com espera e nova tentativa."""

    def __init__(self, token: str):
        self.token = token

    def _limpar(self, texto: str) -> str:
        return texto.replace(self.token, "[TOKEN]")

    def _respeitar_uso(self, cabecalhos) -> None:
        bruto = cabecalhos.get("x-business-use-case-usage")
        if not bruto:
            return
        try:
            itens = [i for lista in json.loads(bruto).values() for i in lista]
        except (json.JSONDecodeError, AttributeError):
            return
        for item in itens:
            uso = max(item.get("call_count", 0), item.get("total_cputime", 0), item.get("total_time", 0))
            if uso >= USO_MAXIMO:
                minutos = item.get("estimated_time_to_regain_access") or 1
                print(f"  uso da API em {uso}%: aguardando {minutos} min")
                time.sleep(minutos * 60)
                return

    def _get_url(self, url: str) -> dict:
        for tentativa in range(len(ESPERAS) + 1):
            try:
                with urllib.request.urlopen(url, timeout=60) as resp:
                    dados = json.load(resp)
                    self._respeitar_uso(resp.headers)
                    return dados
            except urllib.error.HTTPError as e:
                try:
                    erro = json.load(e).get("error", {})
                except (json.JSONDecodeError, ValueError):
                    erro = {}
                codigo = erro.get("code")
                mensagem = self._limpar(f"HTTP {e.code} código {codigo}: {erro.get('message', '')}")
                repetir = codigo in CODIGOS_LIMITE or e.code >= 500
            except (urllib.error.URLError, TimeoutError) as e:
                codigo, repetir = None, True
                mensagem = self._limpar(f"falha de rede: {getattr(e, 'reason', e)}")
            if not repetir or tentativa == len(ESPERAS):
                raise ErroMeta(codigo, mensagem)
            espera = ESPERAS[tentativa]
            print(f"  {mensagem} -> nova tentativa em {espera}s")
            time.sleep(espera)

    def get(self, caminho: str, **params) -> dict:
        params["access_token"] = self.token
        return self._get_url(f"{BASE}/{caminho}?{urllib.parse.urlencode(params)}")

    def listar_posts(self, ig_user_id: str, limite: int | None) -> list[dict]:
        campos = "id,timestamp,media_type,media_product_type,permalink,caption"
        pagina = self.get(f"{ig_user_id}/media", fields=campos, limit=100)
        posts = []
        while True:
            posts.extend(pagina.get("data", []))
            if limite and len(posts) >= limite:
                return posts[:limite]
            proxima = pagina.get("paging", {}).get("next")
            if not proxima:
                return posts
            pagina = self._get_url(proxima)

    def metricas(self, media_id: str, nomes: list[str]) -> tuple[dict, list[str]]:
        """Retorna ({métrica: valor}, [erros]). Se a chamada conjunta falhar com #100, tenta uma a uma."""
        try:
            return self._ler_insights(media_id, nomes), []
        except ErroMeta as e:
            if e.codigo != 100:
                return {}, [str(e)]
        valores, erros = {}, []
        for nome in nomes:
            try:
                valores.update(self._ler_insights(media_id, [nome]))
            except ErroMeta as e:
                erros.append(f"{nome}: {e}")
        return valores, erros

    def _ler_insights(self, media_id: str, nomes: list[str]) -> dict:
        dados = self.get(f"{media_id}/insights", metric=",".join(nomes))
        valores = {}
        for item in dados.get("data", []):
            if item.get("values"):
                valores[item["name"]] = item["values"][0].get("value")
            elif "total_value" in item:
                valores[item["name"]] = item["total_value"].get("value")
        return valores


# ---------------------------------------------------------------- montagem da linha

def tipo_do_post(post: dict) -> str:
    if post.get("media_product_type") == "REELS":
        return "REELS"
    return post.get("media_type", "")


def data_brasilia(timestamp: str) -> str:
    return datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S%z").astimezone(BRASILIA).strftime("%Y-%m-%d %H:%M")


def agora_brasilia() -> str:
    return datetime.now(BRASILIA).strftime("%Y-%m-%d %H:%M:%S")


def serie_da_legenda(legenda: str) -> str | None:
    achado = RE_SERIE.search(legenda or "")
    return achado.group(1).lower() if achado else None


def montar_linha(post: dict, meta: Meta) -> tuple[dict, list[str]]:
    """Dict coluna -> valor. Só inclui as colunas obtidas; as ausentes não são tocadas na planilha."""
    tipo = tipo_do_post(post)
    mapa = METRICAS_REELS if tipo == "REELS" else METRICAS_FEED
    valores, erros = meta.metricas(post["id"], list(mapa))

    linha = {
        "post_id": post["id"],
        "data": data_brasilia(post["timestamp"]),
        "tipo": tipo,
        "permalink": post.get("permalink", ""),
        "legenda": post.get("caption", ""),
        "atualizado_em": agora_brasilia(),
    }
    serie = serie_da_legenda(post.get("caption", ""))
    if serie:
        linha["serie"] = serie

    for metrica, coluna in mapa.items():
        if metrica in valores and valores[metrica] is not None:
            linha[coluna] = valores[metrica]
    if "tempo_medio_assistido_s" in linha:
        linha["tempo_medio_assistido_s"] = round(linha["tempo_medio_assistido_s"] / 1000, 1)
    if "compartilhamentos" in linha and linha.get("alcance"):
        linha["envios_por_alcance"] = round(linha["compartilhamentos"] / linha["alcance"], 4)

    return linha, [f"{post['id']} {e}" for e in erros]


# ---------------------------------------------------------------- Google Sheets

def com_retentativa(funcao, *args, **kwargs):
    """Executa uma chamada ao Sheets; em 429/5xx espera e tenta de novo."""
    import gspread

    for tentativa in range(len(ESPERAS) + 1):
        try:
            return funcao(*args, **kwargs)
        except gspread.exceptions.APIError as e:
            status = getattr(e.response, "status_code", 0)
            if (status != 429 and status < 500) or tentativa == len(ESPERAS):
                raise
            print(f"  Google Sheets HTTP {status} -> nova tentativa em {ESPERAS[tentativa]}s")
            time.sleep(ESPERAS[tentativa])


def abrir_aba(planilha, nome: str, colunas: list[str]):
    """Abre a aba; cria com cabeçalho se não existir; acrescenta colunas faltantes no fim. Retorna (aba, cabeçalho, valores)."""
    import gspread

    try:
        aba = com_retentativa(planilha.worksheet, nome)
    except gspread.WorksheetNotFound:
        print(f"  aba '{nome}' não existe: criando")
        aba = com_retentativa(planilha.add_worksheet, title=nome, rows=1000, cols=len(colunas))

    valores = com_retentativa(aba.get_all_values)
    cabecalho = list(valores[0]) if valores else []
    faltam = [c for c in colunas if c not in cabecalho]
    if faltam:
        cabecalho += faltam
        if len(cabecalho) > aba.col_count:
            com_retentativa(aba.add_cols, len(cabecalho) - aba.col_count)
        com_retentativa(aba.update, [cabecalho], "A1", value_input_option="RAW")
    if not valores:
        valores = [cabecalho]
    return aba, cabecalho, valores


def gravar_posts(planilha, linhas: list[dict]) -> tuple[int, int]:
    """Atualiza linhas existentes (chave post_id) e acrescenta as novas. Nunca apaga. Retorna (novos, atualizados)."""
    from gspread.utils import rowcol_to_a1

    aba, cabecalho, valores = abrir_aba(planilha, "posts", COLUNAS_POSTS)
    col = {nome: i for i, nome in enumerate(cabecalho)}
    i_id = col["post_id"]

    linha_do_post = {}
    for numero, valores_linha in enumerate(valores[1:], start=2):
        pid = valores_linha[i_id] if i_id < len(valores_linha) else ""
        if pid and pid not in linha_do_post:
            linha_do_post[pid] = numero

    atualizacoes, novas = [], []
    for linha in linhas:
        numero = linha_do_post.get(linha["post_id"])
        if numero:
            for coluna, valor in linha.items():
                atualizacoes.append({"range": rowcol_to_a1(numero, col[coluna] + 1), "values": [[valor]]})
        else:
            nova = [""] * len(cabecalho)
            for coluna, valor in linha.items():
                nova[col[coluna]] = valor
            novas.append(nova)

    if novas:
        inicio = len(valores) + 1
        fim = inicio + len(novas) - 1
        if fim > aba.row_count:
            com_retentativa(aba.add_rows, fim - aba.row_count)
        atualizacoes.append({"range": f"A{inicio}", "values": novas})
    if atualizacoes:
        com_retentativa(aba.batch_update, atualizacoes, value_input_option="RAW")

    return len(novas), len(linhas) - len(novas)


def gravar_log(planilha, coletados: int, novos: int, atualizados: int, erros: list[str]) -> None:
    aba, cabecalho, valores = abrir_aba(planilha, "log", COLUNAS_LOG)
    registro = {
        "data_hora": agora_brasilia(),
        "posts_coletados": coletados,
        "novos": novos,
        "atualizados": atualizados,
        "erros": len(erros),
        "detalhe_erros": " | ".join(erros)[:5000],
    }
    linha = [registro.get(c, "") for c in cabecalho]
    numero = len(valores) + 1
    if numero > aba.row_count:
        com_retentativa(aba.add_rows, numero - aba.row_count)
    com_retentativa(aba.update, [linha], f"A{numero}", value_input_option="RAW")


def abrir_planilha():
    import gspread

    cliente = gspread.service_account_from_dict(carregar_credencial_google())
    return com_retentativa(cliente.open_by_key, obter("SHEET_ID"))


# ---------------------------------------------------------------- execução

def imprimir(linhas: list[dict]) -> None:
    mostrar = ["post_id", "data", "tipo", "serie", "alcance", "visualizacoes", "compartilhamentos",
               "salvamentos", "curtidas", "comentarios", "interacoes_totais", "visitas_perfil",
               "seguidores_ganhos", "tempo_medio_assistido_s", "envios_por_alcance"]
    for linha in linhas:
        print("\n" + " | ".join(f"{c}={linha.get(c, '')}" for c in mostrar))
        print(f"  {linha.get('permalink', '')}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Coleta Insights do Instagram e grava na planilha.")
    parser.add_argument("--seco", action="store_true", help="só imprime, não grava na planilha")
    parser.add_argument("--limite", type=int, help="processa só os N posts mais recentes")
    args = parser.parse_args()

    try:
        meta = Meta(obter("META_TOKEN"))
        ig_user_id = obter("IG_USER_ID")
    except ErroConfig as e:
        print(e)
        sys.exit(1)

    erros: list[str] = []
    linhas: list[dict] = []
    try:
        posts = meta.listar_posts(ig_user_id, args.limite)
    except ErroMeta as e:
        posts = []
        erros.append(f"listar posts: {e}")
    print(f"Posts encontrados: {len(posts)}")

    for post in posts:
        try:
            linha, erros_post = montar_linha(post, meta)
        except ErroMeta as e:
            erros.append(f"{post.get('id')}: {e}")
            continue
        linhas.append(linha)
        erros.extend(erros_post)

    if args.seco:
        imprimir(linhas)
        novos = atualizados = 0
    else:
        planilha = abrir_planilha()
        novos, atualizados = gravar_posts(planilha, linhas) if linhas else (0, 0)
        gravar_log(planilha, len(linhas), novos, atualizados, erros)

    print(f"\nColetados: {len(linhas)} · novos: {novos} · atualizados: {atualizados} · erros: {len(erros)}"
          + (" (modo seco: nada gravado)" if args.seco else ""))
    for erro in erros:
        print(f"  ERRO {erro}")
    sys.exit(1 if erros else 0)


if __name__ == "__main__":
    main()
