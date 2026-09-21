"""Testes do provider de demonstracao e do contrato MLBBDataProvider."""

from __future__ import annotations

import pytest

from app.core.exceptions import ProviderNotSupportedError
from app.models.enums import Lane
from app.providers.base import MLBBDataProvider
from app.providers.factory import get_provider
from app.providers.mock import MockDataProvider


@pytest.fixture
def provider() -> MockDataProvider:
    return MockDataProvider()


def test_provider_e_declarado_como_mock(provider: MockDataProvider):
    """Sinalizar dado ficticio e requisito, nao detalhe: nunca deve regredir."""
    assert provider.is_mock is True
    assert provider.name == "mock"
    assert provider.source_description


def test_factory_retorna_o_provider_configurado():
    assert isinstance(get_provider("mock"), MockDataProvider)
    assert isinstance(get_provider("mock"), MLBBDataProvider)


def test_factory_rejeita_provider_desconhecido():
    from app.core.exceptions import ProviderError

    with pytest.raises(ProviderError, match="desconhecido"):
        get_provider("fonte-inexistente")


def test_get_heroes_tem_slugs_unicos(provider: MockDataProvider):
    heroes = provider.get_heroes()
    slugs = [hero.slug for hero in heroes]
    assert len(heroes) > 0
    assert len(slugs) == len(set(slugs))


def test_get_heroes_nao_inventa_imagem(provider: MockDataProvider):
    """Nenhuma URL de imagem e fabricada para dados mock."""
    assert all(hero.image_url is None for hero in provider.get_heroes())


def test_get_hero_stats_traz_duas_leituras_por_heroi(provider: MockDataProvider):
    heroes = provider.get_heroes()
    readings = provider.get_hero_stats()
    assert len(readings) == len(heroes) * 2

    timestamps = {reading.collected_at for reading in readings}
    assert len(timestamps) == 2, "esperado historico (atual + anterior) para calcular tendencia"


def test_get_hero_stats_usa_fracao_e_nao_percentual(provider: MockDataProvider):
    for reading in provider.get_hero_stats():
        assert 0.0 <= reading.win_rate <= 1.0
        assert 0.0 <= reading.pick_rate <= 1.0
        assert 0.0 <= reading.ban_rate <= 1.0


def test_get_hero_stats_de_patch_desconhecido_vem_vazio(provider: MockDataProvider):
    assert provider.get_hero_stats(patch="patch-que-nao-existe") == []


def test_get_meta_filtra_por_lane(provider: MockDataProvider):
    entries = provider.get_meta(lane=Lane.JUNGLE)
    assert entries
    assert all(entry.lane is Lane.JUNGLE for entry in entries)


def test_get_meta_cobre_todas_as_lanes(provider: MockDataProvider):
    lanes = {entry.lane for entry in provider.get_meta()}
    assert lanes == set(Lane)


def test_get_meta_score_coerente_com_tier(provider: MockDataProvider):
    from app.domain.scoring import score_to_tier

    for entry in provider.get_meta():
        assert entry.tier is score_to_tier(entry.score)


def test_get_patches_marca_patch_corrente(provider: MockDataProvider):
    patches = provider.get_patches()
    assert [patch for patch in patches if patch.is_current]


def test_capacidades_nao_suportadas_falham_explicitamente(provider: MockDataProvider):
    """Player/match nao retornam vazio: avisam que a fonte nao suporta."""
    with pytest.raises(ProviderNotSupportedError):
        provider.get_player("123", "456")
    with pytest.raises(ProviderNotSupportedError):
        provider.get_matches("123", "456")
