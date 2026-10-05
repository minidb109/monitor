"""Testes do notifier de e-mail (TDD). SMTP sempre mockado: nenhum e-mail real."""

from __future__ import annotations

import smtplib
from email.message import EmailMessage
from unittest.mock import MagicMock, patch

import pytest

REQUIRED_VARS = [
    "CIEE_EMAIL_HOST",
    "CIEE_EMAIL_PORT",
    "CIEE_EMAIL_USER",
    "CIEE_EMAIL_PASSWORD",
    "CIEE_EMAIL_TO",
]

FAKE_ENV = {
    "CIEE_EMAIL_HOST": "smtp.example.com",
    "CIEE_EMAIL_PORT": "587",
    "CIEE_EMAIL_USER": "remetente@example.com",
    "CIEE_EMAIL_PASSWORD": "senha-super-secreta-123",
    "CIEE_EMAIL_TO": "destino@example.com",
}


def _set_env(monkeypatch, **overrides):
    for var in REQUIRED_VARS:
        monkeypatch.delenv(var, raising=False)
    env = dict(FAKE_ENV)
    env.update(overrides)
    for var, val in env.items():
        if val is not None:
            monkeypatch.setenv(var, val)


def _vaga_exemplo():
    return {
        "codigoVaga": 6250388,
        "nomeEmpresa": "ZOIT MOCK (teste)",
        "areaProfissional": "Informática - TÉC.",
        "areaAtuacao": None,
        "bolsaAuxilio": 900,
        "tipoAuxilioBolsa": "Mensal",
        "descricao": "Suporte técnico em desenvolvimento de software mock",
        "atividades": ["Atender chamados", "Manutenção"],
        "local": {"cidade": "Sorocaba", "uf": "SP", "bairro": "Centro"},
    }


# --- construção do e-mail ---


def test_build_message_assunto_contem_codigo(monkeypatch):
    from ciee_monitor import notifier

    _set_env(monkeypatch)
    config = notifier.EmailConfig.from_env()
    msg = notifier.build_message(_vaga_exemplo(), config)
    assert "6250388" in msg["Subject"]
    assert msg["Subject"] == "[CIEE Monitor] Nova vaga de estágio - 6250388"


def test_build_message_corpo_contem_principais_dados(monkeypatch):
    from ciee_monitor import notifier

    _set_env(monkeypatch)
    config = notifier.EmailConfig.from_env()
    body = notifier.build_message(_vaga_exemplo(), config).get_content()
    assert "6250388" in body
    assert "ZOIT MOCK (teste)" in body
    assert "Informática - TÉC." in body
    assert "900" in body
    assert "Sorocaba" in body
    assert "Suporte técnico em desenvolvimento de software mock" in body
    assert "Atender chamados" in body


def test_build_message_sem_atividades_nao_quebra(monkeypatch):
    from ciee_monitor import notifier

    _set_env(monkeypatch)
    config = notifier.EmailConfig.from_env()
    vaga = _vaga_exemplo()
    vaga["atividades"] = []
    body = notifier.build_message(vaga, config).get_content()
    assert "6250388" in body


def test_build_message_nunca_contem_senha(monkeypatch):
    from ciee_monitor import notifier

    _set_env(monkeypatch)
    config = notifier.EmailConfig.from_env()
    msg = notifier.build_message(_vaga_exemplo(), config)
    assert "senha-super-secreta-123" not in msg.as_string()


def test_build_message_corpo_contem_link_vitrine(monkeypatch):
    from ciee_monitor import notifier

    _set_env(monkeypatch)
    config = notifier.EmailConfig.from_env()
    body = notifier.build_message(_vaga_exemplo(), config).get_content()
    assert "https://ciee.app/login?codigoVagaPortal=6250388" in body
    assert "VITRINE_VAGA" in body


def test_build_message_corpo_contem_horario(monkeypatch):
    from ciee_monitor import notifier

    _set_env(monkeypatch)
    config = notifier.EmailConfig.from_env()
    vaga = _vaga_exemplo()
    vaga["horarioEntrada"] = "09:00:00"
    vaga["horarioSaida"] = "16:00:00"
    body = notifier.build_message(vaga, config).get_content()
    assert "09:00 às 16:00" in body


def test_build_message_sem_codigo_sem_link_nao_quebra(monkeypatch):
    from ciee_monitor import notifier

    _set_env(monkeypatch)
    config = notifier.EmailConfig.from_env()
    vaga = _vaga_exemplo()
    vaga.pop("codigoVaga", None)
    body = notifier.build_message(vaga, config).get_content()
    assert "ciee.app" not in body


# --- configuração via ambiente ---


def test_from_env_le_variaveis(monkeypatch):
    from ciee_monitor import notifier

    _set_env(monkeypatch)
    config = notifier.EmailConfig.from_env()
    assert config.host == "smtp.example.com"
    assert config.port == 587
    assert config.user == "remetente@example.com"
    assert config.password == "senha-super-secreta-123"
    assert config.to == "destino@example.com"


def test_from_env_port_default_587(monkeypatch):
    from ciee_monitor import notifier

    _set_env(monkeypatch, CIEE_EMAIL_PORT=None)
    assert notifier.EmailConfig.from_env().port == 587


