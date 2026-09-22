"""Dependencias compartilhadas pelos endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.services.build_service import BuildService
from app.services.draft_service import DraftService
from app.services.hero_service import HeroService
from app.services.meta_service import MetaService
from app.services.player_service import PlayerService

DbSession = Annotated[Session, Depends(get_db)]


def get_build_service(db: DbSession) -> BuildService:
    return BuildService(db)


def get_draft_service(db: DbSession) -> DraftService:
    return DraftService(db)


def get_hero_service(db: DbSession) -> HeroService:
    return HeroService(db)


def get_meta_service(db: DbSession) -> MetaService:
    return MetaService(db)


def get_player_service(db: DbSession) -> PlayerService:
    return PlayerService(db)


BuildServiceDep = Annotated[BuildService, Depends(get_build_service)]
DraftServiceDep = Annotated[DraftService, Depends(get_draft_service)]
HeroServiceDep = Annotated[HeroService, Depends(get_hero_service)]
MetaServiceDep = Annotated[MetaService, Depends(get_meta_service)]
PlayerServiceDep = Annotated[PlayerService, Depends(get_player_service)]
