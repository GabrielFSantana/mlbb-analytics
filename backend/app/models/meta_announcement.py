"""Registro de quais coletas ja foram anunciadas no Discord."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin


class MetaAnnouncement(Base, TimestampMixin):
    """Marca uma coleta como ja publicada.

    Existe para tornar a publicacao exatamente-uma-vez: sem esse registro,
    reiniciar o bot faria ele reanunciar a mesma atualizacao, e uma falha no
    meio faria a atualizacao se perder. O estado vive no banco (e nao na
    memoria do bot) porque o backend e o dono dos dados, e o bot pode ser
    reiniciado ou escalado livremente.
    """

    __tablename__ = "meta_announcements"
    __table_args__ = (
        UniqueConstraint("collected_at", "source", name="uq_meta_announcement"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    announced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    def __repr__(self) -> str:  # pragma: no cover - conveniencia de debug
        return f"<MetaAnnouncement {self.source} {self.collected_at.isoformat()}>"
