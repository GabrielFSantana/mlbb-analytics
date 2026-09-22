"""Testes da heuristica de score do meta."""

from __future__ import annotations

import pytest

from app.domain.scoring import (
    WIN_RATE_CEILING,
    WIN_RATE_FLOOR,
    calculate_score,
    score_to_tier,
    tier_rank,
)
from app.models.enums import Tier


def test_score_dentro_da_faixa():
    assert calculate_score(0.50, 0.05, 0.10) == pytest.approx(
        calculate_score(0.50, 0.05, 0.10)
    )
    assert 0.0 <= calculate_score(0.0, 0.0, 0.0) <= 100.0
    assert 0.0 <= calculate_score(1.0, 1.0, 1.0) <= 100.0


def test_score_minimo_e_maximo():
    assert calculate_score(WIN_RATE_FLOOR, 0.0, 0.0) == 0.0
    assert calculate_score(WIN_RATE_CEILING, 1.0, 1.0) == 100.0


def test_win_rate_abaixo_do_piso_nao_fica_negativo():
    assert calculate_score(0.10, 0.0, 0.0) == 0.0


def test_score_cresce_com_win_rate():
    baixo = calculate_score(0.48, 0.08, 0.10)
    alto = calculate_score(0.55, 0.08, 0.10)
    assert alto > baixo


def test_win_rate_pesa_mais_que_ban_rate():
    """Um ganho de win rate deve valer mais que o mesmo ganho relativo de ban."""
    so_win = calculate_score(WIN_RATE_CEILING, 0.0, 0.0)
    so_ban = calculate_score(WIN_RATE_FLOOR, 0.0, 1.0)
    assert so_win > so_ban


def test_pick_rate_satura():
    """Acima da saturacao, mais pick rate nao muda o score."""
    assert calculate_score(0.50, 0.03, 0.10) == calculate_score(0.50, 0.90, 0.10)


@pytest.mark.parametrize(
    ("score", "esperado"),
    [
        (100.0, Tier.S_PLUS),
        (63.0, Tier.S_PLUS),
        (62.9, Tier.S),
        (50.0, Tier.S),
        (39.0, Tier.A),
        (31.0, Tier.B),
        (22.0, Tier.C),
        (21.9, Tier.D),
        (0.0, Tier.D),
    ],
)
def test_score_to_tier(score: float, esperado: Tier):
    assert score_to_tier(score) is esperado


def test_tier_rank_ordena_do_mais_forte_ao_mais_fraco():
    ranks = [tier_rank(tier) for tier in (Tier.S_PLUS, Tier.S, Tier.A, Tier.B, Tier.C, Tier.D)]
    assert ranks == sorted(ranks)
