"""Formatação das vagas para exibição no terminal."""

from __future__ import annotations

from typing import Any


def format_bolsa(vaga: dict[str, Any]) -> str:
    bolsa = vaga.get("bolsaAuxilio")
    if isinstance(bolsa, (int, float)):
        tipo = vaga.get("tipoAuxilioBolsa") or "Mensal"
        return f"R$ {bolsa:.2f} ({tipo})"
    # Faixas (quando existirem)
    de_ = vaga.get("bolsaAuxilioDe")
    ate = vaga.get("bolsaAuxilioAte")
    if de_ is not None or ate is not None:
        return f"De {de_} até {ate}"
    salario = vaga.get("salario")
    if isinstance(salario, (int, float)):
        return f"R$ {salario:.2f} (salário)"
    return "não informada"


def format_local(vaga: dict[str, Any]) -> str:
    local = vaga.get("local")
    if not isinstance(local, dict):
        return "não informado"
    cidade = local.get("cidade") or "?"
    uf = local.get("uf") or "?"
    bairro = local.get("bairro")
    base = f"{cidade}/{uf}"
    if bairro:
        base += f" - {bairro}"
    return base


def format_area(vaga: dict[str, Any]) -> str:
    prof = vaga.get("areaProfissional") or "?"
    atuacao = vaga.get("areaAtuacao")
    if atuacao:
        return f"{prof} | {atuacao}"
    return str(prof)


def format_horario(vaga: dict[str, Any]) -> str:
    """Horário do estágio como '09:00 às 16:00' (corta segundos)."""
    entrada = vaga.get("horarioEntrada")
    saida = vaga.get("horarioSaida")

    def hhmm(value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        parts = text.split(":")
        if len(parts) < 2:
            return None
        if not parts[0].isdigit() or not parts[1].isdigit():
            return None
        return f"{int(parts[0]):02d}:{int(parts[1]):02d}"

    ini, fim = hhmm(entrada), hhmm(saida)
    if ini and fim:
        return f"{ini} às {fim}"
    if ini:
        return f"a partir das {ini}"
    if fim:
        return f"até às {fim}"
    return "não informado"


VITRINE_URL_BASE = "https://ciee.app/login"


def vaga_url(codigo: Any) -> str | None:
    """Link direto para a vitrine da vaga.

    Padrão observado: só muda o codigoVagaPortal, ex.
    https://ciee.app/login?codigoVagaPortal=6253523&acesso=VITRINE_VAGA&tag=S_QUERO
    Retorna None quando não há código válido.
    """
    if codigo is None:
        return None
    text = str(codigo).strip()
    if text == "" or text == "?":
        return None
    # Aceita int ou str numérica; rejeita dict/list/objetos inválidos.
    if not text.isdigit():
        return None
    return (
        f"{VITRINE_URL_BASE}?codigoVagaPortal={text}"
        "&acesso=VITRINE_VAGA&tag=S_QUERO"
    )


def format_vaga(vaga: dict[str, Any], is_new: bool) -> str:
    codigo = vaga.get("codigoVaga", "?")
    empresa = vaga.get("nomeEmpresa", "?")
    area = format_area(vaga)
    bolsa = format_bolsa(vaga)
    local = format_local(vaga)
    horario = format_horario(vaga)
    descricao = vaga.get("descricao") or "sem descrição"
    atividades = vaga.get("atividades") or []
    link = vaga_url(vaga.get("codigoVaga"))

    lines = []
    if is_new:
        lines.append("🆕 NOVA VAGA")
    lines.append(f"Código: {codigo}")
    lines.append(f"Empresa: {empresa}")
    lines.append(f"Área: {area}")
    lines.append(f"Bolsa: {bolsa}")
    lines.append(f"Localização: {local}")
    lines.append(f"Horário: {horario}")
    if link is not None:
        lines.append(f"Link: {link}")
    lines.append(f"Descrição: {descricao}")
    if atividades:
        lines.append("Atividades:")
        for a in atividades:
            lines.append(f"  - {a}")
    else:
        lines.append("Atividades: não informadas")
    return "\n".join(lines)
