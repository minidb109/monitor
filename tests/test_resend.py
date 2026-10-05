"""Testes do notifier Resend via HTTPS (TDD - RED primeiro)."""

from __future__ import annotations

import json


FAKE_RESEND_ENV = {
    "RESEND_API_KEY": "re_chave-ficticia-123",
    "CIEE_EMAIL_FROM": "monitor@example.com",
    "CIEE_EMAIL_TO": "destino@example.com",
}


def _set_resend_env(monkeypatch, **overrides):
    for var in ("RESEND_API_KEY", "CIEE_EMAIL_FROM", "CIEE_EMAIL_TO",
                "CIEE_EMAIL_HOST", "CIEE_EMAIL_USER",
                "CIEE_EMAIL_PASSWORD", "CIEE_EMAIL_PORT"):
        monkeypatch.delenv(var, raising=False)
    env = dict(FAKE_RESEND_ENV)
    env.update(overrides)
    for var, val in env.items():
        if val is not None:
            monkeypatch.setenv(var, val)


def _vaga_exemplo():
    return {
        "codigoVaga": 6253523,
        "nomeEmpresa": "LEOCADIO & RODRIGUES BUSINESS SOLUTIONS LTDA",
        "areaProfissional": "Informática - TÉC.",
        "areaAtuacao": None,
        "bolsaAuxilio": 1200,
        "tipoAuxilioBolsa": "Mensal",
        "descricao": None,
        "atividades": [
            "Acessar arquivos e carregá-los com informações solicitadas",
            "Acessar as funções de pesquisa tecnológica",
            "Acessar sistemas internos",
        ],
        "local": {"cidade": "Sorocaba", "uf": "SP", "bairro": "Central Parque Sorocaba"},
    }


def test_resend_config_from_env_ok(monkeypatch):
    from ciee_monitor import notifier

    _set_resend_env(monkeypatch)
    config = notifier.ResendConfig.from_env()
    assert config.api_key == "re_chave-ficticia-123"
    assert config.from_addr == "monitor@example.com"
    assert config.to == "destino@example.com"


def test_resend_config_faltando_erro_sem_expor_chave(monkeypatch):
    import pytest

    from ciee_monitor import notifier

    _set_resend_env(monkeypatch, RESEND_API_KEY=None)
    with pytest.raises(notifier.NotifierConfigError) as excinfo:
        notifier.ResendConfig.from_env()
    assert "RESEND_API_KEY" in str(excinfo.value)
    assert "re_chave-ficticia-123" not in str(excinfo.value)


def test_resend_repr_nunca_expoe_chave(monkeypatch):
    from ciee_monitor import notifier

    _set_resend_env(monkeypatch)
    config = notifier.ResendConfig.from_env()
    assert "re_chave-ficticia-123" not in repr(config)


def test_build_resend_payload_contem_codigo_e_texto(monkeypatch):
    from ciee_monitor import notifier

    _set_resend_env(monkeypatch)
    config = notifier.ResendConfig.from_env()
    payload = notifier.build_resend_payload(_vaga_exemplo(), config)
    assert payload["from"] == "monitor@example.com"
    assert "destino@example.com" in payload["to"]
    assert "6253523" in payload["subject"]
    assert "6253523" in payload["text"]
    assert "LEOCADIO" in payload["text"]
    assert "sistemas internos" in payload["text"]


def test_build_resend_payload_contem_link_texto_e_html(monkeypatch):
    from ciee_monitor import notifier

    _set_resend_env(monkeypatch)
    config = notifier.ResendConfig.from_env()
    payload = notifier.build_resend_payload(_vaga_exemplo(), config)
    url = "https://ciee.app/login?codigoVagaPortal=6253523&acesso=VITRINE_VAGA&tag=S_QUERO"
    assert url in payload["text"]
    assert url in payload["html"] or "codigoVagaPortal=6253523" in payload["html"]
    assert "Ver vaga no CIEE" in payload["html"]
    assert "<a href=" in payload["html"]


def test_build_resend_payload_html_tem_link_unico(monkeypatch):
    from ciee_monitor import notifier

    _set_resend_env(monkeypatch)
    config = notifier.ResendConfig.from_env()
    payload = notifier.build_resend_payload(_vaga_exemplo(), config)
    url = "https://ciee.app/login?codigoVagaPortal=6253523&acesso=VITRINE_VAGA&tag=S_QUERO"
    # Texto mantém a URL crua; HTML deve ter ocorrência única (só o CTA).
    # & escapa para &amp; no HTML, então conta pelo marcador estável.
    assert url in payload["text"]
    assert payload["html"].count("codigoVagaPortal=6253523") == 1
    assert "Link:" not in payload["html"]
    assert "Ver vaga no CIEE" in payload["html"]


def test_build_resend_payload_sem_codigo_sem_link_nao_quebra(monkeypatch):
    from ciee_monitor import notifier

    _set_resend_env(monkeypatch)
    config = notifier.ResendConfig.from_env()
    vaga = _vaga_exemplo()
    vaga.pop("codigoVaga", None)
    payload = notifier.build_resend_payload(vaga, config)
    assert "ciee.app" not in payload["text"]


