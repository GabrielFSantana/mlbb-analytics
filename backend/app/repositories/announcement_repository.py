"""Controle do que ja foi publicado no Discord."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.announcement import Announcement


class AnnouncementRepository:
    """Leitura e escrita na tabela `announcements`."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def was_announced(self, kind: str, reference: str) -> bool:
        stmt = select(Announcement.id).where(
            Announcement.kind == kind, Announcement.reference == reference
        )
        return self.db.scalar(stmt) is not None

    def mark(self, kind: str, reference: str) -> bool:
        """Marca como publicado. Idempotente: devolve False se ja estava."""
        if self.was_announced(kind, reference):
            return False
        self.db.add(
            Announcement(kind=kind, reference=reference, announced_at=datetime.now(UTC))
        )
        return True
