"""Testes do health server (TDD). Só stdlib, portas efêmeras, nenhum segredo real."""

from __future__ import annotations

import http.client

import pytest


@pytest.fixture()
def server():
    from ciee_monitor import health

    srv = health.start_health_server(port=0, host="127.0.0.1")
    yield srv
    srv.shutdown()
    srv.server_close()


def _get(server, path):
    host, port = server.server_address[0], server.server_address[1]
    conn = http.client.HTTPConnection(host, port, timeout=5)
    try:
        conn.request("GET", path)
        resp = conn.getresponse()
        return resp.status, resp.read()
    finally:
        conn.close()


def test_health_endpoint_retorna_200(server):
    status, _ = _get(server, "/health")
    assert status == 200


def test_raiz_retorna_200(server):
    status, _ = _get(server, "/")
    assert status == 200


def test_rota_desconhecida_retorna_404(server):
    status, _ = _get(server, "/nada-aqui")
    assert status == 404


def test_resposta_nao_expoe_credenciais(server):
    _, body = _get(server, "/health")
    assert body == b"ok"
    for marcador in (b"CIEE_EMAIL", b"password", b"PASSWORD", b"token", b"vaga"):
        assert marcador not in body


def test_resolve_port_le_port(monkeypatch):
    from ciee_monitor import health

    monkeypatch.setenv("PORT", "4321")
    assert health.resolve_port() == 4321


def test_resolve_port_default_8000_sem_env(monkeypatch):
    from ciee_monitor import health

    monkeypatch.delenv("PORT", raising=False)
    assert health.resolve_port() == 8000


def test_resolve_port_invalida_erro_claro(monkeypatch):
    from ciee_monitor import health

    monkeypatch.setenv("PORT", "abc")
    with pytest.raises(ValueError, match="PORT"):
        health.resolve_port()


def test_main_watch_inicia_health_e_monitor(monkeypatch):
    from unittest.mock import MagicMock

    import ciee_monitor.__main__ as m

    monkeypatch.delenv("PORT", raising=False)
    fake_health = MagicMock()
    fake_run = MagicMock(return_value=0)
    monkeypatch.setattr(m, "start_health_server", fake_health)
    monkeypatch.setattr(m, "run_forever", fake_run)
    rc = m.main(["--watch", "--interval", "7"])
    assert rc == 0
    fake_health.assert_called_once_with(8000)
    assert fake_run.called


def test_main_watch_port_invalida_sem_traceback(monkeypatch, capsys):
    from unittest.mock import MagicMock

    import ciee_monitor.__main__ as m

    monkeypatch.setenv("PORT", "abc")
    monkeypatch.setattr(m, "run_forever", MagicMock(return_value=0))
    with pytest.raises(SystemExit):
        m.main(["--watch"])
    assert "Traceback" not in capsys.readouterr().err