def test_notify_resend_chama_https_corretamente(monkeypatch):
    from unittest.mock import MagicMock, patch

    from ciee_monitor import notifier

    _set_resend_env(monkeypatch)
    config = notifier.ResendConfig.from_env()

    fake_resp = MagicMock()
    fake_resp.status = 200
    fake_resp.read.return_value = b'{"id":"abc"}'
    fake_resp.__enter__.return_value = fake_resp
    fake_resp.__exit__.return_value = False

    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["url"] = req.full_url
        captured["headers"] = dict(req.header_items())
        captured["data"] = json.loads(req.data.decode("utf-8"))
        captured["timeout"] = timeout
        return fake_resp

    with patch.object(notifier.urllib.request, "urlopen", side_effect=fake_urlopen):
        notifier.notify_vaga_resend(_vaga_exemplo(), config)

    assert captured["url"] == "https://api.resend.com/emails"
    # Authorization Bearer presente (case-insensitive)
    auth = {k.lower(): v for k, v in captured["headers"].items()}.get("authorization", "")
    assert auth == "Bearer re_chave-ficticia-123"
    assert "6253523" in captured["data"]["subject"]
    assert captured["timeout"] == 15


def test_notify_resend_envia_user_agent_customizado(monkeypatch):
    """Cloudflare/Resend bloqueia Python-urllib com 403 error code 1010.

    O notifier deve enviar User-Agent explícito (não Python-urllib).
    """
    from unittest.mock import MagicMock, patch

    from ciee_monitor import notifier

    _set_resend_env(monkeypatch)
    config = notifier.ResendConfig.from_env()

    fake_resp = MagicMock()
    fake_resp.status = 200
    fake_resp.__enter__.return_value = fake_resp
    fake_resp.__exit__.return_value = False

    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["headers"] = {k.lower(): v for k, v in req.header_items()}
        return fake_resp

    with patch.object(notifier.urllib.request, "urlopen", side_effect=fake_urlopen):
        notifier.notify_vaga_resend(_vaga_exemplo(), config)

    ua = captured["headers"].get("user-agent", "")
    assert ua != "", "User-Agent explícito ausente (cai para Python-urllib, bloqueado com 1010)"
    assert "python-urllib" not in ua.lower()


def test_notify_resend_falha_http_vira_notifier_error_sem_chave(monkeypatch):
    import urllib.error

    import pytest

    from ciee_monitor import notifier

    _set_resend_env(monkeypatch)
    config = notifier.ResendConfig.from_env()

    def fake_urlopen(req, timeout=None):
        raise urllib.error.HTTPError(
            req.full_url, 401, "Unauthorized", {}, None
        )

    from unittest.mock import patch

    with patch.object(notifier.urllib.request, "urlopen", side_effect=fake_urlopen):
        with pytest.raises(notifier.NotifierError) as excinfo:
            notifier.notify_vaga_resend(_vaga_exemplo(), config)
    assert "re_chave-ficticia-123" not in str(excinfo.value)
    assert "6253523" in str(excinfo.value)


def test_run_once_usa_resend_quando_chave_presente(tmp_path, monkeypatch):
    import json
    from unittest.mock import MagicMock, patch

    from ciee_monitor import __main__ as m

    _set_resend_env(monkeypatch)
    monkeypatch.delenv("CIEE_KEYWORDS", raising=False)
    seen = tmp_path / "seen.json"
    vagas = [_vaga_exemplo()]
    with patch.object(m, "fetch_todas_vagas", return_value=(vagas, 1)):
        with patch.object(m, "notify_vaga_resend", MagicMock()) as mock_resend:
            with patch.object(m, "notify_vaga", MagicMock()) as mock_smtp:
                assert m.run_once(seen_path=str(seen)) == 0
    assert mock_resend.call_count == 1
    assert mock_smtp.call_count == 0
    assert json.loads(seen.read_text(encoding="utf-8")) == ["6253523"]


def test_run_once_falha_resend_nao_marca_vista_e_throttle_log(tmp_path, monkeypatch, capsys):
    import json
    from unittest.mock import patch

    from ciee_monitor import __main__ as m
    from ciee_monitor.notifier import NotifierError

    _set_resend_env(monkeypatch)
    monkeypatch.delenv("CIEE_KEYWORDS", raising=False)
    # limpa contadores de throttle entre testes
    m._notify_failure_counts.clear()
    seen = tmp_path / "seen.json"
    vagas = [_vaga_exemplo()]
    # 1a tentativa: loga erro cheio
    with patch.object(m, "fetch_todas_vagas", return_value=(vagas, 1)):
        with patch.object(m, "notify_vaga_resend", side_effect=NotifierError("rede caiu")):
            assert m.run_once(seen_path=str(seen)) == 0
    err1 = capsys.readouterr().err
    assert "6253523" in err1
    assert json.loads(seen.read_text(encoding="utf-8")) == []
    # 2a tentativa imediata: throttled (sem repetir erro cheio)
    with patch.object(m, "fetch_todas_vagas", return_value=(vagas, 1)):
        with patch.object(m, "notify_vaga_resend", side_effect=NotifierError("rede caiu")):
            assert m.run_once(seen_path=str(seen)) == 0
    err2 = capsys.readouterr().err
    # deve mencionar retry/throttle, não repetir stack completo a cada ciclo
    assert "6253523" in err2 or "throttled" in err2.lower() or "tentativa" in err2.lower()
    assert json.loads(seen.read_text(encoding="utf-8")) == []
