"""Acesso a dados da sinergia medida entre duplas."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session, joinedload

from app.models.hero_synergy import HeroSynergy


class HeroSynergyRepository:
    """Consultas e escrita na tabela `hero_synergies`."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def list_for_hero(self, hero_id: int) -> list[HeroSynergy]:
        """Todas as duplas gravadas na direcao em que foram buscadas."""
        stmt = (
            select(HeroSynergy)
            .where(HeroSynergy.hero_id == hero_id)
            .options(joinedload(HeroSynergy.partner))
        )
        return list(self.db.scalars(stmt))

    def list_between(self, hero_ids: list[int]) -> list[HeroSynergy]:
        """Duplas em que AMBOS os herois estao no conjunto pedido.

        Busca nas duas direcoes porque gravamos o par como a fonte
        devolveu, sem espelhar. O par existe uma vez so; qual das duas
        linhas o banco tem depende de qual heroi foi consultado antes.
        """
        if len(hero_ids) < 2:
            return []
        stmt = (
            select(HeroSynergy)
            .where(
                HeroSynergy.hero_id.in_(hero_ids),
                HeroSynergy.partner_id.in_(hero_ids),
            )
            .options(
                joinedload(HeroSynergy.hero),
                joinedload(HeroSynergy.partner),
            )
        )
        return list(self.db.scalars(stmt))

    def last_refreshed_at(self, hero_id: int) -> datetime | None:
        """Quando NOS buscamos a linha deste heroi pela ultima vez.

        Como em builds: a validade do cache depende de quando fomos ate la,
        nao de quando a fonte mediu.
        """
        stmt = (
            select(HeroSynergy.created_at)
            .where(HeroSynergy.hero_id == hero_id)
            .order_by(HeroSynergy.created_at.desc())
            .limit(1)
        )
        return self.db.scalar(stmt)

    def replace_for_hero(self, hero_id: int, synergies: list[HeroSynergy]) -> int:
        """Substitui a linha da matriz daquele heroi.

        Sinergia nao e serie temporal: a fonte publica a medicao corrente.
        Guardar historico exigiria uma pergunta de produto que ainda nao
        temos - e multiplicaria 132 linhas por coleta.
        """
        self.db.execute(delete(HeroSynergy).where(HeroSynergy.hero_id == hero_id))
        self.db.add_all(synergies)
        return len(synergies)

    def heroes_com_dados(self, hero_ids: list[int]) -> set[int]:
        """Quais desses herois ja tem alguma dupla gravada, em qualquer direcao."""
        if not hero_ids:
            return set()
        stmt = select(HeroSynergy.hero_id, HeroSynergy.partner_id).where(
            or_(
                HeroSynergy.hero_id.in_(hero_ids),
                HeroSynergy.partner_id.in_(hero_ids),
            )
        )
        encontrados: set[int] = set()
        for hero_id, partner_id in self.db.execute(stmt):
            encontrados.update({hero_id, partner_id})
        return encontrados & set(hero_ids)
