"""Testes da formatacao dos embeds do Discord."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from bot.services.schemas import (
    Hero,
    HeroBuilds,
    HeroCounters,
    HeroDetail,
    MetaEntry,
    MetaResponse,
    MetaUpdate,
    Patch,
)
from bot.ui.embeds import (
    MOCK_WARNING,
    build_builds_embed,
    build_counters_embed,
    build_hero_embed,
    build_meta_embed,
    build_meta_update_embed,
    build_patch_embed,
    lane_label,
)


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


# -- embed de atualizacao automatica (Fase 2) ---------------------------


def make_update(**overrides: object) -> MetaUpdate:
    base: dict[str, object] = {
        "collected_at": datetime(2026, 9, 22, tzinfo=UTC),
        "previous_collected_at": datetime(2026, 9, 21, tzinfo=UTC),
        "patch": "2.1.18",
        "source": "rone_arena",
        "is_mock": False,
        "rising": [make_entry("Leomord", "S", delta=4.2)],
        "falling": [make_entry("Hayabusa", "B", score=45.0, delta=-3.1)],
        "promoted": [make_entry("Leomord", "S", delta=4.2)],
        "demoted": [],
        "biggest_win_rate_gain": [make_entry("Balmond", "A", delta=2.0)],
    }
    base.update(overrides)
    update = MetaUpdate.model_validate(base)
    # previous_tier so existe quando houve mudanca de tier.
    for entrada in update.promoted:
        entrada.previous_tier = "A"
    return update


def test_update_tem_titulo_e_secoes():
    embed = build_meta_update_embed(make_update())
    assert embed.title == "🔥 META UPDATE"

    nomes = [f.name for f in embed.fields]
    assert "📈 Subiu" in nomes
    assert "📉 Caiu" in nomes
    assert "⬆️ Subiu de tier" in nomes
    assert "🔥 Maior crescimento de WR" in nomes
    # Secao vazia nao vira campo vazio.
    assert "⬇️ Caiu de tier" not in nomes


def test_update_mostra_transicao_de_tier():
    embed = build_meta_update_embed(make_update())
    campo = next(f for f in embed.fields if f.name == "⬆️ Subiu de tier")
    assert "A → S" in (campo.value or "")


def test_update_rodape_traz_patch_e_fonte():
    embed = build_meta_update_embed(make_update())
    rodape = embed.footer.text or ""
    assert "2.1.18" in rodape
    assert "rone_arena" in rodape
    assert "DADOS MOCK" not in rodape


def test_update_com_dados_mock_e_sinalizado():
    embed = build_meta_update_embed(make_update(is_mock=True, source="mock"))
    assert MOCK_WARNING in (embed.description or "")
    assert "DADOS MOCK" in (embed.footer.text or "")


def test_update_respeita_limite_de_campo_do_discord():
    muitos = [make_entry(f"Heroi{i}", "S", delta=3.0) for i in range(40)]
    embed = build_meta_update_embed(make_update(rising=muitos))
    assert all(len(f.value or "") <= 1024 for f in embed.fields)


# -- /hero, /counter e /patch (Fase 3b) ---------------------------------


def make_hero_detail(**overrides: object) -> HeroDetail:
    base: dict[str, object] = {
        "id": 1,
        "name": "Leomord",
        "slug": "leomord",
        "role": "fighter",
        "image_url": "https://exemplo/leomord.png",
        "latest_stats": {
            "win_rate": 0.541,
            "pick_rate": 0.021,
            "ban_rate": 0.311,
            "patch": "2.1.18",
            "collected_at": datetime(2026, 9, 22, tzinfo=UTC),
            "source": "rone_arena",
        },
        "lanes": [
            {"lane": "jungle", "tier": "S", "score": 69.7, "score_delta": 4.2},
            {"lane": "exp", "tier": "A", "score": 58.1, "score_delta": None},
        ],
        "patch": "2.1.18",
        "source": "rone_arena",
        "is_mock": False,
    }
    base.update(overrides)
    return HeroDetail.model_validate(base)


def test_hero_embed_mostra_classe_stats_e_lanes():
    embed = build_hero_embed(make_hero_detail())
    assert embed.title == "🦸 Leomord"

    nomes = [f.name for f in embed.fields]
    assert "Classe" in nomes
    assert "Estatisticas" in nomes
    assert "Posicao no meta" in nomes

    stats = next(f for f in embed.fields if f.name == "Estatisticas")
    assert "54.10%" in (stats.value or "")

    meta = next(f for f in embed.fields if f.name == "Posicao no meta")
    assert "JUNGLE" in (meta.value or "")
    assert "+4.2" in (meta.value or "")


def test_hero_embed_traduz_a_classe():
    embed = build_hero_embed(make_hero_detail(role="marksman"))
    classe = next(f for f in embed.fields if f.name == "Classe")
    assert classe.value == "Atirador"


def test_hero_embed_sem_coleta_nao_quebra():
    embed = build_hero_embed(make_hero_detail(latest_stats=None, lanes=[], patch=None))
    stats = next(f for f in embed.fields if f.name == "Estatisticas")
    assert "Sem coleta" in (stats.value or "")


def test_hero_embed_sinaliza_mock():
    embed = build_hero_embed(make_hero_detail(is_mock=True, source="mock"))
    assert MOCK_WARNING in (embed.description or "")
    assert "DADOS MOCK" in (embed.footer.text or "")


def make_counters(**overrides: object) -> HeroCounters:
    base: dict[str, object] = {
        "hero": {"id": 1, "name": "Leomord", "slug": "leomord", "role": "fighter"},
        "strong_against": [{"id": 2, "name": "Pharsa", "slug": "pharsa", "role": "mage"}],
        "weak_against": [{"id": 3, "name": "Phoveus", "slug": "phoveus", "role": "fighter"}],
        "good_with": [{"id": 4, "name": "Angela", "slug": "angela", "role": "support"}],
        "source": "rone_arena",
        "is_mock": False,
    }
    base.update(overrides)
    return HeroCounters.model_validate(base)


def test_counters_embed_tem_as_tres_secoes():
    embed = build_counters_embed(make_counters())
    nomes = [f.name for f in embed.fields]
    assert "✅ Forte contra" in nomes
    assert "❌ Fraco contra" in nomes
    assert "🤝 Combina com" in nomes


def test_counters_embed_sem_relacoes_explica():
    embed = build_counters_embed(
        make_counters(strong_against=[], weak_against=[], good_with=[])
    )
    assert embed.fields == []
    assert "nao publicou relacoes" in (embed.description or "")


def test_patch_embed():
    patch = Patch.model_validate(
        {
            "id": 1,
            "version": "2.1.18",
            "released_at": "2025-09-28",
            "summary": None,
            "is_current": True,
        }
    )
    embed = build_patch_embed(patch)
    assert "2.1.18" in (embed.title or "")
    assert "28/09/2025" in str([f.value for f in embed.fields])


def test_patch_embed_sem_patch():
    embed = build_patch_embed(None)
    assert "coleta" in (embed.description or "")


def test_build_embed_distingue_fonte_fora_de_sem_build():
    """Mensagens diferentes para causas diferentes."""
    sem_build = HeroBuilds.model_validate(
        {
            "hero": {"id": 1, "name": "Julian", "slug": "julian", "role": "mage"},
            "lane": "jungle",
            "builds": [],
            "source": "rone_arena",
            "is_mock": False,
            "source_available": True,
        }
    )
    embed = build_builds_embed(sem_build)
    assert "nao publicou builds" in (embed.description or "")

    fonte_fora = HeroBuilds.model_validate(
        {**sem_build.model_dump(mode="json"), "source_available": False}
    )
    embed = build_builds_embed(fonte_fora)
    assert "indisponivel" in (embed.description or "")
    assert "nao publicou builds" not in (embed.description or "")


def test_build_embed_avisa_dado_antigo_quando_fonte_esta_fora():
    dados = HeroBuilds.model_validate(
        {
            "hero": {"id": 1, "name": "Leomord", "slug": "leomord", "role": "fighter"},
            "lane": "jungle",
            "builds": [
                {
                    "variant": 0,
                    "win_rate": 0.58,
                    "pick_rate": 0.16,
                    "emblem": "Assassin",
                    "battle_spell": "Retribution",
                    "items": [{"name": "War Axe", "position": 0}],
                }
            ],
            "source": "rone_arena",
            "is_mock": False,
            "source_available": False,
        }
    )
    embed = build_builds_embed(dados)
    observacao = next(f for f in embed.fields if f.name == "ℹ️ Observacao")
    assert "indisponivel" in (observacao.value or "")
