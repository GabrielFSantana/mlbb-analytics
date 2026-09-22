"""Enumeracoes de dominio do MLBB.

Sao persistidas como texto (nao como ENUM nativo do Postgres) para que
adicionar um valor novo nao exija migration de tipo.
"""

from __future__ import annotations

from enum import StrEnum


class HeroRole(StrEnum):
    """Classe do heroi, como o proprio jogo a exibe."""

    TANK = "tank"
    FIGHTER = "fighter"
    ASSASSIN = "assassin"
    MAGE = "mage"
    MARKSMAN = "marksman"
    SUPPORT = "support"


class Lane(StrEnum):
    """Rota/funcao dentro da partida."""

    JUNGLE = "jungle"
    GOLD = "gold"
    MID = "mid"
    EXP = "exp"
    ROAM = "roam"


class Tier(StrEnum):
    """Faixa de forca no meta, da mais forte para a mais fraca."""

    S_PLUS = "S+"
    S = "S"
    A = "A"
    B = "B"
    C = "C"
    D = "D"


# Ordem canonica usada para ordenar tiers na API e nos embeds.
TIER_ORDER: tuple[Tier, ...] = (
    Tier.S_PLUS,
    Tier.S,
    Tier.A,
    Tier.B,
    Tier.C,
    Tier.D,
)


class RankFilter(StrEnum):
    """Faixa de ranque a que uma estatistica se refere.

    Os valores espelham as faixas que a fonte de dados expoe, para que a
    traducao entre fonte e dominio seja direta.
    """

    ALL = "all"
    EPIC = "epic"
    LEGEND = "legend"
    MYTHIC = "mythic"
    HONOR = "honor"
    GLORY = "glory"


class RelationType(StrEnum):
    """Relacao entre dois herois, do ponto de vista do heroi principal."""

    #: O heroi principal leva vantagem contra o alvo.
    STRONG = "strong"
    #: O heroi principal leva desvantagem contra o alvo.
    WEAK = "weak"
    #: Boa sinergia quando jogam no mesmo time.
    ASSIST = "assist"
