"""Persistência simples das vagas já vistas (seen.json)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _normalize_code(codigo: Any) -> str | None:
    if codigo is None:
        return None
    # codigoVaga é int na API, mas persistimos como str para evitar
    # divergência int/str entre execuções.
    return str(codigo)


def load_seen(path: str | Path = "seen.json") -> set[str]:
    """Carrega o conjunto de codigoVaga já vistos.

    Retorna conjunto vazio se o arquivo não existir ou estiver corrompido.
    """
    p = Path(path)
    if not p.exists():
        return set()
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    if not isinstance(raw, list):
        return set()
    seen: set[str] = set()
    for item in raw:
        code = _normalize_code(item)
        if code is not None:
            seen.add(code)
    return seen


def save_seen(seen: set[str], path: str | Path = "seen.json") -> None:
    """Salva o conjunto de codigoVaga já vistos como lista JSON ordenada."""
    p = Path(path)
    # Ordena numericamente quando possível para diff legível.
    def sort_key(x: str) -> tuple[int, str]:
        try:
            return (0, f"{int(x):020d}")
        except ValueError:
            return (1, x)

    payload = sorted(seen, key=sort_key)
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def find_new_vagas(
    vagas: list[dict[str, Any]], seen: set[str]
) -> list[dict[str, Any]]:
    """Retorna apenas as vagas cujo codigoVaga ainda não está em `seen`."""
    novas: list[dict[str, Any]] = []
    for vaga in vagas:
        code = _normalize_code(vaga.get("codigoVaga"))
        if code is None:
            continue
        if code not in seen:
            novas.append(vaga)
    return novas


def mark_as_seen(
    vagas: list[dict[str, Any]], seen: set[str]
) -> set[str]:
    """Retorna novo conjunto com os codigoVaga das vagas adicionados."""
    updated = set(seen)
    for vaga in vagas:
        code = _normalize_code(vaga.get("codigoVaga"))
        if code is not None:
            updated.add(code)
    return updated
