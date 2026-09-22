"""Endpoints de builds."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.deps import BuildServiceDep
from app.models.enums import Lane, RankFilter
from app.schemas.build import HeroBuildsResponse
from app.schemas.common import ErrorResponse

router = APIRouter(prefix="/builds", tags=["builds"])


@router.get(
    "/{term}",
    response_model=HeroBuildsResponse,
    responses={404: {"model": ErrorResponse}},
    summary="Builds recomendadas de um heroi",
)
def get_hero_builds(
    term: str,
    service: BuildServiceDep,
    lane: Lane | None = Query(
        default=None,
        description="Lane. Sem valor, usa aquela em que o heroi esta mais forte.",
    ),
    rank_filter: RankFilter = Query(default=RankFilter.ALL),
) -> HeroBuildsResponse:
    """Itens centrais, emblema e feitico mais usados, por lane.

    Busca na fonte sob demanda e reaproveita o resultado gravado enquanto
    ele for recente. Se a fonte estiver fora, devolve o ultimo dado
    conhecido com a data da coleta.
    """
    return service.get_builds(term, lane=lane, rank_filter=rank_filter)
