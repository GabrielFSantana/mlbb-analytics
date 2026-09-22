"""Itens do jogo."""

from __future__ import annotations

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin


class Item(Base, TimestampMixin):
    """Um item comprável.

    `external_id` e o id do item na fonte. Diferente dos herois, aqui ele e
    a chave natural: o nome muda com a traducao, o id nao.
    """

    __tablename__ = "items"

    id: Mapped[int] = mapped_column(primary_key=True)
    external_id: Mapped[int] = mapped_column(Integer, nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="unknown")

    def __repr__(self) -> str:  # pragma: no cover - conveniencia de debug
        return f"<Item {self.external_id} {self.name!r}>"
