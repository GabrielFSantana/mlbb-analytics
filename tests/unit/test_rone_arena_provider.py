"""Testes do provider da fonte comunitaria.

Nao tocam a rede: as respostas sao fixtures gravadas da API real
(tests/fixtures/rone_*.json), servidas por um transporte falso do httpx.
Assim os testes continuam valendo se a fonte sair do ar - e falham se
mudarmos o parser sem querer.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from app.core.exceptions import ProviderError
from app.models.enums import HeroRole, Lane, RankFilter
from app.providers.rone_arena import RoneArenaProvider, slugify

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"

ROTAS = {
    "/api/heroes/positions": "rone_positions.json",
    "/api/heroes/rank": "rone_rank.json",
    "/api/academy/meta/version": "rone_meta_version.json",
}


def _carregar(nome: str) -> dict:
    return json.loads((FIXTURES / nome).read_text(encoding="utf-8"))


def _transporte(status: int = 200, payload: dict | None = None) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        if payload is not None:
            return httpx.Response(status, json=payload)
        nome = ROTAS.get(request.url.path)
        if nome is None:  # pragma: no cover - rota nao usada pelos testes
            return httpx.Response(404, json={"code": 404, "message": "not found"})
        return httpx.Response(status, json=_carregar(nome))

    return httpx.MockTransport(handler)


@pytest.fixture
def provider() -> RoneArenaProvider:
    client = httpx.Client(transport=_transporte())
    return RoneArenaProvider(client=client)


# -- identidade da fonte ------------------------------------------------


def test_provider_nao_e_mock(provider: RoneArenaProvider):
    """O contrario do MockDataProvider: estes dados sao reais."""
    assert provider.is_mock is False
    assert provider.name == "rone_arena"
    assert "nao oficial" in provider.source_description.lower()


def test_janela_invalida_e_rejeitada_na_construcao():
    with pytest.raises(ProviderError, match="nao suportada"):
        RoneArenaProvider(window_days=5)


def test_janela_valida_e_aceita():
    assert RoneArenaProvider(window_days=30).window_days == 30


# -- slug ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("nome", "esperado"),
    [
        ("Leomord", "leomord"),
        ("Yi Sun-shin", "yi-sun-shin"),
        ("Chang'e", "chang-e"),
        ("Luo Yi", "luo-yi"),
        ("X.Borg", "x-borg"),
        ("Popol and Kupa", "popol-and-kupa"),
    ],
)
def test_slugify(nome: str, esperado: str):
    assert slugify(nome) == esperado


# -- catalogo -----------------------------------------------------------


def test_get_heroes_traduz_papel_e_imagem(provider: RoneArenaProvider):
    herois = provider.get_heroes()
    assert herois

    for heroi in herois:
        assert isinstance(heroi.role, HeroRole)
        assert heroi.slug == slugify(heroi.name)
        assert heroi.external_id is not None


def test_get_heroes_usa_imagem_oficial_quando_disponivel(provider: RoneArenaProvider):
    """Diferente do mock, aqui ha URL de imagem real (CDN da Moonton)."""
    com_imagem = [h for h in provider.get_heroes() if h.image_url]
    assert com_imagem
    assert all(h.image_url.startswith("https://") for h in com_imagem)


# -- estatisticas -------------------------------------------------------


def test_get_hero_stats_devolve_fracoes(provider: RoneArenaProvider):
    leituras = provider.get_hero_stats()
    assert leituras
    for leitura in leituras:
        assert 0.0 <= leitura.win_rate <= 1.0
        assert 0.0 <= leitura.pick_rate <= 1.0
        assert 0.0 <= leitura.ban_rate <= 1.0


def test_get_hero_stats_marca_o_ranque_pedido(provider: RoneArenaProvider):
    leituras = provider.get_hero_stats(rank_filter=RankFilter.MYTHIC)
    assert all(leitura.rank_filter is RankFilter.MYTHIC for leitura in leituras)


def test_collected_at_truncado_ao_dia(provider: RoneArenaProvider):
    """Garante idempotencia: duas coletas no mesmo dia geram o mesmo instante."""
    leitura = provider.get_hero_stats()[0]
    assert leitura.collected_at.tzinfo is not None
    assert (leitura.collected_at.hour, leitura.collected_at.minute) == (0, 0)
    assert leitura.collected_at.second == 0
    assert leitura.collected_at.date() == datetime.now(UTC).date()


def test_taxas_fora_da_faixa_sao_limitadas():
    """Um valor absurdo em um heroi nao pode derrubar a coleta inteira."""
    payload = {
        "code": 0,
        "message": "OK",
        "data": {
            "records": [
                {
                    "data": {
                        "main_heroid": 1,
                        "main_hero": {"data": {"name": "Teste", "head": "https://x/y.png"}},
                        "main_hero_win_rate": 1.8,
                        "main_hero_appearance_rate": -0.2,
                        "main_hero_ban_rate": None,
                    }
                }
            ],
            "total": 1,
        },
    }
    linha = payload["data"]["records"][0]["data"]
    assert RoneArenaProvider._taxa(linha, "main_hero_win_rate") == 1.0
    assert RoneArenaProvider._taxa(linha, "main_hero_appearance_rate") == 0.0
    assert RoneArenaProvider._taxa(linha, "main_hero_ban_rate") == 0.0


# -- meta ---------------------------------------------------------------


def test_get_meta_usa_lanes_da_fonte(provider: RoneArenaProvider):
    entradas = provider.get_meta()
    assert entradas
    assert all(isinstance(entrada.lane, Lane) for entrada in entradas)


def test_get_meta_filtra_por_lane(provider: RoneArenaProvider):
    todas = provider.get_meta()
    lane_presente = todas[0].lane
    filtradas = provider.get_meta(lane=lane_presente)
    assert filtradas
    assert all(entrada.lane is lane_presente for entrada in filtradas)


def test_get_meta_tier_coerente_com_score(provider: RoneArenaProvider):
    from app.domain.scoring import score_to_tier

    for entrada in provider.get_meta():
        assert entrada.tier is score_to_tier(entrada.score)


# -- patch --------------------------------------------------------------


def test_current_patch_pega_a_versao_mais_recente(provider: RoneArenaProvider):
    patch = provider.current_patch()
    assert patch
    assert patch[0].isdigit()


def test_get_patches_marca_apenas_um_como_atual(provider: RoneArenaProvider):
    patches = provider.get_patches()
    assert patches
    assert sum(1 for patch in patches if patch.is_current) == 1


# -- tratamento de falhas -----------------------------------------------


def test_erro_http_vira_provider_error():
    client = httpx.Client(transport=_transporte(status=503, payload={"code": 0}))
    provider = RoneArenaProvider(client=client)
    with pytest.raises(ProviderError, match="HTTP 503"):
        provider.get_heroes()


def test_envelope_com_code_diferente_de_zero_vira_provider_error():
    payload = {"code": 1001, "message": "rate limited", "data": {}}
    client = httpx.Client(transport=_transporte(payload=payload))
    provider = RoneArenaProvider(client=client)
    with pytest.raises(ProviderError, match="code=1001"):
        provider.get_heroes()


def test_catalogo_vazio_vira_provider_error():
    payload = {"code": 0, "message": "OK", "data": {"records": [], "total": 0}}
    client = httpx.Client(transport=_transporte(payload=payload))
    provider = RoneArenaProvider(client=client)
    with pytest.raises(ProviderError, match="catalogo"):
        provider.get_heroes()


def test_falha_de_rede_vira_provider_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sem rede")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = RoneArenaProvider(client=client)
    with pytest.raises(ProviderError, match="falha de rede"):
        provider.get_heroes()


# -- cache --------------------------------------------------------------


def test_cache_evita_repetir_a_mesma_chamada():
    chamadas: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        chamadas.append(request.url.path)
        nome = ROTAS[request.url.path]
        return httpx.Response(200, json=_carregar(nome))

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = RoneArenaProvider(client=client)

    provider.get_heroes()
    provider.get_heroes()

    # Duas chamadas identicas devem consumir o cache, nao a rede.
    assert chamadas.count("/api/heroes/positions") == 1
