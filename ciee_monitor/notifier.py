"""Notificação por e-mail de vagas novas (somente stdlib: smtplib/email).

Configuração por variáveis de ambiente (nenhum valor sensível no código):

- CIEE_EMAIL_HOST (obrigatório)
- CIEE_EMAIL_PORT (opcional, padrão 587)
- CIEE_EMAIL_USER (obrigatório)
- CIEE_EMAIL_PASSWORD (obrigatório)
- CIEE_EMAIL_TO (obrigatório, destinatário)

A senha nunca aparece em logs, mensagens de erro ou no e-mail.
"""

from __future__ import annotations

import os
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Any

from .display import format_area, format_bolsa, format_local

DEFAULT_PORT = 587
SMTP_TIMEOUT = 15


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
    codigo = vaga.get("codigoVaga", "?")
    empresa = vaga.get("nomeEmpresa", "?")
    descricao = vaga.get("descricao") or "sem descrição"
    atividades = vaga.get("atividades") or []

    lines = [
        "Nova vaga encontrada no CIEE.",
        "",
        f"Código: {codigo}",
        f"Empresa: {empresa}",
        f"Área: {format_area(vaga)}",
        f"Bolsa: {format_bolsa(vaga)}",
        f"Localização: {format_local(vaga)}",
        "",
        "Descrição:",
        str(descricao),
        "",
    ]
    if atividades:
        lines.append("Atividades:")
        lines.extend(f"  - {a}" for a in atividades)
    else:
        lines.append("Atividades: não informadas")

    msg = EmailMessage()
    msg["Subject"] = f"[CIEE Monitor] Nova vaga de estágio - {codigo}"
    msg["From"] = config.user
    msg["To"] = config.to
    msg.set_content("\n".join(lines))
    return msg


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
