"""Builds recomendadas por heroi e lane."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin
from app.database.types import StrEnumType
from app.models.enums import Lane, RankFilter

if TYPE_CHECKING:
    from app.models.hero import Hero
    from app.models.item import Item


class HeroBuild(Base, TimestampMixin):
    """Uma combinacao de itens, emblema e feitico para um heroi numa lane.

    A fonte publica algumas variantes por heroi/lane, cada uma com a propria
    taxa de vitoria e de uso; `variant` preserva essa ordem.

    ATENCAO: a fonte entrega apenas os itens CENTRAIS (hoje, tres), nao uma
    build fechada de seis. A apresentacao precisa deixar isso claro.
    """

    __tablename__ = "hero_builds"
    __table_args__ = (
        UniqueConstraint(
            "hero_id", "lane", "rank_filter", "variant", name="uq_hero_build_variant"
        ),
        Index("ix_hero_builds_lookup", "hero_id", "lane"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    hero_id: Mapped[int] = mapped_column(
        ForeignKey("heroes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    lane: Mapped[Lane] = mapped_column(StrEnumType(Lane, 20), nullable=False)
    rank_filter: Mapped[RankFilter] = mapped_column(
        StrEnumType(RankFilter, 20), nullable=False, default=RankFilter.ALL
    )
    #: Posicao da variante na resposta da fonte (0 = primeira).
    variant: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    win_rate: Mapped[float] = mapped_column(Float, nullable=False)
    pick_rate: Mapped[float] = mapped_column(Float, nullable=False)
    emblem: Mapped[str | None] = mapped_column(String(80), nullable=True)
    battle_spell: Mapped[str | None] = mapped_column(String(80), nullable=True)

    source: Mapped[str] = mapped_column(String(50), nullable=False, default="unknown")
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    hero: Mapped[Hero] = relationship()
    items: Mapped[list[HeroBuildItem]] = relationship(
        back_populates="build",
        cascade="all, delete-orphan",
        order_by="HeroBuildItem.position",
    )

    def __repr__(self) -> str:  # pragma: no cover - conveniencia de debug
        return f"<HeroBuild hero={self.hero_id} {self.lane} v{self.variant}>"


class HeroBuildItem(Base, TimestampMixin):
    """Um item dentro de uma build, na ordem em que a fonte o listou."""

    __tablename__ = "hero_build_items"
    __table_args__ = (
        UniqueConstraint("build_id", "position", name="uq_hero_build_item_position"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    build_id: Mapped[int] = mapped_column(
        ForeignKey("hero_builds.id", ondelete="CASCADE"), nullable=False, index=True
    )
    item_id: Mapped[int] = mapped_column(
        ForeignKey("items.id", ondelete="CASCADE"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    build: Mapped[HeroBuild] = relationship(back_populates="items")
    item: Mapped[Item] = relationship()
