"""Endpoints de meta."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.deps import MetaServiceDep
from app.models.enums import Lane
from app.schemas.meta import MetaResponse

router = APIRouter(prefix="/meta", tags=["meta"])


@router.get("", response_model=MetaResponse, summary="Meta de todas as lanes")
def get_meta(
    service: MetaServiceDep,
    limit: int | None = Query(default=None, ge=1, le=200),
) -> MetaResponse:
    """Tier list consolidada da coleta mais recente.

    Enquanto a fonte configurada for de demonstracao, `is_mock` vem `true`:
    os consumidores devem sinalizar isso ao usuario final.
    """
    return service.get_meta(limit=limit)


@router.get("/{lane}", response_model=MetaResponse, summary="Meta de uma lane")
def get_meta_by_lane(
    lane: Lane,
    service: MetaServiceDep,
    limit: int | None = Query(default=None, ge=1, le=200),
) -> MetaResponse:
    return service.get_meta(lane=lane, limit=limit)
