"""Schemas de resposta para o meta."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import Lane, Tier
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
    """Tier list de uma ou de todas as lanes."""

    lane: Lane | None = None
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
