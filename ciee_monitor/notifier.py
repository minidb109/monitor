"""Notificação por e-mail de vagas novas (somente stdlib).

Suporta dois backends:

- Resend via HTTPS (produção no Deplexo, onde SMTP é bloqueado):
  POST https://api.resend.com/emails com `RESEND_API_KEY`.
- SMTP via smtplib (uso local / fallback).

Configuração por variáveis de ambiente (nenhum valor sensível no código):

- RESEND_API_KEY (obrigatório p/ Resend)
- CIEE_EMAIL_FROM (obrigatório p/ Resend, remetente verificado)
- CIEE_EMAIL_TO (obrigatório, destinatário)
- CIEE_EMAIL_HOST (obrigatório p/ SMTP)
- CIEE_EMAIL_PORT (opcional p/ SMTP, padrão 587)
- CIEE_EMAIL_USER (obrigatório p/ SMTP)
- CIEE_EMAIL_PASSWORD (obrigatório p/ SMTP)

A senha/chave nunca aparece em logs, mensagens de erro ou no e-mail.
"""

from __future__ import annotations

import json
import os
import smtplib
import urllib.error
import urllib.request
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Any

from .display import format_area, format_bolsa, format_horario, format_local, vaga_url

DEFAULT_PORT = 587
SMTP_TIMEOUT = 15
RESEND_API_URL = "https://api.resend.com/emails"
RESEND_TIMEOUT = 15


class NotifierError(RuntimeError):
    """Falha ao enviar o e-mail (SMTP, rede, etc). Nunca contém a senha."""


class NotifierConfigError(NotifierError):
    """Configuração de e-mail ausente ou inválida."""


@dataclass(frozen=True)
class EmailConfig:
    host: str
    port: int
    user: str
    password: str
    to: str

    def __repr__(self) -> str:  # pragma: no cover - segurança
        return (
            f"EmailConfig(host={self.host!r}, port={self.port!r}, "
            f"user={self.user!r}, password='***', to={self.to!r})"
        )

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> EmailConfig:
        """Lê a configuração das variáveis de ambiente.

        Raises:
            NotifierConfigError: lista as variáveis ausentes (só nomes,
                nunca valores).
        """
        source = os.environ if env is None else env

        def get(name: str) -> str | None:
            value = source.get(name)
            if value is None or not str(value).strip():
                return None
            return str(value).strip()

        missing = [
            name
            for name in (
                "CIEE_EMAIL_HOST",
                "CIEE_EMAIL_USER",
                "CIEE_EMAIL_PASSWORD",
                "CIEE_EMAIL_TO",
            )
            if get(name) is None
        ]
        if missing:
            raise NotifierConfigError(
                "configuração de e-mail incompleta; "
                f"variáveis ausentes: {', '.join(missing)}"
            )

        raw_port = get("CIEE_EMAIL_PORT")
        try:
            port = int(raw_port) if raw_port is not None else DEFAULT_PORT
        except ValueError as exc:
            raise NotifierConfigError(
                "CIEE_EMAIL_PORT inválida; use um número de porta"
            ) from exc

        return cls(
            host=get("CIEE_EMAIL_HOST") or "",
            port=port,
            user=get("CIEE_EMAIL_USER") or "",
            password=get("CIEE_EMAIL_PASSWORD") or "",
            to=get("CIEE_EMAIL_TO") or "",
        )


def build_message(vaga: dict[str, Any], config: EmailConfig) -> EmailMessage:
    """Monta o e-mail de uma vaga nova (sem enviar)."""
    subject, body = build_subject_and_body(vaga)

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = config.user
    msg["To"] = config.to
    msg.set_content(body)
    return msg


@dataclass(frozen=True)
class ResendConfig:
    api_key: str
    from_addr: str
    to: str

    def __repr__(self) -> str:  # pragma: no cover - segurança
        return (
            f"ResendConfig(api_key='***', "
            f"from_addr={self.from_addr!r}, to={self.to!r})"
        )

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> ResendConfig:
        """Lê a configuração Resend das variáveis de ambiente.

        Raises:
            NotifierConfigError: lista as variáveis ausentes (só nomes,
                nunca valores).
        """
        source = os.environ if env is None else env

        def get(name: str) -> str | None:
            value = source.get(name)
            if value is None or not str(value).strip():
                return None
            return str(value).strip()

        missing = [
            name
            for name in (
                "RESEND_API_KEY",
                "CIEE_EMAIL_FROM",
                "CIEE_EMAIL_TO",
            )
            if get(name) is None
        ]
        if missing:
            raise NotifierConfigError(
                "configuração Resend incompleta; "
                f"variáveis ausentes: {', '.join(missing)}"
            )
        return cls(
            api_key=get("RESEND_API_KEY") or "",
            from_addr=get("CIEE_EMAIL_FROM") or "",
            to=get("CIEE_EMAIL_TO") or "",
        )


