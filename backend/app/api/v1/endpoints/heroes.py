"""Endpoints de herois."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.deps import HeroServiceDep
from app.models.enums import HeroRole, RankFilter
from app.schemas.common import ErrorResponse
from app.schemas.hero import HeroListResponse, HeroStatsRead, HeroWithStats

router = APIRouter(prefix="/heroes", tags=["heroes"])


@router.get("", response_model=HeroListResponse, summary="Lista herois")
def list_heroes(
    service: HeroServiceDep,
    role: HeroRole | None = Query(default=None, description="Filtra pela classe do heroi."),
    search: str | None = Query(default=None, description="Busca parcial por nome."),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> HeroListResponse:
    return service.list_heroes(role=role, search=search, limit=limit, offset=offset)


@router.get(
    "/{hero_id}",
    response_model=HeroWithStats,
    responses={404: {"model": ErrorResponse}},
    summary="Detalhe de um heroi",
)
def get_hero(hero_id: int, service: HeroServiceDep) -> HeroWithStats:
    return service.get_hero(hero_id)


@router.get(
    "/by-name/{term}",
    response_model=HeroWithStats,
    responses={404: {"model": ErrorResponse}},
    summary="Detalhe de um heroi por nome ou slug",
)
def get_hero_by_name(term: str, service: HeroServiceDep) -> HeroWithStats:
    """Usado pelo bot, que recebe o nome digitado pelo usuario."""
    return service.get_hero_by_name_or_slug(term)


@router.get(
    "/{hero_id}/stats",
    response_model=list[HeroStatsRead],
    responses={404: {"model": ErrorResponse}},
    summary="Historico de estatisticas de um heroi",
)
def get_hero_stats(
    hero_id: int,
    service: HeroServiceDep,
    patch: str | None = Query(default=None),
    rank_filter: RankFilter | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[HeroStatsRead]:
    return service.list_hero_stats(hero_id, patch=patch, rank_filter=rank_filter, limit=limit)
