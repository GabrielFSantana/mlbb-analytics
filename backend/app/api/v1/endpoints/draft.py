"""Endpoint do assistente de draft."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.deps import DraftServiceDep
from app.models.enums import Lane, RankFilter
from app.schemas.draft import DraftResponse

router = APIRouter(prefix="/draft", tags=["draft"])


@router.get("/suggest", response_model=DraftResponse, summary="Sugere picks para o draft")
def suggest(
    service: DraftServiceDep,
    enemy: list[str] = Query(
        default=[], description="Herois ja escolhidos pelo time inimigo. Repita o parametro."
    ),
    ally: list[str] = Query(default=[], description="Herois ja escolhidos pelo seu time."),
    lane: Lane | None = Query(default=None, description="Lane para a qual voce vai pegar."),
    rank: RankFilter = Query(default=RankFilter.ALL),
) -> DraftResponse:
    """Combina meta, counters e sinergias numa recomendacao explicavel.

    Cada sugestao vem com o porque: quem ela countera, quem a countera e com
    quais aliados combina. Nomes que nao casarem com nenhum heroi voltam em
    `unknown_terms` - um erro de digitacao nao pode virar recomendacao
    calculada em silencio sem aquele heroi.
    """
    return service.suggest(enemies=enemy, allies=ally, lane=lane, rank_filter=rank)
