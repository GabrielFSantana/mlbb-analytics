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
