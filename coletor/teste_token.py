"""Teste do META_TOKEN: lista as páginas do token e a conta do Instagram ligada a cada uma.

Uso (na raiz do repo):  python coletor/teste_token.py

Somente leitura. Nunca imprime o token (CLAUDE.md §2).
Base: docs da Meta "Instagram API with Facebook Login", Graph API v27.0 (lidas em 18/11/2026):
  - GET /me/accounts                                  -> páginas do token
  - GET /{page-id}?fields=instagram_business_account   -> conta IG ligada à página
  - GET /{ig-user-id}?fields=id,username               -> nome de usuário
"""

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import ErroConfig, obter  # noqa: E402

VERSAO = "v27.0"
BASE = f"https://graph.facebook.com/{VERSAO}"
USUARIO_ALVO = "dunkmidia"
PERMISSOES = ["pages_show_list", "instagram_basic", "pages_read_engagement", "instagram_manage_insights"]

# Código de erro da Meta -> explicação (docs: Graph API "Error handling" e referência de /me/accounts)
EXPLICACOES = {
    190: "Token inválido, expirado ou revogado. Gere um novo token do usuário de sistema 'coletor'.",
    102: "Sessão da API inválida. Gere um novo token.",
    10: "Permissão negada: a permissão necessária não foi concedida ao token ou foi removida.",
    283: "Falta a permissão pages_read_engagement.",
    4: "Limite de chamadas do app atingido. Espere e tente de novo.",
    17: "Limite de chamadas do usuário atingido. Espere e tente de novo.",
    100: "Parâmetro ou campo inválido (ou o objeto não existe / o token não enxerga esse ID).",
}


class ErroMeta(RuntimeError):
    def __init__(self, codigo, subcodigo, mensagem):
        self.codigo, self.subcodigo = codigo, subcodigo
        super().__init__(mensagem)


def _sem_token(texto: str, token: str) -> str:
    return texto.replace(token, "[TOKEN]") if token else texto


def chamar(caminho: str, token: str, **params) -> dict:
    """GET na Graph API. Erros viram ErroMeta, sempre sem o token no texto."""
    params["access_token"] = token
    url = f"{BASE}/{caminho}?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        try:
            erro = json.load(e).get("error", {})
        except (json.JSONDecodeError, ValueError):
            erro = {}
        raise ErroMeta(
            erro.get("code"),
            erro.get("error_subcode"),
            _sem_token(erro.get("message", f"HTTP {e.code}"), token),
        ) from None
    except urllib.error.URLError as e:
        raise ErroMeta(None, None, _sem_token(f"Falha de rede: {e.reason}", token)) from None


def explicar(erro: ErroMeta) -> str:
    if erro.codigo in EXPLICACOES:
        return EXPLICACOES[erro.codigo]
    if erro.codigo and 200 <= erro.codigo <= 299:
        return "Erro de permissão: o token não tem a permissão exigida por esta chamada."
    return "Erro não mapeado; veja a mensagem acima."


def diagnosticar_permissoes(token: str) -> None:
    """Mostra o que o token tem e o que falta (GET /me/permissions)."""
    print("\nPermissões do token:")
    try:
        dados = chamar("me/permissions", token).get("data", [])
    except ErroMeta as e:
        print(f"  não foi possível ler /me/permissions: {e}")
        return
    concedidas = {p["permission"] for p in dados if p.get("status") == "granted"}
    for p in PERMISSOES:
        print(f"  [{'ok' if p in concedidas else 'FALTA'}] {p}")
    extras = sorted(concedidas - set(PERMISSOES))
    if extras:
        print(f"  outras concedidas: {', '.join(extras)}")
    faltam = [p for p in PERMISSOES if p not in concedidas]
    if faltam:
        print(
            "\n  Para corrigir: no Gerenciador de Negócios > Usuários do sistema > 'coletor' >\n"
            f"  Gerar novo token (app Dunk Coletor) marcando: {', '.join(faltam)}."
        )


def falhar(etapa: str, erro: ErroMeta, token: str) -> None:
    print(f"\nERRO em {etapa}: código {erro.codigo}, subcódigo {erro.subcodigo}")
    print(f"  Meta: {erro}")
    print(f"  O que significa: {explicar(erro)}")
    diagnosticar_permissoes(token)
    sys.exit(1)


def main() -> None:
    try:
        token = obter("META_TOKEN")
    except ErroConfig as e:
        print(e)
        sys.exit(1)

    print(f"Graph API {VERSAO}. Token lido do .env (não exibido).\n")

    try:
        paginas = chamar("me/accounts", token, fields="id,name", limit=100).get("data", [])
    except ErroMeta as e:
        falhar("GET /me/accounts", e, token)

    if not paginas:
        print("Nenhuma página retornada por /me/accounts.")
        print(
            "  Causas prováveis: a página da Dunk não está atribuída ao usuário de sistema 'coletor'\n"
            "  no Gerenciador de Negócios, ou falta a permissão pages_show_list."
        )
        diagnosticar_permissoes(token)
        sys.exit(1)

    print(f"Páginas do token: {len(paginas)}")
    alvo = None
    for pagina in paginas:
        print(f"\n- Página: {pagina.get('name')} (id {pagina['id']})")
        try:
            ig = chamar(pagina["id"], token, fields="instagram_business_account").get("instagram_business_account")
        except ErroMeta as e:
            falhar(f"GET /{pagina['id']}?fields=instagram_business_account", e, token)
        if not ig:
            print("  sem conta do Instagram profissional ligada")
            continue
        try:
            conta = chamar(ig["id"], token, fields="id,username")
        except ErroMeta as e:
            falhar(f"GET /{ig['id']}?fields=id,username", e, token)
        print(f"  Instagram: @{conta.get('username')} (id {conta['id']})")
        if conta.get("username", "").lower() == USUARIO_ALVO:
            alvo = conta

    print()
    if alvo:
        print(f"@{alvo['username']} encontrado.")
        print(f"  ID da conta: {alvo['id']}")
        print(f"  Para o .env: IG_USER_ID={alvo['id']}")
    else:
        print(f"@{USUARIO_ALVO} NÃO encontrado entre as contas acima.")
        print("  Verifique se o Instagram está ligado à página da Dunk e se a página está atribuída ao 'coletor'.")
        sys.exit(1)


if __name__ == "__main__":
    main()
