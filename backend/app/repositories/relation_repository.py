"""Acesso a dados das relacoes entre herois."""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, joinedload

from app.models.enums import RelationType
from app.models.hero_relation import HeroRelation


class HeroRelationRepository:
    """Consultas e escrita na tabela `hero_relations`."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def list_for_hero(
        self,
        hero_id: int,
        *,
        relation_type: RelationType | None = None,
    ) -> list[HeroRelation]:
        stmt = (
            select(HeroRelation)
            .where(HeroRelation.hero_id == hero_id)
            .options(joinedload(HeroRelation.related_hero))
        )
        if relation_type is not None:
            stmt = stmt.where(HeroRelation.relation_type == relation_type)
        return list(self.db.scalars(stmt))

    def replace_for_source(self, source: str, relations: list[HeroRelation]) -> int:
        """Substitui todas as relacoes de uma fonte.

        Relacoes nao sao serie temporal: a fonte publica o estado atual. Se
        um heroi deixa de contar como counter de outro, a aresta precisa
        sumir - por isso substituimos o conjunto em vez de acumular.
        """
        self.db.execute(delete(HeroRelation).where(HeroRelation.source == source))
        self.db.add_all(relations)
        return len(relations)
