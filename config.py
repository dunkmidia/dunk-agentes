"""Configuração compartilhada: lê o .env e resolve credenciais.

Nunca imprime valores de token ou credencial (CLAUDE.md §2).
"""

import json
import os
from pathlib import Path

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent

load_dotenv(RAIZ / ".env")


class ErroConfig(RuntimeError):
    """Variável de ambiente ausente ou inválida."""


def obter(nome: str) -> str:
    """Retorna a variável de ambiente `nome` ou falha com mensagem clara."""
    valor = os.getenv(nome, "").strip()
    if not valor:
        raise ErroConfig(f"Variável {nome} não definida (veja .env.example).")
    return valor


def carregar_credencial_google() -> dict:
    """Retorna o JSON da conta de serviço Google como dict.

    GOOGLE_SA_JSON aceita:
      - o conteúdo do JSON (uso nos Secrets do GitHub), ou
      - o caminho do arquivo JSON (uso local), relativo à raiz do repo ou absoluto.
    """
    valor = obter("GOOGLE_SA_JSON")

    if valor.startswith("{"):
        try:
            return json.loads(valor)
        except json.JSONDecodeError:
            raise ErroConfig("GOOGLE_SA_JSON: conteúdo inline não é um JSON válido.") from None

    caminho = Path(os.path.expandvars(valor)).expanduser()
    if not caminho.is_absolute():
        caminho = RAIZ / caminho
    if not caminho.is_file():
        raise ErroConfig(f"GOOGLE_SA_JSON: arquivo não encontrado: {caminho}")
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        raise ErroConfig(f"GOOGLE_SA_JSON: arquivo não é um JSON válido: {caminho}") from None
