"""Testes do modo contínuo (TDD - escritos antes da implementação)."""

from unittest.mock import MagicMock, call

import pytest


def test_run_forever_existe_e_chama_run_once_multiplas_vezes():
    from ciee_monitor import watch

    fake_run = MagicMock(return_value=0)
    fake_sleep = MagicMock()

    watch.run_forever(
        interval=300,
        seen_path="seen.json",
        run_once_fn=fake_run,
        sleep_fn=fake_sleep,
        max_iterations=3,
    )

    assert fake_run.call_count == 3
    assert fake_sleep.call_count == 2  # não dorme após a última iteração
    fake_sleep.assert_has_calls([call(300), call(300)])


def test_run_forever_erro_api_nao_encerra_loop():
    from ciee_monitor import watch

    fake_run = MagicMock(side_effect=[1, 1, 0])  # 1 = erro, 0 = ok
    fake_sleep = MagicMock()

    rc = watch.run_forever(
        interval=10,
        seen_path="seen.json",
        run_once_fn=fake_run,
        sleep_fn=fake_sleep,
        max_iterations=3,
    )

    assert rc == 0
    assert fake_run.call_count == 3
    assert fake_sleep.call_count == 2


def test_run_forever_keyboard_interrupt_encerra_limpo(capsys):
    from ciee_monitor import watch

    fake_run = MagicMock(return_value=0)

    def interrupting_sleep(_s):
        raise KeyboardInterrupt()

    rc = watch.run_forever(
        interval=300,
        seen_path="seen.json",
        run_once_fn=fake_run,
        sleep_fn=interrupting_sleep,
        max_iterations=None,
    )

    assert rc == 0
    assert fake_run.call_count == 1
    out = capsys.readouterr().out
    assert "Encerrando" in out or "encerr" in out.lower()


def test_run_forever_nao_marca_vistas_quando_api_falha(tmp_path):
    """Garante que falha não persiste estado (run_once real com fetch mockado)."""
    import json

    from unittest.mock import patch

    from ciee_monitor import api, watch

    seen = tmp_path / "seen.json"
    seen.write_text(json.dumps(["111"]), encoding="utf-8")

    with patch.object(
        api.requests, "get", side_effect=api.requests.exceptions.Timeout()
    ):
        # usa run_once real via watch.run_forever com 1 iteração
        rc = watch.run_forever(
            interval=5,
            seen_path=str(seen),
            timeout=5,
            max_iterations=1,
        )

    assert rc == 0  # watch não propaga erro como falha fatal
    assert json.loads(seen.read_text(encoding="utf-8")) == ["111"]


def test_cli_watch_parse_defaults(monkeypatch):
    from ciee_monitor.__main__ import build_parser, resolve_interval

    monkeypatch.delenv("CIEE_INTERVAL", raising=False)
    args = build_parser().parse_args([])
    assert args.watch is False
    assert resolve_interval(args) == 300


def test_cli_watch_flag_e_interval():
    from ciee_monitor.__main__ import build_parser, resolve_interval

    args = build_parser().parse_args(["--watch", "--interval", "60"])
    assert args.watch is True
    assert resolve_interval(args) == 60


def test_cli_interval_via_env(monkeypatch):
    from ciee_monitor.__main__ import build_parser, resolve_interval

    monkeypatch.setenv("CIEE_INTERVAL", "120")
    args = build_parser().parse_args(["--watch"])
    assert resolve_interval(args) == 120


def test_cli_interval_cli_vence_env(monkeypatch):
    from ciee_monitor.__main__ import build_parser, resolve_interval

    monkeypatch.setenv("CIEE_INTERVAL", "120")
    args = build_parser().parse_args(["--watch", "--interval", "60"])
    assert resolve_interval(args) == 60


def test_cli_interval_invalido_rejeitado():
    from ciee_monitor.__main__ import build_parser
    import argparse

    # argparse deve rejeitar intervalo <= 0 via type/choices ou validação posterior;
    # aqui garantimos que main() retorna erro ou levanta SystemExit/ValueError.
    from ciee_monitor.__main__ import main

    with pytest.raises((SystemExit, ValueError)):
        main(["--watch", "--interval", "0"])


def test_main_watch_chama_run_forever(monkeypatch):
    from unittest.mock import MagicMock

    import ciee_monitor.__main__ as m

    fake = MagicMock(return_value=0)
    monkeypatch.setattr(m, "run_forever", fake)
    rc = m.main(["--watch", "--interval", "7", "--seen-file", "x.json"])
    assert rc == 0
    assert fake.called
    _, kwargs = fake.call_args
    assert kwargs.get("interval") == 7 or fake.call_args[0][0] == 7


def test_main_sem_watch_chama_run_once(monkeypatch):
    from unittest.mock import MagicMock

    import ciee_monitor.__main__ as m

    fake = MagicMock(return_value=0)
    monkeypatch.setattr(m, "run_once", fake)
    rc = m.main([])
    assert rc == 0
    assert fake.called
