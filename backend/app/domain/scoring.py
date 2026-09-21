"""Heuristica interna de pontuacao do meta.

IMPORTANTE
----------
O `score` calculado aqui e UMA METRICA NOSSA, nao um numero oficial do jogo
e nem de nenhuma fonte externa. Ele existe para ordenar herois de forma
consistente entre lanes e patches. Os pesos e limites abaixo sao escolhas
explicitas de produto e podem ser ajustados - se mudarem, mudam tambem os
tiers historicos, entao registre a mudanca antes de alterar.

Racional dos componentes:

* win_rate  - o que mais importa, mas varia pouco (na pratica entre ~42% e
  ~58%), logo e normalizado nessa faixa para nao achatar as diferencas.
* pick_rate - popularidade. Um heroi forte porem raro ainda e relevante,
  por isso tem peso menor que win rate.
* ban_rate  - sinal indireto de forca percebida pela comunidade.

Este modulo e puro: nao depende de banco, rede ou ORM.
"""

from __future__ import annotations

from app.models.enums import TIER_ORDER, Tier

# Faixa realista de win rate usada para normalizar o componente.
WIN_RATE_FLOOR = 0.42
WIN_RATE_CEILING = 0.58

# Valores a partir dos quais consideramos o componente saturado (= 1.0).
PICK_RATE_SATURATION = 0.15
BAN_RATE_SATURATION = 0.50

WEIGHT_WIN_RATE = 0.55
WEIGHT_PICK_RATE = 0.25
WEIGHT_BAN_RATE = 0.20

# Score minimo (inclusive) de cada tier, do mais forte para o mais fraco.
TIER_THRESHOLDS: tuple[tuple[Tier, float], ...] = (
    (Tier.S_PLUS, 78.0),
    (Tier.S, 66.0),
    (Tier.A, 54.0),
    (Tier.B, 42.0),
    (Tier.C, 30.0),
    (Tier.D, 0.0),
)


def _clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


def _normalize(value: float, floor: float, ceiling: float) -> float:
    if ceiling <= floor:
        raise ValueError("ceiling precisa ser maior que floor")
    return _clamp((value - floor) / (ceiling - floor))


def calculate_score(win_rate: float, pick_rate: float, ban_rate: float) -> float:
    """Retorna o score do meta (0-100) para uma leitura de estatisticas.

    Todos os argumentos sao fracoes (0.0-1.0), nao percentuais.
    """
    win_component = _normalize(win_rate, WIN_RATE_FLOOR, WIN_RATE_CEILING)
    pick_component = _clamp(pick_rate / PICK_RATE_SATURATION)
    ban_component = _clamp(ban_rate / BAN_RATE_SATURATION)

    score = (
        WEIGHT_WIN_RATE * win_component
        + WEIGHT_PICK_RATE * pick_component
        + WEIGHT_BAN_RATE * ban_component
    )
    return round(score * 100, 2)


def score_to_tier(score: float) -> Tier:
    """Converte um score (0-100) no tier correspondente."""
    for tier, threshold in TIER_THRESHOLDS:
        if score >= threshold:
            return tier
    return Tier.D


def tier_rank(tier: Tier) -> int:
    """Posicao do tier na ordem canonica (0 = S+). Util para ordenacao."""
    return TIER_ORDER.index(tier)
