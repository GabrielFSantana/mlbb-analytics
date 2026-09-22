"""Testes do detalhe de heroi e dos counters (Fase 3b)."""

from __future__ import annotations

import pytest

from app.models import HeroRelation
from app.models.enums import RelationType


@pytest.fixture
def client_seeded(client, seeded_db):
    return client


# -- detalhe do heroi ---------------------------------------------------


def test_detalhe_traz_posicao_no_meta_por_lane(client_seeded):
    """A lane nao vive na tabela de herois: vem dos snapshots de meta."""
    body = client_seeded.get("/api/v1/heroes/by-name/leomord").json()

    assert body["lanes"], "Leomord joga jungle e exp no dataset mock"
    lanes = {pos["lane"] for pos in body["lanes"]}
    assert lanes == {"jungle", "exp"}
    for pos in body["lanes"]:
        assert pos["tier"]
        assert 0.0 <= pos["score"] <= 100.0


def test_lanes_ordenadas_da_mais_forte_para_a_mais_fraca(client_seeded):
    body = client_seeded.get("/api/v1/heroes/by-name/leomord").json()
    scores = [pos["score"] for pos in body["lanes"]]
    assert scores == sorted(scores, reverse=True)


def test_detalhe_traz_variacao_desde_a_coleta_anterior(client_seeded):
    """O seed mock tem duas coletas, entao ha com o que comparar."""
    body = client_seeded.get("/api/v1/heroes/by-name/leomord").json()
    assert any(pos["score_delta"] is not None for pos in body["lanes"])


def test_detalhe_sinaliza_origem_dos_dados(client_seeded):
    body = client_seeded.get("/api/v1/heroes/by-name/leomord").json()
    assert body["is_mock"] is True
    assert body["source"] == "mock"
    assert body["patch"]


def test_heroi_sem_coleta_nao_quebra(client, db_session):
    """Heroi cadastrado mas sem snapshot: responde sem lanes, nao 500."""
    from app.models import Hero
    from app.models.enums import HeroRole

    db_session.add(Hero(name="Recem Chegado", slug="recem-chegado", role=HeroRole.MAGE))
    db_session.flush()

    body = client.get("/api/v1/heroes/by-name/recem-chegado").json()
    assert body["lanes"] == []
    assert body["latest_stats"] is None


# -- counters -----------------------------------------------------------


def test_counters_separa_os_tres_tipos(client_seeded):
    body = client_seeded.get("/api/v1/heroes/by-name/leomord/counters").json()

    assert body["hero"]["name"] == "Leomord"
    assert body["strong_against"]
    assert body["weak_against"]
    assert body["good_with"]
    assert body["is_mock"] is True


def test_counters_nao_repetem_heroi_entre_listas_do_mesmo_tipo(client_seeded):
    body = client_seeded.get("/api/v1/heroes/by-name/leomord/counters").json()
    for chave in ("strong_against", "weak_against", "good_with"):
        ids = [h["id"] for h in body[chave]]
        assert len(ids) == len(set(ids))


def test_counters_de_heroi_inexistente_retorna_404(client_seeded):
    resposta = client_seeded.get("/api/v1/heroes/by-name/nao-existe/counters")
    assert resposta.status_code == 404


def test_counters_de_heroi_sem_relacoes_vem_vazio(client, db_session):
    from app.models import Hero
    from app.models.enums import HeroRole

    db_session.add(Hero(name="Sem Relacao", slug="sem-relacao", role=HeroRole.TANK))
    db_session.flush()

    body = client.get("/api/v1/heroes/by-name/sem-relacao/counters").json()
    assert body["strong_against"] == []
    assert body["weak_against"] == []
    assert body["good_with"] == []


# -- sincronizacao das relacoes -----------------------------------------


def test_sync_grava_relacoes(db_session):
    from app.providers.mock import MockDataProvider
    from app.services.sync_service import SyncService

    resultado = SyncService(db_session, provider=MockDataProvider()).sync_all()

    assert resultado.relations > 0
    assert db_session.query(HeroRelation).count() == resultado.relations
    tipos = {r.relation_type for r in db_session.query(HeroRelation).all()}
    assert tipos == set(RelationType)


def test_sync_substitui_relacoes_em_vez_de_acumular(db_session):
    """Relacao removida na origem precisa sumir daqui - nao e serie temporal."""
    from app.providers.mock import MockDataProvider
    from app.services.sync_service import SyncService

    primeira = SyncService(db_session, provider=MockDataProvider()).sync_all()
    segunda = SyncService(db_session, provider=MockDataProvider()).sync_all()

    assert segunda.relations == primeira.relations
    assert db_session.query(HeroRelation).count() == primeira.relations
