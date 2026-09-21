"""Heroi: entidade central do catalogo."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin
from app.models.enums import HeroRole

if TYPE_CHECKING:
    from app.models.hero_stats import HeroStats
    from app.models.meta_snapshot import MetaSnapshot


class Hero(Base, TimestampMixin):
    """Um heroi do MLBB.

    `slug` e a chave estavel usada em buscas e integracoes (ex.: "yi-sun-shin"),
    ja que o nome pode variar de grafia entre fontes.
    """

    __tablename__ = "heroes"
    __table_args__ = (Index("ix_heroes_role", "role"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    slug: Mapped[str] = mapped_column(String(80), nullable=False, unique=True, index=True)
    role: Mapped[HeroRole] = mapped_column(String(20), nullable=False)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    stats: Mapped[list[HeroStats]] = relationship(
        back_populates="hero", cascade="all, delete-orphan"
    )
    meta_snapshots: Mapped[list[MetaSnapshot]] = relationship(
        back_populates="hero", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover - conveniencia de debug
        return f"<Hero id={self.id} slug={self.slug!r}>"
