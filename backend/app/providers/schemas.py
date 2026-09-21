"""DTOs trocados entre os providers e o resto da aplicacao.

Sao deliberadamente separados dos modelos ORM e dos schemas da API: uma
fonte de dados nova nao deve conseguir vazar o formato dela para dentro do
dominio.

Os heroi sao identificados por `hero_slug` (e nao por id externo) porque
cada fonte usa uma numeracao propria; o slug e o unico identificador
estavel entre elas.
"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import HeroRole, Lane, RankFilter, Tier


class ProviderDTO(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class HeroData(ProviderDTO):
    name: str
    slug: str
    role: HeroRole
    image_url: str | None = None
    external_id: str | None = Field(
        default=None, description="Id do heroi na fonte de origem, quando existir."
    )


class HeroStatsData(ProviderDTO):
    hero_slug: str
    win_rate: float = Field(ge=0.0, le=1.0, description="Fracao, nao percentual.")
    pick_rate: float = Field(ge=0.0, le=1.0)
    ban_rate: float = Field(ge=0.0, le=1.0)
    matches: int | None = Field(default=None, ge=0)
    rank_filter: RankFilter = RankFilter.ALL
    patch: str
    collected_at: datetime


class MetaEntryData(ProviderDTO):
    hero_slug: str
    lane: Lane
    tier: Tier
    score: float = Field(ge=0.0, le=100.0)
    patch: str
    collected_at: datetime


class PatchData(ProviderDTO):
    version: str
    released_at: date | None = None
    notes_url: str | None = None
    summary: str | None = None
    is_current: bool = False


class PlayerData(ProviderDTO):
    """Placeholder para a Fase 4 (Player Tracking).

    Os campos concretos so serao definidos quando houver uma fonte real; por
    isso o payload bruto e mantido em `raw` em vez de ser adivinhado aqui.
    """

    player_id: str
    server_id: str
    raw: dict[str, object] = Field(default_factory=dict)


class MatchData(ProviderDTO):
    """Placeholder para a Fase 4 (Match History). Ver `PlayerData`."""

    match_id: str
    player_id: str
    raw: dict[str, object] = Field(default_factory=dict)
