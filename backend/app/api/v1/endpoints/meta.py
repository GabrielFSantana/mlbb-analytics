"""Endpoints de meta."""

from __future__ import annotations

from fastapi import APIRouter, Query, status

from app.api.deps import DbSession, MetaServiceDep
from app.models.enums import Lane
from app.schemas.meta import MetaAnnouncementAck, MetaResponse, MetaUpdate
from app.services.meta_update_service import MetaUpdateService

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


# ATENCAO: as rotas de /updates precisam vir ANTES de /{lane}. O FastAPI
# resolve na ordem de declaracao, entao com /{lane} primeiro a chamada a
# /meta/updates/pending casaria com lane="updates" e falharia com 422.


@router.get(
    "/updates/pending",
    response_model=MetaUpdate | None,
    summary="Atualizacao de meta ainda nao publicada",
)
def get_pending_update(db: DbSession) -> MetaUpdate | None:
    """Usado pelo bot para saber se ha novidade a publicar.

    Devolve `null` quando nao ha coleta nova, nao ha coleta anterior com que
    comparar, a coleta ja foi anunciada, ou nada mudou o suficiente.
    """
    return MetaUpdateService(db).pending_update()


@router.post(
    "/updates/ack",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Confirma que uma coleta foi publicada",
)
def ack_update(payload: MetaAnnouncementAck, db: DbSession) -> None:
    """Chamado pelo bot depois de publicar. Idempotente."""
    MetaUpdateService(db).mark_announced(payload.collected_at, payload.source)


@router.get("/{lane}", response_model=MetaResponse, summary="Meta de uma lane")
def get_meta_by_lane(
    lane: Lane,
    service: MetaServiceDep,
    limit: int | None = Query(default=None, ge=1, le=200),
) -> MetaResponse:
    return service.get_meta(lane=lane, limit=limit)
