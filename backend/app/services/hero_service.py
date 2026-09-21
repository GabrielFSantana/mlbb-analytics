"""Regras de negocio de herois."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.enums import HeroRole, RankFilter
from app.models.hero import Hero
from app.models.hero_stats import HeroStats
from app.repositories.hero_repository import HeroRepository
from app.repositories.stats_repository import HeroStatsRepository
from app.schemas.hero import HeroListResponse, HeroRead, HeroStatsRead, HeroWithStats


class HeroService:
    def __init__(self, db: Session) -> None:
        self.heroes = HeroRepository(db)
        self.stats = HeroStatsRepository(db)

    def list_heroes(
        self,
        *,
        role: HeroRole | None = None,
        search: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> HeroListResponse:
        items = self.heroes.list(role=role, search=search, limit=limit, offset=offset)
        total = self.heroes.count(role=role, search=search)
        return HeroListResponse(
            total=total,
            items=[HeroRead.model_validate(hero) for hero in items],
        )

    def get_hero(self, hero_id: int) -> HeroWithStats:
        hero = self._require(self.heroes.get(hero_id), hero_id)
        latest = self.stats.latest_for_hero(hero.id)
        return self._to_with_stats(hero, latest)

    def get_hero_by_name_or_slug(self, term: str) -> HeroWithStats:
        """Busca usada pelo bot: aceita tanto o nome quanto o slug."""
        normalized = term.strip().lower().replace(" ", "-")
        hero = self.heroes.get_by_slug(normalized) or self.heroes.get_by_name(term)
        hero = self._require(hero, term)
        latest = self.stats.latest_for_hero(hero.id)
        return self._to_with_stats(hero, latest)

    def list_hero_stats(
        self,
        hero_id: int,
        *,
        patch: str | None = None,
        rank_filter: RankFilter | None = None,
        limit: int = 50,
    ) -> list[HeroStatsRead]:
        hero = self._require(self.heroes.get(hero_id), hero_id)
        readings = self.stats.list_for_hero(
            hero.id, patch=patch, rank_filter=rank_filter, limit=limit
        )
        return [HeroStatsRead.model_validate(reading) for reading in readings]

    @staticmethod
    def _to_with_stats(hero: Hero, latest: HeroStats | None) -> HeroWithStats:
        return HeroWithStats(
            **HeroRead.model_validate(hero).model_dump(),
            latest_stats=HeroStatsRead.model_validate(latest) if latest else None,
        )

    @staticmethod
    def _require(hero: Hero | None, identifier: object) -> Hero:
        if hero is None:
            raise NotFoundError("heroi", identifier)
        return hero
