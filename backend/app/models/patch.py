"""Patches do jogo."""

from __future__ import annotations

from datetime import date

from sqlalchemy import Boolean, Date, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin


class Patch(Base, TimestampMixin):
    """Uma versao do jogo.

    `is_current` marca o patch vigente; a aplicacao garante que no maximo
    um registro fique marcado (ver PatchRepository.set_current).
    """

    __tablename__ = "patches"

    id: Mapped[int] = mapped_column(primary_key=True)
    version: Mapped[str] = mapped_column(String(20), nullable=False, unique=True, index=True)
    released_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    def __repr__(self) -> str:  # pragma: no cover - conveniencia de debug
        return f"<Patch {self.version!r} current={self.is_current}>"
