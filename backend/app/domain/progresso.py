"""Calculo de ritmo e projecao rumo a uma meta de estrelas.

Este modulo e puro: recebe leituras e devolve numeros. Sem banco, sem rede.

Sobre a projecao
----------------
Projetar e arriscado e a gente diz isso na interface. O ritmo de estrelas
nao e linear: perder sobe e desce, e uma sequencia boa de tres dias nao se
repete pelos proximos trinta. A projecao aqui serve como referencia
("nesse ritmo, seria por volta de tal dia"), nao como promessa - e por isso
so aparece quando ha ritmo positivo e historico suficiente.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

#: Minimo de dias entre a primeira e a ultima leitura para projetar. Abaixo
#: disso qualquer variacao vira um ritmo absurdo quando extrapolada.
DIAS_MINIMOS_PARA_PROJETAR = 3

#: Teto da projecao. Alem disso a conta deixa de informar e vira ruido.
DIAS_MAXIMOS_DE_PROJECAO = 365


@dataclass(slots=True, frozen=True)
class Leitura:
    """Uma leitura de estrelas no tempo."""

    stars: int
    reported_at: datetime


@dataclass(slots=True, frozen=True)
class Ritmo:
    """Quanto o jogador avancou e em quanto tempo."""

    estrelas_ganhas: int
    dias: float
    por_dia: float


def calcular_ritmo(leituras: list[Leitura], *, janela_dias: int = 7) -> Ritmo | None:
    """Ritmo dentro da janela recente.

    Usa a leitura mais antiga DENTRO da janela como ponto de partida; se so
    houver uma leitura no periodo, cai para a anterior a ela, para nao
    devolver "sem ritmo" a quem reporta pouco.
    """
    if len(leituras) < 2:
        return None

    ordenadas = sorted(leituras, key=lambda leitura: leitura.reported_at)
    ultima = ordenadas[-1]
    limite = ultima.reported_at - timedelta(days=janela_dias)

    na_janela = [leitura for leitura in ordenadas if leitura.reported_at >= limite]
    primeira = na_janela[0] if len(na_janela) >= 2 else ordenadas[-2]

    dias = (ultima.reported_at - primeira.reported_at).total_seconds() / 86400
    if dias <= 0:
        return None

    ganhas = ultima.stars - primeira.stars
    return Ritmo(estrelas_ganhas=ganhas, dias=round(dias, 2), por_dia=round(ganhas / dias, 2))


def projetar_conclusao(atual: int, meta: int, ritmo: Ritmo | None) -> datetime | None:
    """Quando a meta seria atingida mantendo o ritmo. None se nao da para dizer."""
    if atual >= meta:
        return None
    if ritmo is None or ritmo.por_dia <= 0:
        return None
    if ritmo.dias < DIAS_MINIMOS_PARA_PROJETAR:
        return None

    dias_restantes = (meta - atual) / ritmo.por_dia
    if dias_restantes > DIAS_MAXIMOS_DE_PROJECAO:
        return None
    return datetime.now(UTC) + timedelta(days=dias_restantes)


def percentual(atual: int, meta: int) -> float:
    """Progresso em porcentagem, limitado a 100."""
    if meta <= 0:
        return 0.0
    return round(min(100.0, max(0.0, atual / meta * 100)), 1)
