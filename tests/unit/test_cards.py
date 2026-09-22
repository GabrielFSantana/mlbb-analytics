"""Testes da renderizacao dos cards em imagem.

Nao tocam a rede: os retratos sao injetados no cache do modulo.
"""

from __future__ import annotations

import io
from datetime import UTC, datetime

import pytest
from PIL import Image

from bot.services.schemas import (
    DraftResponse,
    HeroBuilds,
    HeroCounters,
    HeroDetail,
    MetaResponse,
    TeamProgress,
    WeeklyRanking,
)
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


# -- card de heroi ------------------------------------------------------


def hero_detail(**overrides: object) -> HeroDetail:
    base: dict[str, object] = {
        "id": 1,
        "name": "Chou",
        "slug": "chou",
        "role": "fighter",
        "image_url": "https://cdn/sun.png",
        "latest_stats": {
            "win_rate": 0.447,
            "pick_rate": 0.0097,
            "ban_rate": 0.029,
            "patch": "2.1.18",
            "collected_at": datetime(2026, 9, 22, tzinfo=UTC),
            "source": "rone_arena",
        },
        "lanes": [
            {"lane": "roam", "tier": "D", "score": 18.6, "score_delta": None},
            {"lane": "exp", "tier": "D", "score": 18.6, "score_delta": -1.2},
        ],
        "patch": "2.1.18",
        "source": "rone_arena",
        "rank_filter": "all",
        "is_mock": False,
    }
    base.update(overrides)
    return HeroDetail.model_validate(base)


async def test_hero_card_gera_png():
    dados = await cards.render_hero_card(hero_detail())
    assert dados is not None

    imagem = Image.open(io.BytesIO(dados))
    assert imagem.format == "PNG"
    assert imagem.width == cards.LARGURA


async def test_hero_card_cresce_com_as_lanes():
    """Regressao: com altura fixa, o rodape invadia a area das lanes."""
    sem_lanes = await cards.render_hero_card(hero_detail(lanes=[]))
    com_lanes = await cards.render_hero_card(hero_detail())

    assert sem_lanes is not None and com_lanes is not None
    altura_sem = Image.open(io.BytesIO(sem_lanes)).height
    altura_com = Image.open(io.BytesIO(com_lanes)).height
    # A secao de lanes precisa de espaco proprio, senao sobrepoe o rodape.
    assert altura_com >= altura_sem + cards.ALTURA_PILL


async def test_hero_card_sem_estatisticas_nao_quebra():
    dados = await cards.render_hero_card(hero_detail(latest_stats=None, lanes=[]))
    assert dados is not None


async def test_hero_card_sem_retrato_nao_quebra(monkeypatch):
    monkeypatch.setattr(cards, "_retratos", {})

    async def sem_rede(urls):
        return {}

    monkeypatch.setattr(cards, "_baixar_retratos", sem_rede)
    dados = await cards.render_hero_card(hero_detail())
    assert dados is not None


def test_todos_os_papeis_tem_cor():
    from bot.ui.embeds import ROLE_LABELS

    assert set(ROLE_LABELS) == set(cards.CORES_PAPEL)


def test_faixas_das_barras_batem_com_o_scoring():
    """As barras precisam contar a mesma historia que o tier ao lado.

    Se as constantes do scoring mudarem sem mudar aqui, a barra de win rate
    passaria a discordar visualmente do tier calculado.
    """
    import sys

    sys.path.insert(0, "backend")
    from app.domain.scoring import (
        BAN_RATE_SATURATION,
        PICK_RATE_SATURATION,
        WIN_RATE_CEILING,
        WIN_RATE_FLOOR,
    )

    assert cards.BARRA_WIN_MIN == WIN_RATE_FLOOR
    assert cards.BARRA_WIN_MAX == WIN_RATE_CEILING
    assert cards.BARRA_PICK_MAX == PICK_RATE_SATURATION
    assert cards.BARRA_BAN_MAX == BAN_RATE_SATURATION


