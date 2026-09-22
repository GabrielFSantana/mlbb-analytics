"""Relacoes entre herois: contra quem vai bem, mal, e com quem combina."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin
from app.database.types import StrEnumType
from app.models.enums import RelationType

if TYPE_CHECKING:
    from app.models.hero import Hero


class HeroRelation(Base, TimestampMixin):
    """Uma aresta direcionada entre dois herois.

    Diferente de `HeroStats`, isto nao e serie temporal: a fonte publica o
    estado atual e ele muda raramente. Cada sincronizacao substitui o
    conjunto do heroi, entao uma relacao removida na origem some daqui.
    """

    __tablename__ = "hero_relations"
    __table_args__ = (
        UniqueConstraint(
            "hero_id", "related_hero_id", "relation_type", name="uq_hero_relation"
        ),
        Index("ix_hero_relations_lookup", "hero_id", "relation_type"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    hero_id: Mapped[int] = mapped_column(
        ForeignKey("heroes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    related_hero_id: Mapped[int] = mapped_column(
        ForeignKey("heroes.id", ondelete="CASCADE"), nullable=False
    )
    relation_type: Mapped[RelationType] = mapped_column(
        StrEnumType(RelationType, 20), nullable=False
    )
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="unknown")

    hero: Mapped[Hero] = relationship(foreign_keys=[hero_id], back_populates="relations")
    related_hero: Mapped[Hero] = relationship(foreign_keys=[related_hero_id])

    def __repr__(self) -> str:  # pragma: no cover - conveniencia de debug
        return f"<HeroRelation {self.hero_id} {self.relation_type} {self.related_hero_id}>"
