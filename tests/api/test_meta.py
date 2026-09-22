"""Testes dos endpoints de meta e patches."""

from __future__ import annotations

import pytest

from app.models.enums import TIER_ORDER


@pytest.fixture
def client_seeded(client, seeded_db):
    return client


def test_meta_vazio_nao_e_erro(client):
    """Sem coleta, a API responde 200 com lista vazia - nao 404/500."""
    body = client.get("/api/v1/meta").json()
    assert body["entries"] == []
    assert body["is_mock"] is True


def test_meta_sinaliza_dados_mock(client_seeded):
    body = client_seeded.get("/api/v1/meta").json()
    assert body["is_mock"] is True
    assert body["source"] == "mock"


def test_meta_traz_todas_as_lanes(client_seeded):
    body = client_seeded.get("/api/v1/meta").json()
    lanes = {entry["lane"] for entry in body["entries"]}
    assert lanes == {"jungle", "gold", "mid", "exp", "roam"}


def test_meta_usa_apenas_a_coleta_mais_recente(client_seeded):
    """O seed grava duas coletas; a resposta so pode conter a ultima."""
    body = client_seeded.get("/api/v1/meta").json()
    assert body["collected_at"] > body["previous_collected_at"]

    pares = {(entry["hero"]["id"], entry["lane"]) for entry in body["entries"]}
    assert len(pares) == len(body["entries"]), "nao pode haver heroi/lane duplicado"


def test_meta_por_lane(client_seeded):
    body = client_seeded.get("/api/v1/meta/jungle").json()
    assert body["lane"] == "jungle"
    assert body["entries"]
    assert all(entry["lane"] == "jungle" for entry in body["entries"])


def test_lane_invalida_retorna_422(client_seeded):
    assert client_seeded.get("/api/v1/meta/toplane").status_code == 422


def test_entries_ordenadas_por_tier_e_score(client_seeded):
    entries = client_seeded.get("/api/v1/meta/jungle").json()["entries"]
    ordem = [(TIER_ORDER.index(e["tier"]), -e["score"]) for e in entries]
    assert ordem == sorted(ordem)


def test_limit_corta_a_lista(client_seeded):
    body = client_seeded.get("/api/v1/meta/jungle", params={"limit": 3}).json()
    assert len(body["entries"]) == 3


def test_tendencia_calculada_contra_a_coleta_anterior(client_seeded):
    body = client_seeded.get("/api/v1/meta/jungle").json()
    assert body["rising"], "o dataset mock contem herois em alta"

    for entry in body["rising"]:
        assert entry["score_delta"] > 0
    for entry in body["falling"]:
        assert entry["score_delta"] < 0


def test_entry_traz_win_rate_da_coleta(client_seeded):
    entries = client_seeded.get("/api/v1/meta/jungle").json()["entries"]
    assert all(entry["win_rate"] is not None for entry in entries)
    assert all(0.0 <= entry["win_rate"] <= 1.0 for entry in entries)


def test_patches(client_seeded):
    patches = client_seeded.get("/api/v1/patches").json()
    assert patches
    assert any(patch["is_current"] for patch in patches)


def test_patch_corrente(client_seeded):
    body = client_seeded.get("/api/v1/patches/current").json()
    assert body["is_current"] is True
    assert body["version"].startswith("MOCK")


def test_nao_mistura_fontes_ao_calcular_tendencia(client, db_session):
    """Trocar de provider nao pode gerar tendencia comparando fontes distintas.

    Cenario real: o banco tinha dados de demonstracao e passou a receber
    dados reais. A coleta real nao deve ser comparada com a mock.
    """
    from datetime import UTC, datetime

    from app.models import Hero, MetaSnapshot
    from app.models.enums import HeroRole, Lane, Tier

    heroi = Hero(name="Fonte Teste", slug="fonte-teste", role=HeroRole.FIGHTER)
    db_session.add(heroi)
    db_session.flush()

    antiga = datetime(2026, 1, 1, tzinfo=UTC)
    nova = datetime(2026, 2, 1, tzinfo=UTC)
    db_session.add_all(
        [
            MetaSnapshot(
                hero_id=heroi.id, lane=Lane.JUNGLE, tier=Tier.D, score=10.0,
                patch="MOCK-0.1", collected_at=antiga, source="mock",
            ),
            MetaSnapshot(
                hero_id=heroi.id, lane=Lane.JUNGLE, tier=Tier.S, score=90.0,
                patch="2.1.18", collected_at=nova, source="fonte_real",
            ),
        ]
    )
    db_session.flush()

    body = client.get("/api/v1/meta/jungle").json()
    entrada = next(e for e in body["entries"] if e["hero"]["slug"] == "fonte-teste")

    # Sem a separacao por fonte, isto viria como +80 pontos de "alta".
    assert entrada["score_delta"] is None
    assert body["previous_collected_at"] is None
    assert body["source"] == "fonte_real"
