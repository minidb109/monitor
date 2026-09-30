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
    "idAreaProfissional": 53,  # Informática - TÉC. (guarda-chuva amplo)
    # Sem idAreaAtuacaoEstagio: a relevância é decidida pelo filtro interno
    # de keywords (ciee_monitor.keywords), não pela categoria do CIEE.
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


def fetch_todas_vagas(
    params: dict[str, Any] | None = None,
    timeout: int = 15,
    max_pages: int = 10,
) -> tuple[list[dict[str, Any]], int]:
    """Busca todas as páginas da API (até totalElements ou max_pages).

    Args:
        params: filtros da query string. Usa DEFAULT_PARAMS quando None.
            `size` é respeitado como tamanho da página; `page` como inicial.
        timeout: timeout em segundos por requisição.
        max_pages: teto de segurança contra loop infinito.

    Returns:
        Tupla (vagas acumuladas sem repetir codigoVaga, totalElements).

    Raises:
        CieeApiError: qualquer página com erro aborta como erro de API.
    """
    base = dict(DEFAULT_PARAMS) if params is None else dict(params)
    size = base.get("size", 100)
    try:
        size = int(size)
    except (TypeError, ValueError):
        size = 100
    if size <= 0:
        size = 100

    todas: list[dict[str, Any]] = []
    vistos: set[str] = set()
    total = 0
    page = base.get("page", 0)
    try:
        page = int(page)
    except (TypeError, ValueError):
        page = 0

    for _ in range(max(1, max_pages)):
        query = dict(base)
        query["page"] = page
        query["size"] = size
        content, total = fetch_vagas(params=query, timeout=timeout)
        if not content:
            break
        for vaga in content:
            code = vaga.get("codigoVaga")
            key = str(code) if code is not None else None
            if key is not None and key in vistos:
                continue
            if key is not None:
                vistos.add(key)
            todas.append(vaga)
        if len(todas) >= total or len(content) < size:
            break
        page += 1

    return todas, total