def build_subject_and_body(vaga: dict[str, Any]) -> tuple[str, str]:
    """Assunto + corpo texto compartilhados entre SMTP e Resend."""
    codigo = vaga.get("codigoVaga", "?")
    empresa = vaga.get("nomeEmpresa", "?")
    descricao = vaga.get("descricao") or "sem descrição"
    atividades = vaga.get("atividades") or []
    link = vaga_url(vaga.get("codigoVaga"))

    lines = [
        "Nova vaga encontrada no CIEE.",
        "",
        f"Código: {codigo}",
        f"Empresa: {empresa}",
        f"Área: {format_area(vaga)}",
        f"Bolsa: {format_bolsa(vaga)}",
        f"Localização: {format_local(vaga)}",
        f"Horário: {format_horario(vaga)}",
    ]
    if link is not None:
        lines.append(f"Link: {link}")
    lines.extend(
        [
            "",
            "Descrição:",
            str(descricao),
            "",
        ]
    )
    if atividades:
        lines.append("Atividades:")
        lines.extend(f"  - {a}" for a in atividades)
    else:
        lines.append("Atividades: não informadas")

    subject = f"[CIEE Monitor] Nova vaga de estágio - {codigo}"
    return subject, "\n".join(lines)


def build_resend_payload(vaga: dict[str, Any], config: ResendConfig) -> dict[str, Any]:
    """Monta o payload JSON para POST https://api.resend.com/emails."""
    import html as _html

    subject, body = build_subject_and_body(vaga)
    link = vaga_url(vaga.get("codigoVaga"))
    # HTML com link único: remove a linha "Link: <url>" do corpo (o text
    # mantém) e deixa só o CTA clicável no final.
    html_source = "\n".join(
        line for line in body.split("\n") if not line.startswith("Link: ")
    )
    escaped_body = _html.escape(html_source).replace("\n", "<br>")
    if link is not None:
        escaped_link = _html.escape(link, quote=True)
        html_body = (
            f"{escaped_body}<br><br>"
            f'<a href="{escaped_link}">Ver vaga no CIEE</a>'
        )
    else:
        html_body = escaped_body
    return {
        "from": config.from_addr,
        "to": [config.to],
        "subject": subject,
        "text": body,
        "html": html_body,
    }


def notify_vaga_resend(vaga: dict[str, Any], config: ResendConfig | None = None) -> None:
    """Envia um e-mail via Resend HTTPS API.

    Raises:
        NotifierConfigError: configuração ausente/inválida.
        NotifierError: falha de HTTP/rede (sem expor a API key).
    """
    cfg = config if config is not None else ResendConfig.from_env()
    payload = build_resend_payload(vaga, cfg)
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        RESEND_API_URL,
        data=data,
        headers={
            "Authorization": f"Bearer {cfg.api_key}",
            "Content-Type": "application/json",
            # Cloudflare na frente da api.resend.com bloqueia o default
            # Python-urllib/3.x com 403 error code 1010. UA explícito resolve.
            "User-Agent": "ciee-monitor/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=RESEND_TIMEOUT) as resp:
            status = getattr(resp, "status", 200)
            if status not in (200, 201, 202):
                raise NotifierError(
                    f"falha ao enviar e-mail da vaga {vaga.get('codigoVaga', '?')} "
                    f"via Resend: HTTP {status}"
                )
    except urllib.error.HTTPError as exc:
        codigo = vaga.get("codigoVaga", "?")
        try:
            raw_body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            raw_body = ""
        detail = raw_body.strip()[:500] if raw_body.strip() else exc.reason
        raise NotifierError(
            f"falha ao enviar e-mail da vaga {codigo} via Resend "
            f"(from={cfg.from_addr} to={cfg.to}): "
            f"HTTP {exc.code} {detail}"
        ) from exc
    except (urllib.error.URLError, OSError) as exc:
        codigo = vaga.get("codigoVaga", "?")
        raise NotifierError(
            f"falha ao enviar e-mail da vaga {codigo} via Resend: {exc}"
        ) from exc


def notify_vaga(vaga: dict[str, Any], config: EmailConfig | None = None) -> None:
    """Envia um e-mail para uma vaga nova.

    Args:
        vaga: dicionário da vaga (como retornado pela API).
        config: configuração SMTP; quando None, lida do ambiente.

    Raises:
        NotifierConfigError: configuração ausente/inválida.
        NotifierError: falha de SMTP/rede (sem expor a senha).
    """
    cfg = config if config is not None else EmailConfig.from_env()
    msg = build_message(vaga, cfg)
    try:
        with smtplib.SMTP(cfg.host, cfg.port, timeout=SMTP_TIMEOUT) as smtp:
            smtp.starttls()
            smtp.login(cfg.user, cfg.password)
            smtp.send_message(msg)
    except (smtplib.SMTPException, OSError) as exc:
        codigo = vaga.get("codigoVaga", "?")
        raise NotifierError(
            f"falha ao enviar e-mail da vaga {codigo} via {cfg.host}:{cfg.port}: {exc}"
        ) from exc
