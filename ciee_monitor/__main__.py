"""Monitor CIEE — execução única ou contínua (--watch)."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

from .api import CieeApiError, fetch_vagas
from .display import format_vaga
from .storage import find_new_vagas, load_seen, mark_as_seen, save_seen
from .watch import run_forever

DEFAULT_INTERVAL = 300


def run_once(
    seen_path: str | Path = "seen.json",
    params: dict[str, Any] | None = None,
    timeout: int = 15,
) -> int:
    """Executa uma verificação única. Retorna 0 em sucesso, 1 em erro de API."""
    seen = load_seen(seen_path)

    try:
        vagas, total = fetch_vagas(params=params, timeout=timeout)
    except CieeApiError as exc:
        print(f"Erro ao consultar API do CIEE: {exc}", file=sys.stderr)
        return 1

    novas = find_new_vagas(vagas, seen)

    print(f"Vagas encontradas: {total} (retornadas nesta página: {len(vagas)})")
    print(f"Novas desde a última execução: {len(novas)}")
    print("-" * 60)

    seen_codes = seen
    for vaga in vagas:
        code = str(vaga.get("codigoVaga")) if vaga.get("codigoVaga") is not None else None
        is_new = code is not None and code not in seen_codes
        print(format_vaga(vaga, is_new=is_new))
        print("-" * 60)

    # Persiste todos os codigoVaga retornados para não repetir como novos.
    updated = mark_as_seen(vagas, seen)
    try:
        save_seen(updated, seen_path)
    except OSError as exc:
        print(f"Aviso: não foi possível salvar {seen_path}: {exc}", file=sys.stderr)

    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Monitor CIEE - execução única ou contínua (--watch)")
    p.add_argument("--seen-file", default="seen.json", help="arquivo local de vagas já vistas")
    p.add_argument("--timeout", type=int, default=15, help="timeout HTTP em segundos")
    p.add_argument("--size", type=int, default=100, help="page size da API")
    p.add_argument("--page", type=int, default=0, help="página da API")
    p.add_argument("--watch", action="store_true", help="monitoramento contínuo em loop")
    p.add_argument(
        "--interval",
        type=int,
        default=None,
        help="intervalo entre consultas em segundos (padrão: 300 ou $CIEE_INTERVAL)",
    )
    return p


def resolve_interval(args: argparse.Namespace) -> int:
    """Precedência: --interval > $CIEE_INTERVAL > 300."""
    if args.interval is not None:
        return args.interval
    env = os.getenv("CIEE_INTERVAL")
    if env is not None and env.strip() != "":
        try:
            return int(env)
        except ValueError:
            return DEFAULT_INTERVAL
    return DEFAULT_INTERVAL


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    params: dict[str, Any] | None = None
    if args.size != 100 or args.page != 0:
        from .api import DEFAULT_PARAMS

        params = dict(DEFAULT_PARAMS)
        params["size"] = args.size
        params["page"] = args.page
    if args.watch:
        interval = resolve_interval(args)
        if interval <= 0:
            parser.error("--interval deve ser maior que zero")
        return run_forever(
            interval=interval,
            seen_path=args.seen_file,
            params=params,
            timeout=args.timeout,
        )
    return run_once(seen_path=args.seen_file, params=params, timeout=args.timeout)


if __name__ == "__main__":
    raise SystemExit(main())
