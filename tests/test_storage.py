"""Testes para ciee_monitor.storage (TDD)."""

from ciee_monitor import storage


def test_load_seen_arquivo_inexistente_retorna_vazio(tmp_path):
    seen = storage.load_seen(tmp_path / "seen.json")
    assert seen == set()


def test_save_e_load_roundtrip(tmp_path):
    path = tmp_path / "seen.json"
    storage.save_seen({123, 456}, path)
    assert storage.load_seen(path) == {"123", "456"} or storage.load_seen(path) == {123, 456}


def test_load_seen_json_corrompido_retorna_vazio(tmp_path):
    path = tmp_path / "seen.json"
    path.write_text("nao é json {{{", encoding="utf-8")
    assert storage.load_seen(path) == set()


def test_find_new_vagas_filtra_ja_vistas():
    vagas = [{"codigoVaga": 1}, {"codigoVaga": 2}, {"codigoVaga": 3}]
    seen = {"1", "2"} if isinstance(storage.load_seen.__annotations__.get("return", ""), str) else {"1", "2"}
    # normaliza: storage trabalha com str(codigoVaga)
    novas = storage.find_new_vagas(vagas, {"1", "2"})
    assert [v["codigoVaga"] for v in novas] == [3]


def test_find_new_vagas_todas_novas_quando_seen_vazio():
    vagas = [{"codigoVaga": 10}, {"codigoVaga": 20}]
    assert len(storage.find_new_vagas(vagas, set())) == 2


def test_find_new_vagas_ignora_vaga_sem_codigo():
    vagas = [{"nomeEmpresa": "sem codigo"}, {"codigoVaga": 99}]
    novas = storage.find_new_vagas(vagas, set())
    assert [v.get("codigoVaga") for v in novas] == [99]
