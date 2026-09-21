"""Acesso a dados de patches."""

from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.patch import Patch


class PatchRepository:
    """Consultas e escrita na tabela `patches`."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def list(self, *, limit: int = 50) -> list[Patch]:
        stmt = select(Patch).order_by(Patch.released_at.desc().nullslast()).limit(limit)
        return list(self.db.scalars(stmt))

    def get_by_version(self, version: str) -> Patch | None:
        return self.db.scalar(select(Patch).where(Patch.version == version))

    def get_current(self) -> Patch | None:
        return self.db.scalar(select(Patch).where(Patch.is_current.is_(True)))

    def upsert(
        self,
        *,
        version: str,
        released_at: object | None = None,
        notes_url: str | None = None,
        summary: str | None = None,
        is_current: bool = False,
    ) -> Patch:
        patch = self.get_by_version(version)
        if patch is None:
            patch = Patch(version=version)
            self.db.add(patch)
        patch.released_at = released_at  # type: ignore[assignment]
        patch.notes_url = notes_url
        patch.summary = summary
        if is_current:
            self.set_current(patch)
        return patch

    def set_current(self, patch: Patch) -> None:
        """Marca `patch` como vigente, desmarcando qualquer outro."""
        self.db.execute(update(Patch).values(is_current=False).where(Patch.is_current.is_(True)))
        patch.is_current = True
