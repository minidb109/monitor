"""Health check HTTP para o deploy (somente stdlib).

O Deplexo exige uma resposta HTTP para considerar o container pronto.
Roda em thread daemon junto do `run_forever()` — sem Flask/FastAPI,
sem dependências novas, sem expor dados, vagas ou credenciais.
"""

from __future__ import annotations

import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DEFAULT_PORT = 8000
PORT_ENV_VAR = "PORT"


def resolve_port() -> int:
    """PORT definido → usa PORT; ausente → 8000.

    Raises:
        ValueError: PORT não é um inteiro válido (mensagem clara, sem valores
            sensíveis — porta não é segredo).
    """
    raw = os.getenv(PORT_ENV_VAR)
    if raw is None or raw.strip() == "":
        return DEFAULT_PORT
    try:
        return int(raw.strip())
    except ValueError as exc:
        raise ValueError(
            f"PORT inválida: {raw.strip()!r}; use um número de porta"
        ) from exc


class HealthHandler(BaseHTTPRequestHandler):
    """GET /health e GET / → 200 'ok'; demais rotas → 404."""

    def do_GET(self) -> None:  # noqa: N802 - assinatura da stdlib
        path = self.path.split("?", 1)[0]
        if path in ("/health", "/"):
            body = b"ok"
            self.send_response(200)
        else:
            body = b"not found"
            self.send_response(404)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: object) -> None:
        # Silencia o log por requisição (o Deplexo faz probes frequentes).
        pass


def start_health_server(
    port: int | None = None, host: str = "0.0.0.0"
) -> ThreadingHTTPServer:
    """Sobe o health server em thread daemon e retorna o servidor."""
    server = ThreadingHTTPServer(
        (host, port if port is not None else resolve_port()), HealthHandler
    )
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server
