"""Acesso a dados de snapshots de meta."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.enums import Lane
from app.models.meta_snapshot import MetaSnapshot


class MetaRepository:
    """Consultas e escrita na tabela `meta_snapshots`."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def latest_source(self) -> str | None:
        """Fonte da coleta mais recente."""
        stmt = (
            select(MetaSnapshot.source)
            .order_by(MetaSnapshot.collected_at.desc())
            .limit(1)
        )
        return self.db.scalar(stmt)

    def latest_collected_at(
        self,
        *,
        lane: Lane | None = None,
        source: str | None = None,
    ) -> datetime | None:
        """Timestamp da coleta mais recente (opcionalmente por lane e fonte)."""
        stmt = select(MetaSnapshot.collected_at).order_by(MetaSnapshot.collected_at.desc()).limit(1)
        if lane is not None:
            stmt = stmt.where(MetaSnapshot.lane == lane)
        if source is not None:
            stmt = stmt.where(MetaSnapshot.source == source)
        return self.db.scalar(stmt)

    def previous_collected_at(
        self,
        before: datetime,
        *,
        lane: Lane | None = None,
        source: str | None = None,
    ) -> datetime | None:
        """Timestamp da coleta imediatamente anterior a `before`.

        `source` importa: comparar coletas de fontes diferentes produziria
        variacoes sem sentido (por exemplo, dado real contra dado de
        demonstracao logo apos trocar de provider).
        """
        stmt = (
            select(MetaSnapshot.collected_at)
            .where(MetaSnapshot.collected_at < before)
            .order_by(MetaSnapshot.collected_at.desc())
            .limit(1)
        )
        if lane is not None:
            stmt = stmt.where(MetaSnapshot.lane == lane)
        if source is not None:
            stmt = stmt.where(MetaSnapshot.source == source)
        return self.db.scalar(stmt)

    def list_at(
        self,
        collected_at: datetime,
        *,
        lane: Lane | None = None,
        source: str | None = None,
        with_hero: bool = True,
    ) -> list[MetaSnapshot]:
        """Snapshots de uma coleta, ordenados do maior para o menor score."""
        stmt = (
            select(MetaSnapshot)
            .where(MetaSnapshot.collected_at == collected_at)
            .order_by(MetaSnapshot.score.desc())
        )
        if lane is not None:
            stmt = stmt.where(MetaSnapshot.lane == lane)
        if source is not None:
            stmt = stmt.where(MetaSnapshot.source == source)
        if with_hero:
            stmt = stmt.options(joinedload(MetaSnapshot.hero))
        return list(self.db.scalars(stmt))

    def exists(
        self,
        *,
        hero_id: int,
        lane: Lane,
        patch: str,
        collected_at: datetime,
    ) -> bool:
        stmt = select(MetaSnapshot.id).where(
            MetaSnapshot.hero_id == hero_id,
            MetaSnapshot.lane == lane,
            MetaSnapshot.patch == patch,
            MetaSnapshot.collected_at == collected_at,
        )
        return self.db.scalar(stmt) is not None

    def add(self, snapshot: MetaSnapshot) -> MetaSnapshot:
        self.db.add(snapshot)
        return snapshot
