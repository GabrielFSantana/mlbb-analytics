"""Testes da renderizacao dos cards em imagem.

Nao tocam a rede: os retratos sao injetados no cache do modulo.
"""

from __future__ import annotations

import io
from datetime import UTC, datetime

import pytest
from PIL import Image

from bot.services.schemas import MetaResponse
from bot.ui import cards


def png_solido(cor: tuple[int, int, int] = (200, 30, 30)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (100, 100), cor).save(buffer, format="PNG")
    return buffer.getvalue()


def entrada(nome: str, tier: str, *, imagem: str | None = None) -> dict:
    return {
        "hero": {
            "id": abs(hash(nome)) % 1000,
            "name": nome,
            "slug": nome.lower(),
            "role": "fighter",
            "image_url": imagem,
        },
        "lane": "jungle",
        "tier": tier,
        "score": 70.0,
        "win_rate": 0.53,
    }


def meta(**overrides: object) -> MetaResponse:
    base: dict[str, object] = {
        "lane": "jungle",
        "rank_filter": "mythic",
        "patch": "2.1.18",
        "collected_at": datetime(2026, 9, 22, tzinfo=UTC),
        "source": "rone_arena",
        "is_mock": False,
        "entries": [
            entrada("Sun", "S+", imagem="https://cdn/sun.png"),
            entrada("Hirara", "S", imagem="https://cdn/hirara.png"),
            entrada("Ling", "A"),
        ],
    }
    base.update(overrides)
    return MetaResponse.model_validate(base)


@pytest.fixture(autouse=True)
def retratos_no_cache(monkeypatch):
    """Preenche o cache para a renderizacao nao tentar rede."""
    monkeypatch.setattr(
        cards,
        "_retratos",
        {"https://cdn/sun.png": png_solido(), "https://cdn/hirara.png": png_solido((30, 90, 200))},
    )


async def test_gera_png_valido():
    dados = await cards.render_meta_card(meta(), lane="jungle")
    assert dados is not None

    imagem = Image.open(io.BytesIO(dados))
    assert imagem.format == "PNG"
    assert imagem.width == cards.LARGURA
    assert imagem.height > 200


async def test_sem_entradas_nao_renderiza():
    """Sem dado nao ha card: o comando cai para o embed, que explica o motivo."""
    assert await cards.render_meta_card(meta(entries=[]), lane="jungle") is None


async def test_heroi_sem_retrato_nao_quebra_o_card():
    """Ling entra sem image_url; deve sair com placeholder, nao estourar."""
    dados = await cards.render_meta_card(meta(), lane="jungle")
    assert dados is not None


async def test_altura_cresce_quando_o_tier_quebra_em_varias_linhas():
    """Comparacao justa: mesmo numero de tiers, quantidade de herois diferente.

    (Tres tiers de uma linha ocupam a mesma altura que um tier de tres
    linhas - por isso a comparacao precisa fixar o numero de tiers.)
    """
    uma_linha = await cards.render_meta_card(
        meta(entries=[entrada(f"Heroi{i}", "S") for i in range(cards.POR_LINHA)]),
        lane="jungle",
    )
    tres_linhas = await cards.render_meta_card(
        meta(entries=[entrada(f"Heroi{i}", "S") for i in range(cards.POR_LINHA * 3)]),
        lane="jungle",
    )
    assert uma_linha is not None and tres_linhas is not None
    assert Image.open(io.BytesIO(tres_linhas)).height > Image.open(io.BytesIO(uma_linha)).height


async def test_cada_tier_ocupa_seu_proprio_bloco():
    """Mais tiers = card mais alto, mesmo com o mesmo total de herois."""
    um_tier = await cards.render_meta_card(
        meta(entries=[entrada(f"Heroi{i}", "S") for i in range(6)]), lane="jungle"
    )
    tres_tiers = await cards.render_meta_card(
        meta(
            entries=[entrada(f"A{i}", "S+") for i in range(2)]
            + [entrada(f"B{i}", "S") for i in range(2)]
            + [entrada(f"C{i}", "A") for i in range(2)]
        ),
        lane="jungle",
    )
    assert um_tier is not None and tres_tiers is not None
    assert Image.open(io.BytesIO(tres_tiers)).height > Image.open(io.BytesIO(um_tier)).height


async def test_download_falho_nao_derruba_a_renderizacao(monkeypatch):
    """Se o CDN cair, o card sai sem retratos em vez de nao sair."""
    monkeypatch.setattr(cards, "_retratos", {})

    async def sem_rede(urls):
        return {}

    monkeypatch.setattr(cards, "_baixar_retratos", sem_rede)
    dados = await cards.render_meta_card(meta(), lane="jungle")
    assert dados is not None


def test_encurtar_nomes_longos():
    fonte = cards._carregar_fonte(cards.FONTES_REGULARES, 12)
    curto = cards._encurtar("Sun", fonte, 70)
    longo = cards._encurtar("Popol and Kupa", fonte, 40)

    assert curto == "Sun"
    assert longo.endswith("…")
    assert len(longo) < len("Popol and Kupa")


def test_todos_os_tiers_tem_cor():
    from bot.ui.embeds import TIER_ORDER

    assert set(TIER_ORDER) <= set(cards.CORES_TIER)
