# ciee-monitor

Monitor local (execução única ou contínua com `--watch`) para a API pública de vagas do CIEE, com notificações por e-mail via SMTP. Sem banco de dados, sem frontend, sem WhatsApp, sem daemon/systemd.

## Objetivo

Consultar a API pública de vagas do CIEE e detectar novas oportunidades de estágio em desenvolvimento de software (Sorocaba), marcando `NOVA VAGA` apenas na primeira vez que cada `codigoVaga` relevante aparece.

## API

`GET https://api.ciee.org.br/vagas/vitrine-vaga/publicadas`

Filtros padrão (busca ampla em informática):

- `tipoVaga=ESTAGIO`
- `nivelEnsino=TE`
- `idAreaProfissional=53` (Informática - TÉC.)
- `codigoMunicipio=3552205` (Sorocaba)
- `page=0`, `size=100`, `sort=codigoVaga,desc`

Sem filtro de área de atuação: a relevância é decidida pelo filtro interno de palavras-chave (seção abaixo), então vagas de software chegam mesmo classificadas em outra categoria pelo CIEE.

A coleta percorre as páginas até `totalElements` (respeitando `size`, teto de 10 páginas por ciclo, parando em página vazia). Erro em qualquer página aborta o ciclo como erro de API, sem persistir.

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
- vagas com `codigoVaga` ainda não registrado e relacionadas a software são marcadas com `🆕 NOVA VAGA`

## Filtro por palavras-chave

A API é consultada com os filtros de informática/tecnologia acima, e cada vaga é classificada pelo conteúdo (título, área, descrição e atividades, sem acentos e sem case). Só vagas relacionadas a software geram `NOVA VAGA` e e-mail.

```bash
# lista padrão (ciee_monitor/keywords.py): desenvolvimento, software, programação,
# backend, frontend, java, python, javascript, web, mobile, dados, cloud, qa, ...

# personalizar (separado por vírgula; sem definir, usa o padrão)
CIEE_KEYWORDS=desenvolvimento,software,programação,java,python,backend,frontend .venv/bin/python -m ciee_monitor --watch
```

Persistência: `seen.json` (lista de `codigoVaga` já vistos, como strings). Na segunda execução com os mesmos dados, nada aparece como novo.

O caminho do arquivo pode ser configurado via `CIEE_SEEN_FILE` (precedência: `--seen-file` > `$CIEE_SEEN_FILE` > automático). Sem configurar nada, o app usa `/data/seen.json` quando o diretório `/data` existe (produção no Deplexo, sobrevive a redeploys) e `seen.json` caso contrário (uso local).

```bash
# local (usa seen.json, sem configurar nada)
.venv/bin/python -m ciee_monitor --watch

# produção no Deplexo (usa /data/seen.json automaticamente, sem variável)
python -m ciee_monitor --watch

# forçar um caminho específico (vale em qualquer ambiente)
CIEE_SEEN_FILE=/data/seen.json .venv/bin/python -m ciee_monitor --watch
```

## Notificações por e-mail

Quando uma vaga **nova** é detectada, o monitor envia um e-mail via Resend HTTPS API (produção) ou SMTP (fallback local), só stdlib, sem dependências. Assunto: `[CIEE Monitor] Nova vaga de estágio - <codigo>`.

Status: SMTP real validado localmente; Resend validado via mocks + HTTPS (produção no Deplexo, onde `smtp.gmail.com:587` retorna `[Errno 101] Network is unreachable` mas `https://api.ciee.org.br` e `https://api.resend.com` funcionam).

Configuração produção via `.env` (ignorado pelo git; veja `.env.example` — nunca commite credenciais reais):

```bash
# Resend (recomendado no Deplexo — HTTPS 443 liberado, SMTP 587 bloqueado)
export RESEND_API_KEY='re_sua-chave'
export CIEE_EMAIL_FROM='monitor@seu-dominio-verificado.com'
export CIEE_EMAIL_TO=destino@example.com

# Fallback SMTP local (usado só quando RESEND_API_KEY ausente)
# export CIEE_EMAIL_HOST=smtp.seu-provedor.com
# export CIEE_EMAIL_PORT=587
# export CIEE_EMAIL_USER=voce@example.com
# export CIEE_EMAIL_PASSWORD='sua-senha-ou-app-password'
# export CIEE_EMAIL_TO=destino@example.com

.venv/bin/python -m ciee_monitor
```

Semântica de falha (sem overengineering, sem perda silenciosa):

- E-mail é enviado **somente** para vagas classificadas como novas; vagas já vistas nunca disparam.
- A notificação acontece **antes** de persistir; se o envio falhar, a vaga **não** é marcada como vista e será retentada no próximo ciclo. `seen.json` nunca é corrompido. Vagas 6253523/6253544 pendentes serão notificadas uma vez no primeiro ciclo após configurar Resend.
- Retry com throttle: 1ª falha loga erro cheio, repetidas logan `Retry throttled ... tentativa N`, a cada 6 loga cheio de novo, após 12 emite `ALERTA ... verifique RESEND_API_KEY / api.resend.com:443`. Evita spam de `Novas: 2` a cada 5min.
- Falha de e-mail **não** derruba o `--watch` e **não** é confundida com falha de API (`run_once` segue retornando 1 só para API).
- Sem configuração (nem Resend nem SMTP): erro compreensível em stderr (sem traceback), execução continua com exit 0 e a semântica de `seen.json` permanece a atual.

## Estrutura

- `ciee_monitor/api.py` — `fetch_vagas()` (uma página) + `fetch_todas_vagas()` (paginação até `totalElements`, teto de 10) + `CieeApiError`
- `ciee_monitor/storage.py` — `load_seen()`, `save_seen()`, `find_new_vagas()`, `mark_as_seen()`
- `ciee_monitor/display.py` — `format_vaga()`, `format_bolsa()`, `format_local()`
- `ciee_monitor/__main__.py` — `run_once()` + CLI + hook de notificação (Resend preferido, SMTP fallback, throttle via `_notify_failure_counts`)
- `ciee_monitor/keywords.py` — `DEFAULT_KEYWORDS`, `resolve_keywords()` (`$CIEE_KEYWORDS`), `vaga_matches()`
- `ciee_monitor/notifier.py` — `ResendConfig` + `notify_vaga_resend()` (HTTPS `api.resend.com`, urllib stdlib) + `EmailConfig` + `notify_vaga()` (SMTP fallback)
- `ciee_monitor/watch.py` — `run_forever()` (loop com `sleep`, erro não encerra, `Ctrl+C` limpo)
- `tests/` — testes com mocks (Resend/SMTP sempre mockados, nenhum e-mail real; `test_resend.py` cobre 6253523 real)

## Testes

```bash
.venv/bin/python -m pytest tests/ -v
```

## Limites / fora de escopo (por decisão)

- Sem daemon/systemd, cron ou hospedagem (etapa posterior)
- Sem banco de dados (só `seen.json`)
- Sem frontend
- Sem WhatsApp / WhatsApp Web / scraping / automação de conta
