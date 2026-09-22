"""Schemas de resposta para o meta."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import Lane, RankFilter, Tier
from app.schemas.hero import HeroRead


class MetaEntry(BaseModel):
    """Posicao de um heroi no meta, com a variacao desde a coleta anterior."""

    hero: HeroRead
    lane: Lane
    tier: Tier
    score: float
    score_delta: float | None = Field(
        default=None,
        description="Variacao do score desde a coleta anterior. None se nao ha historico.",
    )
    previous_tier: Tier | None = None
    win_rate: float | None = Field(default=None, description="Fracao (0.0-1.0).")
    win_rate_delta: float | None = Field(
        default=None, description="Variacao da win rate em pontos fracionarios."
    )


class MetaResponse(BaseModel):
    """Tier list de uma ou de todas as lanes, numa faixa de ranque."""

    lane: Lane | None = None
    rank_filter: RankFilter = RankFilter.ALL
    patch: str | None = None
    collected_at: datetime | None = None
    previous_collected_at: datetime | None = None
    source: str
    is_mock: bool = Field(
        description="True quando os dados sao de demonstracao e NAO refletem o jogo real."
    )
    entries: list[MetaEntry]
    rising: list[MetaEntry] = Field(
        default_factory=list, description="Maiores altas de score desde a coleta anterior."
    )
    falling: list[MetaEntry] = Field(
        default_factory=list, description="Maiores quedas de score desde a coleta anterior."
    )


class MetaUpdate(BaseModel):
    """O que mudou entre a coleta atual e a anterior.

    E o payload que o bot transforma na mensagem do canal de atualizacoes.
    """

    collected_at: datetime
    previous_collected_at: datetime
    patch: str | None = None
    source: str
    is_mock: bool
    rising: list[MetaEntry] = Field(default_factory=list, description="Maiores altas de score.")
    falling: list[MetaEntry] = Field(default_factory=list, description="Maiores quedas de score.")
    promoted: list[MetaEntry] = Field(
        default_factory=list, description="Herois que subiram de tier."
    )
    demoted: list[MetaEntry] = Field(
        default_factory=list, description="Herois que cairam de tier."
    )
    biggest_win_rate_gain: list[MetaEntry] = Field(
        default_factory=list, description="Maiores ganhos de win rate."
    )


class MetaAnnouncementAck(BaseModel):
    """Confirmacao de que o bot publicou uma coleta."""

    collected_at: datetime
    source: str
