"""Modelos ORM.

Importar este pacote registra todas as tabelas em `Base.metadata`, o que o
Alembic precisa para o autogenerate.
"""

from app.models.enums import TIER_ORDER, HeroRole, Lane, RankFilter, Tier
from app.models.hero import Hero
from app.models.hero_stats import HeroStats
from app.models.meta_announcement import MetaAnnouncement
from app.models.meta_snapshot import MetaSnapshot
from app.models.patch import Patch

__all__ = [
    "TIER_ORDER",
    "Hero",
    "HeroRole",
    "HeroStats",
    "Lane",
    "MetaAnnouncement",
    "MetaSnapshot",
    "Patch",
    "RankFilter",
    "Tier",
]
