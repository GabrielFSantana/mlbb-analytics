"""Registro do que ja foi publicado no Discord.

Substitui a tabela especifica de meta: com dois tipos de publicacao (meta e
ranking semanal) e provaveis outros depois, uma tabela por tipo so
multiplicaria codigo identico.

A chave e (kind, reference). O que vai em `reference` depende do tipo e e
escolhido para ser estavel e unico:

* meta_update    -> "<fonte>@<collected_at ISO>"
* weekly_ranking -> ano e semana ISO, ex.: "2026-W38"
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin


class AnnouncementKind:
    """Tipos de publicacao. String simples: nao vale um enum de dominio."""

    META_UPDATE = "meta_update"
    WEEKLY_RANKING = "weekly_ranking"


class Announcement(Base, TimestampMixin):
    """Marca que algo ja foi publicado, para nao publicar de novo.

    O estado vive no banco, e nao na memoria do bot, porque o bot reinicia -
    e uma republicacao a cada restart seria pior que nao publicar.
    """

    __tablename__ = "announcements"
    __table_args__ = (UniqueConstraint("kind", "reference", name="uq_announcement"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    reference: Mapped[str] = mapped_column(String(120), nullable=False)
    announced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    def __repr__(self) -> str:  # pragma: no cover - conveniencia de debug
        return f"<Announcement {self.kind} {self.reference!r}>"
