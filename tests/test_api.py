"""Testes para ciee_monitor.api (TDD - escritos antes da implementação)."""

from unittest.mock import MagicMock, patch

import pytest
import requests


def _fake_response(json_data, status_code=200):
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = json_data
    mock_resp.raise_for_status.return_value = None
    return mock_resp


def test_fetch_vagas_retorna_content_e_total():
    from ciee_monitor import api

    payload = {
        "content": [
            {
                "codigoVaga": 123,
                "nomeEmpresa": "Empresa X",
                "areaProfissional": "Informática - TÉC.",
                "areaAtuacao": None,
                "bolsaAuxilio": 1000,
                "descricao": "desc",
                "atividades": ["a", "b"],
                "local": {"cidade": "Sorocaba", "uf": "SP", "bairro": "Centro"},
            }
        ],
        "totalElements": 1,
    }
    with patch.object(api.requests, "get", return_value=_fake_response(payload)) as mock_get:
        vagas, total = api.fetch_vagas(timeout=5)
        assert vagas == payload["content"]
        assert total == 1
        assert mock_get.called


def test_fetch_vagas_usa_filtros_padrao_sorocaba_dev():
    from ciee_monitor import api

    payload = {"content": [], "totalElements": 0}
    with patch.object(api.requests, "get", return_value=_fake_response(payload)) as mock_get:
        api.fetch_vagas()
        _, kwargs = mock_get.call_args
        params = kwargs.get("params") or mock_get.call_args[0][1] if len(mock_get.call_args[0]) > 1 else kwargs["params"]
        # params deve conter os filtros confirmados
        assert params["tipoVaga"] == "ESTAGIO"
        assert params["nivelEnsino"] == "TE"
        assert params["codigoMunicipio"] == 3552205
        assert params["idAreaProfissional"] == 53
        assert params["idAreaAtuacaoEstagio"] == 473


def test_fetch_vagas_erro_http_vira_ciee_api_error():
    from ciee_monitor import api

    with patch.object(
        api.requests, "get", side_effect=requests.exceptions.ConnectionError("fail")
    ):
        with pytest.raises(api.CieeApiError):
            api.fetch_vagas()


def test_fetch_vagas_timeout_vira_ciee_api_error():
    from ciee_monitor import api

    with patch.object(api.requests, "get", side_effect=requests.exceptions.Timeout()):
        with pytest.raises(api.CieeApiError):
            api.fetch_vagas()


def test_fetch_vagas_status_invalido_vira_ciee_api_error():
    from ciee_monitor import api

    bad = _fake_response({"content": []}, status_code=500)
    bad.raise_for_status.side_effect = requests.exceptions.HTTPError("500")
    with patch.object(api.requests, "get", return_value=bad):
        with pytest.raises(api.CieeApiError):
            api.fetch_vagas()


def test_fetch_vagas_json_invalido_vira_ciee_api_error():
    from ciee_monitor import api

    bad = MagicMock()
    bad.status_code = 200
    bad.raise_for_status.return_value = None
    bad.json.side_effect = ValueError("invalid json")
    with patch.object(api.requests, "get", return_value=bad):
        with pytest.raises(api.CieeApiError):
            api.fetch_vagas()


def test_fetch_vagas_sem_content_vira_ciee_api_error():
    from ciee_monitor import api

    with patch.object(api.requests, "get", return_value=_fake_response({"foo": 1})):
        with pytest.raises(api.CieeApiError):
            api.fetch_vagas()
