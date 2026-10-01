"""Monitor CIEE — execução única ou contínua (--watch)."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

from .api import CieeApiError, fetch_todas_vagas
from .display import format_vaga
from .health import resolve_port, start_health_server
from .keywords import resolve_keywords, vaga_matches
from .notifier import (
    EmailConfig,
    NotifierConfigError,
    NotifierError,
    ResendConfig,
    notify_vaga,
    notify_vaga_resend,
)
from .storage import find_new_vagas, load_seen, mark_as_seen, save_seen
from .watch import run_forever

DEFAULT_INTERVAL = 300
DEFAULT_SEEN_FILE = "seen.json"
SEEN_FILE_ENV_VAR = "CIEE_SEEN_FILE"
DATA_DIR = Path("/data")

# Contador em memória de falhas consecutivas de notificação por codigoVaga.
# Evita spam de log quando o backend cai (ex: SMTP bloqueado): 1ª falha loga
# erro cheio, repetidas são throttled, a cada THROTTLE_EVERY loga cheio de novo
# e após ALERT_AFTER emite ALERTA.
_notify_failure_counts: dict[str, int] = {}
THROTTLE_EVERY = 6
ALERT_AFTER = 12


def _log_notify_failure(code: str, exc: Exception) -> None:
    """Loga falha de notificação com throttle para evitar spam de retry."""
    count = _notify_failure_counts.get(code, 0) + 1
    _notify_failure_counts[code] = count
    if count == 1 or count % THROTTLE_EVERY == 0:
        print(f"Erro ao enviar e-mail da vaga {code}: {exc}", file=sys.stderr)
    else:
        print(
            f"Retry throttled da vaga {code}: tentativa {count} falhou, "
            f"próxima em breve (último erro: {exc})",
            file=sys.stderr,
        )
    if count == ALERT_AFTER:
        print(
            f"ALERTA: notificação da vaga {code} falhando há {count} "
            f"tentativas consecutivas, verifique RESEND_API_KEY / "
            f"conectividade com api.resend.com:443",
            file=sys.stderr,
        )


def run_once(
    seen_path: str | Path = "seen.json",
    params: dict[str, Any] | None = None,
    timeout: int = 15,
    keywords: list[str] | None = None,
) -> int:
    """Executa uma verificação única. Retorna 0 em sucesso, 1 em erro de API."""
    seen = load_seen(seen_path)

    try:
        vagas, total = fetch_todas_vagas(params=params, timeout=timeout)
    except CieeApiError as exc:
        print(f"Erro ao consultar API do CIEE: {exc}", file=sys.stderr)
        return 1

    active_keywords = resolve_keywords() if keywords is None else keywords
    novas = [
        vaga
        for vaga in find_new_vagas(vagas, seen)
        if vaga_matches(vaga, active_keywords)
    ]

    print(f"Vagas encontradas: {total} (retornadas nesta página: {len(vagas)})")
    print(f"Novas desde a última execução: {len(novas)}")
    print("-" * 60)

    novos_codes = {
        str(vaga.get("codigoVaga"))
        for vaga in novas
        if vaga.get("codigoVaga") is not None
    }
    for vaga in vagas:
        code = str(vaga.get("codigoVaga")) if vaga.get("codigoVaga") is not None else None
        is_new = code is not None and code in novos_codes
        print(format_vaga(vaga, is_new=is_new))
        print("-" * 60)

    # Notificação: somente vagas novas. A ordem importa:
    # notifica ANTES de persistir, e vagas com falha de envio NÃO são
    # marcadas como vistas — serão retentadas no próximo ciclo, sem
    # corromper seen.json e sem perda silenciosa.
    # Backend: Resend via HTTPS (produção, SMTP bloqueado no Deplexo) tem
    # precedência; SMTP é fallback local.
    notify_failed: set[str] = set()
    if novas:
        backend: str | None = None
        resend_config: ResendConfig | None = None
        smtp_config: EmailConfig | None = None
        try:
            resend_config = ResendConfig.from_env()
            backend = "resend"
        except NotifierConfigError:
            try:
                smtp_config = EmailConfig.from_env()
                backend = "smtp"
            except NotifierConfigError as exc:
                print(f"Erro de configuração de e-mail: {exc}", file=sys.stderr)
                print(
                    "Defina RESEND_API_KEY, CIEE_EMAIL_FROM e CIEE_EMAIL_TO "
                    "(Resend via HTTPS) ou CIEE_EMAIL_HOST, CIEE_EMAIL_PORT, "
                    "CIEE_EMAIL_USER, CIEE_EMAIL_PASSWORD e CIEE_EMAIL_TO "
                    "(SMTP) para ativar notificações.",
                    file=sys.stderr,
                )
                backend = None
        if backend == "resend" and resend_config is not None:
            for vaga in novas:
                code = str(vaga.get("codigoVaga"))
                try:
                    notify_vaga_resend(vaga, resend_config)
                    print(f"E-mail enviado para a vaga {code}.")
                    _notify_failure_counts.pop(code, None)
                except NotifierError as exc:
                    notify_failed.add(code)
                    _log_notify_failure(code, exc)
        elif backend == "smtp" and smtp_config is not None:
            for vaga in novas:
                code = str(vaga.get("codigoVaga"))
                try:
                    notify_vaga(vaga, smtp_config)
                    print(f"E-mail enviado para a vaga {code}.")
                    _notify_failure_counts.pop(code, None)
                except NotifierError as exc:
                    notify_failed.add(code)
                    _log_notify_failure(code, exc)

    # Persiste todos os codigoVaga retornados para não repetir como novos,
    # exceto novas com falha de e-mail (serão notificadas na próxima vez).
    updated = mark_as_seen(
        [v for v in vagas if str(v.get("codigoVaga")) not in notify_failed],
        seen,
    )
    try:
        save_seen(updated, seen_path)
    except OSError as exc:
        print(f"Aviso: não foi possível salvar {seen_path}: {exc}", file=sys.stderr)

    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Monitor CIEE - execução única ou contínua (--watch)")
    p.add_argument("--seen-file", default=None, help="arquivo local de vagas já vistas (padrão: $CIEE_SEEN_FILE, /data/seen.json se /data existir, senão seen.json)")
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


def resolve_seen_file(
    cli_value: str | Path | None = None, data_dir: Path | None = None
) -> str:
    """Precedência: --seen-file > $CIEE_SEEN_FILE > /data/seen.json > seen.json.

    O default automático usa /data/seen.json quando o diretório /data existe
    (produção no Deplexo) e seen.json caso contrário (uso local). Assim a
    produção funciona sem variável de ambiente e o local segue intacto.
    """
    if cli_value is not None and str(cli_value).strip() != "":
        return str(cli_value)
    env = os.getenv(SEEN_FILE_ENV_VAR)
    if env is not None and env.strip() != "":
        return env.strip()
    base = data_dir if data_dir is not None else DATA_DIR
    if base.is_dir():
        return str(base / "seen.json")
    return DEFAULT_SEEN_FILE


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    seen_path = resolve_seen_file(args.seen_file)
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
        try:
            port = resolve_port()
        except ValueError as exc:
            parser.error(str(exc))
        try:
            start_health_server(port)
        except OSError as exc:
            parser.error(f"não foi possível iniciar o health server na porta {port}: {exc}")
        print(f"Health check em :{port} (/health).")
        return run_forever(
            interval=interval,
            seen_path=seen_path,
            params=params,
            timeout=args.timeout,
        )
    return run_once(seen_path=seen_path, params=params, timeout=args.timeout)


if __name__ == "__main__":
    raise SystemExit(main())
