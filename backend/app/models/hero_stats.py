"""Estatisticas agregadas de um heroi em um patch/ranque."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin
from app.database.types import StrEnumType
from app.models.enums import RankFilter

if TYPE_CHECKING:
    from app.models.hero import Hero


class HeroStats(Base, TimestampMixin):
    """Uma leitura de win/pick/ban rate.

    As taxas sao guardadas como fracao (0.0-1.0), nao como percentual, para
    evitar ambiguidade entre fontes. A formatacao para "%" e responsabilidade
    da camada de apresentacao.

    Cada linha e imutavel: uma nova coleta gera uma nova linha, preservando
    o historico necessario para calcular variacoes entre patches.
    """

    __tablename__ = "hero_stats"
    __table_args__ = (
        UniqueConstraint(
            "hero_id", "patch", "rank_filter", "collected_at", name="uq_hero_stats_reading"
        ),
        Index("ix_hero_stats_patch_rank", "patch", "rank_filter"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    hero_id: Mapped[int] = mapped_column(
        ForeignKey("heroes.id", ondelete="CASCADE"), nullable=False, index=True
    )

    win_rate: Mapped[float] = mapped_column(Float, nullable=False)
    pick_rate: Mapped[float] = mapped_column(Float, nullable=False)
    ban_rate: Mapped[float] = mapped_column(Float, nullable=False)
    matches: Mapped[int | None] = mapped_column(Integer, nullable=True)

    rank_filter: Mapped[RankFilter] = mapped_column(
        StrEnumType(RankFilter, 20), nullable=False, default=RankFilter.ALL
    )
    patch: Mapped[str] = mapped_column(String(20), nullable=False)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Rastreabilidade: de onde veio esse numero (ver MLBBDataProvider.name).
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="unknown")

    hero: Mapped[Hero] = relationship(back_populates="stats")

    def __repr__(self) -> str:  # pragma: no cover - conveniencia de debug
        return f"<HeroStats hero_id={self.hero_id} patch={self.patch!r} wr={self.win_rate}>"
