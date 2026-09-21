"""Acesso a dados de herois."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.enums import HeroRole
from app.models.hero import Hero


class HeroRepository:
    """Consultas e escrita na tabela `heroes`."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def list(
        self,
        *,
        role: HeroRole | None = None,
        search: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Hero]:
        stmt = select(Hero).order_by(Hero.name)
        if role is not None:
            stmt = stmt.where(Hero.role == role)
        if search:
            stmt = stmt.where(Hero.name.ilike(f"%{search.strip()}%"))
        stmt = stmt.limit(limit).offset(offset)
        return list(self.db.scalars(stmt))

    def count(self, *, role: HeroRole | None = None, search: str | None = None) -> int:
        stmt = select(func.count()).select_from(Hero)
        if role is not None:
            stmt = stmt.where(Hero.role == role)
        if search:
            stmt = stmt.where(Hero.name.ilike(f"%{search.strip()}%"))
        return int(self.db.scalar(stmt) or 0)

    def get(self, hero_id: int) -> Hero | None:
        return self.db.get(Hero, hero_id)

    def get_by_slug(self, slug: str) -> Hero | None:
        return self.db.scalar(select(Hero).where(Hero.slug == slug))

    def get_by_name(self, name: str) -> Hero | None:
        """Busca case-insensitive por nome exato."""
        return self.db.scalar(select(Hero).where(func.lower(Hero.name) == name.strip().lower()))

    def slug_index(self) -> dict[str, Hero]:
        """Mapa slug -> Hero, usado pela sincronizacao para evitar N+1."""
        return {hero.slug: hero for hero in self.db.scalars(select(Hero))}

    def upsert(
        self,
        *,
        name: str,
        slug: str,
        role: HeroRole,
        image_url: str | None = None,
    ) -> Hero:
        """Cria ou atualiza um heroi identificado pelo slug."""
        hero = self.get_by_slug(slug)
        if hero is None:
            hero = Hero(name=name, slug=slug, role=role, image_url=image_url)
            self.db.add(hero)
        else:
            hero.name = name
            hero.role = role
            if image_url is not None:
                hero.image_url = image_url
        return hero
