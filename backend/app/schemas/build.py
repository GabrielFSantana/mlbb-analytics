"""Schemas de builds."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, computed_field

from app.models.enums import Lane
from app.schemas.hero import HeroRead


class BuildItemRead(BaseModel):
    name: str
    image_url: str | None = None
    position: int


class HeroBuildRead(BaseModel):
    """Uma variante de build.

    `items` traz apenas os itens CENTRAIS publicados pela fonte, nao uma
    build fechada de seis.
    """

    variant: int
    win_rate: float = Field(description="Fracao (0.0-1.0).")
    pick_rate: float
    emblem: str | None = None
    battle_spell: str | None = None
    items: list[BuildItemRead] = Field(default_factory=list)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def win_rate_pct(self) -> float:
        return round(self.win_rate * 100, 2)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def pick_rate_pct(self) -> float:
        return round(self.pick_rate * 100, 2)


class HeroBuildsResponse(BaseModel):
    hero: HeroRead
    lane: Lane | None = None
    builds: list[HeroBuildRead] = Field(default_factory=list)
    collected_at: datetime | None = None
    source: str
    is_mock: bool = False
    source_available: bool = Field(
        default=True,
        description=(
            "False quando precisavamos consultar a fonte e ela falhou. Sem isso, "
            "uma lista vazia por indisponibilidade seria indistinguivel de uma "
            "lista vazia por nao existir build - e o usuario leria a mensagem errada."
        ),
    )
