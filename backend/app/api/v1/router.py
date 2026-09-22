"""Agregador das rotas da v1."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.endpoints import (
    builds,
    composition,
    draft,
    heroes,
    meta,
    patches,
    players,
)

api_router = APIRouter()
api_router.include_router(builds.router)
api_router.include_router(composition.router)
api_router.include_router(draft.router)
api_router.include_router(heroes.router)
api_router.include_router(meta.router)
api_router.include_router(patches.router)
api_router.include_router(players.router)

__all__ = ["api_router"]
