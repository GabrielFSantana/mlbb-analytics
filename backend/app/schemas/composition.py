"""Schemas da leitura de composicao."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, computed_field

from app.domain.composicao import ForcaDaDupla
from app.schemas.hero import HeroRead


class PairRead(BaseModel):
    """Uma dupla e o deslocamento medido para ela.

    ATENCAO ao apresentar: o numero e o efeito DA DUPLA. A matriz da fonte
    e simetrica, entao dizer "b ajuda a" inverteria o sentido do dado - os
    dois herois participam igualmente.
    """

    a: HeroRead
    b: HeroRead
    win_rate_delta: float = Field(
        description="Fracao com sinal. +0.0134 = a dupla desloca 1,34 ponto percentual."
    )
    strength: ForcaDaDupla
    partner_win_rate: float | None = Field(
        default=None, description="Taxa de vitoria geral do segundo heroi, como contexto."
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def delta_pp(self) -> float:
        """O mesmo numero em pontos percentuais, que e como se le no card."""
        return round(self.win_rate_delta * 100, 2)


class CompositionResponse(BaseModel):
    """O que da para afirmar sobre um time, sem extrapolar.

    NAO existe nota geral de proposito. Efeito de dupla nao e aditivo:
    somar os deltas produziria um numero com cara de previsao de vitoria
    que ninguem mediu. Ver `app.domain.composicao`.
    """

    heroes: list[HeroRead] = Field(default_factory=list)
    pairs: list[PairRead] = Field(default_factory=list)
    favorable: int = 0
    unfavorable: int = 0
    neutral: int = Field(
        default=0,
        description=(
            "Duplas cujo efeito e pequeno demais para afirmar qualquer coisa. "
            "Metade dos pares da fonte cai aqui."
        ),
    )
    unknown_terms: list[str] = Field(
        default_factory=list,
        description="Nomes digitados que nao casaram com heroi nenhum.",
    )
    collected_at: datetime | None = None
    source: str
    is_mock: bool = False
    source_available: bool = Field(
        default=True,
        description=(
            "False quando precisavamos consultar a fonte e ela falhou. Sem isso, "
            "uma lista vazia por indisponibilidade seria indistinguivel de uma "
            "composicao sem nenhuma dupla relevante."
        ),
    )
