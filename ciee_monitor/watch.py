"""Loop contínuo do monitor CIEE (sem notificações)."""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable


def _default_run_once(
    seen_path: str | Path, params: dict[str, Any] | None, timeout: int
) -> int:
    # Import lazy para evitar import circular (__main__ importa este módulo).
    from .__main__ import run_once

    return run_once(seen_path=seen_path, params=params, timeout=timeout)


def run_forever(
    interval: int = 300,
    seen_path: str | Path = "seen.json",
    params: dict[str, Any] | None = None,
    timeout: int = 15,
    max_iterations: int | None = None,
    run_once_fn: Callable[..., int] | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> int:
    """Roda o monitor em loop até Ctrl+C.

    - Preserva a persistência do `run_once()` (só persiste em sucesso).
    - Erro da API (retorno 1) NÃO encerra o loop; apenas aguarda e tenta de novo.
    - `max_iterations` existe só para testes/validação local.
    """
    if interval <= 0:
        raise ValueError("intervalo deve ser maior que zero")

    runner = run_once_fn if run_once_fn is not None else _default_run_once

    print("CIEE Monitor iniciado.")
    print(f"Intervalo: {interval} segundos.")

    iteration = 0
    try:
        while True:
            iteration += 1
            stamp = datetime.now().strftime("%H:%M:%S")
            print(f"\n[{stamp}] Consultando CIEE...")

            rc = runner(seen_path=seen_path, params=params, timeout=timeout)
            is_last = max_iterations is not None and iteration >= max_iterations

            if rc != 0:
                # run_once() já registrou o erro em stderr; aqui só orientamos retry.
                if is_last:
                    break
                print(f"\nTentando novamente em {interval} segundos.")
            else:
                if is_last:
                    break
                print(f"\nPróxima consulta em {interval} segundos.")

            try:
                sleep_fn(interval)
            except KeyboardInterrupt:
                raise
    except KeyboardInterrupt:
        print("\nEncerrando monitor. Até logo!")
        return 0

    return 0
