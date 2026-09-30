# ciee-monitor

Monitor local (execução única) para a API pública de vagas do CIEE, sem WhatsApp, sem daemon, sem banco, sem frontend.

## Objetivo

Consultar a API pública de vagas do CIEE e detectar novas oportunidades de estágio em Desenvolvimento de Sistemas (Sorocaba), marcando `NOVA VAGA` apenas na primeira vez que cada `codigoVaga` aparece.

## API

`GET https://api.ciee.org.br/vagas/vitrine-vaga/publicadas`

Filtros padrão (v1):

- `tipoVaga=ESTAGIO`
- `nivelEnsino=TE`
- `idAreaProfissional=53` (Informática - TÉC.)
- `idAreaAtuacaoEstagio=473` (Desenvolvimento de Sistemas)
- `codigoMunicipio=3552205` (Sorocaba)
- `page=0`, `size=100`, `sort=codigoVaga,desc`

## Uso

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# execução única (compatível com v1)
.venv/bin/python -m ciee_monitor

# monitoramento contínuo (padrão 300s)
.venv/bin/python -m ciee_monitor --watch
.venv/bin/python -m ciee_monitor --watch --interval 300

# intervalo via ambiente (CLI tem precedência)
CIEE_INTERVAL=120 .venv/bin/python -m ciee_monitor --watch

# arquivo seen alternativo / timeout / paginação
.venv/bin/python -m ciee_monitor --seen-file seen.json --timeout 15 --size 100 --page 0
```

Saída no terminal:

- quantidade de vagas encontradas (`totalElements` + retornadas na página)
- para cada vaga: código, empresa, área, bolsa, localização, descrição, atividades
- vagas com `codigoVaga` ainda não registrado são marcadas com `🆕 NOVA VAGA`

Persistência: `seen.json` (lista de `codigoVaga` já vistos, como strings). Na segunda execução com os mesmos dados, nada aparece como novo.

## Estrutura

- `ciee_monitor/api.py` — `fetch_vagas()` + `CieeApiError` (rede, timeout, HTTP, JSON)
- `ciee_monitor/storage.py` — `load_seen()`, `save_seen()`, `find_new_vagas()`, `mark_as_seen()`
- `ciee_monitor/display.py` — `format_vaga()`, `format_bolsa()`, `format_local()`
- `ciee_monitor/__main__.py` — `run_once()` (execução única) + CLI (`--watch`, `--interval`, `$CIEE_INTERVAL`)
- `ciee_monitor/watch.py` — `run_forever()` (loop com `sleep`, erro não encerra, `Ctrl+C` limpo)
- `tests/` — testes com mocks (API real hoje retorna 0 vagas para o filtro completo)

## Testes

```bash
.venv/bin/python -m pytest tests/ -v
```

## Limites da v1 (por decisão)

- Sem loop infinito, daemon, cron ou notificações
- Sem banco de dados (só `seen.json`)
- Sem frontend
- Sem WhatsApp / WhatsApp Web / scraping / automação de conta
