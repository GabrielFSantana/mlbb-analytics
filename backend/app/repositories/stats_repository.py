"""Acesso a dados de estatisticas de herois."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import RankFilter
from app.models.hero_stats import HeroStats


class HeroStatsRepository:
    """Consultas e escrita na tabela `hero_stats`."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def list_for_hero(
        self,
        hero_id: int,
        *,
        patch: str | None = None,
        rank_filter: RankFilter | None = None,
        limit: int = 50,
    ) -> list[HeroStats]:
        stmt = (
            select(HeroStats)
            .where(HeroStats.hero_id == hero_id)
            .order_by(HeroStats.collected_at.desc())
            .limit(limit)
        )
        if patch:
            stmt = stmt.where(HeroStats.patch == patch)
        if rank_filter is not None:
            stmt = stmt.where(HeroStats.rank_filter == rank_filter)
        return list(self.db.scalars(stmt))

    def latest_for_hero(
        self,
        hero_id: int,
        *,
        rank_filter: RankFilter = RankFilter.ALL,
    ) -> HeroStats | None:
        stmt = (
            select(HeroStats)
            .where(HeroStats.hero_id == hero_id, HeroStats.rank_filter == rank_filter)
            .order_by(HeroStats.collected_at.desc())
            .limit(1)
        )
        return self.db.scalar(stmt)

    def latest_collected_at(self, *, rank_filter: RankFilter = RankFilter.ALL) -> datetime | None:
        stmt = (
            select(HeroStats.collected_at)
            .where(HeroStats.rank_filter == rank_filter)
            .order_by(HeroStats.collected_at.desc())
            .limit(1)
        )
        return self.db.scalar(stmt)

    def list_at(
        self,
        collected_at: datetime,
        *,
        rank_filter: RankFilter = RankFilter.ALL,
    ) -> list[HeroStats]:
        stmt = select(HeroStats).where(
            HeroStats.collected_at == collected_at,
            HeroStats.rank_filter == rank_filter,
        )
        return list(self.db.scalars(stmt))

    def exists(
        self,
        *,
        hero_id: int,
        patch: str,
        rank_filter: RankFilter,
        collected_at: datetime,
    ) -> bool:
        stmt = select(HeroStats.id).where(
            HeroStats.hero_id == hero_id,
            HeroStats.patch == patch,
            HeroStats.rank_filter == rank_filter,
            HeroStats.collected_at == collected_at,
        )
        return self.db.scalar(stmt) is not None

    def add(self, stats: HeroStats) -> HeroStats:
        self.db.add(stats)
        return stats
