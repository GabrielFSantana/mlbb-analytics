"""Schemas de resposta para herois e estatisticas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.models.enums import HeroRole, RankFilter


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


class HeroWithStats(HeroRead):
    latest_stats: HeroStatsRead | None = None


class HeroListResponse(BaseModel):
    total: int = Field(description="Total de herois que atendem ao filtro.")
    items: list[HeroRead]
