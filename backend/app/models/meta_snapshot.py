"""Posicao de um heroi no meta em um dado momento."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin
from app.database.types import StrEnumType
from app.models.enums import Lane, RankFilter, Tier

if TYPE_CHECKING:
    from app.models.hero import Hero


class MetaSnapshot(Base, TimestampMixin):
    """Tier e score de um heroi em uma lane.

    `score` e um indice interno (0-100) calculado por
    `app.domain.scoring`. Nao e um numero oficial do jogo.
    """

    __tablename__ = "meta_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "hero_id",
            "lane",
            "rank_filter",
            "patch",
            "collected_at",
            name="uq_meta_snapshot_reading",
        ),
        Index("ix_meta_snapshots_lane_rank", "lane", "rank_filter"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    hero_id: Mapped[int] = mapped_column(
        ForeignKey("heroes.id", ondelete="CASCADE"), nullable=False, index=True
    )

    lane: Mapped[Lane] = mapped_column(StrEnumType(Lane, 20), nullable=False)
    rank_filter: Mapped[RankFilter] = mapped_column(
        StrEnumType(RankFilter, 20), nullable=False, default=RankFilter.ALL
    )
    tier: Mapped[Tier] = mapped_column(StrEnumType(Tier, 5), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)

    patch: Mapped[str] = mapped_column(String(20), nullable=False)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="unknown")

    hero: Mapped[Hero] = relationship(back_populates="meta_snapshots")

    def __repr__(self) -> str:  # pragma: no cover - conveniencia de debug
        return f"<MetaSnapshot hero_id={self.hero_id} lane={self.lane} tier={self.tier}>"
