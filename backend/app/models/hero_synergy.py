"""Efeito medido das duplas de herois no mesmo time.

Tabela separada de `hero_relations` porque as duas respondem perguntas
diferentes:

* `hero_relations` guarda a relacao QUALITATIVA que a fonte publica no
  catalogo ("combina com", "e forte contra") - um booleano, sem tamanho.
* `hero_synergy` guarda o deslocamento MEDIDO da taxa de vitoria quando os
  dois herois jogam juntos. Tem sinal e magnitude.

A matriz da fonte e simetrica: conferimos 56 pares nos dois sentidos e o
valor e identico. Ainda assim gravamos o par na direcao em que foi buscado,
sem espelhar: o que a fonte devolveu e o que guardamos. Quem consulta
procura nas duas direcoes.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.hero import Hero


class HeroSynergy(Base, TimestampMixin):
    """Quanto a taxa de vitoria se desloca com os dois herois no mesmo time."""

    __tablename__ = "hero_synergies"
    __table_args__ = (
        UniqueConstraint("hero_id", "partner_id", name="uq_hero_synergy_pair"),
        Index("ix_hero_synergies_lookup", "hero_id", "partner_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    hero_id: Mapped[int] = mapped_column(
        ForeignKey("heroes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    partner_id: Mapped[int] = mapped_column(
        ForeignKey("heroes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    #: Fracao com sinal. +0.0134 = a dupla desloca 1,34 ponto percentual.
    win_rate_delta: Mapped[float] = mapped_column(Float, nullable=False)
    #: Taxa de vitoria geral do parceiro, como a fonte reportou na mesma
    #: resposta. Serve de contexto: uma dupla boa com um heroi fraco no
    #: geral e uma leitura diferente de uma dupla boa com um heroi forte.
    partner_win_rate: Mapped[float | None] = mapped_column(Float, nullable=True)

    source: Mapped[str] = mapped_column(String(50), nullable=False, default="unknown")
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    hero: Mapped[Hero] = relationship(foreign_keys=[hero_id])
    partner: Mapped[Hero] = relationship(foreign_keys=[partner_id])

    def __repr__(self) -> str:  # pragma: no cover - conveniencia de debug
        return f"<HeroSynergy {self.hero_id}+{self.partner_id} {self.win_rate_delta:+.4f}>"
