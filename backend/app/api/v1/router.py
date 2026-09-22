"""Agregador das rotas da v1."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.endpoints import builds, heroes, meta, patches

api_router = APIRouter()
api_router.include_router(builds.router)
api_router.include_router(heroes.router)
api_router.include_router(meta.router)
api_router.include_router(patches.router)

__all__ = ["api_router"]