# -- cards de counter e build -------------------------------------------


def heroi_simples(nome: str, imagem: str | None = "https://cdn/sun.png") -> dict:
    return {
        "id": abs(hash(nome)) % 1000,
        "name": nome,
        "slug": nome.lower(),
        "role": "mage",
        "image_url": imagem,
    }


def counters(**overrides: object) -> HeroCounters:
    base: dict[str, object] = {
        "hero": heroi_simples("Leomord"),
        "strong_against": [heroi_simples("Pharsa"), heroi_simples("Yve")],
        "weak_against": [heroi_simples("Phoveus")],
        "good_with": [heroi_simples("Vexana")],
        "source": "rone_arena",
        "is_mock": False,
    }
    base.update(overrides)
    return HeroCounters.model_validate(base)


def builds(**overrides: object) -> HeroBuilds:
    variante = {
        "variant": 0,
        "win_rate": 0.5797,
        "pick_rate": 0.1632,
        "emblem": "Assassin",
        "battle_spell": "Retribution",
        "items": [
            {"name": "War Axe", "image_url": "https://cdn/sun.png", "position": 0},
            {"name": "Endless Battle", "image_url": None, "position": 1},
        ],
    }
    base: dict[str, object] = {
        "hero": heroi_simples("Leomord"),
        "lane": "jungle",
        "builds": [variante],
        "collected_at": datetime(2026, 9, 22, tzinfo=UTC),
        "source": "rone_arena",
        "is_mock": False,
        "source_available": True,
    }
    base.update(overrides)
    return HeroBuilds.model_validate(base)


async def test_counter_card_gera_png():
    dados = await cards.render_counters_card(counters())
    assert dados is not None
    assert Image.open(io.BytesIO(dados)).width == cards.LARGURA


async def test_counter_card_sem_nenhuma_relacao_nao_renderiza():
    """Sem relacao nao ha card: o embed explica o motivo (fonte fora x vazio)."""
    vazio = counters(strong_against=[], weak_against=[], good_with=[])
    assert await cards.render_counters_card(vazio) is None


async def test_counter_card_com_secao_vazia_ainda_renderiza():
    dados = await cards.render_counters_card(counters(good_with=[]))
    assert dados is not None


async def test_build_card_gera_png():
    dados = await cards.render_build_card(builds())
    assert dados is not None
    assert Image.open(io.BytesIO(dados)).width == cards.LARGURA


async def test_build_card_sem_builds_nao_renderiza():
    assert await cards.render_build_card(builds(builds=[])) is None


async def test_build_card_cresce_com_as_variantes():
    uma = await cards.render_build_card(builds())
    tres = await cards.render_build_card(
        builds(builds=[{**builds().builds[0].model_dump(), "variant": i} for i in range(3)])
    )
    assert uma is not None and tres is not None
    assert Image.open(io.BytesIO(tres)).height > Image.open(io.BytesIO(uma)).height


async def test_build_card_limita_as_variantes_exibidas():
    """Mais de tres variantes nao pode esticar o card indefinidamente."""
    muitas = [{**builds().builds[0].model_dump(), "variant": i} for i in range(8)]
    tres = [{**builds().builds[0].model_dump(), "variant": i} for i in range(3)]

    card_muitas = await cards.render_build_card(builds(builds=muitas))
    card_tres = await cards.render_build_card(builds(builds=tres))
    assert card_muitas is not None and card_tres is not None
    assert Image.open(io.BytesIO(card_muitas)).height == Image.open(io.BytesIO(card_tres)).height


async def test_build_card_item_sem_icone_nao_quebra():
    """Endless Battle entra sem image_url no fixture: sai com placeholder."""
    assert await cards.render_build_card(builds()) is not None


