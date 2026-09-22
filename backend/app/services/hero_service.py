"""Regras de negocio de herois."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.enums import HeroRole, RankFilter, RelationType
from app.models.hero import Hero
from app.models.hero_stats import HeroStats
from app.providers.factory import get_provider
from app.repositories.hero_repository import HeroRepository
from app.repositories.meta_repository import MetaRepository
from app.repositories.relation_repository import HeroRelationRepository
from app.repositories.stats_repository import HeroStatsRepository
from app.schemas.hero import (
    HeroCounters,
    HeroLanePosition,
    HeroListResponse,
    HeroRead,
    HeroStatsRead,
    HeroWithStats,
)


class HeroService:
    def __init__(self, db: Session) -> None:
        self.heroes = HeroRepository(db)
        self.stats = HeroStatsRepository(db)
        self.meta = MetaRepository(db)
        self.relations = HeroRelationRepository(db)

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

    def _to_with_stats(self, hero: Hero, latest: HeroStats | None) -> HeroWithStats:
        provider = get_provider()
        return HeroWithStats(
            **HeroRead.model_validate(hero).model_dump(),
            latest_stats=HeroStatsRead.model_validate(latest) if latest else None,
            lanes=self._lane_positions(hero.id),
            patch=latest.patch if latest else None,
            source=latest.source if latest else None,
            is_mock=provider.is_mock,
        )

    def _lane_positions(self, hero_id: int) -> list[HeroLanePosition]:
        """Tier e score do heroi em cada lane, na coleta mais recente.

        A lane nao vive na tabela de herois: um heroi joga em mais de uma, e
        a forca dele varia entre elas. A informacao vem dos snapshots.
        """
        fonte = self.meta.latest_source()
        ultima = self.meta.latest_collected_at(source=fonte)
        if ultima is None:
            return []

        anterior = self.meta.previous_collected_at(ultima, source=fonte)
        scores_anteriores = {
            snapshot.lane: snapshot.score
            for snapshot in (
                self.meta.list_at(anterior, source=fonte, with_hero=False) if anterior else []
            )
            if snapshot.hero_id == hero_id
        }

        posicoes = [
            HeroLanePosition(
                lane=snapshot.lane,
                tier=snapshot.tier,
                score=snapshot.score,
                score_delta=(
                    round(snapshot.score - scores_anteriores[snapshot.lane], 2)
                    if snapshot.lane in scores_anteriores
                    else None
                ),
            )
            for snapshot in self.meta.list_at(ultima, source=fonte, with_hero=False)
            if snapshot.hero_id == hero_id
        ]
        posicoes.sort(key=lambda p: -p.score)
        return posicoes

    def get_counters(self, term: str) -> HeroCounters:
        """Contra quem o heroi vai bem, mal, e com quem combina."""
        normalized = term.strip().lower().replace(" ", "-")
        hero = self.heroes.get_by_slug(normalized) or self.heroes.get_by_name(term)
        hero = self._require(hero, term)

        relacoes = self.relations.list_for_hero(hero.id)
        por_tipo: dict[RelationType, list[HeroRead]] = {tipo: [] for tipo in RelationType}
        fonte = None
        for relacao in relacoes:
            por_tipo[relacao.relation_type].append(HeroRead.model_validate(relacao.related_hero))
            fonte = relacao.source

        return HeroCounters(
            hero=HeroRead.model_validate(hero),
            strong_against=por_tipo[RelationType.STRONG],
            weak_against=por_tipo[RelationType.WEAK],
            good_with=por_tipo[RelationType.ASSIST],
            source=fonte,
            is_mock=get_provider().is_mock,
        )

    @staticmethod
    def _require(hero: Hero | None, identifier: object) -> Hero:
        if hero is None:
            raise NotFoundError("heroi", identifier)
        return hero
