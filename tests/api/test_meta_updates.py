"""Testes da deteccao e publicacao das atualizacoes de meta."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.models import Announcement, Hero, MetaSnapshot
from app.models.enums import HeroRole, Lane, Tier
from app.services.meta_update_service import MetaUpdateService

ANTES = datetime(2026, 9, 21, tzinfo=UTC)
DEPOIS = datetime(2026, 9, 22, tzinfo=UTC)
FONTE = "fonte_teste"


def criar_heroi(db, nome: str) -> Hero:
    heroi = Hero(name=nome, slug=nome.lower().replace(" ", "-"), role=HeroRole.FIGHTER)
    db.add(heroi)
    db.flush()
    return heroi


def snapshot(hero_id: int, quando: datetime, score: float, tier: Tier) -> MetaSnapshot:
    return MetaSnapshot(
        hero_id=hero_id,
        lane=Lane.JUNGLE,
        tier=tier,
        score=score,
        patch="1.0",
        collected_at=quando,
        source=FONTE,
    )


@pytest.fixture
def duas_coletas(db_session):
    """Um heroi que subiu muito e outro que caiu muito entre duas coletas."""
    subiu = criar_heroi(db_session, "Subiu Muito")
    caiu = criar_heroi(db_session, "Caiu Muito")
    db_session.add_all(
        [
            snapshot(subiu.id, ANTES, 40.0, Tier.B),
            snapshot(subiu.id, DEPOIS, 55.0, Tier.A),
            snapshot(caiu.id, ANTES, 60.0, Tier.S),
            snapshot(caiu.id, DEPOIS, 45.0, Tier.A),
        ]
    )
    db_session.flush()
    return db_session


def test_sem_coleta_nao_ha_atualizacao(db_session):
    assert MetaUpdateService(db_session).pending_update() is None


def test_primeira_coleta_nao_gera_atualizacao(db_session):
    """Sem coleta anterior nao ha com o que comparar."""
    heroi = criar_heroi(db_session, "Solitario")
    db_session.add(snapshot(heroi.id, DEPOIS, 50.0, Tier.A))
    db_session.flush()

    assert MetaUpdateService(db_session).pending_update() is None


def test_detecta_alta_queda_e_mudanca_de_tier(duas_coletas):
    atualizacao = MetaUpdateService(duas_coletas).pending_update()
    assert atualizacao is not None

    assert [e.hero.name for e in atualizacao.rising] == ["Subiu Muito"]
    assert [e.hero.name for e in atualizacao.falling] == ["Caiu Muito"]
    assert [e.hero.name for e in atualizacao.promoted] == ["Subiu Muito"]
    assert [e.hero.name for e in atualizacao.demoted] == ["Caiu Muito"]
    assert atualizacao.collected_at == DEPOIS
    assert atualizacao.previous_collected_at == ANTES


def test_nao_reanuncia_coleta_ja_publicada(duas_coletas):
    """O ponto central da Fase 2: reiniciar o bot nao repete a mensagem."""
    servico = MetaUpdateService(duas_coletas)
    assert servico.pending_update() is not None

    servico.mark_announced(DEPOIS, FONTE)

    assert servico.pending_update() is None


def test_mark_announced_e_idempotente(duas_coletas):
    servico = MetaUpdateService(duas_coletas)
    assert servico.mark_announced(DEPOIS, FONTE) is True
    assert servico.mark_announced(DEPOIS, FONTE) is False
    assert duas_coletas.query(Announcement).count() == 1


def test_variacao_irrelevante_nao_vira_mensagem(db_session):
    """Ruido de arredondamento nao pode virar notificacao no canal."""
    heroi = criar_heroi(db_session, "Parado")
    db_session.add_all(
        [
            snapshot(heroi.id, ANTES, 50.0, Tier.A),
            snapshot(heroi.id, DEPOIS, 50.2, Tier.A),
        ]
    )
    db_session.flush()

    servico = MetaUpdateService(db_session)
    assert servico.pending_update() is None
    # E foi marcada como anunciada, para nao reprocessar a cada poll do bot.
    assert servico.pending_update() is None
    assert db_session.query(Announcement).count() == 1


# -- endpoints ----------------------------------------------------------


def test_endpoint_pendente_devolve_null_sem_novidade(client):
    response = client.get("/api/v1/meta/updates/pending")
    assert response.status_code == 200
    assert response.json() is None


def test_endpoint_pendente_devolve_a_atualizacao(client, duas_coletas):
    body = client.get("/api/v1/meta/updates/pending").json()
    assert body is not None
    assert [e["hero"]["name"] for e in body["rising"]] == ["Subiu Muito"]
    assert body["source"] == FONTE


def test_endpoint_ack_marca_como_publicada(client, duas_coletas):
    pendente = client.get("/api/v1/meta/updates/pending").json()

    resposta = client.post(
        "/api/v1/meta/updates/ack",
        json={"collected_at": pendente["collected_at"], "source": pendente["source"]},
    )
    assert resposta.status_code == 204

    assert client.get("/api/v1/meta/updates/pending").json() is None


def test_rota_de_updates_nao_e_confundida_com_lane(client):
    """Regressao: /{lane} declarado antes capturava "updates" e dava 422."""
    assert client.get("/api/v1/meta/updates/pending").status_code == 200
    assert client.get("/api/v1/meta/jungle").status_code == 200
    assert client.get("/api/v1/meta/naoexiste").status_code == 422
