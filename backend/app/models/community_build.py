"""Build completa agregada a partir dos guias da comunidade.

Tabela separada de `hero_builds` de proposito: sao dados de natureza
diferente e nao podem ser confundidos na leitura.

* `hero_builds` vem de partidas reais, tem taxa de vitoria e cobre so os
  itens centrais que a fonte publica.
* `community_builds` vem de guias escritos por jogadores, tem a build
  fechada de seis e **nao tem taxa de vitoria nenhuma** - o unico numero
  que existe aqui e "em quantos guias este item aparece".

Guardar as duas coisas na mesma tabela exigiria colunas nulas de um lado e
do outro, e no primeiro descuido alguem leria frequencia como se fosse win
rate.

Diferente das builds estatisticas, esta agregacao NAO e separada por lane:
os guias do patch atual sao poucas dezenas por heroi e dividi-los por lane
deixaria a maioria das lanes sem amostra. A apresentacao precisa dizer isso.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.hero import Hero
    from app.models.item import Item


class CommunityBuild(Base, TimestampMixin):
    """Os itens mais citados nos guias de um heroi, num patch."""

    __tablename__ = "community_builds"
    __table_args__ = (UniqueConstraint("hero_id", name="uq_community_build_hero"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    hero_id: Mapped[int] = mapped_column(
        ForeignKey("heroes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    #: Patch dos guias considerados. Sem isso a porcentagem nao tem contexto.
    patch: Mapped[str | None] = mapped_column(String(20), nullable=True)
    #: Denominador de toda porcentagem exibida.
    builds_considered: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    source: Mapped[str] = mapped_column(String(50), nullable=False, default="unknown")
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    hero: Mapped[Hero] = relationship()
    items: Mapped[list[CommunityBuildItem]] = relationship(
        back_populates="build",
        cascade="all, delete-orphan",
        order_by="CommunityBuildItem.position",
    )

    def __repr__(self) -> str:  # pragma: no cover - conveniencia de debug
        return f"<CommunityBuild hero={self.hero_id} n={self.builds_considered}>"


class CommunityBuildItem(Base, TimestampMixin):
    """Um item da build agregada, com a contagem que o colocou ali."""

    __tablename__ = "community_build_items"
    __table_args__ = (
        UniqueConstraint("community_build_id", "position", name="uq_community_build_position"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    community_build_id: Mapped[int] = mapped_column(
        ForeignKey("community_builds.id", ondelete="CASCADE"), nullable=False, index=True
    )
    item_id: Mapped[int] = mapped_column(
        ForeignKey("items.id", ondelete="CASCADE"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    #: Em quantas das builds consideradas este item aparece.
    builds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    build: Mapped[CommunityBuild] = relationship(back_populates="items")
    item: Mapped[Item] = relationship()
