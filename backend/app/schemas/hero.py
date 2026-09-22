"""Schemas de resposta para herois e estatisticas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.models.enums import HeroRole, Lane, RankFilter, RelationType, Tier


class HeroRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    role: HeroRole
    image_url: str | None = None


class HeroStatsRead(BaseModel):
    """Uma leitura de estatisticas.

    As taxas sao devolvidas como fracao (0.0-1.0); os campos `*_pct` existem
    para consumo direto em UI sem risco de multiplicar duas vezes por 100.
    """

    model_config = ConfigDict(from_attributes=True)

    win_rate: float
    pick_rate: float
    ban_rate: float
    matches: int | None = None
    rank_filter: RankFilter
    patch: str
    collected_at: datetime
    source: str

    @computed_field  # type: ignore[prop-decorator]
    @property
    def win_rate_pct(self) -> float:
        return round(self.win_rate * 100, 2)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def pick_rate_pct(self) -> float:
        return round(self.pick_rate * 100, 2)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def ban_rate_pct(self) -> float:
        return round(self.ban_rate * 100, 2)


class HeroLanePosition(BaseModel):
    """Onde o heroi joga e quao forte esta naquela lane."""

    lane: Lane
    tier: Tier
    score: float
    score_delta: float | None = None


class HeroRelationRead(BaseModel):
    """Um heroi relacionado, com o tipo da relacao."""

    relation_type: RelationType
    hero: HeroRead


class HeroWithStats(HeroRead):
    latest_stats: HeroStatsRead | None = None
    lanes: list[HeroLanePosition] = Field(
        default_factory=list, description="Posicao no meta por lane, na coleta mais recente."
    )
    patch: str | None = None
    source: str | None = None
    is_mock: bool = False


class HeroCounters(BaseModel):
    """Contra quem o heroi vai bem, mal, e com quem combina."""

    hero: HeroRead
    strong_against: list[HeroRead] = Field(default_factory=list)
    weak_against: list[HeroRead] = Field(default_factory=list)
    good_with: list[HeroRead] = Field(default_factory=list)
    source: str | None = None
    is_mock: bool = False


class HeroListResponse(BaseModel):
    total: int = Field(description="Total de herois que atendem ao filtro.")
    items: list[HeroRead]
