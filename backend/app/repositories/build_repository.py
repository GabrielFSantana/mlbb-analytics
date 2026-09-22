"""Acesso a dados de itens e builds."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.models.enums import Lane, RankFilter
from app.models.hero_build import HeroBuild, HeroBuildItem
from app.models.item import Item


class ItemRepository:
    """Consultas e escrita na tabela `items`."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def index_by_external_id(self) -> dict[int, Item]:
        return {item.external_id: item for item in self.db.scalars(select(Item))}

    def upsert(
        self,
        *,
        external_id: int,
        name: str,
        image_url: str | None,
        source: str,
    ) -> Item:
        item = self.db.scalar(select(Item).where(Item.external_id == external_id))
        if item is None:
            item = Item(external_id=external_id, name=name, image_url=image_url, source=source)
            self.db.add(item)
        else:
            item.name = name
            if image_url is not None:
                item.image_url = image_url
            item.source = source
        return item


class HeroBuildRepository:
    """Consultas e escrita nas tabelas de build."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def list_for_hero_lane(
        self,
        hero_id: int,
        lane: Lane,
        *,
        rank_filter: RankFilter = RankFilter.ALL,
    ) -> list[HeroBuild]:
        stmt = (
            select(HeroBuild)
            .where(
                HeroBuild.hero_id == hero_id,
                HeroBuild.lane == lane,
                HeroBuild.rank_filter == rank_filter,
            )
            .order_by(HeroBuild.variant)
            .options(selectinload(HeroBuild.items).selectinload(HeroBuildItem.item))
        )
        return list(self.db.scalars(stmt))

    def last_refreshed_at(
        self,
        hero_id: int,
        lane: Lane,
        *,
        rank_filter: RankFilter = RankFilter.ALL,
    ) -> datetime | None:
        """Quando NOS buscamos este par heroi/lane pela ultima vez.

        Diferente de `collected_at`, que e a data do dado segundo a fonte.
        A validade do cache depende de quando fomos ate la, nao de quando a
        fonte mediu - confundir os dois faz o cache nunca valer (se a fonte
        data o passado) ou valer demais.
        """
        stmt = (
            select(HeroBuild.created_at)
            .where(
                HeroBuild.hero_id == hero_id,
                HeroBuild.lane == lane,
                HeroBuild.rank_filter == rank_filter,
            )
            .order_by(HeroBuild.created_at.desc())
            .limit(1)
        )
        return self.db.scalar(stmt)

    def replace_for_hero_lane(
        self,
        hero_id: int,
        lane: Lane,
        rank_filter: RankFilter,
        builds: list[HeroBuild],
    ) -> int:
        """Substitui as builds daquele heroi/lane.

        Builds nao sao serie temporal: a fonte publica a recomendacao atual.
        Guardar historico de build so faria sentido com uma pergunta de
        produto que ainda nao temos.
        """
        self.db.execute(
            delete(HeroBuild).where(
                HeroBuild.hero_id == hero_id,
                HeroBuild.lane == lane,
                HeroBuild.rank_filter == rank_filter,
            )
        )
        self.db.add_all(builds)
        return len(builds)
