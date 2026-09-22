"""Testes do assistente de draft."""

from __future__ import annotations

import pytest

from app.domain.draft import (
    PONTOS_POR_COUNTER,
    PONTOS_POR_SINERGIA,
    SinalDeDraft,
    calcular_score_de_draft,
)
from app.models.enums import Lane, RelationType
from app.services.draft_service import DraftService


@pytest.fixture
def client_seeded(client, seeded_db):
    return client


# -- heuristica (pura) --------------------------------------------------


def test_sem_relacoes_o_score_e_o_do_meta():
    assert calcular_score_de_draft(SinalDeDraft(meta_score=60.0)) == 60.0


def test_counterar_soma_e_ser_counterado_subtrai():
    base = 50.0
    countera = calcular_score_de_draft(SinalDeDraft(meta_score=base, countera=[1, 2]))
    counterado = calcular_score_de_draft(SinalDeDraft(meta_score=base, counterado_por=[1]))

    assert countera == base + 2 * PONTOS_POR_COUNTER
    assert counterado == base - PONTOS_POR_COUNTER


def test_vantagem_e_liquida():
    """Counterar um e ser counterado por outro se anula."""
    sinal = SinalDeDraft(meta_score=50.0, countera=[1], counterado_por=[2])
    assert calcular_score_de_draft(sinal) == 50.0


def test_sinergia_soma_menos_que_counter():
    """Sinergia ajuda, mas nao decide partida como um counter."""
    assert PONTOS_POR_SINERGIA < PONTOS_POR_COUNTER

    sinal = SinalDeDraft(meta_score=50.0, sinergias=[1, 2])
    assert calcular_score_de_draft(sinal) == 50.0 + 2 * PONTOS_POR_SINERGIA


def test_score_fica_no_intervalo_do_meta():
    """0-100 para continuar comparavel com o score de meta ao lado."""
    altissimo = calcular_score_de_draft(
        SinalDeDraft(meta_score=95.0, countera=[1, 2, 3, 4, 5], sinergias=[1, 2, 3])
    )
    baixissimo = calcular_score_de_draft(
        SinalDeDraft(meta_score=5.0, counterado_por=[1, 2, 3, 4, 5])
    )
    assert altissimo == 100.0
    assert baixissimo == 0.0


# -- servico ------------------------------------------------------------


def test_sugere_picks_da_lane(seeded_db):
    resposta = DraftService(seeded_db).suggest(enemies=["Leomord"], lane=Lane.JUNGLE)

    assert resposta.suggestions
    assert all(c.lane is Lane.JUNGLE for c in resposta.suggestions)


def test_nao_sugere_quem_ja_esta_em_campo(seeded_db):
    """Nem inimigos nem aliados podem aparecer como sugestao."""
    resposta = DraftService(seeded_db).suggest(
        enemies=["Leomord"], allies=["Balmond"], lane=Lane.JUNGLE
    )
    sugeridos = {c.hero.slug for c in resposta.suggestions + resposta.counter_picks}

    assert "leomord" not in sugeridos
    assert "balmond" not in sugeridos


def test_nome_desconhecido_e_reportado_e_nao_ignorado(seeded_db):
    """Erro de digitacao nao pode virar recomendacao calculada sem o heroi."""
    resposta = DraftService(seeded_db).suggest(enemies=["Leomordd", "Kagura"])

    assert resposta.unknown_terms == ["Leomordd"]
    assert [h.name for h in resposta.enemies] == ["Kagura"]


def test_nome_repetido_nao_conta_duas_vezes(seeded_db):
    resposta = DraftService(seeded_db).suggest(enemies=["Leomord", "leomord", "Leomord"])
    assert len(resposta.enemies) == 1


def test_counter_e_detectado_nos_dois_sentidos(seeded_db):
    """A relacao vale tanto por "A e forte contra B" quanto por "B e fraco contra A"."""
    from app.models import Hero, HeroRelation
    from app.models.enums import HeroRole

    alvo = Hero(name="Alvo Teste", slug="alvo-teste", role=HeroRole.MAGE)
    seeded_db.add(alvo)
    seeded_db.flush()

    leomord = DraftService(seeded_db).heroes.get_by_slug("leomord")
    # So a aresta inversa: Leomord e FRACO contra o alvo.
    seeded_db.add(
        HeroRelation(
            hero_id=leomord.id,
            related_hero_id=alvo.id,
            relation_type=RelationType.WEAK,
            source="mock",
        )
    )
    seeded_db.flush()

    contra, a_favor, _ = DraftService(seeded_db)._mapas_de_relacao()
    assert alvo.id in a_favor.get(leomord.id, set())
    assert alvo.id not in contra.get(leomord.id, set())


def test_counter_picks_traz_quem_o_meta_esconderia(seeded_db):
    """A lista separada existe justamente para o counter de tier baixo."""
    resposta = DraftService(seeded_db).suggest(enemies=["Leomord"])

    for candidato in resposta.counter_picks:
        assert len(candidato.counters) > len(candidato.countered_by)


def test_sem_coleta_responde_vazio_sem_erro(db_session):
    resposta = DraftService(db_session).suggest(enemies=["Leomord"])

    assert resposta.suggestions == []
    assert resposta.counter_picks == []


# -- endpoint -----------------------------------------------------------


def test_endpoint_sugere(client_seeded):
    body = client_seeded.get(
        "/api/v1/draft/suggest", params=[("enemy", "Leomord"), ("lane", "jungle")]
    ).json()

    assert body["suggestions"]
    assert body["lane"] == "jungle"
    for candidato in body["suggestions"]:
        assert 0.0 <= candidato["draft_score"] <= 100.0


def test_endpoint_aceita_varios_inimigos_e_aliados(client_seeded):
    body = client_seeded.get(
        "/api/v1/draft/suggest",
        params=[("enemy", "Leomord"), ("enemy", "Kagura"), ("ally", "Tigreal")],
    ).json()

    assert {h["name"] for h in body["enemies"]} == {"Leomord", "Kagura"}
    assert [h["name"] for h in body["allies"]] == ["Tigreal"]


def test_endpoint_sem_inimigo_ainda_responde(client_seeded):
    """Sem inimigo, vira simplesmente "o que esta forte nessa lane"."""
    body = client_seeded.get("/api/v1/draft/suggest", params=[("lane", "jungle")]).json()

    assert body["enemies"] == []
    assert body["suggestions"]


def test_endpoint_lane_invalida_retorna_422(client_seeded):
    resposta = client_seeded.get("/api/v1/draft/suggest", params=[("lane", "toplane")])
    assert resposta.status_code == 422
