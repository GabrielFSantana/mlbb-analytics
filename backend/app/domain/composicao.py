"""Leitura de uma composicao a partir do efeito medido de cada dupla.

O QUE E O NUMERO
----------------
A fonte publica, para cada par de herois do mesmo time, um
`increase_win_rate`: quanto a taxa de vitoria se desloca quando os dois
aparecem juntos. Conferimos que a matriz e **simetrica** - em 56 pares
medidos nos dois sentidos, A->B e B->A deram exatamente o mesmo valor. Logo
o numero e o efeito DA DUPLA, e nao "o quanto B ajuda A". A apresentacao
precisa falar de dupla, nunca de um heroi ajudando o outro.

PISO DE RUIDO
-------------
Medido em 22/09/2026 sobre 1056 pares reais, de 8 herois sorteados. O
|delta| se distribui assim:

    p10 0,11pp | p25 0,28pp | p50 0,63pp | p75 1,33pp | p90 2,80pp | max 9,16pp

Metade dos pares fica abaixo de 0,63pp. Chamar isso de sinergia seria dar
nome a ruido, ainda mais porque a fonte nao publica o tamanho da amostra
de cada par. Por isso so afirmamos algo a partir de `LIMIAR_RELEVANTE`.

O QUE ESTE MODULO NAO FAZ
-------------------------
Nao soma os efeitos das duplas para produzir "a nota do time". Efeito de
par nao e aditivo, e a soma pareceria uma previsao de vitoria que ninguem
mediu. Contamos quantas duplas ajudam, quantas atrapalham, e mostramos as
mais fortes de cada lado - isso o dado sustenta.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

#: Abaixo disso nao afirmamos nada: e a metade inferior da distribuicao.
LIMIAR_RELEVANTE = 0.010

#: Aproximadamente o p90 do |delta|. Merece destaque na leitura.
LIMIAR_FORTE = 0.025

#: Quantos pares mostrar de cada lado quando a lista e longa.
TOP_POR_LADO = 5


class ForcaDaDupla(StrEnum):
    """Como ler o efeito de uma dupla."""

    FORTE = "forte"
    FAVORAVEL = "favoravel"
    NEUTRA = "neutra"
    DESFAVORAVEL = "desfavoravel"
    MUITO_RUIM = "muito_ruim"


def classificar(delta: float) -> ForcaDaDupla:
    """Traduz o deslocamento medido em uma leitura.

    Repare que `NEUTRA` cobre os dois lados do zero: um delta de -0,4pp nao
    e "ruim", e indistinguivel de nada.
    """
    if delta >= LIMIAR_FORTE:
        return ForcaDaDupla.FORTE
    if delta >= LIMIAR_RELEVANTE:
        return ForcaDaDupla.FAVORAVEL
    if delta <= -LIMIAR_FORTE:
        return ForcaDaDupla.MUITO_RUIM
    if delta <= -LIMIAR_RELEVANTE:
        return ForcaDaDupla.DESFAVORAVEL
    return ForcaDaDupla.NEUTRA


@dataclass(frozen=True)
class Dupla:
    """Um par de herois e o deslocamento medido para a dupla."""

    a: str
    b: str
    delta: float

    @property
    def forca(self) -> ForcaDaDupla:
        return classificar(self.delta)

    @property
    def relevante(self) -> bool:
        return self.forca is not ForcaDaDupla.NEUTRA


@dataclass(frozen=True)
class LeituraDaComposicao:
    """O que da para afirmar sobre um time, sem extrapolar.

    Nao ha nota geral de proposito: ver o docstring do modulo.
    """

    duplas: tuple[Dupla, ...]
    favoraveis: int
    desfavoraveis: int
    neutras: int

    @property
    def melhor(self) -> Dupla | None:
        relevantes = [d for d in self.duplas if d.delta >= LIMIAR_RELEVANTE]
        return max(relevantes, key=lambda d: d.delta) if relevantes else None

    @property
    def pior(self) -> Dupla | None:
        relevantes = [d for d in self.duplas if d.delta <= -LIMIAR_RELEVANTE]
        return min(relevantes, key=lambda d: d.delta) if relevantes else None


def ordenar_por_impacto(duplas: Iterable[Dupla]) -> tuple[Dupla, ...]:
    """Do mais favoravel ao mais desfavoravel.

    Desempate pelos nomes para que a mesma entrada gere sempre o mesmo card.
    """
    return tuple(sorted(duplas, key=lambda d: (-d.delta, d.a, d.b)))


def ler_composicao(duplas: Iterable[Dupla]) -> LeituraDaComposicao:
    """Conta os efeitos e organiza os pares de um time."""
    ordenadas = ordenar_por_impacto(duplas)
    favoraveis = sum(1 for d in ordenadas if d.delta >= LIMIAR_RELEVANTE)
    desfavoraveis = sum(1 for d in ordenadas if d.delta <= -LIMIAR_RELEVANTE)
    return LeituraDaComposicao(
        duplas=ordenadas,
        favoraveis=favoraveis,
        desfavoraveis=desfavoraveis,
        neutras=len(ordenadas) - favoraveis - desfavoraveis,
    )


def pares_necessarios(quantidade: int) -> int:
    """Quantos herois precisamos consultar para cobrir todos os pares.

    Como a matriz e simetrica, a lista do ultimo heroi so repete pares que
    os anteriores ja trouxeram. Numa fonte comunitaria sem rate limit
    documentado, economizar uma requisicao por consulta importa.
    """
    return max(0, quantidade - 1)
