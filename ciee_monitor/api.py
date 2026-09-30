"""Cliente HTTP para a API pública de vagas do CIEE."""

from __future__ import annotations

from typing import Any

import requests

API_URL = "https://api.ciee.org.br/vagas/vitrine-vaga/publicadas"

DEFAULT_PARAMS: dict[str, Any] = {
    "page": 0,
    "size": 100,
    "sort": "codigoVaga,desc",
    "codigoMunicipio": 3552205,  # Sorocaba
    "tipoVaga": "ESTAGIO",
    "nivelEnsino": "TE",
    "idAreaProfissional": 53,  # Informática - TÉC.
    "idAreaAtuacaoEstagio": 473,  # Área Técnica de Desenvolvimento de Sistemas
}


class CieeApiError(RuntimeError):
    """Erro ao consultar a API do CIEE (rede, timeout ou resposta inválida)."""


def fetch_vagas(
    params: dict[str, Any] | None = None,
    timeout: int = 15,
) -> tuple[list[dict[str, Any]], int]:
    """Busca vagas na API pública do CIEE.

    Args:
        params: filtros da query string. Usa DEFAULT_PARAMS quando None.
        timeout: timeout em segundos para a requisição.

    Returns:
        Tupla (vagas, totalElements) onde vagas é o conteúdo de `content`.

    Raises:
        CieeApiError: em erro de rede, timeout, HTTP inválido ou JSON inesperado.
    """
    query = dict(DEFAULT_PARAMS) if params is None else dict(params)

    try:
        resp = requests.get(API_URL, params=query, timeout=timeout)
        resp.raise_for_status()
    except requests.exceptions.Timeout as exc:
        raise CieeApiError(f"timeout após {timeout}s ao consultar API do CIEE: {exc}") from exc
    except requests.exceptions.RequestException as exc:
        raise CieeApiError(f"erro de rede/HTTP ao consultar API do CIEE: {exc}") from exc

    try:
        data = resp.json()
    except ValueError as exc:
        raise CieeApiError(f"resposta da API do CIEE não é JSON válido: {exc}") from exc

    if not isinstance(data, dict) or "content" not in data:
        raise CieeApiError("resposta da API do CIEE sem campo 'content'")

    content = data["content"]
    if not isinstance(content, list):
        raise CieeApiError("campo 'content' da API do CIEE não é uma lista")

    total = data.get("totalElements", len(content))
    if not isinstance(total, int):
        try:
            total = int(total)
        except (TypeError, ValueError) as exc:
            raise CieeApiError("campo 'totalElements' inválido") from exc

    return content, total
