"""Schemas do assistente de draft."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import Lane, RankFilter, Tier
from app.schemas.hero import HeroRead


class DraftCandidate(BaseModel):
    """Um pick sugerido, com o porque da sugestao.

    As listas existem para a interface poder justificar a recomendacao. Uma
    sugestao sem explicacao a pessoa nao segue.
    """

    hero: HeroRead
    lane: Lane
    tier: Tier
    meta_score: float = Field(description="Score do heroi no meta, antes dos ajustes.")
    draft_score: float = Field(description="Score final, ja com counters e sinergias.")
    counters: list[HeroRead] = Field(
        default_factory=list, description="Inimigos contra os quais leva vantagem."
    )
    countered_by: list[HeroRead] = Field(
        default_factory=list, description="Inimigos que levam vantagem contra ele."
    )
    synergies: list[HeroRead] = Field(
        default_factory=list, description="Aliados com quem combina."
    )


class DraftResponse(BaseModel):
    enemies: list[HeroRead] = Field(default_factory=list)
    allies: list[HeroRead] = Field(default_factory=list)
    lane: Lane | None = None
    rank_filter: RankFilter = RankFilter.ALL
    suggestions: list[DraftCandidate] = Field(
        default_factory=list,
        description="Melhores picks no geral: meta forte, ajustado por counters e sinergias.",
    )
    counter_picks: list[DraftCandidate] = Field(
        default_factory=list,
        description=(
            "Quem especificamente leva vantagem contra o time inimigo, ordenado pela "
            "vantagem. Existe separado porque um counter de tier baixo nunca "
            "apareceria na lista geral, dominada pelo meta - e e justamente ele que "
            "a pessoa foi procurar."
        ),
    )
    unknown_terms: list[str] = Field(
        default_factory=list,
        description=(
            "Nomes informados que nao casaram com nenhum heroi. Ficam explicitos "
            "para um erro de digitacao nao virar uma recomendacao silenciosamente "
            "calculada sem aquele heroi."
        ),
    )
    collected_at: datetime | None = None
    patch: str | None = None
    source: str
    is_mock: bool = False
