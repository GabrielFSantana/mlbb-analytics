"""Endpoints de patches."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.deps import DbSession
from app.repositories.patch_repository import PatchRepository
from app.schemas.common import ErrorResponse, PatchRead

router = APIRouter(prefix="/patches", tags=["patches"])


@router.get("", response_model=list[PatchRead], summary="Lista patches")
def list_patches(db: DbSession, limit: int = Query(default=50, ge=1, le=200)) -> list[PatchRead]:
    patches = PatchRepository(db).list(limit=limit)
    return [PatchRead.model_validate(patch) for patch in patches]


@router.get(
    "/current",
    response_model=PatchRead | None,
    responses={404: {"model": ErrorResponse}},
    summary="Patch vigente",
)
def get_current_patch(db: DbSession) -> PatchRead | None:
    patch = PatchRepository(db).get_current()
    return PatchRead.model_validate(patch) if patch else None
