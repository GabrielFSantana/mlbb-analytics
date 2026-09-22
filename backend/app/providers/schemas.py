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

from app.models.enums import HeroRole, Lane, RankFilter, RelationType, Tier


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
    rank_filter: RankFilter = RankFilter.ALL
    tier: Tier
    score: float = Field(ge=0.0, le=100.0)
    patch: str
    collected_at: datetime


class HeroRelationData(ProviderDTO):
    """Uma relacao direcionada entre dois herois."""

    hero_slug: str
    related_hero_slug: str
    relation_type: RelationType


class ItemData(ProviderDTO):
    """Um item do catalogo."""

    external_id: int
    name: str
    image_url: str | None = None


class HeroBuildData(ProviderDTO):
    """Uma build recomendada para um heroi numa lane.

    `item_ids` traz apenas os itens CENTRAIS que a fonte publica (hoje tres),
    nao uma build fechada. A ordem e a da fonte.
    """

    hero_slug: str
    lane: Lane
    variant: int = Field(ge=0, description="Posicao da variante na resposta da fonte.")
    win_rate: float = Field(ge=0.0, le=1.0)
    pick_rate: float = Field(ge=0.0, le=1.0)
    item_ids: tuple[int, ...] = ()
    emblem: str | None = None
    battle_spell: str | None = None
    talents: tuple[str, ...] = Field(
        default=(),
        description=(
            "Talentos do emblema, ja com nome. Na fonte atual e o unico campo "
            "que difere entre variantes com os mesmos itens: sem ele, duas "
            "opcoes distintas ficam indistinguiveis na tela."
        ),
    )
    rank_filter: RankFilter = RankFilter.ALL
    collected_at: datetime


class HeroSynergyData(ProviderDTO):
    """Efeito medido de uma dupla de herois no mesmo time.

    `win_rate_delta` e o deslocamento da taxa de vitoria quando os dois
    aparecem juntos. Conferimos que a matriz da fonte e simetrica, entao o
    numero pertence a DUPLA - nao e "quanto `partner` ajuda `hero`".
    """

    hero_slug: str
    partner_slug: str
    win_rate_delta: float = Field(
        description="Fracao, com sinal. +0.0134 = 1,34 ponto percentual."
    )
    partner_win_rate: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Taxa de vitoria geral do parceiro."
    )
    collected_at: datetime


class CommunityGuideData(ProviderDTO):
    """Um conjunto de itens tirado de um guia escrito por jogador.

    E materia-prima, nao recomendacao: um guia sozinho e a opiniao de uma
    pessoa. Quem transforma varios deles em frequencia e
    `app.domain.comunidade`.
    """

    hero_slug: str
    item_ids: tuple[int, ...] = ()
    patch: str | None = None


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
