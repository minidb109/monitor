"""Testes para ciee_monitor.display (TDD)."""

from ciee_monitor import display


def _vaga_exemplo():
    return {
        "codigoVaga": 6250388,
        "nomeEmpresa": "ZOIT CONSULTORIA",
        "areaProfissional": "Informática - TÉC.",
        "areaAtuacao": None,
        "bolsaAuxilio": 900,
        "descricao": "Suporte técnico",
        "atividades": ["Atender chamados", "Manutenção"],
        "local": {"cidade": "Rio de Janeiro", "uf": "RJ", "bairro": "Rocha"},
    }


def test_format_vaga_contem_campos_obrigatorios():
    texto = display.format_vaga(_vaga_exemplo(), is_new=True)
    assert "6250388" in texto
    assert "ZOIT CONSULTORIA" in texto
    assert "Informática - TÉC." in texto
    assert "900" in texto
    assert "Rio de Janeiro" in texto
    assert "Suporte técnico" in texto
    assert "Atender chamados" in texto


def test_format_vaga_nova_marca_nova_vaga():
    texto = display.format_vaga(_vaga_exemplo(), is_new=True)
    assert "NOVA VAGA" in texto


def test_format_vaga_ja_vista_nao_marca():
    texto = display.format_vaga(_vaga_exemplo(), is_new=False)
    assert "NOVA VAGA" not in texto


def test_format_vaga_sem_atividades_nao_quebra():
    vaga = _vaga_exemplo()
    vaga["atividades"] = []
    texto = display.format_vaga(vaga, is_new=True)
    assert "6250388" in texto


def test_format_vaga_campos_ausentes_nao_quebra():
    texto = display.format_vaga({}, is_new=True)
    assert isinstance(texto, str)
    assert len(texto) > 0


def test_format_local_none_safe():
    assert isinstance(display.format_local({}), str)
    assert isinstance(display.format_local({"local": None}), str)


def test_format_bolsa_none_safe():
    assert isinstance(display.format_bolsa({}), str)