def comunidade(**overrides: object) -> dict:
    base: dict[str, object] = {
        "items": [
            {
                "name": f"Item {i}",
                "image_url": "https://cdn/sun.png",
                "position": i,
                "builds": 100 - i * 10,
                "share": (100 - i * 10) / 100,
                "in_core": i == 0,
            }
            for i in range(6)
        ],
        "builds_considered": 100,
        "patch": "2.1.18",
        "collected_at": datetime(2026, 9, 22, tzinfo=UTC),
    }
    base.update(overrides)
    return base


async def test_build_card_com_comunidade_e_mais_alto():
    """A build completa e uma secao a mais, nao um rotulo no mesmo espaco."""
    sem = await cards.render_build_card(builds())
    com = await cards.render_build_card(builds(community=comunidade()))

    assert sem is not None and com is not None
    assert Image.open(io.BytesIO(com)).height > Image.open(io.BytesIO(sem)).height


async def test_build_card_sem_itens_na_comunidade_nao_abre_a_secao():
    """Amostra insuficiente nao pode virar uma secao vazia no card."""
    sem = await cards.render_build_card(builds())
    vazia = await cards.render_build_card(
        builds(community=comunidade(items=[], builds_considered=2))
    )

    assert sem is not None and vazia is not None
    assert Image.open(io.BytesIO(vazia)).height == Image.open(io.BytesIO(sem)).height


async def test_build_card_com_talentos_nao_quebra():
    variante = {**builds().builds[0].model_dump(), "talents": "Rupture · Weapons Master"}
    dados = await cards.render_build_card(builds(builds=[variante]))
    assert dados is not None


async def test_build_card_com_comunidade_sem_icone_nao_quebra():
    itens = [{**item, "image_url": None} for item in comunidade()["items"]]
    dados = await cards.render_build_card(builds(community=comunidade(items=itens)))
    assert dados is not None


# -- card de draft ------------------------------------------------------


def candidato(nome: str, tier: str, **extras: object) -> dict:
    base = {
        "hero": heroi_simples(nome),
        "lane": "exp",
        "tier": tier,
        "meta_score": 60.0,
        "draft_score": 67.0,
        "counters": [],
        "countered_by": [],
        "synergies": [],
    }
    base.update(extras)
    return base


def draft(**overrides: object) -> DraftResponse:
    base: dict[str, object] = {
        "enemies": [heroi_simples("Leomord")],
        "allies": [heroi_simples("Tigreal")],
        "lane": "exp",
        "rank_filter": "all",
        "suggestions": [candidato("Paquito", "S+"), candidato("Gloo", "S")],
        "counter_picks": [
            candidato("Phoveus", "C", counters=[heroi_simples("Leomord")], draft_score=35.0)
        ],
        "unknown_terms": [],
        "patch": "2.1.18",
        "source": "rone_arena",
        "is_mock": False,
    }
    base.update(overrides)
    return DraftResponse.model_validate(base)


async def test_draft_card_gera_png():
    dados = await cards.render_draft_card(draft())
    assert dados is not None
    assert Image.open(io.BytesIO(dados)).width == cards.LARGURA


async def test_draft_card_sem_nada_a_sugerir_nao_renderiza():
    assert await cards.render_draft_card(draft(suggestions=[], counter_picks=[])) is None


async def test_draft_card_cresce_com_as_secoes():
    so_sugestoes = await cards.render_draft_card(draft(counter_picks=[]))
    completo = await cards.render_draft_card(draft())

    assert so_sugestoes is not None and completo is not None
    assert Image.open(io.BytesIO(completo)).height > Image.open(io.BytesIO(so_sugestoes)).height


async def test_draft_card_reserva_espaco_para_nomes_nao_reconhecidos():
    """Regressao: o aviso precisa caber, senao sobrepoe o rodape."""
    sem_aviso = await cards.render_draft_card(draft())
    com_aviso = await cards.render_draft_card(draft(unknown_terms=["Leomordd"]))

    assert sem_aviso is not None and com_aviso is not None
    assert Image.open(io.BytesIO(com_aviso)).height > Image.open(io.BytesIO(sem_aviso)).height


# -- card de progresso do time ------------------------------------------


