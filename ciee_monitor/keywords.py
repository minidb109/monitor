"""Filtro de vagas por palavras-chave relacionadas a software (somente stdlib).

A API do CIEE é consultada com os filtros de informática/tecnologia e este
módulo classifica o conteúdo de cada vaga (título, área, descrição e
atividades). O matching é substring, insensível a maiúsculas e acentos.
"""

from __future__ import annotations

import os
import unicodedata
from typing import Any

KEYWORDS_ENV_VAR = "CIEE_KEYWORDS"

DEFAULT_KEYWORDS: list[str] = [
    "desenvolvimento",
    "software",
    "programação",
    "programador",
    "backend",
    "back-end",
    "frontend",
    "front-end",
    "full stack",
    "java",
    "python",
    "javascript",
    "typescript",
    "web",
    "mobile",
    "sistemas",
    "análise e desenvolvimento de sistemas",
    "banco de dados",
    "dados",
    "inteligência artificial",
    "machine learning",
    "devops",
    "cloud",
    "qa",
    "testes automatizados",
]


def resolve_keywords() -> list[str]:
    """CIEE_KEYWORDS (separada por vírgula) ou a lista padrão.

    Retorna uma cópia nova a cada chamada. Lista vazia/ausente → padrão.
    """
    raw = os.getenv(KEYWORDS_ENV_VAR)
    if raw is not None and raw.strip() != "":
        parsed = [item.strip() for item in raw.split(",")]
        parsed = [item for item in parsed if item != ""]
        if parsed:
            return parsed
    return list(DEFAULT_KEYWORDS)


def _normalize(text: str) -> str:
    """Minúsculas sem acentos para comparação."""
    folded = unicodedata.normalize("NFKD", text.casefold())
    return "".join(ch for ch in folded if not unicodedata.combining(ch))


def vaga_text(vaga: dict[str, Any]) -> str:
    """Texto analisável da vaga: título, área, descrição e atividades."""
    parts: list[str] = []
    for field in ("titulo", "tituloVaga", "nomeVaga"):
        value = vaga.get(field)
        if isinstance(value, str) and value.strip():
            parts.append(value)
    for field in ("areaProfissional", "areaAtuacao"):
        value = vaga.get(field)
        if isinstance(value, str) and value.strip():
            parts.append(value)
    descricao = vaga.get("descricao")
    if isinstance(descricao, str) and descricao.strip():
        parts.append(descricao)
    atividades = vaga.get("atividades")
    if isinstance(atividades, list):
        parts.extend(str(a) for a in atividades if str(a).strip())
    return "\n".join(parts)


def vaga_matches(vaga: dict[str, Any], keywords: list[str]) -> bool:
    """True se algum termo aparece no texto da vaga (case/acentos ignorados)."""
    text = _normalize(vaga_text(vaga))
    if not text:
        return False
    return any(_normalize(kw) in text for kw in keywords if kw.strip())
