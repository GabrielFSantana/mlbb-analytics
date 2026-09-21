"""Testes da formatacao dos embeds do Discord."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from bot.services.schemas import Hero, MetaEntry, MetaResponse
from bot.ui.embeds import MOCK_WARNING, build_meta_embed, lane_label


def make_entry(
    name: str,
    tier: str,
    *,
    lane: str = "jungle",
    score: float = 80.0,
    delta: float | None = None,
    win_rate: float | None = 0.53,
) -> MetaEntry:
    return MetaEntry(
        hero=Hero(id=abs(hash(name)) % 1000, name=name, slug=name.lower(), role="fighter"),
        lane=lane,
        tier=tier,
        score=score,
        score_delta=delta,
        win_rate=win_rate,
        win_rate_delta=0.012 if delta else None,
    )


def make_meta(**overrides: object) -> MetaResponse:
    base: dict[str, object] = {
        "lane": "jungle",
        "patch": "MOCK-0.1",
        "collected_at": datetime(2026, 9, 15, tzinfo=UTC),
        "previous_collected_at": datetime(2026, 9, 8, tzinfo=UTC),
        "source": "mock",
        "is_mock": True,
        "entries": [make_entry("Leomord", "S+"), make_entry("Balmond", "A", score=60.0)],
        "rising": [make_entry("Leomord", "S+", delta=4.2)],
        "falling": [make_entry("Hayabusa", "B", score=45.0, delta=-3.1)],
    }
    base.update(overrides)
    return MetaResponse.model_validate(base)


def test_titulo_usa_o_nome_da_lane():
    embed = build_meta_embed(make_meta(), lane="jungle")
    assert embed.title == "🔥 META MLBB — JUNGLE"


def test_titulo_sem_lane_mostra_todas():
    embed = build_meta_embed(make_meta(lane=None), lane=None)
    assert "TODAS AS LANES" in (embed.title or "")


def test_dados_mock_sao_sinalizados_na_descricao_e_no_rodape():
    """Requisito explicito: dado ficticio nunca pode parecer real."""
    embed = build_meta_embed(make_meta(), lane="jungle")
    assert MOCK_WARNING in (embed.description or "")
    assert "DADOS MOCK" in (embed.footer.text or "")


def test_dados_reais_nao_levam_aviso_de_mock():
    embed = build_meta_embed(make_meta(is_mock=False, source="community"), lane="jungle")
    assert embed.description is None
    assert "DADOS MOCK" not in (embed.footer.text or "")


def test_herois_sao_agrupados_por_tier():
    embed = build_meta_embed(make_meta(), lane="jungle")
    tiers = [field.name for field in embed.fields]
    assert any("S+" in name for name in tiers)
    assert any("A" in name for name in tiers)

    s_plus = next(field for field in embed.fields if "S+" in (field.name or ""))
    assert "Leomord" in (s_plus.value or "")


def test_secoes_de_tendencia_aparecem():
    embed = build_meta_embed(make_meta(), lane="jungle")
    names = [field.name for field in embed.fields]
    assert "📈 Em alta" in names
    assert "📉 Em queda" in names

    alta = next(field for field in embed.fields if field.name == "📈 Em alta")
    assert "+4.2" in (alta.value or "")


def test_rodape_traz_patch_e_fonte():
    embed = build_meta_embed(make_meta(), lane="jungle")
    footer = embed.footer.text or ""
    assert "MOCK-0.1" in footer
    assert "15/09/2026" in footer
    assert "mock" in footer


def test_banco_vazio_explica_o_que_fazer():
    embed = build_meta_embed(
        make_meta(entries=[], rising=[], falling=[], patch=None, collected_at=None),
        lane="jungle",
    )
    assert "sync" in (embed.description or "")
    assert embed.fields == []


def test_primeira_coleta_avisa_que_nao_ha_tendencia():
    embed = build_meta_embed(
        make_meta(previous_collected_at=None, rising=[], falling=[]),
        lane="jungle",
    )
    names = [field.name for field in embed.fields]
    assert "📊 Tendencia" in names


@pytest.mark.parametrize(
    ("lane", "esperado"),
    [("jungle", "JUNGLE"), ("gold", "GOLD LANE"), ("roam", "ROAM"), (None, "TODAS AS LANES")],
)
def test_lane_label(lane: str | None, esperado: str):
    assert lane_label(lane) == esperado


def test_campos_respeitam_o_limite_do_discord():
    entries = [make_entry(f"Heroi{index}", "S", score=70.0) for index in range(40)]
    embed = build_meta_embed(make_meta(entries=entries), lane="jungle")
    assert all(len(field.value or "") <= 1024 for field in embed.fields)
