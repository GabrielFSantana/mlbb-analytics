"""Delimitacao da semana usada no ranking.

A semana e ISO (segunda a domingo) e fechada em UTC. Fixar isso num lugar
so evita que o job, o servico e a mensagem discordem sobre "que semana e
essa" - divergencia que produziria ranking duplicado ou nenhum.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta


def inicio_da_semana(momento: datetime) -> datetime:
    """Segunda-feira 00:00 UTC da semana de `momento`."""
    referencia = momento.astimezone(UTC)
    segunda = referencia - timedelta(days=referencia.weekday())
    return segunda.replace(hour=0, minute=0, second=0, microsecond=0)


def semana_anterior(momento: datetime) -> tuple[datetime, datetime]:
    """Intervalo [inicio, fim) da semana ja encerrada.

    Rodando na segunda, devolve a semana que acabou de fechar - que e a que
    tem dado completo para ranquear.
    """
    inicio_atual = inicio_da_semana(momento)
    return inicio_atual - timedelta(days=7), inicio_atual


def rotulo_iso(inicio: datetime) -> str:
    """Identificador estavel da semana, ex.: "2026-W38"."""
    ano, semana, _ = inicio.isocalendar()
    return f"{ano}-W{semana:02d}"


def periodo_legivel(inicio: datetime, fim: datetime) -> tuple[date, date]:
    """Datas de inicio e fim (inclusivo) para exibicao."""
    return inicio.date(), (fim - timedelta(days=1)).date()
