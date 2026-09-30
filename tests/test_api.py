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
        # params deve conter os filtros amplos (sem restrição de atuação)
        assert params["tipoVaga"] == "ESTAGIO"
        assert params["nivelEnsino"] == "TE"
        assert params["codigoMunicipio"] == 3552205
        assert params["idAreaProfissional"] == 53
        assert "idAreaAtuacaoEstagio" not in params


def _vaga_pagina(codigo):
    return {"codigoVaga": codigo, "nomeEmpresa": "Empresa X"}


def _fetch_paginado(paginas):
    """Mocka requests.get servindo uma lista de payloads por número da página."""
    from ciee_monitor import api

    chamadas = []

    def fake_get(url, params=None, timeout=None):
        chamadas.append(params["page"])
        return _fake_response(paginas[params["page"]])

    return api, fake_get, chamadas


def test_fetch_todas_vagas_percorre_paginas_ate_total():
    from unittest.mock import patch

    from ciee_monitor import api

    paginas = [
        {"content": [_vaga_pagina(c) for c in range(100)], "totalElements": 250},
        {"content": [_vaga_pagina(c) for c in range(100, 200)], "totalElements": 250},
        {"content": [_vaga_pagina(c) for c in range(200, 250)], "totalElements": 250},
    ]
    _, fake_get, chamadas = _fetch_paginado(paginas)
    with patch.object(api.requests, "get", side_effect=fake_get):
        vagas, total = api.fetch_todas_vagas()
    assert chamadas == [0, 1, 2]
    assert total == 250
    assert [v["codigoVaga"] for v in vagas] == list(range(250))


def test_fetch_todas_vagas_total_cabe_em_uma_pagina():
    from unittest.mock import patch

    from ciee_monitor import api

    paginas = [{"content": [_vaga_pagina(c) for c in range(50)], "totalElements": 50}]
    _, fake_get, chamadas = _fetch_paginado(paginas)
    with patch.object(api.requests, "get", side_effect=fake_get):
        vagas, total = api.fetch_todas_vagas()
    assert chamadas == [0]
    assert total == 50
    assert len(vagas) == 50


def test_fetch_todas_vagas_pagina_vazia_encerra():
    from unittest.mock import patch

    from ciee_monitor import api

    paginas = [
        {"content": [_vaga_pagina(c) for c in range(100)], "totalElements": 200},
        {"content": [], "totalElements": 200},
    ]
    _, fake_get, chamadas = _fetch_paginado(paginas)
    with patch.object(api.requests, "get", side_effect=fake_get):
        vagas, total = api.fetch_todas_vagas()
    assert chamadas == [0, 1]
    assert len(vagas) == 100


def test_fetch_todas_vagas_erro_na_pagina_propaga():
    from unittest.mock import patch

    import pytest
    import requests

    from ciee_monitor import api

    payload0 = {"content": [_vaga_pagina(c) for c in range(100)], "totalElements": 200}

    def fake_get(url, params=None, timeout=None):
        if params["page"] == 0:
            return _fake_response(payload0)
        raise requests.exceptions.ConnectionError("caiu na página 1")

    with patch.object(api.requests, "get", side_effect=fake_get):
        with pytest.raises(api.CieeApiError):
            api.fetch_todas_vagas()


def test_fetch_todas_vagas_respeita_teto_de_paginas():
    from unittest.mock import patch

    from ciee_monitor import api

    def fake_get(url, params=None, timeout=None):
        base = params["page"] * 100
        return _fake_response(
            {"content": [_vaga_pagina(base + c) for c in range(100)], "totalElements": 5000}
        )

    with patch.object(api.requests, "get", side_effect=fake_get) as mock_get:
        vagas, total = api.fetch_todas_vagas(max_pages=3)
    assert mock_get.call_count == 3
    assert total == 5000
    assert len(vagas) == 300


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
