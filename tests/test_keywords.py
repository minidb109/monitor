"""Testes do filtro de vagas por palavras-chave (TDD)."""

from __future__ import annotations

import pytest


def _vaga_java_backend():
    return {
        "codigoVaga": 101,
        "nomeEmpresa": "Tech Mock",
        "areaProfissional": "Informática - TÉC.",
        "descricao": "Estágio Java Backend com Spring",
        "atividades": ["Desenvolver APIs REST", "Code review"],
    }


def _vaga_desenvolvimento_sistemas():
    return {
        "codigoVaga": 102,
        "nomeEmpresa": "Sistemas Mock",
        "areaProfissional": "Informática - TÉC.",
        "areaAtuacao": "Desenvolvimento de Sistemas",
        "descricao": "Apoio à equipe de TI",
        "atividades": ["Rotinas administrativas do setor"],
    }


def _vaga_irrelevante():
    return {
        "codigoVaga": 103,
        "nomeEmpresa": "RH Mock",
        "areaProfissional": "Administração",
        "descricao": "Auxiliar administrativo com rotinas de escritório",
        "atividades": ["Atender telefone", "Arquivar documentos"],
    }


def test_java_backend_aceita(monkeypatch):
    from ciee_monitor import keywords

    monkeypatch.delenv("CIEE_KEYWORDS", raising=False)
    assert keywords.vaga_matches(_vaga_java_backend(), keywords.resolve_keywords())


def test_desenvolvimento_de_sistemas_aceita(monkeypatch):
    from ciee_monitor import keywords

    monkeypatch.delenv("CIEE_KEYWORDS", raising=False)
    assert keywords.vaga_matches(
        _vaga_desenvolvimento_sistemas(), keywords.resolve_keywords()
    )


def test_vaga_sem_relacao_rejeitada(monkeypatch):
    from ciee_monitor import keywords

    monkeypatch.delenv("CIEE_KEYWORDS", raising=False)
    assert not keywords.vaga_matches(_vaga_irrelevante(), keywords.resolve_keywords())


def test_match_sem_acento(monkeypatch):
    from ciee_monitor import keywords

    monkeypatch.delenv("CIEE_KEYWORDS", raising=False)
    vaga = {"codigoVaga": 104, "descricao": "Estagio em programacao web"}
    assert keywords.vaga_matches(vaga, keywords.resolve_keywords())


def test_keywords_via_env(monkeypatch):
    from ciee_monitor import keywords

    monkeypatch.setenv("CIEE_KEYWORDS", "astronomia, telescópios")
    assert keywords.resolve_keywords() == ["astronomia", "telescópios"]
    assert keywords.vaga_matches(
        {"codigoVaga": 105, "descricao": "Estágio em astronomia observacional"},
        keywords.resolve_keywords(),
    )
    assert not keywords.vaga_matches(
        _vaga_java_backend(), keywords.resolve_keywords()
    )


def test_sem_env_usa_padrao(monkeypatch):
    from ciee_monitor import keywords

    monkeypatch.delenv("CIEE_KEYWORDS", raising=False)
    assert keywords.resolve_keywords() == keywords.DEFAULT_KEYWORDS
    assert keywords.resolve_keywords() is not keywords.DEFAULT_KEYWORDS


def _set_fake_email_env(monkeypatch):
    monkeypatch.setenv("CIEE_EMAIL_HOST", "smtp.example.com")
    monkeypatch.setenv("CIEE_EMAIL_USER", "remetente@example.com")
    monkeypatch.setenv("CIEE_EMAIL_PASSWORD", "senha-ficticia")
    monkeypatch.setenv("CIEE_EMAIL_TO", "destino@example.com")


def test_dedup_continua_funcionando(tmp_path, monkeypatch):
    from unittest.mock import MagicMock, patch

    from ciee_monitor import __main__ as m

    monkeypatch.delenv("CIEE_KEYWORDS", raising=False)
    _set_fake_email_env(monkeypatch)
    seen = tmp_path / "seen.json"
    vagas = [_vaga_java_backend()]
    with patch.object(m, "fetch_vagas", return_value=(vagas, 1)):
        with patch.object(m, "notify_vaga", MagicMock()):
            assert m.run_once(seen_path=str(seen)) == 0
    with patch.object(m, "fetch_vagas", return_value=(vagas, 1)):
        notify_mock = MagicMock()
        with patch.object(m, "notify_vaga", notify_mock):
            assert m.run_once(seen_path=str(seen)) == 0
    assert notify_mock.call_count == 0


def test_email_somente_para_novas_relevantes(tmp_path, monkeypatch):
    import json
    from unittest.mock import MagicMock, patch

    from ciee_monitor import __main__ as m

    monkeypatch.delenv("CIEE_KEYWORDS", raising=False)
    _set_fake_email_env(monkeypatch)
    relevante_nova = _vaga_java_backend()
    relevante_vista = dict(_vaga_desenvolvimento_sistemas(), codigoVaga=102)
    irrelevante_nova = _vaga_irrelevante()
    seen = tmp_path / "seen.json"
    seen.write_text(json.dumps(["102"]), encoding="utf-8")
    vagas = [relevante_nova, relevante_vista, irrelevante_nova]
    with patch.object(m, "fetch_vagas", return_value=(vagas, 3)):
        notify_mock = MagicMock()
        with patch.object(m, "notify_vaga", notify_mock):
            assert m.run_once(seen_path=str(seen)) == 0
    assert notify_mock.call_count == 1
    assert notify_mock.call_args[0][0]["codigoVaga"] == 101