def progresso_jogador(nome: str, estrelas: int, **extras: object) -> dict:
    base = {
        "display_name": nome,
        "discord_user_id": abs(hash(nome)) % 10000,
        "stars": estrelas,
        "percent": min(100.0, estrelas / 200 * 100),
        "reported_at": datetime(2026, 9, 22, tzinfo=UTC),
        "reached": estrelas >= 200,
    }
    base.update(extras)
    return base


def progresso_time(**overrides: object) -> TeamProgress:
    base: dict[str, object] = {
        "goal": 200,
        "players": [
            progresso_jogador("Um", 203),
            progresso_jogador("Dois", 142, stars_gained=12, days_measured=7.0),
        ],
        "total_stars": 345,
        "average_stars": 172.5,
        "players_reached": 1,
        "team_stars_gained": 12,
        "window_days": 7,
        "self_reported": True,
    }
    base.update(overrides)
    return TeamProgress.model_validate(base)


async def test_progresso_card_gera_png():
    dados = await cards.render_progress_card(progresso_time())
    assert dados is not None
    assert Image.open(io.BytesIO(dados)).width == cards.LARGURA


async def test_progresso_card_sem_jogadores_ainda_renderiza():
    """Time vazio precisa de card que explique como comecar, nao de nada."""
    dados = await cards.render_progress_card(
        progresso_time(players=[], total_stars=0, players_reached=0, team_stars_gained=None)
    )
    assert dados is not None


async def test_progresso_card_cresce_com_o_time():
    poucos = await cards.render_progress_card(progresso_time())
    muitos = await cards.render_progress_card(
        progresso_time(players=[progresso_jogador(f"J{i}", 100 + i) for i in range(8)])
    )
    assert poucos is not None and muitos is not None
    assert Image.open(io.BytesIO(muitos)).height > Image.open(io.BytesIO(poucos)).height


# -- card do ranking semanal --------------------------------------------


def mover(nome: str, ganho: int, **extras: object) -> dict:
    base = {
        "display_name": nome,
        "discord_user_id": abs(hash(nome)) % 10000,
        "stars_start": 100,
        "stars_end": 100 + ganho,
        "stars_gained": ganho,
        "reports": 3,
        "reached": False,
        "crossed_goal": False,
    }
    base.update(extras)
    return base


def ranking(**overrides: object) -> WeeklyRanking:
    base: dict[str, object] = {
        "week_label": "2026-W38",
        "week_start": "2026-09-15",
        "week_end": "2026-09-21",
        "goal": 200,
        "movers": [mover("A", 44, crossed_goal=True), mover("B", 22), mover("C", -12)],
        "team_stars_gained": 54,
        "players_reported": 3,
        "self_reported": True,
    }
    base.update(overrides)
    return WeeklyRanking.model_validate(base)


async def test_ranking_card_gera_png():
    dados = await cards.render_weekly_ranking_card(ranking())
    assert dados is not None
    assert Image.open(io.BytesIO(dados)).width == cards.LARGURA


async def test_ranking_card_sem_movimentacao_ainda_renderiza():
    dados = await cards.render_weekly_ranking_card(
        ranking(movers=[], team_stars_gained=0, players_reported=0)
    )
    assert dados is not None


async def test_ranking_card_cresce_com_os_jogadores():
    poucos = await cards.render_weekly_ranking_card(ranking())
    muitos = await cards.render_weekly_ranking_card(
        ranking(movers=[mover(f"J{i}", i) for i in range(9)])
    )
    assert poucos is not None and muitos is not None
    assert Image.open(io.BytesIO(muitos)).height > Image.open(io.BytesIO(poucos)).height


def test_posicoes_do_podio_tem_cor_propria():
    """Medalhas sao desenhadas: a fonte do container nao tem emoji colorido."""
    assert set(cards.CORES_POSICAO) == {0, 1, 2}
    assert len(set(cards.CORES_POSICAO.values())) == 3