def test_from_env_faltando_config_erro_claro_sem_expor_senha(monkeypatch):
    from ciee_monitor import notifier

    _set_env(monkeypatch, CIEE_EMAIL_HOST=None, CIEE_EMAIL_TO=None)
    with pytest.raises(notifier.NotifierConfigError) as excinfo:
        notifier.EmailConfig.from_env()
    texto = str(excinfo.value)
    assert "CIEE_EMAIL_HOST" in texto
    assert "CIEE_EMAIL_TO" in texto
    assert "senha-super-secreta-123" not in texto


# --- envio via SMTP (mockado) ---


def test_notify_chama_smtp_corretamente(monkeypatch):
    from ciee_monitor import notifier

    _set_env(monkeypatch)
    config = notifier.EmailConfig.from_env()

    fake_smtp = MagicMock()
    fake_factory = MagicMock(return_value=fake_smtp)
    # context manager do smtplib
    fake_smtp.__enter__.return_value = fake_smtp

    with patch.object(notifier.smtplib, "SMTP", fake_factory):
        notifier.notify_vaga(_vaga_exemplo(), config)

    fake_factory.assert_called_once_with("smtp.example.com", 587, timeout=15)
    fake_smtp.starttls.assert_called_once_with()
    fake_smtp.login.assert_called_once_with("remetente@example.com", "senha-super-secreta-123")
    assert fake_smtp.send_message.call_count == 1
    sent: EmailMessage = fake_smtp.send_message.call_args[0][0]
    assert sent["To"] == "destino@example.com"
    assert "6250388" in sent["Subject"]


def test_notify_falha_smtp_vira_notifier_error_sem_expor_senha(monkeypatch):
    from ciee_monitor import notifier

    _set_env(monkeypatch)
    config = notifier.EmailConfig.from_env()

    with patch.object(
        notifier.smtplib,
        "SMTP",
        side_effect=smtplib.SMTPException("conexão recusada"),
    ):
        with pytest.raises(notifier.NotifierError) as excinfo:
            notifier.notify_vaga(_vaga_exemplo(), config)
    assert "senha-super-secreta-123" not in str(excinfo.value)


# --- integração com run_once ---


def _run_once_com_fetch_mockado(tmp_path, vagas, **patches):
    """Roda run_once real com fetch mockado e notify mockado/injetável."""
    import json

    from ciee_monitor import __main__ as m

    seen = tmp_path / "seen.json"
    if "seen_inicial" in patches:
        seen.write_text(json.dumps(patches.pop("seen_inicial")), encoding="utf-8")
    with patch.object(m, "fetch_todas_vagas", return_value=(vagas, len(vagas))):
        notify_mock = patches.get("notify_mock", MagicMock())
        with patch.object(m, "notify_vaga", notify_mock):
            rc = m.run_once(seen_path=str(seen))
    saved = None
    if seen.exists():
        saved = json.loads(seen.read_text(encoding="utf-8"))
    return rc, notify_mock, saved


def test_run_once_vaga_nova_dispara_notificacao(tmp_path, monkeypatch):
    _set_env(monkeypatch)
    rc, notify_mock, saved = _run_once_com_fetch_mockado(tmp_path, [_vaga_exemplo()])
    assert rc == 0
    assert notify_mock.call_count == 1
    assert notify_mock.call_args[0][0]["codigoVaga"] == 6250388
    assert "6250388" in saved


def test_run_once_vaga_conhecida_nao_dispara(tmp_path):
    rc, notify_mock, saved = _run_once_com_fetch_mockado(
        tmp_path, [_vaga_exemplo()], seen_inicial=["6250388"]
    )
    assert rc == 0
    assert notify_mock.call_count == 0
    assert saved == ["6250388"]


def test_run_once_falha_email_nao_corrompe_seen_e_nao_confunde_com_api(
    tmp_path, capsys, monkeypatch
):
    import json

    from unittest.mock import patch

    from ciee_monitor import __main__ as m
    from ciee_monitor.notifier import NotifierError

    _set_env(monkeypatch)

    seen = tmp_path / "seen.json"
    seen.write_text(json.dumps(["111"]), encoding="utf-8")
    vagas = [_vaga_exemplo()]  # 6250388 nova

    with patch.object(m, "fetch_todas_vagas", return_value=(vagas, 1)):
        with patch.object(m, "notify_vaga", side_effect=NotifierError("smtp caiu")):
            rc = m.run_once(seen_path=str(seen))

    assert rc == 0  # falha de e-mail não é falha de API (que retornaria 1)
    err = capsys.readouterr().err
    assert "e-mail" in err.lower() or "email" in err.lower()
    assert "6250388" in err  # identifica a vaga com problema
    # estado válido e preservado: antiga intacta, nova NÃO marcada (será retentada)
    saved = json.loads(seen.read_text(encoding="utf-8"))
    assert saved == ["111"]


def test_run_once_sem_config_email_erro_compreensivel_sem_traceback(
    tmp_path, monkeypatch, capsys
):
    import json
    from unittest.mock import patch

    from ciee_monitor import __main__ as m

    for var in REQUIRED_VARS:
        monkeypatch.delenv(var, raising=False)
    seen = tmp_path / "seen.json"
    with patch.object(m, "fetch_todas_vagas", return_value=([_vaga_exemplo()], 1)):
        rc = m.run_once(seen_path=str(seen))  # não deve levantar

    assert rc == 0
    err = capsys.readouterr().err
    assert "CIEE_EMAIL_HOST" in err  # erro de configuração compreensível
    assert "Traceback" not in err
    # sem configuração, mantém semântica atual: marca como vista
    assert json.loads(seen.read_text(encoding="utf-8")) == ["6250388"]
